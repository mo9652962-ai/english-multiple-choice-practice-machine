"""Library units 查询 (v2.75) — 供阅读训练/听力精听页使用
GET /api/library/units?unit_type=reading&limit=6
"""
from __future__ import annotations

import sqlite3
from fastapi import APIRouter, Depends, Query

from ..database import get_db

router = APIRouter(prefix="/library", tags=["library"])


@router.get("/units")
def list_units(unit_type: str = Query("", description="题型: reading/listening/cloze"),
               limit: int = Query(10, ge=1, le=100),
               connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """按题型返回已发布单元的短文列表 (阅读/听力入口数据源)"""
    sql = """SELECT units.id, units.paper_id, units.unit_type, units.title,
                    units.passage, units.subtype, units.audio_path,
                    papers.year, papers.title AS paper_title, papers.profile_id
             FROM units
             JOIN papers ON papers.id = units.paper_id
             WHERE papers.status = 'published' AND papers.deleted_at IS NULL
               AND ((units.passage IS NOT NULL AND units.passage != '') OR units.audio_path IS NOT NULL)"""
    params: list = []
    if unit_type:
        sql += " AND units.unit_type = ?"
        params.append(unit_type)
    sql += " ORDER BY units.id DESC LIMIT ?"
    params.append(limit)
    rows = connection.execute(sql, params).fetchall()
    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "unit_id": r["id"],
            "paper_id": r["paper_id"],
            "unit_type": r["unit_type"],
            "title": r["title"],
            "subtype": r["subtype"],
            "passage": (r["passage"] or "")[:600],
            "excerpt": (r["passage"] or "")[:200],
            "year": r["year"],
            "paper_title": r["paper_title"],
            "profile_id": r["profile_id"],
            "audio_url": f"/audio/{r['audio_path'].split('/')[-1]}" if r["audio_path"] else None,
        })
    return {"items": items, "count": len(items)}
