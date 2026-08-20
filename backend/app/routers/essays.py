"""P1 作文批改 API（v9.26——考研大小作文多维精批）。

- POST /api/essays/evaluate     提交作文 → AI 多维批改 + 持久化
- GET  /api/essays              历史批改列表
- GET  /api/essays/{id}         单次批改详情
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..services.ai_client import chat_completion, parse_json_response
from prompts.essay_prompt import ESSAY_SYSTEM_PROMPT, build_essay_user_prompt

router = APIRouter(prefix="/essays", tags=["essays"])


class EssayEvaluateRequest(BaseModel):
    essay_type: str = Field(default="essay_large", description="essay_small / essay_large")
    subject: str = Field(default="英语一")
    prompt_title: str = Field(default="")
    user_content: str = Field(min_length=10, max_length=5000)


@router.post("/evaluate")
def evaluate_essay(
    request: EssayEvaluateRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """AI 批改作文（考研阅卷组标准——评分/维度/行内批注/词汇升格/范文）。"""
    content = request.user_content.strip()
    word_count = len(content.split())
    raw = chat_completion(
        connection,
        [
            {"role": "system", "content": ESSAY_SYSTEM_PROMPT},
            {"role": "user", "content": build_essay_user_prompt(
                request.essay_type, request.subject, request.prompt_title, content
            )},
        ],
        response_format={"type": "json_object"},
        max_tokens=2500,
    )
    try:
        parsed = parse_json_response(raw)
    except ValueError:
        raise HTTPException(status_code=502, detail="AI 返回解析失败，请重试")

    # 规范化
    parsed.setdefault("score", 0)
    parsed.setdefault("max_score", 20 if request.essay_type != "essay_small" else 10)
    parsed.setdefault("band", "")
    parsed.setdefault("dimensions", {})
    parsed.setdefault("overall_comment", "")
    parsed.setdefault("markups", [])
    parsed.setdefault("lexical_upgrades", [])
    parsed.setdefault("model_essay", "")
    parsed.setdefault("essay_highlights", [])

    # 持久化（多用户: user_id 由 get_current_user 提供——简化版先 NULL）
    cursor = connection.execute(
        """INSERT INTO essay_submissions
            (essay_type, subject, prompt_title, user_content, word_count,
             score, max_score, band_name, dimensions, overall_comment,
             markups, lexical_upgrades, model_essay, essay_highlights)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            request.essay_type, request.subject, request.prompt_title, content, word_count,
            float(parsed["score"]), float(parsed["max_score"]), parsed["band"],
            json.dumps(parsed["dimensions"], ensure_ascii=False),
            parsed["overall_comment"],
            json.dumps(parsed["markups"], ensure_ascii=False),
            json.dumps(parsed["lexical_upgrades"], ensure_ascii=False),
            parsed["model_essay"],
            json.dumps(parsed["essay_highlights"], ensure_ascii=False),
        ),
    )
    connection.commit()
    submission_id = int(cursor.lastrowid)
    return {
        "submission_id": submission_id,
        "word_count": word_count,
        **parsed,
    }


@router.get("")
def list_essays(
    connection: sqlite3.Connection = Depends(get_db),
    limit: int = 20,
) -> dict[str, Any]:
    """历史批改列表（不含全文——轻量）。"""
    rows = connection.execute(
        """SELECT id, essay_type, subject, prompt_title, word_count, score, max_score,
                  band_name, overall_comment, created_at
           FROM essay_submissions ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return {
        "items": [dict(r) for r in rows],
        "count": len(rows),
    }


@router.get("/{submission_id}")
def get_essay(
    submission_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM essay_submissions WHERE id = ?", (submission_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="批改记录不存在")
    data = dict(row)
    for field in ("dimensions", "markups", "lexical_upgrades", "essay_highlights"):
        try:
            data[field] = json.loads(data.get(field) or "[]")
        except (TypeError, json.JSONDecodeError):
            data[field] = [] if field != "dimensions" else {}
    return data
