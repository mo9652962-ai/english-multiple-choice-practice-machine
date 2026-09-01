"""AI 模型池：按档位选择模型，并对配额/限流错误做进程内降级。

模型池只复用现有 ``ai_profiles`` 配置，不保存 API Key，也不修改已有 AI
客户端。调用方通过回调传入模型名，因此既能复用 ``chat_completion``，也便于
单元测试注入一个轻量的假模型。
"""
from __future__ import annotations

import inspect
import os
import re
import sqlite3
import time
from typing import Any, Callable, Literal

from .ai_client import _profile_with_key, chat_completion, get_ai_profile

ModelTier = Literal["high", "low"]

exhausted_models: set[str] = set()
rate_limited_until: dict[str, float] = {}
RATE_LIMIT_COOLDOWN_SECONDS = 60.0


def _error_text(error: BaseException) -> str:
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    parts = [str(error)]
    if status is not None:
        parts.append(f"HTTP {status}")
    return " ".join(parts).lower()


def is_rate_limit_error(error: BaseException) -> bool:
    """识别 429 或常见 rate-limit 错误。"""
    text = _error_text(error)
    return bool(re.search(r"\b429\b|rate.?limit", text, re.IGNORECASE))


def is_quota_error(error: BaseException) -> bool:
    """识别余额/配额/限流错误，供模型池决定是否继续降级。"""
    text = _error_text(error)
    markers = (
        "allocationquota",
        "insufficientbalance",
        "insufficient_balance",
        "insufficient-quota",
        "insufficient_quota",
        "quota",
        "balance",
        "payment required",
        "rate.?limit",
    )
    return bool(re.search(r"\b(402|429)\b|" + "|".join(markers), text, re.IGNORECASE))


def _split_models(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _catalog_models(connection: sqlite3.Connection, profile_id: int) -> list[str]:
    rows = connection.execute(
        """
        SELECT model_id FROM ai_profile_models
        WHERE profile_id = ? AND is_visible = 1 AND is_available = 1
        ORDER BY updated_at DESC, model_id
        """,
        (profile_id,),
    ).fetchall()
    return [str(row["model_id"]).strip() for row in rows if str(row["model_id"]).strip()]


def _candidate_models(
    tier: ModelTier,
    connection: sqlite3.Connection,
) -> tuple[int, list[str]]:
    profile = get_ai_profile(connection)
    profile_id = int(profile["id"])
    # 解密一次用于确认配置可读；实际请求仍交给 chat_completion 处理。
    saved = _profile_with_key(connection, profile_id)
    default_model = str(saved.get("default_model") or "").strip()
    catalog = _catalog_models(connection, profile_id)
    env_name = "EPM_AI_HIGH_MODELS" if tier == "high" else "EPM_AI_LOW_MODELS"
    explicit = _split_models(os.environ.get(env_name))

    if tier == "high":
        ordered = [default_model, *explicit, *catalog]
    else:
        # low 档优先使用显式低成本模型，其次使用已发现的同接口模型，
        # 最后才回退到默认模型，保证只有一个配置模型时仍可工作。
        ordered = [*explicit, *[model for model in catalog if model != default_model], default_model]

    result: list[str] = []
    seen: set[str] = set()
    for model in ordered:
        if model and model not in seen:
            seen.add(model)
            result.append(model)
    return profile_id, result


def get_model_candidates(
    tier: ModelTier,
    connection: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """返回当前用户默认 profile 下某档位的候选模型（不包含密钥）。"""
    profile_id, models = _candidate_models(tier, connection)
    return [{"profile_id": profile_id, "model": model, "tier": tier} for model in models]


def _invoke_callback(fn: Callable[..., Any], model: str) -> Any:
    """调用 fn(model)，并兼容无参数的测试回调。"""
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(model)
    positional = [
        parameter
        for parameter in signature.parameters.values()
        if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
    ]
    if not positional and not any(
        parameter.kind == parameter.VAR_POSITIONAL
        for parameter in signature.parameters.values()
    ):
        return fn()
    return fn(model)


def completions_with_fallback(
    tier: ModelTier,
    fn: Callable[..., Any],
    connection: sqlite3.Connection,
) -> dict[str, Any]:
    """逐模型调用 fn，只有配额/限流错误才自动降级。"""
    candidates = get_model_candidates(tier, connection)
    now = time.time()
    last_error: BaseException | None = None
    attempted = False
    for candidate in candidates:
        model = str(candidate if isinstance(candidate, str) else candidate["model"])
        if model in exhausted_models:
            continue
        cooldown = rate_limited_until.get(model, 0.0)
        if cooldown > now:
            continue
        if cooldown:
            rate_limited_until.pop(model, None)
        attempted = True
        try:
            return {"data": _invoke_callback(fn, model), "model": model}
        except Exception as error:
            last_error = error
            if not is_quota_error(error):
                raise
            if is_rate_limit_error(error):
                rate_limited_until[model] = time.time() + RATE_LIMIT_COOLDOWN_SECONDS
            elif re.search(r"\b403\b|allocationquota|insufficient.?balance", _error_text(error)):
                exhausted_models.add(model)
            # 配额/限流错误继续尝试下一个候选。
            continue
    if last_error is not None:
        raise last_error
    if not attempted:
        raise ValueError(f"{tier} 档暂无可用模型（候选正在冷却或已耗尽）")
    raise ValueError(f"{tier} 档暂无可用模型")


def chat_completion_with_fallback(
    connection: sqlite3.Connection,
    messages: list[dict[str, str]],
    *,
    tier: ModelTier = "high",
    response_format: dict[str, Any] | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """兼容现有 chat_completion 的模型池封装。"""
    profile = get_ai_profile(connection)

    def call(model: str) -> str:
        return chat_completion(
            connection,
            messages,
            response_format=response_format,
            profile_id=int(profile["id"]),
            model=model,
            max_tokens=max_tokens,
        )

    return completions_with_fallback(tier, call, connection)
