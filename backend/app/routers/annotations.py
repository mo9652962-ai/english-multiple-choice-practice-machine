"""v3.0: 做题标注 API — 关键词高亮 + 笔记持久化
- GET    /api/units/{unit_id}/annotations  列出单元标注
- POST   /api/units/{unit_id}/annotations  新建标注
- PUT    /api/annotations/{annotation_id}  更新标注（笔记/颜色）
- DELETE /api/annotations/{annotation_id}  删除标注
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["annotations"])


from ..database import get_db


class AnnotationCreate(BaseModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=500)
    note: str = Field(default="", max_length=2000)
    color: str = Field(default="amber", pattern="^(amber|green|blue|red|purple)$")


class AnnotationUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern="^(amber|green|blue|red|purple)$")


def _row(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": r["id"],
        "unit_id": r["unit_id"],
        "start_offset": r["start_offset"],
        "end_offset": r["end_offset"],
        "text": r["text"],
        "note": r["note"],
        "color": r["color"],
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


@router.get("/units/{unit_id}/annotations")
def list_annotations(unit_id: int, connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM annotations WHERE unit_id = ? ORDER BY start_offset",
        (unit_id,),
    ).fetchall()
    return [_row(r) for r in rows]


@router.get("/annotations")
def list_all_annotations(
    connection: sqlite3.Connection = Depends(get_db),
    keyword: str | None = None,
) -> list[dict]:
    """v3.0: 全量标注（笔记管理页用）——JOIN units 带单元标题"""
    sql = """SELECT a.id, a.unit_id, a.start_offset, a.end_offset, a.text, a.note,
                    a.color, a.created_at, a.updated_at,
                    u.title AS unit_title,
                    p.year AS paper_year
             FROM annotations a
             LEFT JOIN units u ON u.id = a.unit_id
             LEFT JOIN papers p ON p.id = u.paper_id
             WHERE 1=1"""
    params: list[Any] = []
    if keyword:
        sql += " AND (a.text LIKE ? OR a.note LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    sql += " ORDER BY a.created_at DESC, a.id DESC"
    rows = connection.execute(sql, params).fetchall()
    result = []
    for r in rows:
        item = _row(r)
        item["unit_title"] = r["unit_title"] or f"单元 {r['unit_id']}"
        item["paper_year"] = r["paper_year"]
        result.append(item)
    return result


@router.post("/units/{unit_id}/annotations")
def create_annotation(
    unit_id: int,
    payload: AnnotationCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    if payload.end_offset <= payload.start_offset:
        raise HTTPException(status_code=400, detail="end_offset 必须大于 start_offset")
    cursor = connection.execute(
        """INSERT INTO annotations (unit_id, start_offset, end_offset, text, note, color, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (unit_id, payload.start_offset, payload.end_offset, payload.text, payload.note,
         payload.color, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM annotations WHERE id = ?", (cursor.lastrowid,)
    ).fetchone()
    return _row(row)


@router.put("/annotations/{annotation_id}")
def update_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    current = connection.execute(
        "SELECT * FROM annotations WHERE id = ?", (annotation_id,)
    ).fetchone()
    if not current:
        raise HTTPException(status_code=404, detail="标注不存在")
    new_note = payload.note if payload.note is not None else current["note"]
    new_color = payload.color if payload.color is not None else current["color"]
    connection.execute(
        """UPDATE annotations SET note = ?, color = ?, updated_at = ? WHERE id = ?""",
        (new_note, new_color, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), annotation_id),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM annotations WHERE id = ?", (annotation_id,)
    ).fetchone()
    return _row(row)


@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> dict:
    cursor = connection.execute("DELETE FROM annotations WHERE id = ?", (annotation_id,))
    connection.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="标注不存在")
    return {"ok": True, "id": annotation_id}
