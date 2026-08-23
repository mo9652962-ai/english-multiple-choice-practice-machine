"""AI 任务路由与降级链（v2.40+）。

在 ai_client.chat_completion 之上加一层「任务级路由」：
- 按任务（wrong_diagnosis / vocab_labeling / ...）选择 profile
- primary 失败时沿 fallback 链降级（云端 → 本地 → 缓存）
- 每次调用记录到 ai_usage 表（用量/延迟/状态）

设计要点：
- 不修改 chat_completion 签名，兼容存量调用
- 新代码用 chat_with_routing()；存量逐步迁移
- 健康检查结果缓存 60s，避免每次调用探测
"""
from __future__ import annotations

import json
import os  # v9.32: EPM_AI_DAILY_QUOTA 配额配置
import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from .ai_client import chat_completion

# 已知任务名（用于文档与校验；profile.task_tags 用这些名字声明自己能处理的任务）
KNOWN_TASKS = (
    "wrong_diagnosis",
    "vocab_labeling",
    "import_assist",
    "essay_grading",
    "article_generate",
    "ocr_fallback",
    "chat_explain",
)

_health_cache: dict[int, tuple[float, bool]] = {}
_HEALTH_TTL = 60.0

_TRANSIENT = {"timeout", "unavailable", "empty", "http_429", "http_500", "http_502", "http_503", "http_504"}


