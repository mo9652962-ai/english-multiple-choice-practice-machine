"""精讲典藏（AI 解析收藏）——v9.28 Gemini batch5 任务4 落地

DeepExplainDrawer 长难句/选项分析/定位句 → 一键收藏进典藏本，复习闭环。
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db

router = APIRouter(prefix="/collections", tags=["collections"])


class CollectionCreate(BaseModel):
    question_id: int
    fragment_type: str = Field(default="note", description="long_sentence/option/keyword/note")
    content: str = Field(..., min_length=1, max_length=2000)
    source: str = "deep-explain"


@router.post("")
def create_collection(
    request: CollectionCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """收藏一条精讲片段"""
    if connection.execute(
        "SELECT 1 FROM questions WHERE id = ?", (request.question_id,)
    ).fetchone() is None:
        raise HTTPException(404, "题目不存在")
    cur = connection.execute(
        """INSERT INTO explain_collections (question_id, fragment_type, content, source)
           VALUES (?, ?, ?, ?)""",
        (request.question_id, request.fragment_type, request.content.strip(), request.source),
    )
    connection.commit()
    return {"ok": True, "id": cur.lastrowid}


@router.get("")
def list_collections(
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """典藏列表（最新在前，带题号/单元信息）"""
    rows = connection.execute(
        """SELECT c.id, c.question_id, c.fragment_type, c.content, c.source, c.created_at,
                  q.number AS question_number,
                  u.title AS unit_title
           FROM explain_collections c
           JOIN questions q ON q.id = c.question_id
           LEFT JOIN units u ON u.id = q.unit_id
           ORDER BY c.id DESC
           LIMIT 200"""
    ).fetchall()
    return [
        {
            "id": r["id"],
            "question_id": r["question_id"],
            "fragment_type": r["fragment_type"],
            "content": r["content"],
            "source": r["source"],
            "created_at": r["created_at"],
            "question_number": r["question_number"],
            "unit_title": r["unit_title"],
        }
        for r in rows
    ]


@router.delete("/{collection_id}")
def delete_collection(
    collection_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    cur = connection.execute(
        "DELETE FROM explain_collections WHERE id = ?", (collection_id,)
    )
    connection.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "典藏不存在")
    return {"ok": True}
