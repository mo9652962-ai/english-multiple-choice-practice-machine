"""学习排行榜 (v2.39, 多邻国/百词斩式) — 本周学习进度可视化
榜单维度: 本周答题数 / 正确率 / 词汇掌握 / 练习场次 (自我对照激励)

多用户隔离: 全部统计按当前登录用户过滤（EPM_AUTH=1）；
practice_answers 无 user_id 列，经 session_id 关联 practice_sessions.user_id。
EPM_AUTH=0 时按 user_id IS NULL 兼容单用户旧数据。
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from fastapi import APIRouter, Depends

from ..database import get_db
from .auth import maybe_require_user

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("")
def get_leaderboard(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """本周学习数据 + 各维度进度（按当前用户隔离）"""
    user_id = user["id"] if user else None
    today = date.today()
    week_start = today - timedelta(days=today.weekday())  # 周一
    ws = week_start.isoformat()

    # 本周答题（经 session 关联到用户）
    week_answered = connection.execute(
        """SELECT COUNT(*) FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           WHERE ps.user_id IS ? AND substr(pa.answered_at,1,10) >= ?""",
        (user_id, ws),
    ).fetchone()[0]
    week_correct = connection.execute(
        """SELECT COUNT(*) FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           WHERE ps.user_id IS ? AND substr(pa.answered_at,1,10) >= ? AND pa.is_correct = 1""",
        (user_id, ws),
    ).fetchone()[0]
    week_rate = round(week_correct / week_answered * 100) if week_answered else 0

    # 本周场次 (按 started_at)
    week_sessions = connection.execute(
        "SELECT COUNT(*) FROM practice_sessions WHERE user_id IS ? AND substr(started_at,1,10) >= ?",
        (user_id, ws),
    ).fetchone()[0]

    # 本周新学词汇
    week_vocab = connection.execute(
        """SELECT COUNT(*) FROM vocabulary_entries
           WHERE user_id IS ? AND substr(COALESCE(last_seen_at, updated_at),1,10) >= ?
             AND study_status != 'new'""",
        (user_id, ws),
    ).fetchone()[0]

    # 本周每日答题 (7 天柱状)
    days = []
    for i in range(6, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        n = connection.execute(
            """SELECT COUNT(*) FROM practice_answers pa
               JOIN practice_sessions ps ON ps.id = pa.session_id
               WHERE ps.user_id IS ? AND substr(pa.answered_at,1,10) = ?""",
            (user_id, d),
        ).fetchone()[0]
        days.append({"day": d, "count": n})

    # 连续打卡
    ld = {r[0] for r in connection.execute(
        "SELECT DISTINCT day FROM learning_days WHERE user_id IS ?", (user_id,)
    ).fetchall()}
    streak = 0
    d = today
    if d.isoformat() not in ld:
        d -= timedelta(days=1)
    while d.isoformat() in ld:
        streak += 1
        d -= timedelta(days=1)

    # 总览 (全周期)
    total_answered = connection.execute(
        """SELECT COUNT(*) FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           WHERE ps.user_id IS ?""",
        (user_id,),
    ).fetchone()[0]
    total_correct = connection.execute(
        """SELECT COUNT(*) FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           WHERE ps.user_id IS ? AND pa.is_correct = 1""",
        (user_id,),
    ).fetchone()[0]

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
