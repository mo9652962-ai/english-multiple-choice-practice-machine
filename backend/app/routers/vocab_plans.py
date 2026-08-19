"""单词分级背诵计划 (v2.22) — 墨墨/扇贝式词书 + 每日任务 + 进度
词书: 四级核心700 / 六级核心600 / 考研高频1580 / 高中核心800 / 热点词
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from fastapi import APIRouter, Depends

from ..database import get_db

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])

# 词书定义: name, category_pattern, target_count, desc
WORD_BOOKS = [
    {"key": "cet4_core", "name": "四级核心词", "pattern": "四级·高频%", "target": 700,
     "desc": "四级真题高频核心词（考频排序）", "icon": "📘"},
    {"key": "cet6_core", "name": "六级核心词", "pattern": "六级·高频%", "target": 600,
     "desc": "六级真题高频核心词", "icon": "📙"},
    {"key": "kaoyan_freq", "name": "考研高频词", "pattern": "考研%高频%", "target": 1580,
     "desc": "考研真题高频词（kajweb 考频排序）", "icon": "🎓"},
    {"key": "gaokao_core", "name": "高中核心词", "pattern": "高中%", "target": 800,
     "desc": "高考核心词汇", "icon": "🏫"},
    {"key": "hot_words", "name": "真题热点词", "pattern": "%热点%", "target": 300,
     "desc": "近两年真题高频出现词（AI 释义）", "icon": "🔥"},
]


@router.get("/plans")
def get_plans(connection: sqlite3.Connection = Depends(get_db)):
    """词书列表 + 每本进度"""
    today = date.today().isoformat()
    plans = []
    for book in WORD_BOOKS:
        total = connection.execute(
            "SELECT COUNT(*) FROM vocabulary_entries WHERE category LIKE ?",
            (book["pattern"],)).fetchone()[0]
        learned = connection.execute(
            "SELECT COUNT(*) FROM vocabulary_entries WHERE category LIKE ? AND study_status != 'new'",
            (book["pattern"],)).fetchone()[0]
        # 今日学这本词书的词数 (learning_days 按 category 统计不可行, 用 fsrs_last_review 估算)
        today_learned = connection.execute(
            """SELECT COUNT(*) FROM vocabulary_entries
               WHERE category LIKE ? AND date(fsrs_last_review) = ?""",
            (book["pattern"], today)).fetchone()[0]
        plans.append({
            "key": book["key"], "name": book["name"], "desc": book["desc"], "icon": book["icon"],
            "target": min(book["target"], total), "total": total,
            "learned": learned, "today_learned": today_learned,
            "progress": min(100, round(learned / book["target"] * 100)) if book["target"] else 0,
        })
    return {"plans": plans}


@router.get("/plans/{plan_key}/daily")
def get_daily_task(plan_key: str, connection: sqlite3.Connection = Depends(get_db)):
    """某词书今日任务: 新词 N 个 + FSRS 到期复习"""
    book = next((b for b in WORD_BOOKS if b["key"] == plan_key), None)
    if not book:
        return {"error": "unknown plan"}
    today = date.today().isoformat()
    # 新词: 优先 study_status='new' 且无 fsrs 记录
    new_words = connection.execute(
        """SELECT id, term, phonetic, common_meaning, contextual_meaning, part_of_speech
           FROM vocabulary_entries
           WHERE category LIKE ? AND study_status = 'new'
           ORDER BY id LIMIT 20""",
        (book["pattern"],)).fetchall()
    # 到期复习: fsrs_due <= today
    due_words = connection.execute(
        """SELECT id, term, phonetic, common_meaning, contextual_meaning, part_of_speech
           FROM vocabulary_entries
           WHERE category LIKE ? AND fsrs_due IS NOT NULL AND fsrs_due <= ? AND fsrs_due != ''
           ORDER BY fsrs_due LIMIT 50""",
        (book["pattern"], today + "T23:59:59")).fetchall()
    # 组合: 新词优先, 不足补复习
    all_words = [dict(w) for w in new_words] + [dict(w) for w in due_words]
    # v2.22 修复: 若整本词书都无进度, 回退推荐未学词 (防止空任务)
    if not all_words:
        all_words = [dict(w) for w in connection.execute(
            """SELECT id, term, phonetic, common_meaning, contextual_meaning, part_of_speech, study_status
               FROM vocabulary_entries
               WHERE category LIKE ? AND study_status = 'new'
               ORDER BY id LIMIT 20""",
            (book["pattern"],)).fetchall()]
        if not all_words:
            all_words = [dict(w) for w in connection.execute(
                """SELECT id, term, phonetic, common_meaning, contextual_meaning, part_of_speech, study_status
                   FROM vocabulary_entries
                   WHERE category LIKE ?
                   ORDER BY id LIMIT 20""",
                (book["pattern"],)).fetchall()]
    return {
        "plan": book["name"],
        "new_count": len([w for w in all_words if w["study_status"] == "new"]),
        "due_count": len([w for w in all_words if w["study_status"] != "new"]),
        "daily_target": 20,
        "words": all_words,
    }