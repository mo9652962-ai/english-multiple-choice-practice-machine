"""错题间隔重复（SM-2 简化版）——v9.28 Gemini batch5 任务3 落地

- 答对质量分 >= 3：间隔递增（1 → 6 → interval*ease）
- 答错质量分 < 3：间隔重置 1
- ease_factor 更新公式: EF' = EF + (0.1 - (5-q)*(0.08 + (5-q)*0.02))，下限 1.3
- 每日队列: due_date <= 今天，按 due_date + ease_factor 排序，默认 30 题
"""
import sqlite3
from datetime import date, timedelta

MIN_EASE = 1.3
DEFAULT_QUEUE_LIMIT = 30


def _today() -> str:
    return date.today().isoformat()


def update_srs_record(
    connection: sqlite3.Connection,
    question_id: int,
    quality_score: int,
    user_id: int | None = None,
) -> dict:
    """根据作答质量分更新 SRS 记录（质量分 0-5）。答对自动挂钩用 q=4，答错 q=1。"""
    quality_score = max(0, min(5, int(quality_score)))
    row = connection.execute(
        "SELECT * FROM spaced_repetition_records WHERE user_id IS ? AND question_id = ?",
        (user_id, question_id),
    ).fetchone()

    today = _today()
    if row is None:
        interval = 1 if quality_score >= 3 else 0
        ease = 2.5
        # 新错题：错一次间隔 0（今天再练），对一次间隔 1
        due = date.today() if interval == 0 else date.today() + timedelta(days=1)
        connection.execute(
            """INSERT INTO spaced_repetition_records
               (user_id, question_id, interval_days, ease_factor, review_date, due_date)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, question_id, interval, ease, today, due.isoformat()),
        )
        return {"interval": interval, "ease": ease, "due": due.isoformat()}

    interval = row["interval_days"]
    ease = row["ease_factor"]
    if quality_score >= 3:
        # 答对：间隔递增
        if interval <= 1:
            interval = 6 if interval == 1 else 1
        else:
            interval = max(1, int(interval * ease))
    else:
        # 答错：重置
        interval = 1
    # EF 更新（SM-2 公式）
    ease = ease + (0.1 - (5 - quality_score) * (0.08 + (5 - quality_score) * 0.02))
    if ease < MIN_EASE:
        ease = MIN_EASE
    due = date.today() + timedelta(days=interval)
    connection.execute(
        """UPDATE spaced_repetition_records
           SET interval_days = ?, ease_factor = ?, review_date = ?, due_date = ?
           WHERE id = ?""",
        (interval, ease, today, due.isoformat(), row["id"]),
    )
    return {"interval": interval, "ease": ease, "due": due.isoformat()}


def get_due_queue(
    connection: sqlite3.Connection,
    limit: int = DEFAULT_QUEUE_LIMIT,
    user_id: int | None = None,
) -> list[dict]:
    """今日到期复习队列：due_date <= 今天，due 早 + ease 低优先。"""
    rows = connection.execute(
        """
        SELECT r.question_id, q.stem, r.interval_days, r.ease_factor, r.due_date,
               (SELECT w.wrong_count FROM wrong_stats w
                WHERE w.question_id = r.question_id AND w.user_id IS ?) AS wrong_count
        FROM spaced_repetition_records r
        JOIN questions q ON q.id = r.question_id
        WHERE r.user_id IS ? AND r.due_date <= ?
        ORDER BY r.due_date ASC, r.ease_factor ASC
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
            "due": r["due_date"],
            "wrong_count": r["wrong_count"] or 0,
        }
        for r in rows
    ]


def count_due(connection: sqlite3.Connection, user_id: int | None = None) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS n FROM spaced_repetition_records WHERE user_id IS ? AND due_date <= ?",
        (user_id, _today()),
    ).fetchone()
    return row["n"] or 0