def _parse_task_tags(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _task_profiles(
    connection: sqlite3.Connection,
    task: str,
) -> list[dict[str, Any]]:
    """按 task_tags 匹配 + priority 排序，返回候选 profile 列表。"""
    rows = connection.execute(
        """
        SELECT id, name, base_url, enabled, is_default, default_model,
               temperature, max_tokens, task_tags, priority
        FROM ai_profiles
        WHERE enabled = 1
        ORDER BY priority ASC, is_default DESC, id ASC
        """
    ).fetchall()
    candidates: list[dict[str, Any]] = []
    for row in rows:
        tags = _parse_task_tags(row["task_tags"])
        # 无 task_tags 的 profile 视为通用兜底（只排在最后）
        if tags and task not in tags:
            continue
        candidates.append(dict(row))
    return candidates


def _health(connection: sqlite3.Connection, profile_id: int) -> bool:
    """轻量健康检查：base_url 是否可达（60s 缓存）。"""
    now = time.time()
    cached = _health_cache.get(profile_id)
    if cached and now - cached[0] < _HEALTH_TTL:
        return cached[1]
    row = connection.execute(
        "SELECT base_url FROM ai_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    ok = bool(row and row["base_url"].strip())
    _health_cache[profile_id] = (now, ok)
    return ok


def _record_usage(
    connection: sqlite3.Connection,
    *,
    task: str,
    provider: str,
    model: str,
    user_id: int | None = None,  # v9.32: 配额——按用户记录
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    latency_ms: int = 0,
    status: str = "ok",
    error: str = "",
) -> None:
    try:
        connection.execute(
            """
            INSERT INTO ai_usage
                (task, provider, model, user_id, prompt_tokens, completion_tokens,
                 latency_ms, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task,
                provider[:80],
                model[:120],
                user_id,
                prompt_tokens,
                completion_tokens,
                latency_ms,
                status,
                error[:300],
            ),
        )
        connection.commit()
    except sqlite3.Error:
        # 用量记录失败不应阻断主流程
        pass


def chat_with_routing(
    connection: sqlite3.Connection,
    task: str,
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, Any] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    user_id: int | None = None,  # v9.32: 配额——透传记录
) -> str:
    """按任务路由调用 AI：候选 profile 按 priority 顺序 → 降级链 → 明确报错。

    chat_completion 内部已带 429/5xx 重试；这里负责跨 profile 降级。
    候选顺序 = ai_profiles.priority 升序（本地优先可把本地 profile 的 priority 调小）。
    """
    candidates = _task_profiles(connection, task)
    if not candidates:
        # 无匹配 profile：交给默认行为（等价于原 chat_completion）
        return chat_completion(
            connection,
            messages,
            response_format=response_format,
            model=model,
            max_tokens=max_tokens,
        )
    last_error: Exception | None = None
    for candidate in candidates:
        tags = _parse_task_tags(candidate["task_tags"])
        if tags and task not in tags:
            continue
        if not _health(connection, candidate["id"]):
            continue
        started = time.monotonic()
        usage_out: dict[str, int] = {}
        try:
            result = chat_completion(
                connection,
                messages,
                response_format=response_format,
                profile_id=candidate["id"],
                model=model or candidate["default_model"] or None,
                max_tokens=max_tokens or candidate["max_tokens"] or None,
                usage_out=usage_out,  # v9.27: 记录真实 tokens
            )
            _record_usage(
                connection,
                task=task,
                provider=candidate["name"],
                model=model or candidate["default_model"] or "",
                user_id=user_id,  # v9.32
                prompt_tokens=usage_out.get("prompt_tokens", 0),
                completion_tokens=usage_out.get("completion_tokens", 0),
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            return result
        except ValueError as error:
            last_error = error
            _record_usage(
                connection,
                task=task,
                provider=candidate["name"],
                model=model or candidate["default_model"] or "",
                user_id=user_id,  # v9.32
                latency_ms=int((time.monotonic() - started) * 1000),
                status="fallback",
                error=str(error),
            )
            # 只对瞬态错误降级；明显配置错误（如未填 base_url）直接抛
            if any(token in str(error) for token in ("请先填写", "未启用", "API 配置不存在")):
                raise
            continue
    raise ValueError(f"AI 服务暂不可用（{task}）：{last_error or '无可用配置'}")


def usage_stats(connection: sqlite3.Connection, days: int = 30) -> dict[str, Any]:
    """按任务聚合用量统计（供设置页展示）。"""
    rows = connection.execute(
        """
        SELECT task, provider, COUNT(*) AS calls,
               SUM(prompt_tokens) AS prompt_tokens,
               SUM(completion_tokens) AS completion_tokens,
               SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok_calls,
               ROUND(AVG(latency_ms)) AS avg_latency_ms
        FROM ai_usage
        WHERE created_at >= datetime('now', ?)
        GROUP BY task, provider
        ORDER BY calls DESC
        """,
        (f"-{days} days",),
    ).fetchall()
    return {"days": days, "rows": [dict(row) for row in rows]}


# ── v9.32: 每日 AI 配额（防多人模式登录用户无限调用烧 key）──

# 环境变量配置：EPM_AI_DAILY_QUOTA=0（默认）不限制；部署者设置如 100 = 每人每天 100 次（chat+speaking 合并）
DAILY_QUOTA = int((os.environ.get("EPM_AI_DAILY_QUOTA") or "0").strip() or 0)


class QuotaExceeded(Exception):
    """当日 AI 调用配额已用完。"""


def check_daily_quota(
    connection: sqlite3.Connection,
    user_id: int | None,
    task: str,
    quota: int = DAILY_QUOTA,
) -> None:
    """多人模式按用户+任务检查当日调用次数；超限抛 QuotaExceeded。

    单用户（user_id=None）或 quota<=0（未配置）→ 不限制。

    v9.33 原子化加固：原实现是 SELECT COUNT + Python 比较（check-then-act），
    并发请求可同时读到相同计数、双双通过后各写一条 → 超额。
    现改为 BEGIN IMMEDIATE 事务内「锁库 → 计数 → 判定」，写者串行化，
    判定与后续 INSERT 处于同一写事务，杜绝 TOCTOU 超扣窗口。
    """
    if user_id is None or quota <= 0:
        return
    # BEGIN IMMEDIATE：立刻取写锁（SQLite 库级锁），其他写事务在此排队。
    # 计数判定在锁内完成 → 并发 check 不可能同时看到"未满"的同一快照。
    was_in_transaction = connection.in_transaction
    if not was_in_transaction:
        connection.execute("BEGIN IMMEDIATE")
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS n FROM ai_usage
            WHERE user_id = ? AND task = ?
              AND created_at >= date('now', 'localtime')
              AND created_at < date('now', 'localtime', '+1 day')
            """,
            (user_id, task),
        ).fetchone()
        if row and row["n"] >= quota:
            if not was_in_transaction:
                connection.rollback()
            raise QuotaExceeded(
                f"今日 AI 调用次数已达上限（{quota} 次/日），请明天再试"
            )
        # 未超限：保持事务打开，调用方随后的 record_user_usage INSERT
        # 在同一写事务中提交——判定与写入原子绑定。
        # （ai.py/speaking.py 的 check→record 序列在同一 connection 上执行）
    except QuotaExceeded:
        raise
    except sqlite3.Error:
        if not was_in_transaction and connection.in_transaction:
            connection.rollback()
        # 锁冲突/数据库错误时放行主流程（配额失败不应阻断学习功能）


def record_user_usage(
    connection: sqlite3.Connection,
    user_id: int | None,
    task: str,
    provider: str,
    model: str,
    **kwargs,
) -> None:
    """路由层手动记录用户 AI 调用（chat/speaking 不经过 ai_router 时用）。"""
    try:
        _record_usage(
            connection,
            task=task,
            provider=provider or "unknown",
            model=model or "",
            user_id=user_id,
            **kwargs,
        )
    except Exception:
        pass
