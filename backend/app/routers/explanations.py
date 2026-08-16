"""任务 E（第 4 部分）：题目解析 API。

- GET /api/questions/{question_id}/explain  获取单题解析
  200 {"available": true,  "content": {...}, "source_model", "updated_at"}  有解析
  200 {"available": false}                                                  暂无解析（题存在）
  404                                                                      题目不存在

content 为结构化 JSON（由 backend/prompts/explain_prompt.py 约定）：
{correct_analysis, wrong_options: [{key, reason}], knowledge_points, study_advice}
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db

router = APIRouter(tags=["explanations"])


@router.get("/questions/{question_id}/explain")
def get_question_explain(
    question_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    question = connection.execute(
        "SELECT id FROM questions WHERE id = ?", (question_id,)
    ).fetchone()
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    row = connection.execute(
        """
        SELECT content, source_model, updated_at
        FROM question_explanations
        WHERE question_id = ?
        """,
        (question_id,),
    ).fetchone()
    if row is None:
        return {"question_id": question_id, "available": False}

    try:
        content = json.loads(row["content"])
    except (TypeError, json.JSONDecodeError):
        # 历史脏数据兜底：按纯文本解析展示
        content = {"correct_analysis": str(row["content"]), "wrong_options": [],
                   "knowledge_points": [], "study_advice": ""}
    return {
        "question_id": question_id,
        "available": True,
        "content": content,
        "source_model": row["source_model"],
        "updated_at": row["updated_at"],
    }


@router.get("/explanations/coverage")
def explanations_coverage(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """解析覆盖率（管理端/批量生成进度展示）。"""
    row = connection.execute(
        """
        SELECT COUNT(q.id) AS total,
               SUM(CASE WHEN e.question_id IS NOT NULL THEN 1 ELSE 0 END) AS explained
        FROM questions AS q
        LEFT JOIN question_explanations AS e ON e.question_id = q.id
        """
    ).fetchone()
    total = int(row["total"] or 0)
    explained = int(row["explained"] or 0)
    return {
        "total": total,
        "explained": explained,
        "remaining": max(0, total - explained),
        "percentage": round(explained * 100 / total, 1) if total else 0,
    }
