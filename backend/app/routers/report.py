"""学习报告 (v2.30) — 支持全部级别 + 单级别维度
正确率趋势 + 题型统计 + 词汇进度 + 学习时长 + 智能建议 + 级别汇总
v9.30 安全修复: practice_answers/wrong_stats/practice_sessions 按当前用户 user_id 过滤
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from fastapi import APIRouter, Depends

from ..database import get_active_profile_id, get_db
from .auth import maybe_require_user

router = APIRouter(prefix="/report", tags=["report"])

_LABEL = {"cloze": "完形", "reading": "阅读", "paragraph_matching": "PartB",
          "part_b": "PartB", "listening": "听力", "word_bank": "选词"}


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


def _profile_list(connection):
    return connection.execute(
        "SELECT id, name FROM question_bank_profiles ORDER BY id").fetchall()


def _type_stats(connection, profile_id=None, user_id=None):
    q = """SELECT u.unit_type,
                  SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) correct,
                  COUNT(*) total
           FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           JOIN questions q ON q.id = pa.question_id
           JOIN units u ON u.id = q.unit_id
           JOIN papers p ON p.id = u.paper_id
           WHERE ps.user_id IS ? AND p.deleted_at IS NULL"""
    args = [user_id]
    if profile_id:
        q += " AND p.profile_id = ?"
        args.append(profile_id)
    q += " GROUP BY u.unit_type"
    rows = connection.execute(q, args).fetchall()
    out = []
    for row in rows:
        rate = round(row["correct"] / row["total"] * 100) if row["total"] else 0
        out.append({"type": row["unit_type"], "label": _LABEL.get(row["unit_type"], row["unit_type"]),
                    "correct": row["correct"], "total": row["total"], "rate": rate})
    return out


def _trend(connection, profile_id=None, user_id=None):
    days30 = (date.today() - timedelta(days=29)).isoformat()
    q = """SELECT date(pa.answered_at) day,
                  SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) correct,
                  COUNT(*) total
           FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           JOIN questions q ON q.id = pa.question_id
           JOIN units u ON u.id = q.unit_id
           JOIN papers p ON p.id = u.paper_id
           WHERE ps.user_id IS ? AND date(pa.answered_at) >= ? AND p.deleted_at IS NULL"""
    args = [user_id, days30]
    if profile_id:
        q += " AND p.profile_id = ?"
        args.append(profile_id)
    q += " GROUP BY date(pa.answered_at) ORDER BY day"
    rows = connection.execute(q, args).fetchall()
    return [{"day": r["day"][5:], "rate": round(r["correct"] / r["total"] * 100) if r["total"] else 0,
             "total": r["total"]} for r in rows]


def _profile_summary(connection, user_id=None):
    """每级别汇总: 练习场次 + 正确率 + 错题数"""
    profiles = _profile_list(connection)
    out = []
    for p in profiles:
        sess = connection.execute(
            "SELECT COUNT(*) n FROM practice_sessions ps "
            "JOIN papers p2 ON p2.id = ps.paper_id WHERE ps.user_id IS ? AND p2.profile_id = ?",
            (user_id, p["id"])).fetchone()
        ans = connection.execute(
            """SELECT SUM(CASE WHEN pa.is_correct THEN 1 ELSE 0 END) correct, COUNT(*) total
               FROM practice_answers pa
               JOIN practice_sessions ps ON ps.id = pa.session_id
               JOIN questions q ON q.id = pa.question_id
               JOIN units u ON u.id = q.unit_id
               JOIN papers p2 ON p2.id = u.paper_id
               WHERE ps.user_id IS ? AND p2.profile_id = ? AND p2.deleted_at IS NULL""",
            (user_id, p["id"])).fetchone()
        wrong = connection.execute(
            """SELECT COUNT(*) n FROM wrong_stats ws
               JOIN questions q ON q.id = ws.question_id
               JOIN units u ON u.id = q.unit_id
               JOIN papers p2 ON p2.id = u.paper_id
               WHERE ws.user_id IS ? AND p2.profile_id = ? AND p2.deleted_at IS NULL""",
            (user_id, p["id"])).fetchone()
        rate = round(ans["correct"] / ans["total"] * 100) if ans["total"] else 0
        out.append({"profile_id": p["id"], "name": p["name"],
                    "sessions": sess["n"] if sess else 0,
                    "answered": ans["total"] if ans else 0,
                    "rate": rate, "wrong": wrong["n"] if wrong else 0})
    return out


@router.get("")
def get_report(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """综合学习报告: ?scope=all(默认,全级别) | current(当前级别)"""
    scope = "all"
    active_pid = get_active_profile_id(connection)
    user_id = _current_user_id(user)
    profile = connection.execute(
        "SELECT id, name FROM question_bank_profiles WHERE id = ?", (active_pid,)
    ).fetchone()
    active_name = profile["name"] if profile else "当前级别"

    today = date.today()
    days7 = (today - timedelta(days=6)).isoformat()

    # ① 全部级别趋势 (scope=all) 或当前级别
    trend = _trend(connection, None if scope == "all" else active_pid, user_id)

    # ② 题型统计 (全级别汇总 + 当前级别)
    by_type_all = _type_stats(connection, None, user_id)
    by_type_current = _type_stats(connection, active_pid, user_id)

    # ③ 每级别汇总
    by_profile = _profile_summary(connection, user_id)

    # ④ 词汇进度 (当前用户)
    vocab = connection.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN study_status != 'new' THEN 1 ELSE 0 END) learned,
                  SUM(CASE WHEN study_status = 'mastered' THEN 1 ELSE 0 END) mastered
           FROM vocabulary_entries WHERE user_id IS ?""",
        (user_id,)).fetchone()

    # ⑤ 活跃 (近7天, 全局表低危 — 挂认证已覆盖)
    active7 = connection.execute(
        "SELECT COUNT(DISTINCT day) days, COUNT(*) activities FROM learning_days WHERE day >= ?",
        (days7,)).fetchone()

    # ⑥ 错题概况 (当前用户)
    wrong_stats = connection.execute(
        """SELECT COUNT(*) n, SUM(CASE WHEN wrong_count >= 2 THEN 1 ELSE 0 END) repeat_wrong
           FROM wrong_stats WHERE user_id IS ?""",
        (user_id,)).fetchone()

    # ⑦ 练习总量 (当前用户)
    practice = connection.execute(
        "SELECT COUNT(*) sessions, SUM(CASE WHEN status = 'submitted' THEN 1 ELSE 0 END) submitted "
        "FROM practice_sessions WHERE user_id IS ?", (user_id,)).fetchone()

    # ⑦b v2.38: 近14天每日答题量趋势 (当前用户)
    answered_trend = []
    for i in range(13, -1, -1):
        day = (today - timedelta(days=i)).isoformat()
        n = connection.execute(
            """SELECT COUNT(*) FROM practice_answers pa
               JOIN practice_sessions ps ON ps.id = pa.session_id
               WHERE ps.user_id IS ? AND substr(pa.answered_at, 1, 10) = ?""",
            (user_id, day),
        ).fetchone()[0]
        answered_trend.append({"day": day, "count": n})

    # ⑦c v2.41: 本周 vs 上周对比 (当前用户)
    def _week_stats(ws: str, we: str) -> dict:
        n = connection.execute(
            """SELECT COUNT(*) FROM practice_answers pa
               JOIN practice_sessions ps ON ps.id = pa.session_id
               WHERE ps.user_id IS ? AND substr(pa.answered_at,1,10) >= ? AND substr(pa.answered_at,1,10) <= ?""",
            (user_id, ws, we)).fetchone()[0]
        c = connection.execute(
            """SELECT COUNT(*) FROM practice_answers pa
               JOIN practice_sessions ps ON ps.id = pa.session_id
               WHERE ps.user_id IS ? AND substr(pa.answered_at,1,10) >= ? AND substr(pa.answered_at,1,10) <= ? AND pa.is_correct = 1""",
            (user_id, ws, we)).fetchone()[0]
        v = connection.execute(
            """SELECT COUNT(*) FROM vocabulary_entries
               WHERE user_id IS ? AND substr(COALESCE(last_seen_at, updated_at),1,10) >= ? AND substr(COALESCE(last_seen_at, updated_at),1,10) <= ? AND study_status != 'new'""",
            (user_id, ws, we)).fetchone()[0]
        return {"answered": n, "correct": c, "rate": round(c / n * 100) if n else 0, "vocab": v}

    monday = today - timedelta(days=today.weekday())
    this_week = _week_stats(monday.isoformat(), today.isoformat())
    last_week = _week_stats((monday - timedelta(days=7)).isoformat(), (monday - timedelta(days=1)).isoformat())
    week_compare = {
        "this": this_week,
        "last": last_week,
        "answered_delta": this_week["answered"] - last_week["answered"],
        "rate_delta": this_week["rate"] - last_week["rate"],
        "vocab_delta": this_week["vocab"] - last_week["vocab"],
    }

    # ⑧ 建议 (基于全级别薄弱 + 词汇 + 活跃)
    suggestions = []
    if by_type_all:
        weakest = min(by_type_all, key=lambda x: x["rate"])
        if weakest["total"] >= 3 and weakest["rate"] < 60:
            suggestions.append(f"🔍 全级别 {weakest['label']} 正确率仅 {weakest['rate']}%（{weakest['correct']}/{weakest['total']}），建议专项强化")
    if by_profile:
        weakest_p = min(by_profile, key=lambda x: x["rate"])
        if weakest_p["answered"] >= 5 and weakest_p["rate"] < 70:
            suggestions.append(f"🎯 {weakest_p['name']} 正确率 {weakest_p['rate']}%（{weakest_p['answered']} 题），重点突破")
    if vocab and (vocab["learned"] or 0) < 100:
        suggestions.append("📖 词汇量积累中，建议每天完成词书任务（新词 20 + 复习）")
    if active7 and active7["days"] >= 5:
        suggestions.append(f"🔥 连续活跃 {active7['days']} 天，保持节奏！")
    if wrong_stats and wrong_stats["repeat_wrong"]:
        suggestions.append(f"📝 {wrong_stats['repeat_wrong']} 道高频错题待重做，建议优先清理")

    total_row = connection.execute(
        """SELECT COUNT(*) FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id WHERE ps.user_id IS ?""",
        (user_id,)).fetchone()[0]
    correct_row = connection.execute(
        """SELECT COUNT(*) FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           WHERE ps.user_id IS ? AND pa.is_correct = 1""",
        (user_id,)).fetchone()[0]

    return {
        "scope": scope,
        "active_profile": {"id": active_pid, "name": active_name},
        "profiles": [{"id": p["id"], "name": p["name"]} for p in _profile_list(connection)],
        "trend": trend,
        "by_type": by_type_all,
        "by_type_current": by_type_current,
        "by_profile": by_profile,
        "vocab": {"total": vocab["total"] if vocab else 0,
                  "learned": vocab["learned"] if vocab else 0,
                  "mastered": vocab["mastered"] if vocab else 0},
        "activity": {"active_days": active7["days"] if active7 else 0,
                     "activities": active7["activities"] if active7 else 0},
        "wrong": {"total": wrong_stats["n"] if wrong_stats else 0,
                  "repeat": wrong_stats["repeat_wrong"] if wrong_stats else 0},
        "practice": {"sessions": practice["sessions"] if practice else 0,
                     "submitted": practice["submitted"] if practice else 0},
        "answered_trend": answered_trend,
        "week_compare": week_compare,
        "total_answered": total_row,
        "total_rate": round(correct_row / total_row * 100) if total_row else 0,
        "suggestions": suggestions,
    }


@router.get("/heatmap")
def get_heatmap(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """v2.35: 学习热力图 (GitHub 风格) — 近 16 周每日活动次数"""
    today = date.today()
    start = today - timedelta(days=16 * 7 - 1)
    rows = connection.execute(
        """SELECT day, COUNT(*) AS n FROM learning_days
           WHERE day >= ? GROUP BY day""",
        (start.isoformat(),),
    ).fetchall()
    counts = {r["day"]: r["n"] for r in rows}
    cells = []
    for i in range(16 * 7):
        d = start + timedelta(days=i)
        iso = d.isoformat()
        cells.append({
            "date": iso,
            "count": counts.get(iso, 0),
            "level": min(4, int(counts.get(iso, 0) / 2)) if counts.get(iso) else 0,
        })
    # 对齐到周日开始 (GitHub 风格列=周)
    max_level = max((c["level"] for c in cells), default=0)
    return {"weeks": 16, "cells": cells, "max_level": max_level,
            "total": sum(counts.values())}
