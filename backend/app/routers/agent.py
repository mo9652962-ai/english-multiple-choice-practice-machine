"""AI 学习智能体 API。"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..services.agent_runtime import run_learning_agent
from .auth import maybe_require_user

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRunRequest(BaseModel):
    user_id: int | None = Field(default=None, ge=1)
    goal: str = Field(default="", max_length=500)


class MemoryRequest(BaseModel):
    type: str = Field(default="fact", min_length=1, max_length=40)
    content: str = Field(min_length=1, max_length=5000)
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)


def _current_user_id(user: dict | None, requested: int | None = None) -> int | None:
    return int(user["id"]) if user else requested


def _decode(value: str) -> Any:
    try:
        return json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return value


@router.post("/run")
def create_run(
    request: AgentRunRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    user_id = _current_user_id(user, request.user_id)
    return run_learning_agent(user_id, connection=connection, goal=request.goal)


@router.get("/runs")
def list_runs(
    limit: int = 20,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> list[dict[str, Any]]:
    user_id = _current_user_id(user)
    rows = connection.execute(
        "SELECT * FROM agent_runs WHERE user_id IS ? ORDER BY id DESC LIMIT ?",
        (user_id, max(1, min(limit, 100))),
    ).fetchall()
    return [dict(row) for row in rows]


@router.get("/runs/{run_id}")
def get_run(
    run_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    user_id = _current_user_id(user)
    row = connection.execute(
        "SELECT * FROM agent_runs WHERE id = ? AND user_id IS ?", (run_id, user_id)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Agent 运行记录不存在")
    result = dict(row)
    for table, key in (("agent_steps", "steps"), ("agent_decisions", "decisions"), ("agent_tool_calls", "tool_calls")):
        items = [dict(item) for item in connection.execute(f"SELECT * FROM {table} WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()]
        for item in items:
            for field in ("input", "output", "args", "result"):
                if field in item:
                    item[field] = _decode(item[field])
        result[key] = items
    return result


@router.post("/decisions/{decision_id}/approve")
def approve_decision(
    decision_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    user_id = _current_user_id(user)
    row = connection.execute(
        """SELECT d.* FROM agent_decisions d JOIN agent_runs r ON r.id = d.run_id
           WHERE d.id = ? AND r.user_id IS ?""",
        (decision_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Agent 决策不存在")
    connection.execute(
        "UPDATE agent_decisions SET status = 'approved' WHERE id = ?", (decision_id,)
    )
    connection.commit()
    return {"id": decision_id, "status": "approved"}


@router.post("/memories")
def create_memory(
    request: MemoryRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    user_id = _current_user_id(user)
    cursor = connection.execute(
        """INSERT INTO user_memories (user_id, type, content, importance, confidence)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, request.type.strip(), request.content.strip(), request.importance, request.confidence),
    )
    connection.commit()
    row = connection.execute("SELECT * FROM user_memories WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


@router.get("/memories")
def list_memories(
    limit: int = 50,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> list[dict[str, Any]]:
    user_id = _current_user_id(user)
    rows = connection.execute(
        """SELECT * FROM user_memories WHERE user_id IS ?
           ORDER BY importance DESC, id DESC LIMIT ?""",
        (user_id, max(1, min(limit, 200))),
    ).fetchall()
    return [dict(row) for row in rows]
