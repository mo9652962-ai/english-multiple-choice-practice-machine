"""考场打印与试卷导出路由。
提供出版级 A4 标准双栏排版试卷、答题卡与解析册 HTML 导出。
"""

from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..database import get_db
from ..services.exam_print import (
    generate_paper_print_html,
    generate_wrong_questions_print_html,
)
from .auth import maybe_require_user

router = APIRouter(prefix="/export", tags=["export"])


class WrongQuestionsPrintRequest(BaseModel):
    question_ids: list[int] = Field(min_length=1, max_length=200)
    title: str = Field(default="考研英语 · 错题专项攻坚卷", max_length=100)


@router.get("/paper/{paper_id}/print", response_class=HTMLResponse)
def export_paper_print(
    paper_id: int,
    include_answers: bool = True,
    connection: sqlite3.Connection = Depends(get_db),
) -> HTMLResponse:
    try:
        html_content = generate_paper_print_html(
            connection,
            paper_id,
            include_answers=include_answers,
        )
        return HTMLResponse(content=html_content, status_code=200)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"试卷排版生成失败: {error}") from error


@router.post("/wrong-questions/print", response_class=HTMLResponse)
def export_wrong_questions_print(
    request: WrongQuestionsPrintRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> HTMLResponse:
    try:
        user_id = user["id"] if user else None
        html_content = generate_wrong_questions_print_html(
            connection,
            request.question_ids,
            title=request.title,
            user_id=user_id,
        )
        return HTMLResponse(content=html_content, status_code=200)
    except (LookupError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"错题攻坚卷排版生成失败: {error}") from error
