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
        # v2.9: 按当前级别针对性推荐
        "recommendations": _build_recommendations(connection, profile_id),
    }


def _build_recommendations(connection: sqlite3.Connection, profile_id: int) -> dict:
    """v2.9: 按当前级别(题库)生成针对性推荐。
    规则推荐(无外部ML): 继续练习 / 本级别真题卷 / 本级别高频错题 / 薄弱单元
    """
    # ① 继续练习: 最近一次未完成的练习(该级别)
    continue_paper = connection.execute(
        """
        SELECT papers.id, papers.year, papers.subject, papers.title
        FROM practice_sessions
        JOIN papers ON papers.id = practice_sessions.paper_id
        WHERE papers.profile_id = ? AND papers.deleted_at IS NULL
          AND practice_sessions.status = 'in_progress'
        ORDER BY practice_sessions.id DESC LIMIT 1
        """,
        (profile_id,),
    ).fetchone()

    # ② 本级别真题卷: 已发布, 最近年份优先, 取 6 份
    papers = connection.execute(
        """
        SELECT id, year, subject, title
        FROM papers
        WHERE status = 'published' AND profile_id = ? AND deleted_at IS NULL
        ORDER BY year DESC, id DESC LIMIT 6
        """,
        (profile_id,),
    ).fetchall()

    # ③ 本级别高频错题 TOP3: 错题本数据
    top_wrong = connection.execute(
        """
        SELECT questions.id, questions.stem, questions.question_type,
               wrong_stats.wrong_count
        FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE papers.profile_id = ? AND papers.deleted_at IS NULL
          AND wrong_stats.wrong_count > 0
        ORDER BY wrong_stats.wrong_count DESC, wrong_stats.last_wrong_at DESC
        LIMIT 3
        """,
        (profile_id,),
    ).fetchall()

    # ④ 薄弱单元: 该级别错误率最高的单元(按错题数)
    weak_units = connection.execute(
        """
        SELECT units.id, units.title, COUNT(wrong_stats.question_id) AS wrong_n
        FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE papers.profile_id = ? AND papers.deleted_at IS NULL
          AND wrong_stats.wrong_count > 0
        GROUP BY units.id, units.title
        ORDER BY wrong_n DESC LIMIT 3
        """,
        (profile_id,),
    ).fetchall()

    # ⑤ 能力雷达: 按 unit_type 统计该级别正确率 (阅读/完形/匹配)
    ability = connection.execute(
        """
        SELECT u.unit_type,
               SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) AS correct,
               COUNT(*) AS total
        FROM practice_answers pa
        JOIN questions q ON q.id = pa.question_id
        JOIN units u ON u.id = q.unit_id
        JOIN papers p ON p.id = u.paper_id
        WHERE p.profile_id = ? AND p.deleted_at IS NULL
        GROUP BY u.unit_type
        ORDER BY (COUNT(*) * 1.0) DESC
        """,
        (profile_id,),
    ).fetchall()

    def _trim(text: str, n: int = 60) -> str:
        text = (text or "").replace("\n", " ").strip()
        return text if len(text) <= n else text[:n] + "…"

    return {
        "continue_paper": dict(continue_paper) if continue_paper else None,
        "papers": [dict(r) for r in papers],
        "top_wrong": [
            {
                "id": r["id"],
                "prompt": _trim(r["stem"]),
                "question_type": r["question_type"],
                "wrong_count": r["wrong_count"],
            }
            for r in top_wrong
        ],
        "weak_units": [
            {"id": r["id"], "title": r["title"], "wrong_n": r["wrong_n"]}
            for r in weak_units
        ],
        # v2.10: 能力雷达 (按题型正确率) + 薄弱题型(一键专项)
        "ability_radar": [
            {
                "type": r["unit_type"],
                "correct": r["correct"],
                "total": r["total"],
                "rate": round(r["correct"] / r["total"] * 100) if r["total"] else None,
            }
            for r in ability
        ],
    }


@router.get("/streak")
def streak(connection: sqlite3.Connection = Depends(get_db)) -> dict:
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
