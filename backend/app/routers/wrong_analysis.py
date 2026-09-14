"""Retired compatibility module for the former wrong-analysis API.

The active, user-scoped implementation lives under ``/api/ai``:
``POST /api/ai/analyze-wrong`` and ``GET /api/ai/wrong-analysis-status``.

This module is intentionally kept importable because older integrations may
still import ``router`` while migrating.  It is not registered by ``main``;
if a downstream deployment registers it accidentally, requests receive an
explicit migration response instead of a startup-time import failure or an
unscoped data read.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/wrong/analysis", tags=["wrong-analysis"])


def _retired() -> None:
    raise HTTPException(
        status_code=410,
        detail="错题分析接口已迁移到 /api/ai/analyze-wrong 和 /api/ai/wrong-analysis-status",
    )


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def retired_wrong_analysis_route(path: str) -> None:
    """Return a clear migration response for every former endpoint."""
    _retired()
