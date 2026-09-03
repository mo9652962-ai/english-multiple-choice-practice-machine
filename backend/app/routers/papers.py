from __future__ import annotations

import json
import random
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_active_profile_id, get_db
from ..services.trash import trash_paper
from .auth import maybe_require_user, require_admin


router = APIRouter(prefix="/papers", tags=["papers"])


class GenerateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    profile_id: int | None = None
    types: dict[str, int] = Field(
        default_factory=lambda: {"single_choice": 10},
        description="题型 -> 题数，如 {single_choice: 8, multiple_choice: 2}",
    )
    randomize: bool = True
    pass_score: float = 60.0


# 可组卷的题型白名单
COMPOSABLE_TYPES = ("single_choice", "multiple_choice", "judgement", "fill_blank")


@router.post("/generate")
def generate_paper(
    request: GenerateRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """动态组卷：按题型×数量从当前题库随机抽题，生成一张可考试的编排试卷。"""
    profile_id = request.profile_id or get_active_profile_id(connection)
    profile = connection.execute(
        "SELECT id, name FROM question_bank_profiles WHERE id = ? AND deleted_at IS NULL",
        (profile_id,),
    ).fetchone()
    if profile is None:
        raise HTTPException(404, "题库不存在")

    # 过滤非法题型、归一化
    types = {k: max(0, int(v)) for k, v in request.types.items() if k in COMPOSABLE_TYPES and int(v) > 0}
    if not types:
        raise HTTPException(400, "请至少指定一种可组卷题型及题目数量")

    picked: list[dict] = []
    for qtype, count in types.items():
        rows = connection.execute(
            """SELECT q.id, q.question_type, q.score
               FROM questions q
               JOIN units u ON q.unit_id = u.id
               JOIN papers pa ON u.paper_id = pa.id
               WHERE pa.profile_id = ? AND pa.deleted_at IS NULL
                 AND q.question_type = ?
                 AND q.answer IS NOT NULL AND q.answer != ''
               ORDER BY RANDOM() LIMIT ?""",
            (profile_id, qtype, count),
        ).fetchall()
        picked.extend(dict(r) for r in rows)

    if not picked:
        raise HTTPException(400, "该题库暂无可用题目，请先导入题库")

    # 全局乱序
    if request.randomize:
        random.shuffle(picked)

    qids = [q["id"] for q in picked]
    max_score = round(sum((q["score"] or 1) for q in picked), 1)
    config = {
        "types": types,
        "randomize": request.randomize,
        "pass_score": request.pass_score,
    }
    cursor = connection.execute(
        """INSERT INTO generated_papers
        (title, description, profile_id, configuration, question_ids,
         total_questions, max_score, pass_score, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (request.title, request.description, profile_id, json.dumps(config, ensure_ascii=False),
         json.dumps(qids), len(qids), max_score, request.pass_score,
         user["id"] if user else None),
    )
    connection.commit()
    return {
        "id": cursor.lastrowid,
        "title": request.title,
        "total_questions": len(qids),
        "max_score": max_score,
        "pass_score": request.pass_score,
        "question_ids": qids,
        "type_breakdown": types,
        "message": f"组卷成功：共 {len(qids)} 题，满分 {max_score}",
    }


@router.get("/generated")
def list_generated(
    connection: sqlite3.Connection = Depends(get_db),
) -> list[dict]:
    """列出动态生成的试卷。"""
    rows = connection.execute(
        """SELECT gp.*, (SELECT COUNT(*) FROM exam_sessions e
                         WHERE e.profile_id = gp.profile_id) AS started_count
           FROM generated_papers gp
           ORDER BY gp.id DESC LIMIT 50"""
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("")
def list_papers(connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    profile_id = get_active_profile_id(connection)
    rows = connection.execute(
        """
        SELECT papers.*,
               COUNT(DISTINCT units.id) AS unit_count,
               COUNT(questions.id) AS question_count
        FROM papers
        LEFT JOIN units ON units.paper_id = papers.id
        LEFT JOIN questions ON questions.unit_id = units.id
        WHERE papers.profile_id = ? AND papers.deleted_at IS NULL
        GROUP BY papers.id
        ORDER BY papers.year DESC, papers.title
        """,
        (profile_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@router.get("/{paper_id}")
def get_paper(
    paper_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> dict:
    profile_id = get_active_profile_id(connection)
    paper = connection.execute(
        """
        SELECT * FROM papers
        WHERE id = ? AND profile_id = ? AND deleted_at IS NULL
        """,
        (paper_id, profile_id),
    ).fetchone()
    if paper is None:
        raise HTTPException(404, "试卷不存在或不属于当前题库配置")
    units = connection.execute(
        """
        SELECT units.*,
               COUNT(questions.id) AS question_count,
               COALESCE(SUM(questions.score), 0) AS max_score
        FROM units
        LEFT JOIN questions ON questions.unit_id = units.id
        WHERE units.paper_id = ?
        GROUP BY units.id
        ORDER BY units.sequence
        """,
        (paper_id,),
    ).fetchall()
    return {**dict(paper), "units": [dict(row) for row in units]}


@router.delete("/{paper_id}")
def delete_paper(
    paper_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    _admin: dict = Depends(require_admin),
) -> dict:
    try:
        result = trash_paper(connection, paper_id)
        connection.commit()
        return {"trashed": True, **result}
    except ValueError as error:
        connection.rollback()
        raise HTTPException(404, str(error)) from error
