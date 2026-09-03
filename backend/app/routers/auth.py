# -*- coding: utf-8 -*-
"""AI 英语刷题机 — 多用户认证（v9.24, 多人部署支持）

零依赖方案:
  - 密码: hashlib.pbkdf2_hmac (sha256, 100k 迭代, 随机盐)
  - token: secrets.token_urlsafe(32) opaque token, 存 users 表（查表即验证）
  - 鉴权: Authorization: Bearer <token> → get_current_user 依赖

启用方式: EPM_AUTH=1 时 /api 业务路由要求登录（PUBLIC_PATHS 除外）
向后兼容: 未启用 EPM_AUTH 时 get_current_user 返回匿名用户（现有单用户体验不变）
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..database import ensure_user_organization, get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# 启用开关（1=多人模式，0=本地单用户兼容）
AUTH_ENABLED = os.environ.get("EPM_AUTH", "").strip() in ("1", "true", "on")

# v9.30 安全修复: 部署者可指定管理员用户名（EPM_ADMIN_USERNAME）
# 指定后：该用户名注册即为管理员；未指定时所有新用户默认为普通用户
ADMIN_USERNAME = os.environ.get("EPM_ADMIN_USERNAME", "").strip()

_PBKDF2_ITERATIONS = 100_000

# v9.30 安全修复: 登录失败计数限流（防暴力破解）
# 同一 IP+用户名 15 分钟内失败 >= 5 次 → 锁定 15 分钟
_LOGIN_MAX_FAILURES = 5
_LOGIN_WINDOW_SECONDS = 15 * 60
_login_failures: dict[str, list[float]] = {}
import threading
_login_failures_lock = threading.Lock()


def _login_lock_key(ip: str, username: str) -> str:
    return f"{ip}:{username.lower()}"


def _login_is_locked(ip: str, username: str) -> bool:
    import time
    key = _login_lock_key(ip, username)
    with _login_failures_lock:
        now = time.time()
        window = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_WINDOW_SECONDS]
        if window:
            _login_failures[key] = window
        return len(window) >= _LOGIN_MAX_FAILURES


def _login_record_failure(ip: str, username: str) -> None:
    import time
    key = _login_lock_key(ip, username)
    with _login_failures_lock:
        now = time.time()
        _login_failures.setdefault(key, []).append(now)
        # 清理过期 key（防止内存无限增长）
        _login_failures[key] = [
            t for t in _login_failures[key] if now - t < _LOGIN_WINDOW_SECONDS
        ]
        if len(_login_failures) > 10_000:
            _login_failures.clear()


def _login_clear_failures(ip: str, username: str) -> None:
    key = _login_lock_key(ip, username)
    with _login_failures_lock:
        _login_failures.pop(key, None)


# ---------------- 密码 / token 工具 ----------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest_hex = stored.split("$", 1)
        expected = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), _PBKDF2_ITERATIONS
        ).hex()
        return hmac.compare_digest(expected, digest_hex)
    except Exception:
        return False


def generate_token() -> str:
    return secrets.token_urlsafe(32)


# ---------------- 请求模型 ----------------
class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------- 依赖 ----------------
def get_current_user(request: Request, connection=Depends(get_db)) -> dict | None:
    """从 Authorization: Bearer <token> 解析当前用户。
    未启用 EPM_AUTH 时返回 None（兼容本地单用户）。"""
    if not AUTH_ENABLED:
        return None
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    row = connection.execute(
        """
        SELECT id, username, is_admin, active_organization_id
        FROM users WHERE token = ?
        """,
        (token,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": bool(row["is_admin"]),
        "active_organization_id": row["active_organization_id"],
    }


def require_user(user=Depends(get_current_user)) -> dict:
    """强制要求登录（EPM_AUTH=1 时使用）"""
    if user is None:
        raise HTTPException(401, "未登录")
    return user


def maybe_require_user(user=Depends(get_current_user)) -> dict | None:
    """v9.24: EPM_AUTH=1 时强制登录（未登录 401）；=0 时放行（兼容单用户）"""
    if AUTH_ENABLED and user is None:
        raise HTTPException(401, "未登录")
    return user


def require_admin(user=Depends(get_current_user)) -> dict:
    """Require an administrator in multi-user mode.

    The local single-user mode deliberately remains compatible with the
    existing desktop workflow; once ``EPM_AUTH`` is enabled, every caller
    must be authenticated and have the admin flag.
    """
    if not AUTH_ENABLED:
        return user or {"id": None, "username": "local", "is_admin": True}
    if user is None:
        raise HTTPException(401, "未登录")
    if not user["is_admin"]:
        raise HTTPException(403, "需要管理员权限")
    return user


# ---------------- 路由 ----------------
@router.post("/register")
def register(
    request: RegisterRequest,
    connection=Depends(get_db),
) -> dict:
    username = request.username.strip()
    if not username:
        raise HTTPException(400, "用户名不能为空")
    existing = connection.execute(
        "SELECT id FROM users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    if existing:
        raise HTTPException(409, "用户名已存在")
    token = generate_token()
    # v9.30 安全修复: 仅显式配置的用户名可以成为管理员。
    # 未设置 EPM_ADMIN_USERNAME 时，所有新用户默认都是普通用户。
    user_count = connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    is_first = user_count == 0
    is_admin = bool(ADMIN_USERNAME and username.lower() == ADMIN_USERNAME.lower())
    cursor = connection.execute(
        """INSERT INTO users (username, password_hash, token, is_admin, last_login_at)
        VALUES (?, ?, ?, ?, datetime('now'))""",
        (username, hash_password(request.password), token, 1 if is_admin else 0),
    )
    new_user_id = cursor.lastrowid
    active_organization_id = ensure_user_organization(
        connection, int(new_user_id), username
    )
    # v9.24: 首个用户注册时——把本地单用户遗留数据（user_id IS NULL）迁移给他
    if is_first:
        legacy_tables = (
            "vocabulary_entries",
            "exam_sessions",
            "practice_sessions",
            "ai_conversations",
            "wrong_stats",
            "spaced_repetition_records",
            "learning_days",
            "annotations",
            "essay_submissions",
            "speaking_sessions",
            "agent_runs",
            "user_memories",
            "knowledge_docs",
            "knowledge_chunks",
            "chat_messages",
            "diagnostic_reports",
            "wrong_analysis_reports",
            "ai_usage",
            "explain_collections",
            "user_achievements",
        )
        for table in legacy_tables:
            try:
                columns = {
                    row["name"]
                    for row in connection.execute(f"PRAGMA table_info({table})")
                }
                if table == "explain_collections" and columns and "user_id" not in columns:
                    connection.execute(
                        "ALTER TABLE explain_collections ADD COLUMN user_id INTEGER DEFAULT NULL"
                    )
                    columns.add("user_id")
                if table == "user_achievements" and columns and "user_id" not in columns:
                    connection.execute(
                        "ALTER TABLE user_achievements RENAME TO user_achievements_old"
                    )
                    connection.execute(
                        """CREATE TABLE user_achievements (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            user_id INTEGER DEFAULT NULL,
                            badge_key TEXT NOT NULL,
                            earned_at TEXT NOT NULL,
                            progress INTEGER DEFAULT 0,
                            target INTEGER DEFAULT 0,
                            UNIQUE (user_id, badge_key)
                        )"""
                    )
                    connection.execute(
                        """INSERT INTO user_achievements
                           (id, user_id, badge_key, earned_at, progress, target)
                           SELECT id, NULL, badge_key, earned_at, progress, target
                           FROM user_achievements_old"""
                    )
                    connection.execute("DROP TABLE user_achievements_old")
                    columns.add("user_id")
                if "user_id" in columns:
                    connection.execute(
                        f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL",
                        (new_user_id,),
                    )
            except Exception:
                pass
    connection.commit()
    return {
        "token": token,
        "user": {"id": new_user_id,
                 "username": username,
                 "is_admin": bool(is_admin),
                 "active_organization_id": active_organization_id,
                 "migrated_legacy": is_first},
    }


@router.post("/login")
def login(
    request: LoginRequest,
    request_obj: Request,
    connection=Depends(get_db),
) -> dict:
    # v9.30 安全修复: 登录失败计数限流（防暴力破解）
    ip = request_obj.client.host if request_obj.client else "unknown"
    username = request.username.strip()
    if _login_is_locked(ip, username):
        raise HTTPException(429, "失败次数过多，请 15 分钟后再试")
    row = connection.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    if row is None or not verify_password(request.password, row["password_hash"]):
        _login_record_failure(ip, username)
        raise HTTPException(401, "用户名或密码错误")
    _login_clear_failures(ip, username)
    token = generate_token()
    connection.execute(
        "UPDATE users SET token = ?, last_login_at = datetime('now') WHERE id = ?",
        (token, row["id"]),
    )
    connection.commit()
    return {
        "token": token,
        "user": {
            "id": row["id"],
            "username": row["username"],
            "is_admin": bool(row["is_admin"]),
            "active_organization_id": row["active_organization_id"],
        },
    }


@router.get("/me")
def me(user=Depends(get_current_user)) -> dict:
    if user is None:
        raise HTTPException(401, "未登录")
    return {
        "id": user["id"],
        "username": user["username"],
        "is_admin": bool(user["is_admin"]),
        "active_organization_id": user.get("active_organization_id"),
    }
