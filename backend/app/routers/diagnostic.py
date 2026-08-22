"""学习诊断报告 API（P0）。

POST /api/diagnostic/report  —— 生成诊断报告（归因 → 聚合 → 水平 → 推荐 → 趋势）
GET  /api/diagnostic/report/{id} —— 读取历史报告
GET  /api/diagnostic/reports   —— 报告列表
"""
from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_active_profile_id, get_db
from ..services.diagnostic_report import (
    generate_diagnostic_report,
    list_diagnostic_reports,
    load_diagnostic_report,
)
from .auth import maybe_require_user

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


class DiagnosticRequest(BaseModel):
    question_ids: list[int] = Field(..., min_length=1, max_length=200)
    previous_report_id: int | None = None


@router.post("/report")
def create_report(
    request: DiagnosticRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    profile_id = get_active_profile_id(connection)
    try:
        result = generate_diagnostic_report(
            connection,
            request.question_ids,
            previous_report_id=request.previous_report_id,
            profile_id=profile_id,
            user_id=_current_user_id(user),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return result


@router.get("/report/{report_id}")
def get_report(
    report_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    report = load_diagnostic_report(connection, report_id, user_id=_current_user_id(user))
    if report is None:
        raise HTTPException(status_code=404, detail="诊断报告不存在")
    return report


@router.get("/reports")
def get_reports(
    limit: int = 10,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> list[dict[str, Any]]:
    return list_diagnostic_reports(connection, limit=min(limit, 50), user_id=_current_user_id(user))
