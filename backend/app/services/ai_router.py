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
import hashlib
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
    "question_labeling",
    "deep_explain",
    "speaking_practice",
    "rag_qa",
    "similar_questions",
    "connection_test",
    "agent_analyze",
    "agent_plan",
)

_health_cache: dict[int, tuple[float, bool, str]] = {}
_HEALTH_TTL = 60.0

_TRANSIENT = {"timeout", "unavailable", "empty", "http_429", "http_500", "http_502", "http_503", "http_504"}

# 仅缓存输入确定、结果可复用的任务；聊天、口语和作文涉及时效性或个人内容，
# 默认不缓存。缓存留在本地 SQLite，且多用户模式把 user_id 纳入 key。
CACHEABLE_TASKS = frozenset({
    "wrong_diagnosis",
    "vocab_labeling",
    "import_assist",
    "question_labeling",
    "deep_explain",
    "article_generate",
    "rag_qa",
    "similar_questions",
})
CACHE_TTL_SECONDS = max(
    0, int((os.environ.get("EPM_AI_CACHE_TTL_SECONDS") or "86400").strip() or 0)
)


def _ensure_structured_response(
    response: str,
    response_format: dict[str, Any] | None,
) -> str:
    """Reject malformed JSON before it reaches a business service or cache.

    The provider remains responsible for the schema details of each task. The
    router only enforces the contract requested by ``response_format`` so a
    malformed provider response can use the normal fallback chain.
    """
    if not isinstance(response, str) or not response.strip():
        raise ValueError("模型返回为空")
    if response_format and response_format.get("type") == "json_object":
        try:
            parsed = json.loads(response)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("模型返回不是合法 JSON") from error
        if not isinstance(parsed, dict):
            raise ValueError("模型返回不是 JSON 对象")
    return response


def _parse_task_tags(value: str) -> list[str]:
    try:
        parsed = json.loads(value or "[]")
        return [str(item) for item in parsed] if isinstance(parsed, list) else []
    except (TypeError, json.JSONDecodeError):
        return []


