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
from .auth import maybe_require_user


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


class AnnotationCreate(BaseModel):
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=500)
    note: str = Field(default="", max_length=2000)
    color: str = Field(default="amber", pattern="^(amber|green|blue|red|purple)$")
    tag: str = Field(default="", max_length=20)


class AnnotationUpdate(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    color: str | None = Field(default=None, pattern="^(amber|green|blue|red|purple)$")
    tag: str | None = Field(default=None, max_length=20)


def _row(r: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": r["id"],
        "unit_id": r["unit_id"],
        "start_offset": r["start_offset"],
        "end_offset": r["end_offset"],
        "text": r["text"],
        "note": r["note"],
        "color": r["color"],
        "tag": r["tag"] if "tag" in r.keys() else "",
        "created_at": r["created_at"],
        "updated_at": r["updated_at"],
    }


@router.get("/units/{unit_id}/annotations")
def list_annotations(
    unit_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> list[dict]:
    rows = connection.execute(
        "SELECT * FROM annotations WHERE unit_id = ? AND user_id IS ? ORDER BY start_offset",
        (unit_id, _current_user_id(user)),
    ).fetchall()
    return [_row(r) for r in rows]


@router.get("/annotations")
def list_all_annotations(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
    keyword: str | None = None,
) -> list[dict]:
    """v3.0: 全量标注（笔记管理页用）——JOIN units 带单元标题"""
    user_id = _current_user_id(user)
    sql = """SELECT a.id, a.unit_id, a.start_offset, a.end_offset, a.text, a.note,
                    a.color, a.created_at, a.updated_at,
                    u.title AS unit_title,
                    p.year AS paper_year
             FROM annotations a
             LEFT JOIN units u ON u.id = a.unit_id
             LEFT JOIN papers p ON p.id = u.paper_id
             WHERE a.user_id IS ?"""
    params: list[Any] = [user_id]
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
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    if payload.end_offset <= payload.start_offset:
        raise HTTPException(status_code=400, detail="end_offset 必须大于 start_offset")
    cursor = connection.execute(
        """INSERT INTO annotations (unit_id, start_offset, end_offset, text, note, color, tag, user_id, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (unit_id, payload.start_offset, payload.end_offset, payload.text, payload.note,
         payload.color, payload.tag, _current_user_id(user),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM annotations WHERE id = ? AND user_id IS ?",
        (cursor.lastrowid, _current_user_id(user)),
    ).fetchone()
    return _row(row)


@router.put("/annotations/{annotation_id}")
def update_annotation(
    annotation_id: int,
    payload: AnnotationUpdate,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    user_id = _current_user_id(user)
    current = connection.execute(
        "SELECT * FROM annotations WHERE id = ? AND user_id IS ?", (annotation_id, user_id)
    ).fetchone()
    if not current:
        raise HTTPException(status_code=404, detail="标注不存在")
    new_note = payload.note if payload.note is not None else current["note"]
    new_color = payload.color if payload.color is not None else current["color"]
    new_tag = payload.tag if payload.tag is not None else current["tag"]
    connection.execute(
        """UPDATE annotations SET note = ?, color = ?, tag = ?, updated_at = ? WHERE id = ? AND user_id IS ?""",
        (new_note, new_color, new_tag, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), annotation_id, user_id),
    )
    connection.commit()
    row = connection.execute(
        "SELECT * FROM annotations WHERE id = ? AND user_id IS ?", (annotation_id, user_id)
    ).fetchone()
    return _row(row)


@router.delete("/annotations/{annotation_id}")
def delete_annotation(
    annotation_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    cursor = connection.execute(
        "DELETE FROM annotations WHERE id = ? AND user_id IS ?",
        (annotation_id, _current_user_id(user)),
    )
    connection.commit()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="标注不存在")
    return {"ok": True, "id": annotation_id}


@router.get("/annotations/review")
def review_annotations(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
    limit: int = 20,
) -> dict:
    """v3.0-enhance: 复习模式——随机取笔记（优先无笔记内容/旧的）"""
    user_id = _current_user_id(user)
    rows = connection.execute(
        """SELECT a.id, a.unit_id, a.start_offset, a.end_offset, a.text, a.note, a.color, a.tag,
                  a.created_at, a.updated_at,
                  u.title AS unit_title
           FROM annotations a
           LEFT JOIN units u ON u.id = a.unit_id
           WHERE a.user_id IS ?
           ORDER BY CASE WHEN a.note = '' THEN 0 ELSE 1 END, RANDOM()
           LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    items = []
    for r in rows:
        item = _row(r)
        item["unit_title"] = r["unit_title"] or f"单元 {r['unit_id']}"
        items.append(item)
    return {
        "items": items,
        "total": connection.execute(
            "SELECT COUNT(*) c FROM annotations WHERE user_id IS ?", (user_id,)
        ).fetchone()["c"],
    }


@router.get("/annotations/stats")
def annotation_stats(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """v3.0-enhance: 笔记统计——总数/本周新增/标签分布/颜色分布"""
    user_id = _current_user_id(user)
    total = connection.execute(
        "SELECT COUNT(*) c FROM annotations WHERE user_id IS ?", (user_id,)
    ).fetchone()["c"]
    week = connection.execute(
        """SELECT COUNT(*) c FROM annotations
           WHERE user_id IS ? AND created_at >= datetime('now', 'localtime', '-7 days')""",
        (user_id,),
    ).fetchone()["c"]
    today = connection.execute(
        """SELECT COUNT(*) c FROM annotations
           WHERE user_id IS ? AND date(created_at) = date('now', 'localtime')""",
        (user_id,),
    ).fetchone()["c"]
    tags = connection.execute(
        """SELECT tag, COUNT(*) c FROM annotations
           WHERE user_id IS ? AND tag != '' GROUP BY tag ORDER BY c DESC""",
        (user_id,),
    ).fetchall()
    colors = connection.execute(
        """SELECT color, COUNT(*) c FROM annotations
           WHERE user_id IS ? GROUP BY color ORDER BY c DESC""",
        (user_id,),
    ).fetchall()
    return {
        "total": total,
        "week": week,
        "today": today,
        "tags": [{"tag": r["tag"], "count": r["c"]} for r in tags],
        "colors": [{"color": r["color"], "count": r["c"]} for r in colors],
    }


@router.get("/annotations/stats")
def annotation_stats_v2(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """v9.24: 标注统计（前端 NotesView 调用——此前缺失导致在线模式 404）"""
    user_id = _current_user_id(user)
    total = connection.execute(
        "SELECT COUNT(*) FROM annotations WHERE user_id IS ?", (user_id,)
    ).fetchone()[0]
    by_tag = dict(
        connection.execute(
            "SELECT tag, COUNT(*) FROM annotations WHERE user_id IS ? AND tag != '' GROUP BY tag",
            (user_id,),
        ).fetchall()
    )
    recent = [
        dict(r)
        for r in connection.execute(
            """SELECT id, unit_id, text, tag, created_at
               FROM annotations WHERE user_id IS ? ORDER BY id DESC LIMIT 5""",
            (user_id,),
        ).fetchall()
    ]
    return {"total": total, "by_tag": by_tag, "recent": recent}
