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
                (task, provider, model, prompt_tokens, completion_tokens,
                 latency_ms, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task,
                provider[:80],
                model[:120],
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
