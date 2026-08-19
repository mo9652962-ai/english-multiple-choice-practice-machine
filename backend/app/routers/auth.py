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

from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# 启用开关（1=多人模式，0=本地单用户兼容）
AUTH_ENABLED = os.environ.get("EPM_AUTH", "").strip() in ("1", "true", "on")

_PBKDF2_ITERATIONS = 100_000


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
        "SELECT id, username, is_admin FROM users WHERE token = ?", (token,)
    ).fetchone()
    if row is None:
        return None
    return {"id": row["id"], "username": row["username"], "is_admin": bool(row["is_admin"])}


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
    """强制要求管理员（EPM_AUTH=1 时使用）"""
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
    # 首个注册用户自动成为管理员
    is_first = connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 0
    cursor = connection.execute(
        """INSERT INTO users (username, password_hash, token, is_admin, last_login_at)
        VALUES (?, ?, ?, ?, datetime('now'))""",
        (username, hash_password(request.password), token, 1 if is_first else 0),
    )
    new_user_id = cursor.lastrowid
    # v9.24: 首个用户注册时——把本地单用户遗留数据（user_id IS NULL）迁移给他
    if is_first:
        for table in ("vocabulary_entries", "exam_sessions", "practice_sessions", "ai_conversations"):
            try:
                connection.execute(
                    f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (new_user_id,)
                )
            except Exception:
                pass
    connection.commit()
    return {
        "token": token,
        "user": {"id": new_user_id,
                 "username": username,
                 "is_admin": is_first,
                 "migrated_legacy": is_first},
    }


@router.post("/login")
def login(
    request: LoginRequest,
    connection=Depends(get_db),
) -> dict:
    row = connection.execute(
        "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (request.username.strip(),)
    ).fetchone()
    if row is None or not verify_password(request.password, row["password_hash"]):
        raise HTTPException(401, "用户名或密码错误")
    token = generate_token()
    connection.execute(
        "UPDATE users SET token = ?, last_login_at = datetime('now') WHERE id = ?",
        (token, row["id"]),
    )
    connection.commit()
    return {
        "token": token,
        "user": {"id": row["id"], "username": row["username"], "is_admin": bool(row["is_admin"])},
    }


@router.get("/me")
def me(user=Depends(get_current_user)) -> dict:
    if user is None:
        raise HTTPException(401, "未登录")
    return {"id": user["id"], "username": user["username"], "is_admin": bool(user["is_admin"])}
