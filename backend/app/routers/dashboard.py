from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from fastapi import APIRouter, Depends

from ..database import get_active_profile_id, get_db
from ..services.listening import listening_unit_has_audio_sql
from .auth import maybe_require_user

router = APIRouter(tags=["dashboard"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


@router.get("/startup")
@router.get("/overview", include_in_schema=False)
@router.get("/dashboard", include_in_schema=False)
def dashboard(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    profile_id = get_active_profile_id(connection)
    user_id = _current_user_id(user)
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
          AND wrong_stats.user_id IS ?
          AND papers.profile_id = ? AND papers.deleted_at IS NULL
        """,
        (user_id, profile_id),
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
          AND wrong_stats.user_id IS ?
          AND papers.profile_id = ? AND papers.deleted_at IS NULL
        """,
        (user_id, profile_id),
    ).fetchone()["count"]
    recent = connection.execute(
        """
        SELECT practice_sessions.id, practice_sessions.mode,
               practice_sessions.status, practice_sessions.started_at,
               practice_sessions.submitted_at, practice_sessions.score,
               practice_sessions.max_score, papers.year
        FROM practice_sessions
        LEFT JOIN papers ON papers.id = practice_sessions.paper_id
        WHERE practice_sessions.user_id IS ?
          AND (papers.profile_id = ? OR practice_sessions.paper_id IS NULL)
        ORDER BY practice_sessions.id DESC
        LIMIT 5
        """,
        (user_id, profile_id),
    ).fetchall()
    listening_audio_condition = listening_unit_has_audio_sql("units")
    unit_type_counts = {
        str(row["unit_type"]): int(row["count"])
        for row in connection.execute(
            f"""
            SELECT units.unit_type, COUNT(*) AS count
            FROM units
            JOIN papers ON papers.id = units.paper_id
            JOIN questions ON questions.unit_id = units.id
            WHERE papers.profile_id = ?
              AND papers.status = 'published'
              AND papers.deleted_at IS NULL
              AND (units.unit_type <> 'listening' OR ({listening_audio_condition}))
            GROUP BY units.unit_type
            """,
            (profile_id,),
        ).fetchall()
    }
    paper_type_counts = {
        str(row["unit_type"]): int(row["count"])
        for row in connection.execute(
            f"""
            SELECT units.unit_type, COUNT(DISTINCT papers.id) AS count
            FROM units
            JOIN papers ON papers.id = units.paper_id
            JOIN questions ON questions.unit_id = units.id
            WHERE papers.profile_id = ?
              AND papers.status = 'published'
              AND papers.deleted_at IS NULL
              AND (units.unit_type <> 'listening' OR ({listening_audio_condition}))
            GROUP BY units.unit_type
            """,
            (profile_id,),
        ).fetchall()
    }
    return {
        "active_profile": dict(profile) if profile else None,
        "paper_count": paper_count,
        "unit_count": unit_count,
        "question_count": question_count,
        "wrong_count": wrong_count,
        "frequent_count": frequent_count,
        "unit_type_counts": unit_type_counts,
        "paper_type_counts": paper_type_counts,
        "recent_sessions": [dict(row) for row in recent],
        # v2.9: 按当前级别针对性推荐
        "recommendations": _build_recommendations(connection, profile_id, user_id),
        # v2.18: 今日学习计划 + 考试倒计时
        "today_plan": _build_today_plan(connection, profile_id, dict(profile).get("name", "") if profile else "", user_id),
        "exam_countdown": _next_exam_dates(),
    }


def _next_exam_dates(today: date | None = None) -> list[dict]:
    """v2.18: 目标考试倒计时 (研究: 练题狗/好题库 备考节点功能)
    高考 6月7日; 四六级 6月/12月第2个周六; 考研 12月第4个周六
    """
    today = today or date.today()
    def nth_saturday(year: int, month: int, n: int) -> date:
        first = date(year, month, 1)
        # 第一个周六
        offset = (5 - first.weekday()) % 7
        return first + timedelta(days=offset + (n - 1) * 7)
    candidates = [
        ("高考", date(today.year, 6, 7)),
        ("四级", nth_saturday(today.year, 6, 2)),
        ("六级", nth_saturday(today.year, 6, 2)),
        ("考研", nth_saturday(today.year, 12, 4)),
    ]
    # 若当年 6 月已过, 补明年 6 月
    for name, d in list(candidates):
        if d < today:
            if name == "高考":
                candidates.append(("高考", date(today.year + 1, 6, 7)))
            elif name in ("四级", "六级"):
                candidates.append((name, nth_saturday(today.year + 1, 6, 2)))
            else:
                candidates.append((name, nth_saturday(today.year + 1, 12, 4)))
    out = []
    for name, d in candidates:
        if d < today: continue
        out.append({"name": name, "date": d.isoformat(), "days_left": (d - today).days})
    out.sort(key=lambda x: x["days_left"])
    return out


@router.get("/exam-countdown")
def exam_countdown(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """v2.18: 目标考试倒计时"""
    return {"exams": _next_exam_dates()}


def _build_today_plan(
    connection: sqlite3.Connection, profile_id: int, profile_name: str, user_id: int | None = None
) -> dict:
    """v2.18: 今日学习计划 (研究: 练题狗 AI智能推题 / 可栗口语 自动安排复习)
    v2.19: 研究强化 - 艾宾浩斯"每日=新学+复习" + 任务量/时间预估 + 完成度追踪
    """
    today = date.today().isoformat()
    # ① FSRS 今日待复习单词
    from ..services.fsrs_scheduler import get_due_today
    try:
        due = get_due_today(connection, user_id=user_id)
        due_count = len(due)
    except Exception:
        due_count = 0
    # ② 今日新词目标 (艾宾浩斯: 每日新学 + 复习; 默认 20/天)
    new_words = connection.execute(
        """SELECT COUNT(*) n FROM vocabulary_entries
           WHERE user_id IS ? AND study_status = 'new' AND (fsrs_due IS NULL OR fsrs_due <= ?)""",
        (user_id, today + "T23:59:59")).fetchone()["n"]
    new_target = min(20, max(0, new_words))
    # 今日已学新词 (learning_days 记录)
    learned_today = connection.execute(
        """SELECT COUNT(*) n FROM learning_days
           WHERE user_id IS ? AND day = ? AND activity_type IN ('vocabulary','word')""",
        (user_id, today)).fetchone()["n"]
    # ③ 薄弱题型: 能力雷达最低正确率题型
    weak_type = None
    ability = connection.execute(
        """
        SELECT u.unit_type, SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) correct,
               COUNT(*) total
        FROM practice_answers pa JOIN questions q ON q.id = pa.question_id
        JOIN units u ON u.id = q.unit_id JOIN papers p ON p.id = u.paper_id
        JOIN practice_sessions ps ON ps.id = pa.session_id
        WHERE ps.user_id IS ? AND p.profile_id = ? AND p.deleted_at IS NULL
        GROUP BY u.unit_type HAVING COUNT(*) >= 3
        ORDER BY (correct * 1.0 / COUNT(*)) ASC LIMIT 1
        """, (user_id, profile_id)).fetchone()
    if ability:
        weak_type = ability["unit_type"]
    # ④ 待复习错题 (错 >= 2 次)
    wrong = connection.execute(
        """SELECT COUNT(*) n FROM wrong_stats WHERE wrong_count >= 2 AND user_id IS ?
           AND question_id IN (SELECT id FROM questions WHERE unit_id IN
               (SELECT id FROM units WHERE paper_id IN
                   (SELECT id FROM papers WHERE profile_id = ? AND deleted_at IS NULL)))""",
        (user_id, profile_id)).fetchone()["n"]
    # 今日已做练习
    practiced_today = connection.execute(
        """SELECT COUNT(*) n FROM learning_days
           WHERE user_id IS ? AND day = ? AND activity_type IN ('practice','exam')""",
        (user_id, today)).fetchone()["n"]
    # ⑤ 今日推荐练习题型
    counts = connection.execute(
        """SELECT u.unit_type, COUNT(DISTINCT u.id) n FROM units u
           JOIN papers p ON p.id = u.paper_id
           WHERE p.profile_id = ? AND p.deleted_at IS NULL GROUP BY u.unit_type
           ORDER BY n DESC LIMIT 1""", (profile_id,)).fetchone()
    practice_type = counts["unit_type"] if counts else None
    practice_label = {"cloze": "完形/选词填空", "reading": "阅读理解",
                      "paragraph_matching": "长篇匹配/七选五", "part_b": "七选五/匹配"}.get(practice_type or "", "专项练习")
    # 时间预估 (研究: 刷题计划 任务量可调)
    words_min = max(5, due_count * 0.4)
    new_min = new_target * 0.5
    practice_min = {"cloze": 12, "reading": 15, "paragraph_matching": 15, "part_b": 12, "listening": 25}.get(practice_type or "", 12)
    wrong_min = min(20, max(5, wrong * 1.2))
    total_min = round(words_min + new_min + practice_min + wrong_min)
    return {
        "words_due": due_count,
        "new_words_target": new_target,
        "new_words_learned": learned_today,
        "weak_type": weak_type,
        "wrong_review": wrong,
        "practice_type": practice_type,
        "practice_label": practice_label,
        "total_minutes": total_min,
        "plan": [
            {"icon": "📖", "label": f"背 {new_target} 个新词 + 复习 {due_count} 个",
             "minutes": round(words_min + new_min), "done": due_count == 0 and learned_today >= new_target,
             "action": "words"},
            {"icon": "✏️", "label": f"{profile_name} · {practice_label}专项",
             "minutes": practice_min, "done": practiced_today > 0, "action": practice_type or "random"},
            {"icon": "📝", "label": f"重做 {wrong} 道高频错题",
             "minutes": wrong_min, "done": wrong == 0, "action": "wrong"},
        ],
    }


def _build_recommendations(connection: sqlite3.Connection, profile_id: int, user_id: int | None = None) -> dict:
    """v2.9: 按当前级别(题库)生成针对性推荐。
    规则推荐(无外部ML): 继续练习 / 本级别真题卷 / 本级别高频错题 / 薄弱单元
    """
    # ① 继续练习: 最近一次未完成的练习(该级别)
    continue_paper = connection.execute(
        """
        SELECT papers.id, papers.year, papers.subject, papers.title
        FROM practice_sessions
        JOIN papers ON papers.id = practice_sessions.paper_id
        WHERE practice_sessions.user_id IS ?
          AND papers.profile_id = ? AND papers.deleted_at IS NULL
          AND practice_sessions.status = 'in_progress'
        ORDER BY practice_sessions.id DESC LIMIT 1
        """,
        (user_id, profile_id),
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
        WHERE wrong_stats.user_id IS ?
          AND papers.profile_id = ? AND papers.deleted_at IS NULL
          AND wrong_stats.wrong_count > 0
        ORDER BY wrong_stats.wrong_count DESC, wrong_stats.last_wrong_at DESC
        LIMIT 3
        """,
        (user_id, profile_id),
    ).fetchall()

    # ④ 薄弱单元: 该级别错误率最高的单元(按错题数)
    weak_units = connection.execute(
        """
        SELECT units.id, units.title, COUNT(wrong_stats.question_id) AS wrong_n
        FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE wrong_stats.user_id IS ?
          AND papers.profile_id = ? AND papers.deleted_at IS NULL
          AND wrong_stats.wrong_count > 0
        GROUP BY units.id, units.title
        ORDER BY wrong_n DESC LIMIT 3
        """,
        (user_id, profile_id),
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
        JOIN practice_sessions ps ON ps.id = pa.session_id
        WHERE ps.user_id IS ? AND p.profile_id = ? AND p.deleted_at IS NULL
        GROUP BY u.unit_type
        ORDER BY (COUNT(*) * 1.0) DESC
        """,
        (user_id, profile_id),
    ).fetchall()

    # ⑥ 题型可用性: 该级别各 unit_type 单元数 (前端练习卡据此显示/灰化)
    unit_type_counts = {
        row["unit_type"]: row["n"]
        for row in connection.execute(
            """
            SELECT u.unit_type, COUNT(DISTINCT u.id) AS n
            FROM units u
            JOIN papers p ON p.id = u.paper_id
            WHERE p.profile_id = ? AND p.deleted_at IS NULL
            GROUP BY u.unit_type
            """,
            (profile_id,),
        ).fetchall()
    }

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
        # v2.12: 题型可用性 (练习卡动态显示/灰化)
        "unit_type_counts": unit_type_counts,
    }


@router.get("/streak")
def streak(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    from ..services.streak import get_streak, get_heatmap_data, get_monthly_summary, get_weekly_report
    return {
        "streak": get_streak(connection),
        "heatmap": get_heatmap_data(connection, days=180),
        "monthly": get_monthly_summary(connection),
        "weekly": get_weekly_report(connection),
    }


@router.get("/dashboard/streak", include_in_schema=False)
def streak_alias(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """兼容前端 /dashboard/streak 路径"""
    return streak(connection, user)