def _task_profiles(
    connection: sqlite3.Connection,
    task: str,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    """按 task_tags 匹配 + priority 排序，返回候选 profile 列表。"""
    rows = connection.execute(
        """
        SELECT id, name, base_url, enabled, is_default, default_model,
               temperature, max_tokens, task_tags, priority
        FROM ai_profiles
        WHERE enabled = 1
          AND (? IS NULL OR id = ?)
        ORDER BY priority ASC, is_default DESC, id ASC
        """,
        (profile_id, profile_id),
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
    row = connection.execute(
        "SELECT base_url FROM ai_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    base_url = row["base_url"].strip() if row else ""
    cached = _health_cache.get(profile_id)
    if cached and now - cached[0] < _HEALTH_TTL and cached[2] == base_url:
        return cached[1]
    ok = bool(base_url)
    # Include the URL in the cache value so saving a previously empty or
    # changed profile takes effect immediately instead of waiting for TTL.
    _health_cache[profile_id] = (now, ok, base_url)
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
    try:
        from .metrics import record_event
        record_event(
            connection,
            "ai_call_succeeded" if status in {"ok", "cached"} else "ai_call_failed",
            user_id=user_id,
            detail={"task": task, "provider": provider, "status": status},
        )
    except Exception:
        # Local metrics are strictly best-effort and never affect AI behavior.
        pass


def _cache_key(
    task: str,
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, Any] | None,
    profile_id: int | None,
    model: str | None,
    max_tokens: int | None,
    user_id: int | None,
) -> str | None:
    if CACHE_TTL_SECONDS <= 0 or task not in CACHEABLE_TASKS:
        return None
    payload = {
        "task": task,
        "messages": messages,
        "response_format": response_format,
        "profile_id": profile_id,
        "model": model,
        "max_tokens": max_tokens,
        "user_id": user_id,
        "cache_version": 1,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _read_cached_response(
    connection: sqlite3.Connection,
    cache_key: str | None,
) -> tuple[str, str] | None:
    if not cache_key:
        return None
    try:
        row = connection.execute(
            """
            SELECT response, model
            FROM ai_response_cache
            WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
            """,
            (cache_key,),
        ).fetchone()
        if not row:
            # 清理同 key 的过期记录，失败不影响主流程。
            connection.execute("DELETE FROM ai_response_cache WHERE cache_key = ?", (cache_key,))
            return None
        was_in_transaction = connection.in_transaction
        connection.execute(
            "UPDATE ai_response_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
            (cache_key,),
        )
        if not was_in_transaction:
            connection.commit()
        return str(row["response"]), str(row["model"] or "")
    except sqlite3.Error:
        return None


def _write_cached_response(
    connection: sqlite3.Connection,
    cache_key: str | None,
    *,
    task: str,
    user_id: int | None,
    profile_id: int | None,
    model: str,
    response: str,
) -> None:
    if not cache_key:
        return
    try:
        was_in_transaction = connection.in_transaction
        connection.execute(
            """
            INSERT INTO ai_response_cache
                (cache_key, task, user_id, profile_id, model, response, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now', ?))
            ON CONFLICT(cache_key) DO UPDATE SET
                task = excluded.task,
                user_id = excluded.user_id,
                profile_id = excluded.profile_id,
                model = excluded.model,
                response = excluded.response,
                hit_count = 0,
                created_at = CURRENT_TIMESTAMP,
                expires_at = excluded.expires_at
            """,
            (
                cache_key,
                task,
                user_id,
                profile_id,
                model,
                response,
                f"+{CACHE_TTL_SECONDS} seconds",
            ),
        )
        if not was_in_transaction:
            connection.commit()
    except sqlite3.Error:
        # 缓存失败绝不能阻断真实 AI 结果。
        pass


def chat_with_routing(
    connection: sqlite3.Connection,
    task: str,
    messages: list[dict[str, str]],
    *,
    response_format: dict[str, Any] | None = None,
    profile_id: int | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
    user_id: int | None = None,  # v9.32: 配额——透传记录
) -> str:
    """按任务路由调用 AI：候选 profile 按 priority 顺序 → 降级链 → 明确报错。

    chat_completion 内部已带 429/5xx 重试；这里负责跨 profile 降级。
    候选顺序 = ai_profiles.priority 升序（本地优先可把本地 profile 的 priority 调小）。
    """
    cache_key = _cache_key(
        task,
        messages,
        response_format=response_format,
        profile_id=profile_id,
        model=model,
        max_tokens=max_tokens,
        user_id=user_id,
    )
    cached = _read_cached_response(connection, cache_key)
    if cached is not None:
        cached_response, cached_model = cached
        try:
            cached_response = _ensure_structured_response(cached_response, response_format)
        except ValueError:
            # Do not keep poisoning a deterministic task with an old malformed
            # response written before the structured-output gate existed.
            if cache_key:
                connection.execute("DELETE FROM ai_response_cache WHERE cache_key = ?", (cache_key,))
                if not connection.in_transaction:
                    connection.commit()
        else:
            _record_usage(
                connection,
                task=task,
                provider="local-cache",
                model=cached_model or model or "",
                user_id=user_id,
                status="cached",
            )
            return cached_response

    # 统一入口配额：业务路由不再各自预检/记录，新增 AI 任务经过这里即可获得
    # 同一套配额控制。只有多人模式且部署者配置了配额时才生效。
    quota_transaction_started = not connection.in_transaction
    check_daily_quota(connection, user_id, task)
    candidates = _task_profiles(connection, task, profile_id=profile_id)
    if not candidates:
        # 直连兼容路径不会经过 _record_usage；释放本次检查打开的事务，避免
        # 把 SQLite 写锁带入下游调用。
        if quota_transaction_started and connection.in_transaction:
            connection.commit()
        # 无匹配 profile：交给默认行为（等价于原 chat_completion）
        result = _ensure_structured_response(chat_completion(
            connection,
            messages,
            response_format=response_format,
            profile_id=profile_id,
            model=model,
            max_tokens=max_tokens,
        ), response_format)
        _write_cached_response(
            connection,
            cache_key,
            task=task,
            user_id=user_id,
            profile_id=profile_id,
            model=model or "",
            response=result,
        )
        return result
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
            result = _ensure_structured_response(chat_completion(
                connection,
                messages,
                response_format=response_format,
                profile_id=candidate["id"],
                model=model or candidate["default_model"] or None,
                max_tokens=max_tokens or candidate["max_tokens"] or None,
                usage_out=usage_out,  # v9.27: 记录真实 tokens
            ), response_format)
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
            _write_cached_response(
                connection,
                cache_key,
                task=task,
                user_id=user_id,
                profile_id=candidate["id"],
                model=model or candidate["default_model"] or "",
                response=result,
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
    if quota_transaction_started and connection.in_transaction:
        connection.rollback()
    raise ValueError(f"AI 服务暂不可用（{task}）：{last_error or '无可用配置'}")


def usage_stats(connection: sqlite3.Connection, days: int = 30) -> dict[str, Any]:
    """按任务聚合用量统计（供设置页展示）。"""
    rows = connection.execute(
        """
        SELECT task, provider, COUNT(*) AS calls,
               SUM(prompt_tokens) AS prompt_tokens,
               SUM(completion_tokens) AS completion_tokens,
               SUM(CASE WHEN status IN ('ok', 'cached') THEN 1 ELSE 0 END) AS ok_calls,
               SUM(CASE WHEN status = 'cached' THEN 1 ELSE 0 END) AS cached_calls,
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
    """多人模式按用户检查当日全部 AI 调用次数；超限抛 QuotaExceeded。

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
            WHERE user_id = ?
              AND created_at >= date('now', 'localtime')
              AND created_at < date('now', 'localtime', '+1 day')
            """,
            (user_id,),
        ).fetchone()
        if row and row["n"] >= quota:
            if not was_in_transaction:
                connection.rollback()
            raise QuotaExceeded(
                f"今日 AI 调用次数已达上限（{quota} 次/日），请明天再试"
            )
    # 未超限：保持事务打开，统一路由随后的 _record_usage INSERT
    # 在同一写事务中提交——判定与写入原子绑定。
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
    """兼容需要在统一路由之外记录一次 AI 尝试的调用方。"""
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
