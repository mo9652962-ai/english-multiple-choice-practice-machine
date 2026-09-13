"""Opt-in local learning metrics.

Metrics are disabled by default and stay in the same SQLite database as the
user's learning data. Only allow-listed event names and short metadata are
stored; question text, answers, API keys and free-form feedback are excluded.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from typing import Any


CONSENT_KEY = "local_metrics_consent"
EVENT_NAMES = {
    "first_launch",
    "app_launch",
    "practice_started",
    "practice_completed",
    "first_practice_completed",
    "wrong_review_completed",
    "vocabulary_review_started",
    "vocabulary_review_completed",
    "import_succeeded",
    "vocabulary_added",
    "ai_call_succeeded",
    "ai_call_failed",
    "feedback_submitted",
    "app_error",
    "install_succeeded",
    "install_failed",
}

DETAIL_KEYS = {
    "mode",
    "question_count",
    "source",
    "version",
    "rating",
    "task",
    "status",
    "provider",
    "category",
    "route",
}


def _consent_key(user_id: int | None) -> str:
    """Return a consent key scoped to the authenticated user when present."""
    return CONSENT_KEY if user_id is None else f"{CONSENT_KEY}:{int(user_id)}"


def get_consent(connection: sqlite3.Connection, user_id: int | None = None) -> bool:
    row = connection.execute(
        "SELECT value FROM app_settings WHERE key = ?",
        (_consent_key(user_id),),
    ).fetchone()
    return bool(row and str(row[0] or "").lower() == "enabled")


def set_consent(
    connection: sqlite3.Connection,
    enabled: bool,
    user_id: int | None = None,
) -> bool:
    consent_key = _consent_key(user_id)
    connection.execute(
        "INSERT INTO app_settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (consent_key, "enabled" if enabled else "disabled"),
    )
    if not enabled:
        connection.execute(
            "DELETE FROM local_metrics_events WHERE user_id IS ?",
            (user_id,),
        )
    connection.commit()
    return enabled


def record_event(
    connection: sqlite3.Connection,
    event_name: str,
    *,
    user_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> bool:
    if event_name not in EVENT_NAMES or not get_consent(connection, user_id):
        return False
    safe_detail = {
        str(key)[:40]: str(value)[:120]
        for key, value in (detail or {}).items()
        if str(key)[:40] in DETAIL_KEYS
    }
    connection.execute(
        """
        INSERT INTO local_metrics_events(user_id, event_name, detail)
        VALUES (?, ?, ?)
        """,
        (user_id, event_name, json.dumps(safe_detail, ensure_ascii=False)),
    )
    connection.commit()
    return True


def summarize(
    connection: sqlite3.Connection,
    *,
    user_id: int | None = None,
    days: int = 30,
) -> dict[str, Any]:
    days = max(1, min(365, int(days)))
    rows = connection.execute(
        """
        SELECT event_name, COUNT(*) AS count
        FROM local_metrics_events
        WHERE user_id IS ? AND created_at >= datetime('now', ?)
        GROUP BY event_name ORDER BY count DESC, event_name
        """,
        (user_id, f"-{days} days"),
    ).fetchall()
    event_rows = connection.execute(
        """
        SELECT event_name, detail, created_at
        FROM local_metrics_events
        WHERE user_id IS ? AND created_at >= datetime('now', ?)
        ORDER BY created_at ASC
        """,
        (user_id, f"-{days} days"),
    ).fetchall()
    total = sum(int(row["count"]) for row in rows)
    active_days = connection.execute(
        """
        SELECT COUNT(DISTINCT date(created_at)) AS count
        FROM local_metrics_events
        WHERE user_id IS ? AND created_at >= datetime('now', ?)
        """,
        (user_id, f"-{days} days"),
    ).fetchone()["count"]
    total_questions = 0
    wrong_review_started = 0
    wrong_review_completed = 0
    vocabulary_review_started = 0
    vocabulary_review_completed = 0
    activity_days = set()
    for row in event_rows:
        activity_days.add(str(row["created_at"] or "")[:10])
        try:
            detail = json.loads(row["detail"] or "{}")
        except (TypeError, json.JSONDecodeError):
            detail = {}
        event_name = str(row["event_name"] or "")
        try:
            question_count = max(0, int(detail.get("question_count", 0)))
        except (TypeError, ValueError):
            question_count = 0
        if event_name == "practice_completed":
            total_questions += question_count
        if event_name == "practice_started" and str(detail.get("mode", "")) == "wrong":
            wrong_review_started += question_count or 1
        elif event_name == "wrong_review_completed":
            wrong_review_completed += question_count or 1
        elif event_name == "vocabulary_review_started":
            vocabulary_review_started += question_count or 1
        elif event_name == "vocabulary_review_completed":
            vocabulary_review_completed += question_count or 1
    seven_day_cutoff = (date.today() - timedelta(days=6)).isoformat()
    active_days_7d = len({day for day in activity_days if day >= seven_day_cutoff})
    return {
        "days": days,
        "enabled": get_consent(connection, user_id),
        "total_events": total,
        "active_days": int(active_days or 0),
        "active_days_7d": active_days_7d,
        "returned_after_first_activity_7d": active_days_7d >= 2,
        "total_questions": total_questions,
        "wrong_review_started": wrong_review_started,
        "wrong_review_completed": wrong_review_completed,
        "wrong_review_rate": (
            round(min(1, wrong_review_completed / wrong_review_started), 4)
            if wrong_review_started else None
        ),
        "vocabulary_review_started": vocabulary_review_started,
        "vocabulary_review_completed": vocabulary_review_completed,
        "vocabulary_review_rate": (
            round(min(1, vocabulary_review_completed / vocabulary_review_started), 4)
            if vocabulary_review_started else None
        ),
        "by_event": [dict(row) for row in rows],
    }
