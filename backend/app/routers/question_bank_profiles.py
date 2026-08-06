from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_active_profile_id, get_db, set_active_profile_id
from ..schemas import (
    BatchPaperMoveRequest,
    QuestionBankProfileCreate,
    QuestionBankProfileUpdate,
    TrashRestoreRequest,
)
from ..services.trash import (
    list_trash,
    purge_trash,
    restore_trash,
    trash_profile,
)


router = APIRouter(tags=["question-bank-profiles"])


def _bad_request(message: str, status: int = 422) -> HTTPException:
    return HTTPException(status, {"code": "QUESTION_BANK_PROFILE_ERROR", "message": message})


@router.get("/question-bank-profiles")
def list_profiles(connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    active_id = get_active_profile_id(connection)
    rows = connection.execute(
        """
        SELECT p.*,
               COUNT(DISTINCT papers.id) AS paper_count,
               COUNT(DISTINCT units.id) AS unit_count,
               COUNT(DISTINCT questions.id) AS question_count,
               MAX(papers.updated_at) AS last_used_at
        FROM question_bank_profiles AS p
        LEFT JOIN papers
          ON papers.profile_id = p.id AND papers.deleted_at IS NULL
        LEFT JOIN units ON units.paper_id = papers.id
        LEFT JOIN questions ON questions.unit_id = units.id
        WHERE p.deleted_at IS NULL
        GROUP BY p.id
        ORDER BY (p.id = ?) DESC, p.is_default DESC, p.updated_at DESC, p.id
        """,
        (active_id,),
    ).fetchall()
    return [{**dict(row), "is_active": int(row["id"]) == active_id} for row in rows]


@router.post("/question-bank-profiles")
def create_profile(
    request: QuestionBankProfileCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    name = request.name.strip()
    if not name:
        raise _bad_request("题库配置名称不能为空")
    try:
        cursor = connection.execute(
            """
            INSERT INTO question_bank_profiles(name, description)
            VALUES (?, ?)
            """,
            (name, request.description.strip()),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise _bad_request("已经存在同名题库配置", 409) from error
    row = connection.execute(
        "SELECT * FROM question_bank_profiles WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return {**dict(row), "is_active": False, "paper_count": 0}


@router.patch("/question-bank-profiles/{profile_id}")
def update_profile(
    profile_id: int,
    request: QuestionBankProfileUpdate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = connection.execute(
        "SELECT * FROM question_bank_profiles WHERE id = ? AND deleted_at IS NULL",
        (profile_id,),
    ).fetchone()
    if row is None:
        raise _bad_request("题库配置不存在", 404)
    name = request.name.strip() if request.name is not None else row["name"]
    description = (
        request.description.strip()
        if request.description is not None
        else row["description"]
    )
    try:
        connection.execute(
            """
            UPDATE question_bank_profiles
            SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (name, description, profile_id),
        )
        connection.commit()
    except sqlite3.IntegrityError as error:
        raise _bad_request("已经存在同名题库配置", 409) from error
    return dict(
        connection.execute(
            "SELECT * FROM question_bank_profiles WHERE id = ?", (profile_id,)
        ).fetchone()
    )


@router.post("/question-bank-profiles/{profile_id}/activate")
def activate_profile(
    profile_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        set_active_profile_id(connection, profile_id)
    except ValueError as error:
        raise _bad_request(str(error), 404) from error
    connection.execute(
        "UPDATE question_bank_profiles SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (profile_id,),
    )
    connection.commit()
    return {"activated": True, "profile_id": profile_id}


@router.delete("/question-bank-profiles/{profile_id}")
def delete_profile(
    profile_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        result = trash_profile(connection, profile_id)
        connection.commit()
        return {"trashed": True, **result}
    except ValueError as error:
        connection.rollback()
        raise _bad_request(str(error)) from error


@router.post("/papers/batch-move")
def batch_move_papers(
    request: BatchPaperMoveRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    paper_ids = sorted(set(request.paper_ids))
    target = connection.execute(
        """
        SELECT id, name FROM question_bank_profiles
        WHERE id = ? AND deleted_at IS NULL
        """,
        (request.target_profile_id,),
    ).fetchone()
    if target is None:
        raise _bad_request("目标题库配置不存在", 404)
    placeholders = ",".join("?" for _ in paper_ids)
    rows = connection.execute(
        f"""
        SELECT id, profile_id, year, title, external_key
        FROM papers
        WHERE id IN ({placeholders}) AND deleted_at IS NULL
        ORDER BY id
        """,
        paper_ids,
    ).fetchall()
    if len(rows) != len(paper_ids):
        raise _bad_request("部分试卷不存在或已经在回收站", 404)
    renamed: list[dict] = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        for row in rows:
            title = row["title"]
            external_key = row["external_key"]
            duplicate = None
            if external_key:
                duplicate = connection.execute(
                    """
                    SELECT id FROM papers
                    WHERE profile_id = ? AND external_key = ?
                      AND deleted_at IS NULL AND id <> ?
                    """,
                    (request.target_profile_id, external_key, row["id"]),
                ).fetchone()
            if duplicate:
                base = title
                suffix = 2
                candidate = f"{base}（{suffix}）"
                while connection.execute(
                    """
                    SELECT 1 FROM papers
                    WHERE profile_id = ? AND title = ? COLLATE NOCASE
                      AND deleted_at IS NULL
                    """,
                    (request.target_profile_id, candidate),
                ).fetchone():
                    suffix += 1
                    candidate = f"{base}（{suffix}）"
                title = candidate
                external_key = f"{external_key}:copy:{row['id']}"
                renamed.append({"paper_id": int(row["id"]), "title": title})
            connection.execute(
                """
                UPDATE papers
                SET profile_id = ?, title = ?, external_key = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (request.target_profile_id, title, external_key, row["id"]),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {
        "moved": len(rows),
        "target_profile_id": request.target_profile_id,
        "renamed": renamed,
    }


@router.get("/trash")
def trash_items(connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    return list_trash(connection)


@router.post("/trash/{trash_id}/restore")
def restore_item(
    trash_id: int,
    request: TrashRestoreRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        result = restore_trash(connection, trash_id, request.target_profile_id)
        connection.commit()
        return result
    except ValueError as error:
        connection.rollback()
        raise _bad_request(str(error)) from error


@router.delete("/trash/{trash_id}")
def purge_item(
    trash_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        result = purge_trash(connection, trash_id)
        connection.commit()
        return result
    except ValueError as error:
        connection.rollback()
        raise _bad_request(str(error), 404) from error
