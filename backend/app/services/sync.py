"""AI 英语刷题机 — 跨端增量同步服务 (Local-First Sync Engine)
支持 Web / Electron / Android 多端离线做题、双向增量对账与 FSRS 复习进度无缝同步。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any


def _parse_json(val: Any, default: Any) -> Any:
    if not val:
        return default
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(str(val))
    except (json.JSONDecodeError, TypeError):
        return default


def exchange_sync_data(
    connection: sqlite3.Connection,
    user_id: int | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """双向原子对账：
    1. 接收客户端推送的增量数据 (Push) 并安全合并 (LWW + Union)
    2. 拉取云端当前最新学习档案 (Pull) 返回客户端
    """
    now_iso = datetime.now().isoformat()
    push_data = payload.get("push") or {}

    pushed_counts = {
        "learning_days": 0,
        "wrong_stats": 0,
        "fsrs_records": 0,
        "collections": 0,
    }

    # ─────────────────────────────────────────────────────────────
    # 1. Push 合并阶段
    # ─────────────────────────────────────────────────────────────

    # (a) 打卡记录合并 (learning_days - 集合并集)
    pushed_days = push_data.get("learning_days") or []
    for item in pushed_days:
        day = item.get("day")
        act = item.get("activity_type") or "practice"
        detail = item.get("detail") or ""
        if day:
            connection.execute(
                """
                INSERT OR IGNORE INTO learning_days (user_id, day, activity_type, detail)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, day, act, detail),
            )
            pushed_counts["learning_days"] += 1

    # (b) 错题本统计合并 (wrong_stats - 偏序最大值合并)
    pushed_wrongs = push_data.get("wrong_stats") or []
    for w in pushed_wrongs:
        qid = w.get("question_id")
        if not qid:
            continue
        # 校验外键有效性，避免未入库题目导致整体同步中断
        if not connection.execute("SELECT 1 FROM questions WHERE id = ?", (qid,)).fetchone():
            continue
        c_attempt = int(w.get("attempt_count") or 0)
        c_wrong = int(w.get("wrong_count") or 0)
        c_last_wrong = w.get("last_wrong_at")
        c_last_attempt = w.get("last_attempt_at")
        c_note = (w.get("note") or "").strip()
        c_results = _parse_json(w.get("recent_results"), [])

        existing = connection.execute(
            "SELECT * FROM wrong_stats WHERE user_id IS ? AND question_id = ?",
            (user_id, qid),
        ).fetchone()

        if existing:
            m_attempt = max(existing["attempt_count"], c_attempt)
            m_wrong = max(existing["wrong_count"], c_wrong)
            m_last_wrong = max(filter(None, [existing["last_wrong_at"], c_last_wrong]), default=None)
            m_last_attempt = max(filter(None, [existing["last_attempt_at"], c_last_attempt]), default=None)
            m_note = c_note if c_note else existing["note"]

            connection.execute(
                """
                UPDATE wrong_stats
                SET attempt_count = ?, wrong_count = ?, last_wrong_at = ?, last_attempt_at = ?, note = ?
                WHERE user_id IS ? AND question_id = ?
                """,
                (m_attempt, m_wrong, m_last_wrong, m_last_attempt, m_note, user_id, qid),
            )
        else:
            connection.execute(
                """
                INSERT INTO wrong_stats
                    (user_id, question_id, attempt_count, wrong_count, last_wrong_at, last_attempt_at, note, recent_results)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, qid, c_attempt, c_wrong, c_last_wrong, c_last_attempt, c_note, json.dumps(c_results)),
            )
        pushed_counts["wrong_stats"] += 1

    # (c) FSRS 间隔复习进度合并 (spaced_repetition_records - 最新复习时间胜出)
    pushed_fsrs = push_data.get("fsrs_records") or []
    for f in pushed_fsrs:
        qid = f.get("question_id")
        if not qid:
            continue
        if not connection.execute("SELECT 1 FROM questions WHERE id = ?", (qid,)).fetchone():
            continue
        due_date = f.get("due_date") or f.get("fsrs_due") or now_iso
        fsrs_due = f.get("fsrs_due") or due_date
        stability = float(f.get("fsrs_stability") or 0.0)
        difficulty = float(f.get("fsrs_difficulty") or 0.0)
        state = int(f.get("fsrs_state") or 0)
        step = int(f.get("fsrs_step") or 0)
        last_review = f.get("fsrs_last_review") or f.get("review_date") or now_iso
        interval_days = int(f.get("interval_days") or 1)
        ease_factor = float(f.get("ease_factor") or 2.5)

        existing = connection.execute(
            "SELECT * FROM spaced_repetition_records WHERE user_id IS ? AND question_id = ?",
            (user_id, qid),
        ).fetchone()

        if existing:
            # 谁最近复习过就以谁的状态为准
            ex_rev = existing["fsrs_last_review"] or existing["review_date"] or ""
            if last_review >= ex_rev:
                connection.execute(
                    """
                    UPDATE spaced_repetition_records
                    SET interval_days = ?, ease_factor = ?, review_date = ?, due_date = ?,
                        fsrs_due = ?, fsrs_stability = ?, fsrs_difficulty = ?, fsrs_state = ?,
                        fsrs_step = ?, fsrs_last_review = ?
                    WHERE user_id IS ? AND question_id = ?
                    """,
                    (
                        interval_days, ease_factor, last_review, due_date,
                        fsrs_due, stability, difficulty, state, step, last_review,
                        user_id, qid,
                    ),
                )
        else:
            connection.execute(
                """
                INSERT INTO spaced_repetition_records
                    (user_id, question_id, interval_days, ease_factor, review_date, due_date,
                     fsrs_due, fsrs_stability, fsrs_difficulty, fsrs_state, fsrs_step, fsrs_last_review)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id, qid, interval_days, ease_factor, last_review, due_date,
                    fsrs_due, stability, difficulty, state, step, last_review,
                ),
            )
        pushed_counts["fsrs_records"] += 1

    # (d) 精讲典藏合并 (explain_collections)
    pushed_colls = push_data.get("collections") or []
    for c in pushed_colls:
        qid = c.get("question_id")
        content = c.get("content")
        if qid and content:
            if not connection.execute("SELECT 1 FROM questions WHERE id = ?", (qid,)).fetchone():
                continue
            # 检查是否有 user_id 列
            col_names = {row["name"] for row in connection.execute("PRAGMA table_info(explain_collections)")}
            if "user_id" in col_names:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO explain_collections (user_id, question_id, fragment_type, content, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, qid, c.get("fragment_type", "note"), content, c.get("source", "deep-explain")),
                )
            else:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO explain_collections (question_id, fragment_type, content, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (qid, c.get("fragment_type", "note"), content, c.get("source", "deep-explain")),
                )
            pushed_counts["collections"] += 1

    connection.commit()

    # ─────────────────────────────────────────────────────────────
    # 2. Pull 拉取阶段 (提取服务端当前用户全集)
    # ─────────────────────────────────────────────────────────────
    server_days = [
        dict(row)
        for row in connection.execute(
            "SELECT day, activity_type, detail, created_at FROM learning_days WHERE user_id IS ?",
            (user_id,),
        ).fetchall()
    ]

    server_wrongs = [
        dict(row)
        for row in connection.execute(
            """
            SELECT question_id, attempt_count, wrong_count, recent_results,
                   consecutive_correct, manually_frequent, last_wrong_at, last_attempt_at, note
            FROM wrong_stats
            WHERE user_id IS ?
            """,
            (user_id,),
        ).fetchall()
    ]

    server_fsrs = [
        dict(row)
        for row in connection.execute(
            """
            SELECT question_id, interval_days, ease_factor, review_date, due_date,
                   fsrs_due, fsrs_stability, fsrs_difficulty, fsrs_state, fsrs_step, fsrs_last_review
            FROM spaced_repetition_records
            WHERE user_id IS ?
            """,
            (user_id,),
        ).fetchall()
    ]

    col_names = {row["name"] for row in connection.execute("PRAGMA table_info(explain_collections)")}
    if "user_id" in col_names:
        server_collections = [
            dict(row)
            for row in connection.execute(
                "SELECT question_id, fragment_type, content, source, created_at FROM explain_collections WHERE user_id IS ?",
                (user_id,),
            ).fetchall()
        ]
    else:
        server_collections = [
            dict(row)
            for row in connection.execute(
                "SELECT question_id, fragment_type, content, source, created_at FROM explain_collections"
            ).fetchall()
        ]

    return {
        "status": "synced",
        "server_time": now_iso,
        "pushed_summary": pushed_counts,
        "pull": {
            "learning_days": server_days,
            "wrong_stats": server_wrongs,
            "fsrs_records": server_fsrs,
            "collections": server_collections,
        },
    }
