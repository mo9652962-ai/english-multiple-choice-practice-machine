"""Privacy-first local usage metrics API."""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..database import get_db
from ..services.metrics import EVENT_NAMES, get_consent, record_event, set_consent, summarize
from .auth import maybe_require_user

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


class ConsentRequest(BaseModel):
    enabled: bool


class EventRequest(BaseModel):
    event_name: str = Field(min_length=1, max_length=64)
    detail: dict[str, Any] = Field(default_factory=dict)


@router.get("/consent")
def read_consent(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, bool]:
    return {"enabled": get_consent(connection, _user_id(user))}


@router.put("/consent")
def update_consent(
    request: ConsentRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, bool]:
    return {"enabled": set_consent(connection, request.enabled, _user_id(user))}


@router.post("/events")
def create_event(
    request: EventRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, bool]:
    if request.event_name not in EVENT_NAMES:
        raise HTTPException(status_code=422, detail="不支持的指标事件")
    return {
        "recorded": record_event(
            connection,
            request.event_name,
            user_id=_user_id(user),
            detail=request.detail,
        )
    }


@router.get("/summary")
def metrics_summary(
    days: int = Query(default=30, ge=1, le=365),
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    return summarize(connection, user_id=_user_id(user), days=days)
