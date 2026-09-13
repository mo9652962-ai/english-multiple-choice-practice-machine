"""错题 FSRS 间隔复习服务。

题目复习与词汇复习共用 FSRS 的 Card 调度模型。旧版
``interval_days/ease_factor/due_date`` 字段继续保留，便于旧库和旧客户端读取；
新的 ``fsrs_*`` 字段是调度事实来源。
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from .fsrs_scheduler import card_from_db, card_to_dict, new_card, review_card

DEFAULT_QUEUE_LIMIT = 30


def _today() -> str:
    return date.today().isoformat()


def _rating_key(quality_score: int) -> str:
    """将旧 API 的 0-5 质量分映射到 FSRS 的三档反馈。"""
    if quality_score >= 4:
        return "mastered"
    if quality_score == 3:
        return "hard"
    return "again"


def _due_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now().astimezone()
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.astimezone()


def update_srs_record(
    connection: sqlite3.Connection,
    question_id: int,
    quality_score: int,
    user_id: int | None = None,
) -> dict:
    """根据作答质量分更新题目 FSRS 卡片（质量分 0-5）。"""
    quality_score = max(0, min(5, int(quality_score)))
    row = connection.execute(
        "SELECT * FROM spaced_repetition_records "
        "WHERE user_id IS ? AND question_id = ?",
        (user_id, question_id),
    ).fetchone()
    card = card_from_db(dict(row)) if row else new_card()
    updated_card, retrievability, interval_desc = review_card(
        card, _rating_key(quality_score)
    )
    fsrs_data = card_to_dict(updated_card)
    due = _due_datetime(fsrs_data.get("fsrs_due"))
    interval = max(0, (due.date() - date.today()).days)
    old_ease = float(row["ease_factor"] if row and row["ease_factor"] is not None else 2.5)
    # ease_factor 仅为旧客户端展示兼容值；FSRS difficulty 是新调度字段。
    ease = max(1.3, min(3.0, old_ease + (0.05 if quality_score >= 4 else -0.08)))
    today = _today()
    due_date = due.date().isoformat()
    if row is None:
        connection.execute(
            """
            INSERT INTO spaced_repetition_records
                (user_id, question_id, interval_days, ease_factor, review_date, due_date,
                 fsrs_due, fsrs_stability, fsrs_difficulty, fsrs_state,
                 fsrs_step, fsrs_last_review)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, question_id, interval, ease, today, due_date,
                fsrs_data["fsrs_due"], fsrs_data["fsrs_stability"],
                fsrs_data["fsrs_difficulty"], fsrs_data["fsrs_state"],
                fsrs_data["fsrs_step"], fsrs_data["fsrs_last_review"],
            ),
        )
    else:
        connection.execute(
            """
            UPDATE spaced_repetition_records
            SET interval_days = ?, ease_factor = ?, review_date = ?, due_date = ?,
                fsrs_due = ?, fsrs_stability = ?, fsrs_difficulty = ?,
                fsrs_state = ?, fsrs_step = ?, fsrs_last_review = ?
            WHERE id = ?
            """,
            (
                interval, ease, today, due_date,
                fsrs_data["fsrs_due"], fsrs_data["fsrs_stability"],
                fsrs_data["fsrs_difficulty"], fsrs_data["fsrs_state"],
                fsrs_data["fsrs_step"], fsrs_data["fsrs_last_review"],
                row["id"],
            ),
        )
    return {
        "interval": interval,
        "ease": round(ease, 2),
        "due": fsrs_data["fsrs_due"],
        "interval_desc": interval_desc,
        "retrievability": round(float(retrievability), 4),
        "algorithm": "fsrs",
    }


def get_due_queue(
    connection: sqlite3.Connection,
    limit: int = DEFAULT_QUEUE_LIMIT,
    user_id: int | None = None,
) -> list[dict]:
    """今日到期题目队列：FSRS 到期时间优先，难度高者优先。"""
    rows = connection.execute(
        """
        SELECT r.question_id, q.stem, r.interval_days, r.ease_factor,
               r.fsrs_difficulty, r.fsrs_due, r.due_date,
               (SELECT w.wrong_count FROM wrong_stats w
                WHERE w.question_id = r.question_id AND w.user_id IS ?) AS wrong_count
        FROM spaced_repetition_records r
        JOIN questions q ON q.id = r.question_id
        WHERE r.user_id IS ?
          AND COALESCE(substr(r.fsrs_due, 1, 10), r.due_date) <= ?
        ORDER BY COALESCE(r.fsrs_due, r.due_date) ASC,
                 COALESCE(r.fsrs_difficulty, 0) DESC,
                 r.ease_factor ASC
        LIMIT ?
        """,
        (user_id, user_id, _today(), limit),
    ).fetchall()
    return [
        {
            "question_id": r["question_id"],
            "stem": r["stem"][:200] if r["stem"] else "",
            "interval": r["interval_days"],
            "ease": round(r["ease_factor"], 2),
            "due": r["fsrs_due"] or r["due_date"],
            "wrong_count": r["wrong_count"] or 0,
            "algorithm": "fsrs" if r["fsrs_due"] else "legacy",
        }
        for r in rows
    ]


def count_due(connection: sqlite3.Connection, user_id: int | None = None) -> int:
    row = connection.execute(
        """
        SELECT COUNT(*) AS n
        FROM spaced_repetition_records
        WHERE user_id IS ?
          AND COALESCE(substr(fsrs_due, 1, 10), due_date) <= ?
        """,
        (user_id, _today()),
    ).fetchone()
    return int(row["n"] or 0)
