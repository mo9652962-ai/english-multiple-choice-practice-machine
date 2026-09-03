# -*- coding: utf-8 -*-
"""AI 英语刷题机 — 学习连续打卡系统 (streak)

参考 (2026-08 研究):
  - Duolingo: streak 机制使 DAU +36%, churn 47%→28%
  - Lingoat 研究: streak 应绑定 retrieval practice / spaced repetition，
    而非"打开即打卡"——避免"为保 streak 而划水"
  - vue3-calendar-heatmap: GitHub 风格贡献日历热力图

设计:
  - 每天有任意"有效学习行为"即记录 1 次:
    ① 提交练习 (practice submit)
    ② 复习单词 (vocabulary review)
    ③ AI 错题分析 / 相似题生成
  - streak = 从今天起往前连续有学习行为的天数
  - 热力图数据: 最近 180 天每天的学习行为次数
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta

# 有效学习行为表 (可以扩展)
LEARNING_ACTIVITY_TYPES = {
    "practice_submit": "刷题",
    "vocab_review": "背单词",
    "ai_analyze": "AI 错题分析",
    "ai_article": "AI 文章",
    "similar_questions": "相似题练习",
}


def record_activity(
    connection: sqlite3.Connection,
    activity_type: str,
    detail: str = "",
    user_id: int | None = None,
) -> None:
    """记录一次学习行为（每天每类型只记一次，防刷；按用户隔离）"""
    if activity_type not in LEARNING_ACTIVITY_TYPES:
        activity_type = "practice_submit"
    today = date.today().isoformat()
    # 当天该类型已记录则跳过
    exists = connection.execute(
        """SELECT 1 FROM learning_days
           WHERE user_id IS ? AND day = ? AND activity_type = ?""",
        (user_id, today, activity_type),
    ).fetchone()
    if exists:
        return
    connection.execute(
        """INSERT INTO learning_days (user_id, day, activity_type, detail)
           VALUES (?, ?, ?, ?)""",
        (user_id, today, activity_type, detail[:200]),
    )
    connection.commit()


def get_streak(connection: sqlite3.Connection) -> dict:
    """计算当前连续打卡天数
    
    Returns:
        {"current": N, "best": N, "today_active": bool}
    """
    # 今天是否有行为
    today = date.today().isoformat()
    today_active = connection.execute(
        "SELECT 1 FROM learning_days WHERE day = ? LIMIT 1", (today,)
    ).fetchone() is not None

    # 计算连续天数（从今天或昨天开始）
    days = {
        row["day"]
        for row in connection.execute(
            "SELECT DISTINCT day FROM learning_days"
        ).fetchall()
    }

    current = 0
    cursor = date.today() if today_active else date.today() - timedelta(days=1)
    # 如果今天没学习，从昨天开始算（今天还没学完不算断）
    while cursor.isoformat() in days:
        current += 1
        cursor -= timedelta(days=1)

    # 历史最长
    best = 0
    sorted_days = sorted(days)
    run = 0
    prev = None
    for d in sorted_days:
        d_date = date.fromisoformat(d)
        if prev is not None and (d_date - prev).days == 1:
            run += 1
        else:
            run = 1
        best = max(best, run)
        prev = d_date

    return {
        "current": current,
        "best": best,
        "today_active": today_active,
    }


def get_heatmap_data(connection: sqlite3.Connection, days: int = 180) -> list[dict]:
    """获取最近 N 天的每日学习行为统计（热力图数据）
    
    Returns:
        [{"date": "2026-02-01", "count": 3}, ...]
    """
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    rows = connection.execute(
        """SELECT day, COUNT(*) AS count
           FROM learning_days
           WHERE day >= ?
           GROUP BY day
           ORDER BY day""",
        (start,),
    ).fetchall()
    return [{"date": r["day"], "count": r["count"]} for r in rows]


def get_monthly_summary(connection: sqlite3.Connection) -> dict:
    """本月学习概览"""
    month_start = date.today().replace(day=1).isoformat()
    rows = connection.execute(
        """SELECT activity_type, COUNT(*) AS count
           FROM learning_days
           WHERE day >= ?
           GROUP BY activity_type
           ORDER BY count DESC""",
        (month_start,),
    ).fetchall()
    total = sum(r["count"] for r in rows)
    return {
        "month": date.today().strftime("%Y-%m"),
        "total_activities": total,
        "active_days": len(
            connection.execute(
                "SELECT DISTINCT day FROM learning_days WHERE day >= ?",
                (month_start,),
            ).fetchall()
        ),
        "breakdown": [
            {"type": r["activity_type"], "label": LEARNING_ACTIVITY_TYPES.get(r["activity_type"], r["activity_type"]), "count": r["count"]}
            for r in rows
        ],
    }


def get_weekly_report(connection: sqlite3.Connection) -> dict:
    """最近 7 天学习周报
    
    借鉴: Way of Life "skip 而非 miss" 设计——强调进步而非惩罚
    """
    week_start = (date.today() - timedelta(days=6)).isoformat()
    today = date.today().isoformat()

    # 每天的活动类型
    daily = connection.execute(
        """SELECT day, activity_type, COUNT(*) AS count
           FROM learning_days
           WHERE day >= ?
           GROUP BY day, activity_type
           ORDER BY day""",
        (week_start,),
    ).fetchall()

    by_day: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for row in daily:
        by_day[row["day"]] = by_day.get(row["day"], 0) + row["count"]
        by_type[row["activity_type"]] = by_type.get(row["activity_type"], 0) + row["count"]

    active_days = len(by_day)
    total_activities = sum(by_day.values())

    # 连续日（计算最近连续天数，今天未学不算断）
    streak_days = 0
    cursor = date.today()
    if today not in by_day:
        cursor = date.today() - timedelta(days=1)
    while cursor.isoformat() in by_day:
        streak_days += 1
        cursor -= timedelta(days=1)

    # 每日明细
    detail = []
    for i in range(7):
        d = (date.today() - timedelta(days=6 - i)).isoformat()
        detail.append({
            "date": d,
            "active": d in by_day,
            "count": by_day.get(d, 0),
        })

    return {
        "period": f"{week_start} ~ {today}",
        "active_days": active_days,
        "total_activities": total_activities,
        "streak_days": streak_days,
        "breakdown": [
            {"type": t, "label": LEARNING_ACTIVITY_TYPES.get(t, t), "count": c}
            for t, c in sorted(by_type.items(), key=lambda x: -x[1])
        ],
        "daily": detail,
    }
