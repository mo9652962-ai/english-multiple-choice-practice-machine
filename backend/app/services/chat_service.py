"""学习陪伴聊天室服务。"""
from __future__ import annotations

import asyncio
import sqlite3
from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from .ai_client import chat_completion


CHAT_SYSTEM_PROMPT = """你是「阿墨」，墨题刷题机的学习陪伴 AI，一个亲切靠谱的研友。
* 定位：英语学习陪伴与答疑，不是 Agent、不管理任务计划。
* 回复简短自然（一般 2-4 句），像真实研友聊天，不说教、不刷屏。
* 用户问英语/考研/刷题问题（词汇、语法、真题、方法）时认真解答，可简短。
* 用户闲聊时自然回应，亲切俏皮但不油腻。
* 永远不承认自己是 AI，自称「阿墨」。"""

_CHAT_CONTEXT_LIMIT = 10
_MAX_MESSAGE_LENGTH = 4000
_PLACEHOLDER_CONTENTS = {
    "...",
    "…",
    "正在输入",
    "正在输入…",
    "[AI 正在输入…]",
}


def _as_message_dict(message: Mapping[str, Any] | sqlite3.Row) -> dict[str, Any]:
    return dict(message)


def _is_ai_placeholder(message: Mapping[str, Any]) -> bool:
    if str(message.get("sender_type") or "") != "ai":
        return False
    content = str(message.get("content") or "").strip()
    return not content or content in _PLACEHOLDER_CONTENTS


def get_recent_messages(
    connection: sqlite3.Connection,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """按时间正序返回聊天室最近的消息。"""
    try:
        safe_limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        safe_limit = 100
    rows = connection.execute(
        """
        SELECT id, user_id, sender_type, sender_name, content, request_id, created_at
        FROM chat_messages
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (safe_limit,),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def save_message(
    connection: sqlite3.Connection,
    user_id: int | None,
    sender_type: str,
    sender_name: str | None,
    content: str,
    request_id: str | None = None,
) -> dict[str, Any]:
    """保存一条聊天室消息并返回可直接广播的消息对象。"""
    normalized_type = str(sender_type or "").strip().lower()
    if normalized_type not in {"user", "ai"}:
        raise ValueError("消息发送者类型不正确")
    normalized_content = str(content or "").strip()
    if not normalized_content:
        raise ValueError("消息内容不能为空")
    if len(normalized_content) > _MAX_MESSAGE_LENGTH:
        raise ValueError(f"消息内容不能超过 {_MAX_MESSAGE_LENGTH} 个字符")

    cursor = connection.execute(
        """
        INSERT INTO chat_messages
            (user_id, sender_type, sender_name, content, request_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            normalized_type,
            str(sender_name).strip() if sender_name else None,
            normalized_content,
            request_id,
        ),
    )
    connection.commit()
    row = connection.execute(
        """
        SELECT id, user_id, sender_type, sender_name, content, request_id, created_at
        FROM chat_messages
        WHERE id = ?
        """,
        (cursor.lastrowid,),
    ).fetchone()
    if row is None:
        raise RuntimeError("消息保存后无法读取")
    return dict(row)


def build_ai_prompt(
    connection: sqlite3.Connection,
    recent_messages: Sequence[Mapping[str, Any] | sqlite3.Row],
    user_message: str,
) -> list[dict[str, str]]:
    """组装阿墨的人设、最近上下文和本次用户消息。"""
    del connection  # 保留连接参数，便于后续按学习数据扩展上下文。
    normalized_user_message = str(user_message or "").strip()
    if not normalized_user_message:
        raise ValueError("消息内容不能为空")

    context: list[str] = []
    for raw_message in recent_messages:
        message = _as_message_dict(raw_message)
        if _is_ai_placeholder(message):
            continue
        sender_type = str(message.get("sender_type") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if sender_type not in {"user", "ai"} or not content:
            continue
        context.append(f"[{sender_type}] {content}")
    context = context[-_CHAT_CONTEXT_LIMIT:]

    messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]
    if context:
        messages.append(
            {
                "role": "user",
                "content": "聊天室最近对话上下文（仅作参考）：\n" + "\n".join(context),
            }
        )
    messages.append({"role": "user", "content": normalized_user_message})
    return messages


async def stream_ai_reply(
    connection: sqlite3.Connection,
    recent_messages: Sequence[Mapping[str, Any] | sqlite3.Row],
    user_message: str,
) -> AsyncIterator[str]:
    """调用现有 AI 客户端，并将完整结果切成 WS 可发送的增量片段。

    当前项目的 chat_completion 是同步非流式客户端，因此这里只在工作线程中
    完成一次现有调用，再将返回文本分段发出，避免阻塞 FastAPI 事件循环；未来
    客户端支持上游流式响应时，可在此处替换为真正的 token 迭代而不改变 WS 协议。
    """
    messages = build_ai_prompt(connection, recent_messages, user_message)
    content = await asyncio.to_thread(
        chat_completion,
        connection,
        messages,
        max_tokens=500,
    )
    full_content = str(content or "").strip()
    if not full_content:
        raise ValueError("阿墨暂时没有生成回复，请稍后再试")
    chunk_size = 12
    for start in range(0, len(full_content), chunk_size):
        yield full_content[start : start + chunk_size]
        await asyncio.sleep(0)

