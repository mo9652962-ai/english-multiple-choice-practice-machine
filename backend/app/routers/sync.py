"""跨端增量同步路由 (Local-First Sync API)"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..services.sync import exchange_sync_data
from .auth import maybe_require_user

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncExchangeRequest(BaseModel):
    client_time: str | None = None
    last_synced_at: str | None = None
    push: dict[str, Any] = Field(default_factory=dict)


@router.post("/exchange")
def sync_exchange(
    request: SyncExchangeRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    try:
        user_id = user["id"] if user else None
        return exchange_sync_data(
            connection,
            user_id,
            request.model_dump(),
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"增量同步失败: {error}") from error


@router.get("/status")
def sync_status(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    user_id = user["id"] if user else None
    days_cnt = connection.execute(
        "SELECT COUNT(*) FROM learning_days WHERE user_id IS ?", (user_id,)
    ).fetchone()[0]
    wrongs_cnt = connection.execute(
        "SELECT COUNT(*) FROM wrong_stats WHERE user_id IS ?", (user_id,)
    ).fetchone()[0]
    fsrs_cnt = connection.execute(
        "SELECT COUNT(*) FROM spaced_repetition_records WHERE user_id IS ?", (user_id,)
    ).fetchone()[0]

    return {
        "user_id": user_id,
        "is_authenticated": user is not None,
        "server_counts": {
            "learning_days": days_cnt,
            "wrong_stats": wrongs_cnt,
            "fsrs_records": fsrs_cnt,
        },
    }
