from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..database import get_active_profile_id, get_db


router = APIRouter(tags=["dashboard"])


@router.get("/startup")
@router.get("/overview", include_in_schema=False)
@router.get("/dashboard", include_in_schema=False)
def dashboard(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    profile_id = get_active_profile_id(connection)
    profile = connection.execute(
        "SELECT id, name FROM question_bank_profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    paper_count = connection.execute(
        """
        SELECT COUNT(*) AS count FROM papers
        WHERE status = 'published' AND profile_id = ? AND deleted_at IS NULL
        """,
        (profile_id,),
    ).fetchone()["count"]
    unit_count = connection.execute(
        """
        SELECT COUNT(*) AS count FROM units
        JOIN papers ON papers.id = units.paper_id
        WHERE papers.profile_id = ? AND papers.deleted_at IS NULL
        """,
        (profile_id,),
    ).fetchone()["count"]
    question_count = connection.execute(
        """
        SELECT COUNT(*) AS count FROM questions
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE papers.profile_id = ? AND papers.deleted_at IS NULL
        """,
        (profile_id,),
    ).fetchone()["count"]
    wrong_count = connection.execute(
        """
        SELECT COUNT(*) AS count FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE wrong_stats.wrong_count > 0
          AND papers.profile_id = ? AND papers.deleted_at IS NULL
        """,
        (profile_id,),
    ).fetchone()["count"]
    frequent_count = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE (
              manually_frequent = 1
           OR wrong_count >= 3
           OR (
                json_array_length(recent_results) >= 5
                AND (
                    SELECT COUNT(*)
                    FROM json_each(recent_results)
                    WHERE value = 0
                ) >= 3
           ))
          AND papers.profile_id = ? AND papers.deleted_at IS NULL
        """,
        (profile_id,),
    ).fetchone()["count"]
    recent = connection.execute(
        """
        SELECT practice_sessions.id, practice_sessions.mode,
               practice_sessions.status, practice_sessions.started_at,
               practice_sessions.submitted_at, practice_sessions.score,
               practice_sessions.max_score, papers.year
        FROM practice_sessions
        LEFT JOIN papers ON papers.id = practice_sessions.paper_id
        WHERE papers.profile_id = ? OR practice_sessions.paper_id IS NULL
        ORDER BY practice_sessions.id DESC
        LIMIT 5
        """,
        (profile_id,),
    ).fetchall()
    return {
        "active_profile": dict(profile) if profile else None,
        "paper_count": paper_count,
        "unit_count": unit_count,
        "question_count": question_count,
        "wrong_count": wrong_count,
        "frequent_count": frequent_count,
        "recent_sessions": [dict(row) for row in recent],
    }


@router.get("/streak")
def streak(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """学习连续打卡 + 热力图数据 + 周报"""
    from ..services.streak import get_streak, get_heatmap_data, get_monthly_summary, get_weekly_report
    return {
        "streak": get_streak(connection),
        "heatmap": get_heatmap_data(connection, days=180),
        "monthly": get_monthly_summary(connection),
        "weekly": get_weekly_report(connection),
    }


@router.get("/dashboard/streak", include_in_schema=False)
def streak_alias(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """兼容前端 /dashboard/streak 路径"""
    return streak(connection)
