"""学习日历 (v2.49) — 按月学习记录热力视图 (Focus-To-Do 日历视图)
数据源: learning_days (day + activity_type + count)
"""
from __future__ import annotations

import sqlite3
from datetime import date
from fastapi import APIRouter, Depends

from ..database import get_db

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("")
def calendar_month(year: int | None = None, month: int | None = None,
                   connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """指定月份学习记录 (默认当月). 返回每天活动数 + 活动类型分布"""
    today = date.today()
    y = year or today.year
    m = month or today.month
    start = f"{y:04d}-{m:02d}-01"
    if m == 12:
        end = f"{y + 1:04d}-01-01"
    else:
        end = f"{y:04d}-{m + 1:02d}-01"

    rows = connection.execute(
        """SELECT day, activity_type, COUNT(*) n FROM learning_days
           WHERE day >= ? AND day < ?
           GROUP BY day, activity_type ORDER BY day""",
        (start, end)).fetchall()

    # 每天聚合
    daily: dict[str, dict] = {}
    type_total: dict[str, int] = {}
    for day, atype, n in rows:
        d = daily.setdefault(day, {"day": day, "total": 0, "types": {}})
        d["total"] += n
        d["types"][atype] = d["types"].get(atype, 0) + n
        type_total[atype] = type_total.get(atype, 0) + n

    return {
        "year": y,
        "month": m,
        "days": list(daily.values()),
        "total_activities": sum(type_total.values()),
        "type_total": [{"type": k, "count": v} for k, v in sorted(type_total.items(), key=lambda x: -x[1])],
    }
