"""内置反馈入口 (v2.95) — 内测方案 P0: 设置页"反馈建议"按钮 + feedback 表
零摩擦: 3 秒提交, 预设分类: 报错/不好用/想要新功能/其他
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..database import get_active_profile_id, get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _init_table(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL DEFAULT 'other',
        content TEXT NOT NULL,
        contact TEXT DEFAULT '',
        page TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'new',
        created_at TEXT NOT NULL
    )""")


def _ensure_table(connection):
    _init_table(connection)
    connection.commit()


class FeedbackIn(BaseModel):
    category: str = Field(default="other", description="报错/bad/idea/other")
    content: str = Field(..., min_length=2, max_length=2000)
    contact: str = Field(default="", max_length=200)
    page: str = Field(default="", max_length=100)


@router.post("")
def submit_feedback(item: FeedbackIn, connection: sqlite3.Connection = Depends(get_db)):
    _ensure_table(connection)
    cur = connection.execute(
        "INSERT INTO feedback (category, content, contact, page, created_at) VALUES (?,?,?,?,?)",
        (item.category, item.content.strip(), item.contact.strip(), item.page.strip(),
         datetime.now().isoformat(timespec="seconds")),
    )
    connection.commit()
    return {"ok": True, "id": cur.lastrowid, "message": "反馈已收到，谢谢！"}


@router.get("")
def list_feedback(connection: sqlite3.Connection = Depends(get_db)):
    _ensure_table(connection)
    rows = connection.execute(
        "SELECT id, category, content, contact, page, status, created_at FROM feedback ORDER BY id DESC LIMIT 200"
    ).fetchall()
    cols = ["id", "category", "content", "contact", "page", "status", "created_at"]
    return [dict(zip(cols, r)) for r in rows]
