"""学习排行榜 (v2.39, 多邻国/百词斩式) — 本周学习进度可视化
榜单维度: 本周答题数 / 正确率 / 词汇掌握 / 练习场次 (自我对照激励)
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from fastapi import APIRouter, Depends

from ..database import get_db

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
def get_leaderboard(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """本周学习数据 + 各维度进度"""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # 周一
    ws = week_start.isoformat()

    # 本周答题
    week_answered = connection.execute(
        "SELECT COUNT(*) FROM practice_answers WHERE substr(answered_at,1,10) >= ?",
        (ws,),
    ).fetchone()[0]
    week_correct = connection.execute(
        "SELECT COUNT(*) FROM practice_answers WHERE substr(answered_at,1,10) >= ? AND is_correct = 1",
        (ws,),
    ).fetchone()[0]
    week_rate = round(week_correct / week_answered * 100) if week_answered else 0

    # 本周场次 (按 started_at)
    week_sessions = connection.execute(
        "SELECT COUNT(*) FROM practice_sessions WHERE substr(started_at,1,10) >= ?",
        (ws,),
    ).fetchone()[0]

    # 本周新学词汇
    week_vocab = connection.execute(
        "SELECT COUNT(*) FROM vocabulary_entries WHERE substr(COALESCE(last_seen_at, updated_at),1,10) >= ? AND study_status != 'new'",
        (ws,),
    ).fetchone()[0]

    # 本周每日答题 (7 天柱状)
    days = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        n = connection.execute(
            "SELECT COUNT(*) FROM practice_answers WHERE substr(answered_at,1,10) = ?",
            (d,),
        ).fetchone()[0]
        days.append({"day": d, "count": n})

    # 连续打卡
    ld = {r[0] for r in connection.execute("SELECT DISTINCT day FROM learning_days").fetchall()}
    streak = 0
    d = today
    if d.isoformat() not in ld:
        d -= timedelta(days=1)
    while d.isoformat() in ld:
        streak += 1
        d -= timedelta(days=1)

    # 总览 (全周期)
    total_answered = connection.execute("SELECT COUNT(*) FROM practice_answers").fetchone()[0]
    total_correct = connection.execute(
        "SELECT COUNT(*) FROM practice_answers WHERE is_correct = 1").fetchone()[0]

    return {
        "week": {"start": ws, "end": today.isoformat()},
        "answered": week_answered,
        "correct": week_correct,
        "rate": week_rate,
        "sessions": week_sessions,
        "vocab_new": week_vocab,
        "streak": streak,
        "days": days,
        "total_answered": total_answered,
        "total_rate": round(total_correct / total_answered * 100) if total_answered else 0,
        "level": _level(week_answered, week_sessions),
    }


def _level(answered: int, sessions: int) -> dict:
    """段位 (游戏化: 按本周答题量)"""
    if answered >= 300:
        return {"name": "钻石", "icon": "💎", "color": "#4a6fa5"}
    if answered >= 150:
        return {"name": "黄金", "icon": "🥇", "color": "#a8842f"}
    if answered >= 60:
        return {"name": "白银", "icon": "🥈", "color": "#8a8a8a"}
    if sessions > 0:
        return {"name": "青铜", "icon": "🥉", "color": "#a05a2c"}
    return {"name": "未开始", "icon": "🌱", "color": "#787369"}
