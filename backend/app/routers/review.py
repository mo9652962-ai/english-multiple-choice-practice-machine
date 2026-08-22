"""错题复习（SRS 间隔重复）路由——v9.28 Gemini batch5 任务3 落地"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..services import coverage as coverage_service
from ..services import review as review_service
from .auth import maybe_require_user

router = APIRouter(prefix="/review", tags=["review"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


@router.get("/coverage/{unit_id}")
def unit_coverage(
    unit_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """v9.28: Gemini batch5 任务2——单篇文章生词覆盖率"""
    return coverage_service.get_passage_coverage(connection, unit_id)


class RateRequest(BaseModel):
    quality: int = Field(..., ge=0, le=5, description="作答质量分 0-5（5 完美回忆）")


@router.get("/queue")
def due_queue(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """今日到期复习队列（按 due 早 + ease 低优先）"""
    user_id = _current_user_id(user)
    queue = review_service.get_due_queue(connection, user_id=user_id)
    return {
        "due_count": review_service.count_due(connection, user_id=user_id),
        "items": queue,
    }


@router.post("/{question_id}/rate")
def rate_question(
    question_id: int,
    request: RateRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """提交作答质量分 → 更新 SRS 间隔"""
    # 校验题目存在
    if connection.execute(
        "SELECT 1 FROM questions WHERE id = ?", (question_id,)
    ).fetchone() is None:
        raise HTTPException(404, "题目不存在")
    result = review_service.update_srs_record(
        connection, question_id, request.quality, user_id=_current_user_id(user)
    )
    connection.commit()
    return {"ok": True, **result}
