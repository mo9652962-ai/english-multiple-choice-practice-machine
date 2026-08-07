"""学习报告 (v2.25) — 竞品好题库/练题狗核心: 数据可视化叙事
正确率趋势 + 题型统计 + 词汇进度 + 学习时长 + 智能建议
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from fastapi import APIRouter, Depends

from ..database import get_active_profile_id, get_db

router = APIRouter(prefix="/api/report", tags=["report"])


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False)


@router.get("")
def get_report(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """综合学习报告"""
    profile_id = get_active_profile_id(connection)
    profile = connection.execute(
        "SELECT id, name FROM question_bank_profiles WHERE id = ?", (profile_id,)
    ).fetchone()
    profile_name = profile["name"] if profile else "当前级别"

    today = date.today()
    days7 = (today - timedelta(days=6)).isoformat()
    days30 = (today - timedelta(days=29)).isoformat()

    # ① 正确率趋势 (近30天, 按天)
    trend = connection.execute(
        """SELECT date(pa.answered_at) day,
                  SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) correct,
                  COUNT(*) total
           FROM practice_answers pa
           WHERE date(pa.answered_at) >= ?
           GROUP BY date(pa.answered_at)
           ORDER BY day""",
        (days30,),
    ).fetchall()
    trend_data = []
    for row in trend:
        rate = round(row["correct"] / row["total"] * 100) if row["total"] else 0
        trend_data.append({"day": row["day"][5:], "rate": rate, "total": row["total"]})

    # ② 题型统计 (当前级别)
    by_type = connection.execute(
        """SELECT u.unit_type,
                  SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) correct,
                  COUNT(*) total
           FROM practice_answers pa
           JOIN questions q ON q.id = pa.question_id
           JOIN units u ON u.id = q.unit_id
           JOIN papers p ON p.id = u.paper_id
           WHERE p.profile_id = ? AND p.deleted_at IS NULL
           GROUP BY u.unit_type""",
        (profile_id,),
    ).fetchall()
    type_stats = []
    for row in by_type:
        rate = round(row["correct"] / row["total"] * 100) if row["total"] else 0
        label = {"cloze": "完形", "reading": "阅读", "paragraph_matching": "PartB",
                 "part_b": "PartB", "listening": "听力"}.get(row["unit_type"], row["unit_type"])
        type_stats.append({"type": row["unit_type"], "label": label,
                           "correct": row["correct"], "total": row["total"], "rate": rate})

    # ③ 词汇进度
    vocab = connection.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN study_status != 'new' THEN 1 ELSE 0 END) learned,
                  SUM(CASE WHEN study_status = 'mastered' THEN 1 ELSE 0 END) mastered
           FROM vocabulary_entries""",
    ).fetchone()

    # ④ 学习时长/活跃 (近7天)
    active7 = connection.execute(
        """SELECT COUNT(DISTINCT day) days, COUNT(*) activities
           FROM learning_days WHERE day >= ?""",
        (days7,),
    ).fetchone()

    # ⑤ 错题概况
    wrong_stats = connection.execute(
        """SELECT COUNT(*) n,
                  SUM(CASE WHEN wrong_count >= 2 THEN 1 ELSE 0 END) repeat_wrong
           FROM wrong_stats""",
    ).fetchone()

    # ⑥ 练习总量
    practice = connection.execute(
        """SELECT COUNT(*) sessions,
                  SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) submitted
           FROM practice_sessions""",
    ).fetchone()

    # ⑦ 建议 (规则: 薄弱题型 + 词汇缺口 + 连续性)
    suggestions = []
    if type_stats:
        weakest = min(type_stats, key=lambda x: x["rate"])
        if weakest["total"] >= 3 and weakest["rate"] < 60:
            suggestions.append(f"🔍 {weakest['label']}正确率仅 {weakest['rate']}%（{weakest['correct']}/{weakest['total']}），建议专项强化")
    if vocab and vocab["learned"] < 100:
        suggestions.append("📖 词汇量积累中，建议每天完成词书任务（新词 20 + 复习）")
    streak = connection.execute(
        "SELECT 1 FROM learning_days WHERE day = ? LIMIT 1",
        (today.isoformat(),),
    ).fetchone()
    if active7 and active7["days"] >= 5:
        suggestions.append(f"🔥 连续活跃 {active7['days']} 天，保持节奏！")
    elif streak:
        suggestions.append(f"⚡ 今天已开始学习，坚持打卡！")
    if wrong_stats and wrong_stats["repeat_wrong"]:
        suggestions.append(f"📝 {wrong_stats['repeat_wrong']} 道高频错题待重做，建议优先清理")

    return {
        "profile": profile_name,
        "trend": trend_data,
        "by_type": type_stats,
        "vocab": {"total": vocab["total"] if vocab else 0,
                  "learned": vocab["learned"] if vocab else 0,
                  "mastered": vocab["mastered"] if vocab else 0},
        "activity": {"active_days": active7["days"] if active7 else 0,
                     "activities": active7["activities"] if active7 else 0},
        "wrong": {"total": wrong_stats["n"] if wrong_stats else 0,
                  "repeat": wrong_stats["repeat_wrong"] if wrong_stats else 0},
        "practice": {"sessions": practice["sessions"] if practice else 0,
                     "submitted": practice["submitted"] if practice else 0},
        "suggestions": suggestions,
    }