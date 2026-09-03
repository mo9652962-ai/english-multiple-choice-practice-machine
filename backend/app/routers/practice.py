from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_active_profile_id, get_db
from ..schemas import AnswerUpdate, PracticeCreate
from ..services.practice import (
    IncompleteSubmissionError,
    create_session,
    get_session,
    save_answer,
    submit_session,
    submit_unit,
)
from .auth import maybe_require_user


router = APIRouter(prefix="/practice", tags=["practice"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


def translate_error(error: Exception) -> HTTPException:
    if isinstance(error, IncompleteSubmissionError):
        return HTTPException(
            409,
            {
                "code": "incomplete_submission",
                "message": str(error),
                "unit_id": error.unit_id,
                "unit_title": error.unit_title,
                "question_id": error.question_id,
                "question_number": error.question_number,
            },
        )
    if isinstance(error, LookupError):
        return HTTPException(404, str(error))
    return HTTPException(400, str(error))


def _scope_wrong_practice(
    connection: sqlite3.Connection,
    request: PracticeCreate,
    user_id: int | None,
) -> PracticeCreate:
    """把 wrong 模式的题目集合先限制到当前用户，再交给历史 service。"""
    if request.mode != "wrong":
        return request
    conditions = [
        "ws.user_id IS ?",
        "ws.wrong_count > 0",
        "p.profile_id = ?",
        "p.deleted_at IS NULL",
    ]
    params: list[object] = [user_id, get_active_profile_id(connection)]
    if request.unit_ids:
        placeholders = ",".join("?" for _ in request.unit_ids)
        conditions.append(f"q.unit_id IN ({placeholders})")
        params.extend(request.unit_ids)
    if request.question_ids:
        placeholders = ",".join("?" for _ in request.question_ids)
        conditions.append(f"q.id IN ({placeholders})")
        params.extend(request.question_ids)
    if request.unit_type:
        conditions.append("u.unit_type = ?")
        params.append(request.unit_type)
    rows = connection.execute(
        f"""SELECT DISTINCT ws.question_id
            FROM wrong_stats ws
            JOIN questions q ON q.id = ws.question_id
            JOIN units u ON u.id = q.unit_id
            JOIN papers p ON p.id = u.paper_id
            WHERE {' AND '.join(conditions)}""",
        params,
    ).fetchall()
    question_ids = [int(row["question_id"]) for row in rows]
    if not question_ids:
        raise LookupError("当前用户没有符合条件的错题")
    return request.model_copy(update={"question_ids": question_ids})


@router.post("/sessions")
def create(
    request: PracticeCreate,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    try:
        user_id = _current_user_id(user)
        scoped_request = _scope_wrong_practice(connection, request, user_id)
        return create_session(connection, scoped_request, user_id=user_id)
    except (ValueError, LookupError) as error:
        raise translate_error(error) from error


@router.get("/sessions/{session_id}")
def detail(
    session_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    try:
        return get_session(connection, session_id, user_id=_current_user_id(user))
    except (ValueError, LookupError) as error:
        raise translate_error(error) from error


@router.put("/sessions/{session_id}/answers/{question_id}")
def update_answer(
    session_id: int,
    question_id: int,
    request: AnswerUpdate,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, bool]:
    try:
        save_answer(
            connection,
            session_id,
            question_id,
            request.answer,
            request.option_order,
            user_id=_current_user_id(user),
        )
        return {"saved": True}
    except (ValueError, LookupError) as error:
        raise translate_error(error) from error


@router.post("/sessions/{session_id}/submit")
def submit(
    session_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    try:
        result = submit_session(connection, session_id, user_id=_current_user_id(user))
        _record_streak_activity(
            connection, "practice_submit", f"session {session_id}",
            user_id=_current_user_id(user),
        )
        return result
    except (ValueError, LookupError) as error:
        raise translate_error(error) from error


def _record_streak_activity(
    connection: sqlite3.Connection, activity_type: str, detail: str = "",
    user_id: int | None = None,
) -> None:
    """记录 streak 学习行为（失败静默，不影响主流程；按用户隔离）"""
    try:
        from ..services.streak import record_activity
        record_activity(connection, activity_type, detail, user_id=user_id)
    except Exception:
        pass


@router.post("/sessions/{session_id}/units/{unit_id}/submit")
def submit_current_unit(
    session_id: int,
    unit_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    try:
        return submit_unit(connection, session_id, unit_id, user_id=_current_user_id(user))
    except (ValueError, LookupError) as error:
        raise translate_error(error) from error
