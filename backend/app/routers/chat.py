"""学习陪伴聊天室 REST 与 WebSocket 接口。"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..database import connect, get_db
from ..routers.auth import AUTH_ENABLED, maybe_require_user
from ..services.chat_service import (
    save_message,
    stream_ai_reply,
)

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)

_connections: dict[WebSocket, int | None] = {}
_ai_request_users: dict[str, int | None] = {}
_connections_lock = asyncio.Lock()
_AI_MENTION_RE = re.compile(r"@(?:ai|墨|阿墨)", re.IGNORECASE)


def _base36(value: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value == 0:
        return "0"
    digits: list[str] = []
    while value:
        value, remainder = divmod(value, 36)
        digits.append(alphabet[remainder])
    return "".join(reversed(digits))


def _new_request_id() -> str:
    timestamp = _base36(int(time.time() * 1000))
    return f"ai-{timestamp}-{secrets.token_hex(4)}"


def _user_id(user: dict[str, Any] | None) -> int | None:
    if user is None:
        return None
    try:
        return int(user["id"])
    except (KeyError, TypeError, ValueError):
        return None


def _wire_message(message: dict[str, Any], client_id: str | None = None) -> dict[str, Any]:
    return {
        "type": "message",
        "id": message["id"],
        "userId": message["user_id"],
        "senderType": message["sender_type"],
        "senderName": message["sender_name"],
        "content": message["content"],
        "requestId": message["request_id"],
        "createdAt": message["created_at"],
        "clientId": client_id,
    }


async def _broadcast(event: dict[str, Any], user_id: int | None = None) -> None:
    """串行广播，避免多个并发 AI 任务同时写同一个 WebSocket。"""
    if user_id is None and event.get("type") in {"ai_start", "ai_delta", "ai_done", "ai_error"}:
        user_id = _ai_request_users.get(str(event.get("requestId")))
    async with _connections_lock:
        stale: list[WebSocket] = []
        for websocket, connection_user_id in list(_connections.items()):
            if user_id is not None and connection_user_id != user_id:
                continue
            try:
                await websocket.send_json(event)
            except (WebSocketDisconnect, RuntimeError, OSError):
                stale.append(websocket)
        for websocket in stale:
            _connections.pop(websocket, None)


async def _broadcast_presence() -> None:
    async with _connections_lock:
        event = {"type": "presence", "online": len(_connections)}
        stale: list[WebSocket] = []
        for websocket in list(_connections):
            try:
                await websocket.send_json(event)
            except (WebSocketDisconnect, RuntimeError, OSError):
                stale.append(websocket)
        for websocket in stale:
            _connections.pop(websocket, None)


def _get_recent_messages(
    connection, user_id: int | None, limit: int = 100
) -> list[dict[str, Any]]:
    """读取当前用户的聊天上下文；chat_messages 没有独立会话外键。"""
    try:
        safe_limit = max(1, min(int(limit), 500))
    except (TypeError, ValueError):
        safe_limit = 100
    rows = connection.execute(
        """
        SELECT id, user_id, sender_type, sender_name, content, request_id, created_at
        FROM chat_messages
        WHERE user_id IS ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (user_id, safe_limit),
    ).fetchall()
    return [dict(row) for row in reversed(rows)]


def _websocket_user_id(websocket: WebSocket, connection) -> int | None:
    """在启用 EPM_AUTH 时从 WS Header 或 query token 读取当前用户。"""
    if not AUTH_ENABLED:
        return None
    authorization = websocket.headers.get("authorization", "")
    token = authorization[7:].strip() if authorization.startswith("Bearer ") else ""
    if not token:
        token = websocket.query_params.get("token", "").strip()
    if not token:
        return None
    row = connection.execute(
        "SELECT id FROM users WHERE token = ?",
        (token,),
    ).fetchone()
    return int(row["id"]) if row is not None else None


async def _run_ai_reply(
    user_id: int | None,
    recent_messages: list[dict[str, Any]],
    user_message: str,
) -> None:
    request_id = _new_request_id()
    _ai_request_users[request_id] = user_id
    await _broadcast(
        {
            "type": "ai_start",
            "requestId": request_id,
            "senderName": "阿墨",
        },
        user_id=user_id,
    )
    connection = connect()
    chunks: list[str] = []
    try:
        async for chunk in stream_ai_reply(connection, recent_messages, user_message):
            chunks.append(chunk)
            await _broadcast(
                {
                    "type": "ai_delta",
                    "requestId": request_id,
                    "content": chunk,
                },
                user_id=user_id,
            )
        full_content = "".join(chunks).strip()
        saved = save_message(
            connection,
            user_id,
            "ai",
            "阿墨",
            full_content,
            request_id=request_id,
        )
        await _broadcast(
            {
                "type": "ai_done",
                "requestId": request_id,
                "senderName": "阿墨",
                "fullContent": full_content,
                "messageId": saved["id"],
                "createdAt": saved["created_at"],
            },
            user_id=user_id,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("聊天室 AI 回复失败")
        await _broadcast(
            {
                "type": "ai_error",
                "requestId": request_id,
                "error": "阿墨暂时没连上，请稍后再试",
            }
        )
    finally:
        _ai_request_users.pop(request_id, None)
        connection.close()


@router.get("/messages")
def list_messages(
    connection=Depends(get_db),
    _user: dict[str, Any] | None = Depends(maybe_require_user),
) -> list[dict[str, Any]]:
    return _get_recent_messages(connection, _user_id(_user), limit=100)


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    connection = connect()
    ai_tasks: set[asyncio.Task[None]] = set()
    try:
        user_id = _websocket_user_id(websocket, connection)
        if AUTH_ENABLED and user_id is None:
            await websocket.close(code=1008, reason="未登录")
            return

        async with _connections_lock:
            _connections[websocket] = user_id
        await _broadcast_presence()

        while True:
            try:
                raw = await websocket.receive_text()
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "error": "消息必须是合法 JSON"})
                continue
            if not isinstance(payload, dict):
                await websocket.send_json({"type": "error", "error": "消息格式不正确"})
                continue

            message_type = payload.get("type")
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            if message_type != "message":
                await websocket.send_json({"type": "error", "error": "不支持的消息类型"})
                continue

            content = payload.get("content")
            if not isinstance(content, str) or not content.strip():
                await websocket.send_json({"type": "error", "error": "消息内容不能为空"})
                continue
            try:
                saved = save_message(
                    connection,
                    user_id,
                    "user",
                    "研友" if user_id is not None else "你",
                    content,
                )
            except ValueError as error:
                await websocket.send_json({"type": "error", "error": str(error)})
                continue

            client_id = payload.get("clientId")
            client_id = str(client_id) if client_id is not None else None
            await _broadcast(_wire_message(saved, client_id), user_id=user_id)

            if _AI_MENTION_RE.search(content):
                recent_messages = _get_recent_messages(connection, user_id, limit=10)
                task = asyncio.create_task(
                    _run_ai_reply(user_id, recent_messages, content)
                )
                ai_tasks.add(task)
                task.add_done_callback(ai_tasks.discard)
    except WebSocketDisconnect:
        pass
    except (RuntimeError, OSError):
        pass
    finally:
        async with _connections_lock:
            _connections.pop(websocket, None)
        connection.close()
        await _broadcast_presence()
