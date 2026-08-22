"""成就徽章系统 (v2.29) — 游戏化激励 (多邻国/百词斩式)
规则引擎: 检查用户数据 → 授予徽章 → 前端展示
v9.30 安全修复: 全部检查函数按当前用户 user_id 过滤（多用户隔离）
"""
from __future__ import annotations

import sqlite3
from datetime import date
from fastapi import APIRouter, Depends

from ..database import get_active_profile_id, get_db
from .auth import maybe_require_user

router = APIRouter(prefix="/achievements", tags=["achievements"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None

# 徽章定义: key, name, icon, desc, 检查函数
BADGES = []


def badge(key, name, icon, desc, check):
    BADGES.append({"key": key, "name": name, "icon": icon, "desc": desc, "check": check})


def _init_table(connection):
    connection.execute("""CREATE TABLE IF NOT EXISTS user_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        badge_key TEXT NOT NULL UNIQUE,
        earned_at TEXT NOT NULL,
        progress INTEGER DEFAULT 0,
        target INTEGER DEFAULT 0
    )""")


# ── 徽章规则（v9.30: 全部按 user_id 过滤）──
def _practice_count(connection, user_id=None):
    r = connection.execute(
        "SELECT COUNT(*) n FROM practice_sessions WHERE user_id IS ?", (user_id,)
    ).fetchone()
    return r["n"]


def _streak(connection, profile_id, user_id=None):
    today = date.today().isoformat()
    days = {r["day"] for r in connection.execute(
        "SELECT DISTINCT day FROM learning_days WHERE day >= date('now', '-60 days')"
    ).fetchall()}
    # 从今天或昨天往前数
    from datetime import timedelta
    d = date.today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def _vocab_learned(connection, user_id=None):
    r = connection.execute(
        "SELECT COUNT(*) n FROM vocabulary_entries WHERE user_id IS ? AND study_status != 'new'",
        (user_id,),
    ).fetchone()
    return r["n"]


def _vocab_mastered(connection, user_id=None):
    r = connection.execute(
        "SELECT COUNT(*) n FROM vocabulary_entries WHERE user_id IS ? AND study_status = 'mastered'",
        (user_id,),
    ).fetchone()
    return r["n"]


def _wrong_redone(connection, user_id=None):
    r = connection.execute(
        "SELECT SUM(attempt_count) n FROM wrong_stats WHERE user_id IS ? AND attempt_count > 1",
        (user_id,),
    ).fetchone()
    return r["n"] or 0


def _exam_done(connection, user_id=None):
    r = connection.execute(
        "SELECT COUNT(*) n FROM exam_sessions WHERE user_id IS ? AND status = 'submitted'",
        (user_id,),
    ).fetchone()
    return r["n"]


def _paper_done(connection, user_id=None):
    r = connection.execute(
        """SELECT COUNT(DISTINCT ps.id) n FROM practice_unit_submissions pus
           JOIN practice_sessions ps ON ps.id = pus.session_id
           WHERE ps.user_id IS ?""",
        (user_id,),
    ).fetchone()
    return r["n"]


def _correct_count(connection, user_id=None):
    r = connection.execute(
        """SELECT COUNT(*) n FROM practice_answers pa
           JOIN practice_sessions ps ON ps.id = pa.session_id
           WHERE ps.user_id IS ? AND pa.is_correct = 1""",
        (user_id,),
    ).fetchone()
    return r["n"] or 0


def _wrong_redone_50(connection, user_id=None):
    return _wrong_redone(connection, user_id)


def _paper_done_100(connection, user_id=None):
    return _paper_done(connection, user_id)


badge("first_practice", "初次练习", "🎯", "完成你的第一场练习", lambda c, p, u: (_practice_count(c, u), 1))
badge("streak_7", "七日坚持", "🔥", "连续打卡 7 天", lambda c, p, u: (_streak(c, p, u), 7))
badge("streak_30", "月度之星", "🔥", "连续打卡 30 天", lambda c, p, u: (_streak(c, p, u), 30))
badge("vocab_100", "词汇入门", "📚", "掌握 100 个单词", lambda c, p, u: (_vocab_learned(c, u), 100))
badge("vocab_1000", "词汇大师", "🏛️", "掌握 1000 个单词", lambda c, p, u: (_vocab_learned(c, u), 1000))
badge("vocab_master_500", "词汇精研", "🎖️", "精研 500 个单词", lambda c, p, u: (_vocab_mastered(c, u), 500))
badge("wrong_10", "错题清道夫", "🧹", "重做 10 道错题", lambda c, p, u: (_wrong_redone(c, u), 10))
badge("exam_1", "模考初体验", "✍️", "完成第一场模拟考试", lambda c, p, u: (_exam_done(c, u), 1))
badge("paper_5", "刷题新秀", "📝", "完成 5 套练习", lambda c, p, u: (_paper_done(c, u), 5))
badge("paper_30", "刷题达人", "🏆", "完成 30 套练习", lambda c, p, u: (_paper_done(c, u), 30))
badge("correct_500", "答题高手", "💯", "累计答对 500 题", lambda c, p, u: (_correct_count(c, u), 500))
badge("streak_14", "半月坚持", "🌙", "连续打卡 14 天", lambda c, p, u: (_streak(c, p, u), 14))
badge("paper_100", "刷题王者", "👑", "完成 100 套练习", lambda c, p, u: (_paper_done_100(c, u), 100))
badge("wrong_50", "错题克星", "🛡️", "重做 50 道错题", lambda c, p, u: (_wrong_redone_50(c, u), 50))


@router.get("")
def get_achievements(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
):
    """徽章列表 + 进度 + 是否已获得"""
    _init_table(connection)
    profile_id = get_active_profile_id(connection)
    user_id = _current_user_id(user)
    earned = {r["badge_key"]: r for r in connection.execute(
        "SELECT * FROM user_achievements").fetchall()}
    items = []
    for b in BADGES:
        try:
            current, target = b["check"](connection, profile_id, user_id)
        except Exception:
            current, target = 0, b.get("target", 1)
        items.append({
            "key": b["key"], "name": b["name"], "icon": b["icon"], "desc": b["desc"],
            "earned": b["key"] in earned,
            "earned_at": earned[b["key"]]["earned_at"] if b["key"] in earned else None,
            "progress": min(current, target), "target": target,
            "percent": round(min(current, target) / target * 100) if target else 0,
        })
    earned_count = len(earned)
    return {"badges": items, "earned_count": earned_count, "total": len(BADGES)}


@router.post("/check")
def check_achievements(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
):
    """检查并授予新徽章 (提交练习/学习行为后调用)"""
    _init_table(connection)
    profile_id = get_active_profile_id(connection)
    user_id = _current_user_id(user)
    now = date.today().isoformat()
    new_earned = []
    for b in BADGES:
        try:
            current, target = b["check"](connection, profile_id, user_id)
        except Exception:
            continue
        exists = connection.execute(
            "SELECT 1 FROM user_achievements WHERE badge_key = ?", (b["key"],)).fetchone()
        if current >= target and not exists:
            connection.execute(
                "INSERT INTO user_achievements (badge_key, earned_at, progress, target) VALUES (?,?,?,?)",
                (b["key"], now, min(current, target), target))
            new_earned.append(b)
    connection.commit()
    return {"new_badges": new_earned, "count": len(new_earned)}
