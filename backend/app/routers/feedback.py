"""内置反馈入口 (v2.95) — 内测方案 P0: 设置页"反馈建议"按钮 + feedback 表
零摩擦: 3 秒提交, 预设分类: 报错/不好用/想要新功能/其他
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Literal

from ..database import get_db
from .auth import require_admin

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
    # 结构化内测字段以增量方式补到旧反馈表，兼容 v2.95 以前已经存在的本地库。
    existing = {row[1] for row in connection.execute("PRAGMA table_info(feedback)")}
    for column, declaration in {
        "participant_code": "TEXT NOT NULL DEFAULT ''",
        "difficulty_rating": "INTEGER",
        "explanation_rating": "INTEGER",
        "coverage_rating": "INTEGER",
        "continue_intent": "TEXT",
    }.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE feedback ADD COLUMN {column} {declaration}")
    connection.commit()


class FeedbackIn(BaseModel):
    category: str = Field(default="other", description="报错/bad/idea/other")
    content: str = Field(..., min_length=2, max_length=2000)
    contact: str = Field(default="", max_length=200)
    page: str = Field(default="", max_length=100)
    # 内测编号只允许用户自填的匿名短码，不收集姓名、手机号或设备标识。
    participant_code: str = Field(default="", max_length=32, pattern=r"^[A-Za-z0-9_-]*$")
    difficulty_rating: int | None = Field(default=None, ge=1, le=5)
    explanation_rating: int | None = Field(default=None, ge=1, le=5)
    coverage_rating: int | None = Field(default=None, ge=1, le=5)
    continue_intent: Literal["yes", "no", "unsure"] | None = None


@router.post("")
def submit_feedback(item: FeedbackIn, connection: sqlite3.Connection = Depends(get_db)):
    _ensure_table(connection)
    cur = connection.execute(
        """INSERT INTO feedback (
            category, content, contact, page, participant_code,
            difficulty_rating, explanation_rating, coverage_rating,
            continue_intent, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            item.category,
            item.content.strip(),
            item.contact.strip(),
            item.page.strip(),
            item.participant_code.strip(),
            item.difficulty_rating,
            item.explanation_rating,
            item.coverage_rating,
            item.continue_intent,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    connection.commit()
    return {"ok": True, "id": cur.lastrowid, "message": "反馈已收到，谢谢！"}


@router.get("")
def list_feedback(
    connection: sqlite3.Connection = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    _ensure_table(connection)
    rows = connection.execute(
        """SELECT id, category, content, contact, page, participant_code,
                  difficulty_rating, explanation_rating, coverage_rating,
                  continue_intent, status, created_at
           FROM feedback ORDER BY id DESC LIMIT 200"""
    ).fetchall()
    cols = [
        "id", "category", "content", "contact", "page", "participant_code",
        "difficulty_rating", "explanation_rating", "coverage_rating",
        "continue_intent", "status", "created_at",
    ]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/summary")
def feedback_summary(
    days: int = Query(default=30, ge=1, le=365),
    connection: sqlite3.Connection = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    """Return anonymous aggregates for the pilot decision gates.

    This endpoint intentionally excludes feedback text, contact details and
    participant codes.  A self-entered code is only counted as a distinct
    anonymous label, never as an authenticated user or a payment record.
    """
    _ensure_table(connection)
    window = f"-{days} days"
    totals = connection.execute(
        """SELECT COUNT(*) AS response_count,
                  COUNT(DISTINCT NULLIF(participant_code, '')) AS participant_count,
                  ROUND(AVG(difficulty_rating), 2) AS difficulty_average,
                  ROUND(AVG(explanation_rating), 2) AS explanation_average,
                  ROUND(AVG(coverage_rating), 2) AS coverage_average
           FROM feedback
           WHERE created_at >= datetime('now', ?)""",
        (window,),
    ).fetchone()
    category_rows = connection.execute(
        """SELECT category, COUNT(*) AS count
           FROM feedback
           WHERE created_at >= datetime('now', ?)
           GROUP BY category ORDER BY count DESC, category""",
        (window,),
    ).fetchall()
    intent_rows = connection.execute(
        """SELECT COALESCE(NULLIF(continue_intent, ''), 'unrated') AS intent,
                  COUNT(*) AS count
           FROM feedback
           WHERE created_at >= datetime('now', ?)
           GROUP BY intent ORDER BY intent""",
        (window,),
    ).fetchall()
    return {
        "days": days,
        "response_count": int(totals["response_count"] or 0),
        "participant_count": int(totals["participant_count"] or 0),
        "ratings": {
            "difficulty_average": totals["difficulty_average"],
            "explanation_average": totals["explanation_average"],
            "coverage_average": totals["coverage_average"],
        },
        "by_category": [dict(row) for row in category_rows],
        "continue_intent": [dict(row) for row in intent_rows],
    }
