# -*- coding: utf-8 -*-
"""AI 英语刷题机 — FSRS 间隔复习模块

基于 open-spaced-repetition/fsrs (pip install fsrs)
替代原有的固定间隔系统 (again=1d, hard=3d, mastered=7d)
FSRS 使用机器学习个性化调整每个人的记忆曲线

用法:
    from app.services.fsrs_scheduler import get_scheduler, review_card, get_due_count

架构:
    - 每个单词持有一个 FSRS Card 状态 (stability, difficulty, due date)
    - 用户评级映射: 不认识→Again, 有点印象→Hard, 已掌握→Good
    - 每日复习看板: get_due_count() 返回今日待复习数量
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from fsrs import Card, Rating, Scheduler, State

# 评分映射
RATING_MAP = {
    "again": Rating.Again,       # 不认识
    "hard": Rating.Hard,          # 有点印象
    "mastered": Rating.Good,      # 已掌握
}

# FSRS 参数（官方默认 recommended）
_scheduler = Scheduler()


def get_scheduler() -> Scheduler:
    """获取全局 FSRS scheduler 实例"""
    return _scheduler


def new_card() -> Card:
    """创建新卡（首次学习）"""
    return Card()


def review_card(card: Card, rating_key: str) -> tuple[Card, float, str]:
    """复习一张卡，返回 (新卡状态, 记忆可提取概率, 下次复习间隔描述)
    
    Args:
        card: FSRS Card 对象（从数据库反序列化）
        rating_key: "again" | "hard" | "mastered"
    
    Returns:
        (updated_card, retrievability, interval_desc)
    """
    rating = RATING_MAP.get(rating_key, Rating.Hard)
    # v2.75 防御: 旧数据 fsrs_state=0 非法, 重置为新卡 (fsrs State 枚举从 1 开始)
    try:
        if card.state is None or int(card.state) not in (1, 2, 3, 4):
            card.state = State.New
    except Exception:
        card.state = State.New
    new_card, review_log = _scheduler.review_card(card, rating)
    
    # 计算记忆可提取概率
    retrievability = _scheduler.get_card_retrievability(new_card)
    
    # 生成人类可读的间隔描述
    delta = new_card.due - datetime.now(timezone.utc)
    days = delta.days
    if days < 1:
        hours = delta.seconds // 3600
        desc = f"{hours} 小时后"
    elif days == 1:
        desc = "明天"
    elif days < 7:
        desc = f"{days} 天后"
    elif days < 30:
        desc = f"{days // 7} 周后"
    else:
        desc = f"{days // 30} 个月后"
    
    return new_card, retrievability, desc


def card_from_db(row: dict) -> Card:
    """从数据库行反序列化 FSRS Card"""
    card = Card()
    if row.get("fsrs_due"):
        from datetime import datetime
        card.due = datetime.fromisoformat(row["fsrs_due"])
    if row.get("fsrs_stability") is not None:
        card.stability = float(row["fsrs_stability"])
    if row.get("fsrs_difficulty") is not None:
        card.difficulty = float(row["fsrs_difficulty"])
    if row.get("fsrs_state") is not None:
        card.state = int(row["fsrs_state"])
    if row.get("fsrs_step") is not None:
        card.step = int(row["fsrs_step"])
    if row.get("fsrs_last_review") is not None:
        card.last_review = datetime.fromisoformat(row["fsrs_last_review"])
    return card


def card_to_dict(card: Card) -> dict:
    """序列化 FSRS Card 为数据库可存储的字典"""
    return {
        "fsrs_due": card.due.isoformat() if card.due else None,
        "fsrs_stability": card.stability,
        "fsrs_difficulty": card.difficulty,
        "fsrs_state": card.state.value if hasattr(card.state, 'value') else int(card.state),
        "fsrs_step": card.step,
        "fsrs_last_review": card.last_review.isoformat() if card.last_review else None,
    }


def get_due_count(connection: sqlite3.Connection) -> int:
    """获取今日待复习单词数"""
    now = datetime.now(timezone.utc).isoformat()
    row = connection.execute(
        """SELECT COUNT(*) FROM vocabulary_entries
           WHERE fsrs_due IS NOT NULL
             AND fsrs_due <= ?
             AND study_status != 'mastered'""",
        (now,),
    ).fetchone()
    return row[0] if row else 0


def get_due_today(connection: sqlite3.Connection, limit: int = 20) -> list[dict]:
    """获取今日待复习单词列表（按 retrievability 最低优先）"""
    now = datetime.now(timezone.utc).isoformat()
    rows = connection.execute(
        """SELECT id, term, encounter_count, study_status,
                  fsrs_due, fsrs_stability, fsrs_difficulty,
                  common_meaning, contextual_meaning
           FROM vocabulary_entries
           WHERE fsrs_due IS NOT NULL
             AND fsrs_due <= ?
           ORDER BY fsrs_due ASC
           LIMIT ?""",
        (now, limit),
    ).fetchall()
    result = []
    for row in rows:
        entry = dict(row)
        if entry["fsrs_due"]:
            due = datetime.fromisoformat(entry["fsrs_due"])
            entry["due_ago"] = str(datetime.now(timezone.utc) - due).split(".")[0]
        result.append(entry)
    return result
