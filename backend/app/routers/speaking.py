"""P2 口语陪练 API（v9.26——考研复试仿真/日常对话/发音纠偏）。

- POST /api/speaking/sessions                创建会话（返回考官开场白）
- POST /api/speaking/sessions/{id}/turns     提交回答 → 考官回应 + 纠错 + 追问
- POST /api/speaking/sessions/{id}/finish    结束会话 → 生成四维评分报告
- GET  /api/speaking/sessions/{id}           会话详情（历史轮次）
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from ..services.ai_client import chat_completion
from prompts.speaking_prompt import (
    SCENARIOS,
    SPEAKING_SYSTEM_PROMPT,
    build_speaking_user_prompt,
)

router = APIRouter(prefix="/speaking", tags=["speaking"])


class SessionCreateRequest(BaseModel):
    scenario: str = Field(default="graduate_interview")
    topic: str = Field(default="")


class TurnSubmitRequest(BaseModel):
    user_text: str = Field(min_length=1, max_length=2000)
    duration_ms: int = 0


@router.post("/sessions")
def create_session(
    request: SessionCreateRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """创建口语会话，返回考官开场白（本地模板——0 成本）。"""
    scenario = request.scenario if request.scenario in SCENARIOS else "graduate_interview"
    meta = SCENARIOS[scenario]
    cursor = connection.execute(
        """INSERT INTO speaking_sessions (scenario, topic, ai_role, status)
           VALUES (?, ?, ?, 'active')""",
        (scenario, request.topic, meta["role"]),
    )
    connection.commit()
    session_id = int(cursor.lastrowid)
    # 开场白作为第 0 轮存档
    connection.execute(
        """INSERT INTO speaking_turns (session_id, turn_index, ai_reply)
           VALUES (?, 0, ?)""",
        (session_id, meta["opening"]),
    )
    connection.commit()
    return {
        "session_id": session_id,
        "scenario": scenario,
        "opening_message": {
            "role": "assistant",
            "content": meta["opening"],
            "audio_text": meta["opening"],
            "created_at": "",
        },
    }


@router.post("/sessions/{session_id}/turns")
def submit_turn(
    session_id: int,
    request: TurnSubmitRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """提交考生回答 → AI 考官回应（回应 + 语法纠错 + 地道升级 + 追问 + 流畅分）。"""
    session = connection.execute(
        "SELECT * FROM speaking_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="会话已结束")

    # 历史轮次（最近 6 轮）
    history_rows = connection.execute(
        """SELECT user_text, ai_reply FROM speaking_turns
           WHERE session_id = ? AND turn_index > 0 ORDER BY turn_index DESC LIMIT 6""",
        (session_id,),
    ).fetchall()
    history: list[dict] = []
    for r in reversed(history_rows):
        if r["user_text"]:
            history.append({"role": "user", "content": r["user_text"]})
        history.append({"role": "assistant", "content": r["ai_reply"]})

    raw = chat_completion(
        connection,
        [
            {"role": "system", "content": SPEAKING_SYSTEM_PROMPT},
            {"role": "user", "content": build_speaking_user_prompt(
                session["scenario"], session["topic"], history, request.user_text
            )},
        ],
        response_format={"type": "json_object"},
        max_tokens=800,
    )
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="AI 返回解析失败，请重试")

    ai_reply = str(parsed.get("reply") or "").strip()
    if not ai_reply:
        raise HTTPException(status_code=502, detail="AI 未返回有效回应")

    grammar = parsed.get("grammar_corrections") or []
    native_upgrade = str(parsed.get("native_upgrade") or "")
    fluency = float(parsed.get("fluency_score") or 0)

    # 下一轮索引
    row = connection.execute(
        "SELECT COALESCE(MAX(turn_index), 0) AS mx FROM speaking_turns WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    next_index = int(row["mx"]) + 1

    connection.execute(
        """INSERT INTO speaking_turns
            (session_id, turn_index, user_text, ai_reply, grammar_corrections,
             native_upgrade, audio_duration_ms)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            session_id, next_index, request.user_text, ai_reply,
            json.dumps(grammar, ensure_ascii=False),
            native_upgrade, request.duration_ms,
        ),
    )
    # 更新会话流畅分（滚动平均）
    connection.execute(
        """UPDATE speaking_sessions
           SET score_fluency = (score_fluency + ?) / 2, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (fluency, session_id),
    )
    connection.commit()

    return {
        "turn_id": next_index,
        "ai_reply": ai_reply,
        "feedback": {
            "grammar_corrections": grammar,
            "native_upgrade": native_upgrade,
            "fluency_score": fluency,
        },
    }


@router.post("/sessions/{session_id}/finish")
def finish_session(
    session_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """结束会话 → 本地汇总四维评分（流畅/语法/词汇/连贯——无额外 AI 调用）。"""
    session = connection.execute(
        "SELECT * FROM speaking_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    turns = connection.execute(
        """SELECT user_text, ai_reply, grammar_corrections FROM speaking_turns
           WHERE session_id = ? AND turn_index > 0""",
        (session_id,),
    ).fetchall()

    # 汇总指标
    total_words = sum(len((t["user_text"] or "").split()) for t in turns)
    avg_len = total_words / len(turns) if turns else 0
    grammar_hits = 0
    for t in turns:
        try:
            grammar_hits += len(json.loads(t["grammar_corrections"] or "[]"))
        except (TypeError, json.JSONDecodeError):
            pass

    fluency = float(session["score_fluency"] or 0)
    grammar_score = max(0, min(100, 100 - grammar_hits * 5))
    vocabulary = max(0, min(100, 70 + avg_len * 2))
    coherence = max(0, min(100, 60 + len(turns) * 5))

    report = {
        "dimensions": {
            "fluency": round(fluency, 1),
            "grammar": round(grammar_score, 1),
            "vocabulary": round(vocabulary, 1),
            "coherence": round(coherence, 1),
        },
        "turn_count": len(turns),
        "total_words": total_words,
        "grammar_corrections_count": grammar_hits,
        "summary": (
            "本次练习共 {} 轮，累计 {} 词。流畅度 {}，语法 {}（纠错 {} 处），"
            "词汇 {}，连贯 {}。继续坚持每日开口练习，注意时态一致与连读。"
        ).format(
            len(turns), total_words,
            round(fluency), round(grammar_score), grammar_hits,
            round(vocabulary), round(coherence),
        ),
    }
    connection.execute(
        """UPDATE speaking_sessions
           SET score_fluency = ?, score_grammar = ?, score_vocabulary = ?,
               score_coherence = ?, summary_report = ?, status = 'finished',
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (
            report["dimensions"]["fluency"], report["dimensions"]["grammar"],
            report["dimensions"]["vocabulary"], report["dimensions"]["coherence"],
            json.dumps(report, ensure_ascii=False), session_id,
        ),
    )
    connection.commit()
    return {"session_id": session_id, **report}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    session = connection.execute(
        "SELECT * FROM speaking_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    turns = connection.execute(
        """SELECT turn_index, user_text, ai_reply, grammar_corrections, native_upgrade
           FROM speaking_turns WHERE session_id = ? ORDER BY turn_index""",
        (session_id,),
    ).fetchall()
    data = dict(session)
    turn_list: list[dict[str, Any]] = []
    for row in turns:
        t = dict(row)
        try:
            t["grammar_corrections"] = json.loads(t["grammar_corrections"] or "[]")
        except (TypeError, json.JSONDecodeError):
            t["grammar_corrections"] = []
        turn_list.append(t)
    try:
        data["summary_report"] = json.loads(data.get("summary_report") or "{}")
    except (TypeError, json.JSONDecodeError):
        data["summary_report"] = {}
    data["turns"] = turn_list
    return data
