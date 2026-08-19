"""模拟考试模式 — 全真限时刷题
从题库随机抽题 → 限时作答 → 交卷即时评分 → 历史成绩
参考: 星火英语/粉笔考研 智能模考 (研究 2026-08)
"""
from __future__ import annotations

import json
import random
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..database import get_db
from .auth import maybe_require_user


def _parse_dt(s: str) -> datetime:
    """v2.44: 解析时间字符串 (支持空格/T 分隔)"""
    if not s:
        return datetime.now()
    return datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))


def _user_scope(user: dict | None, alias: str = "") -> tuple[str, list]:
    """v9.24: EPM_AUTH 开启时返回 user_id 过滤条件；关闭时返回空（兼容单用户）"""
    from .auth import AUTH_ENABLED
    if not AUTH_ENABLED or user is None:
        return "", []
    prefix = f"{alias}." if alias else ""
    return f" AND {prefix}user_id = ?", [user["id"]]

router = APIRouter(prefix="/exam", tags=["exam"])


class ExamStart(BaseModel):
    profile_id: int = Field(1, ge=1)
    count: int = Field(20, ge=5, le=100)
    minutes: int | None = Field(None, ge=1, le=180)


class AnswerUpdate(BaseModel):
    answer: str = ""
    option_order: list[str] = Field(default_factory=list)


def _error(code: str, message: str, details: object | None = None) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": code, "message": message, "details": details or {}})


def _pick_questions(connection: sqlite3.Connection, profile_id: int, count: int) -> list[dict]:
    """从指定 profile 随机抽题（仅选择题）"""
    rows = connection.execute(
        """
        SELECT q.id, q.external_key AS question_key, q.number, q.stem, q.score, q.metadata,
               u.id AS unit_id, u.title AS unit_title, u.unit_type,
               pa.id AS paper_id, pa.year, pa.title AS paper_title
        FROM questions q
        JOIN units u ON q.unit_id = u.id
        JOIN papers pa ON u.paper_id = pa.id
        WHERE pa.profile_id = ? AND pa.deleted_at IS NULL
          AND q.question_type = 'single_choice'
        """,
        (profile_id,),
    ).fetchall()
    if not rows:
        raise _error("EMPTY_BANK", "该题库暂无可用题目，请先导入题库")
    picked = random.sample(rows, min(count, len(rows)))
    return [dict(r) for r in picked]


def _load_options(connection: sqlite3.Connection, question_id: int) -> list[dict]:
    rows = connection.execute(
        "SELECT stable_key, content FROM options WHERE question_id = ? ORDER BY sequence, id",
        (question_id,),
    ).fetchall()
    return [{"key": r["stable_key"], "content": r["content"]} for r in rows]


@router.post("/start")
def start(request: ExamStart, connection: sqlite3.Connection = Depends(get_db),
          user: dict | None = Depends(maybe_require_user)) -> dict:
    profile = connection.execute(
        "SELECT id, name FROM question_bank_profiles WHERE id = ? AND deleted_at IS NULL",
        (request.profile_id,),
    ).fetchone()
    if profile is None:
        raise _error("PROFILE_NOT_FOUND", "题库不存在")
    questions = _pick_questions(connection, request.profile_id, request.count)
    minutes = request.minutes or max(5, round(len(questions) * 1.0))
    qids = [q["id"] for q in questions]
    # v9.24: 创建时记录 user_id（EPM_AUTH=1 时）
    scope, scope_params = _user_scope(user)
    cursor = connection.execute(
        """INSERT INTO exam_sessions
        (profile_id, title, question_ids, total_questions, duration_minutes, status, user_id)
        VALUES (?, ?, ?, ?, ?, 'active', ?)""",
        (request.profile_id, f"{profile['name']} 模拟考试", json.dumps(qids), len(qids), minutes,
         user["id"] if user else None),
    )
    connection.commit()
    return {"id": cursor.lastrowid, "title": f"{profile['name']} 模拟考试",
            "total_questions": len(qids), "duration_minutes": minutes,
            "ends_at": (datetime.now() + timedelta(minutes=minutes)).isoformat(timespec="seconds")}


@router.get("/sessions/{exam_id}")
def detail(exam_id: int, connection: sqlite3.Connection = Depends(get_db),
           user: dict | None = Depends(maybe_require_user)) -> dict:
    scope, scope_params = _user_scope(user)
    row = connection.execute(
        f"SELECT * FROM exam_sessions WHERE id = ?{scope}", (exam_id, *scope_params)
    ).fetchone()
    if row is None:
        raise _error("NOT_FOUND", "考试不存在")
    qids = json.loads(row["question_ids"])
    questions = []
    for qid in qids:
        q = connection.execute(
            """SELECT q.id, q.external_key AS question_key, q.number, q.stem, q.score,
                      pa.year, pa.title AS paper_title, u.passage, u.unit_type
               FROM questions q
               JOIN units u ON q.unit_id = u.id
               JOIN papers pa ON u.paper_id = pa.id
               WHERE q.id = ?""",
            (qid,),
        ).fetchone()
        if q is None:
            continue
        questions.append({
            "id": q["id"], "number": q["number"], "stem": q["stem"],
            "score": q["score"], "year": q["year"], "paper_title": q["paper_title"],
            # v3.3: 返回文章上下文（选词填空/阅读需要——否则只有指令无法作答）
            "passage": (q["passage"] or "").replace("\r\n", "\n").strip(),
            "unit_type": q["unit_type"],
            "options": _load_options(connection, q["id"]),
            "answered": None,
        })
    # 已答
    for ans in connection.execute(
        "SELECT question_id, user_answer FROM exam_answers WHERE exam_id = ?", (exam_id,)
    ).fetchall():
        for q in questions:
            if q["id"] == ans["question_id"]:
                q["answered"] = ans["user_answer"]
    remaining = 0
    if row["status"] == "active":
        # SQLite CURRENT_TIMESTAMP 是 UTC
        started = datetime.fromisoformat(row["started_at"].replace(" ", "T"))
        remaining = max(0, int((started + timedelta(minutes=row["duration_minutes"]) - datetime.utcnow()).total_seconds()))
    return {
        "id": exam_id,
        "title": row["title"],
        "status": row["status"],
        "total_questions": row["total_questions"],
        "duration_minutes": row["duration_minutes"],
        "remaining_seconds": remaining,
        "questions": questions,
        "started_at": row["started_at"],
        "submitted_at": row["submitted_at"],
        "score": row["score"],
        "max_score": row["max_score"],
        "correct_count": row["correct_count"],
        "wrong_count": row["wrong_count"],
        "unanswered_count": row["unanswered_count"],
    }


@router.put("/sessions/{exam_id}/answers/{question_id}")
def update_answer(
    exam_id: int, question_id: int, request: AnswerUpdate,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    scope, scope_params = _user_scope(user)
    row = connection.execute(
        f"SELECT * FROM exam_sessions WHERE id = ?{scope}", (exam_id, *scope_params)
    ).fetchone()
    if row is None:
        raise _error("NOT_FOUND", "考试不存在")
    if row["status"] != "active":
        raise _error("EXAM_FINISHED", "考试已结束")
    # v9.21: 服务端超时强制检查（防超时后继续作答刷分）
    started = _parse_dt(row["started_at"])
    deadline = started + timedelta(minutes=(row["duration_minutes"] or 0), seconds=60)
    if datetime.utcnow() > deadline:
        connection.execute("UPDATE exam_sessions SET status='expired' WHERE id=?", (exam_id,))
        connection.commit()
        raise _error("EXAM_EXPIRED", "考试时间已截止，无法继续作答")
    # v9.21: 题目归属校验（防写入不属于本考试的题目答案）
    qids = json.loads(row["question_ids"])
    if question_id not in qids:
        raise _error("QUESTION_NOT_IN_EXAM", "题目不属于本考试")
    connection.execute(
        """INSERT INTO exam_answers (exam_id, question_id, user_answer, option_order, answered_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(exam_id, question_id) DO UPDATE SET
            user_answer = excluded.user_answer,
            option_order = excluded.option_order,
            answered_at = excluded.answered_at""",
        (exam_id, question_id, request.answer,
         json.dumps(request.option_order), datetime.utcnow().isoformat(timespec="seconds")),
    )
    connection.commit()
    return {"saved": True}


@router.post("/sessions/{exam_id}/submit")
def submit(exam_id: int, connection: sqlite3.Connection = Depends(get_db),
           user: dict | None = Depends(maybe_require_user)) -> dict:
    scope, scope_params = _user_scope(user)
    row = connection.execute(
        f"SELECT * FROM exam_sessions WHERE id = ?{scope}", (exam_id, *scope_params)
    ).fetchone()
    if row is None:
        raise _error("NOT_FOUND", "考试不存在")
    if row["status"] != "active":
        return _result(connection, exam_id)
    # v9.21: 服务端超时强制检查（超时自动判 expired）
    started = _parse_dt(row["started_at"])
    deadline = started + timedelta(minutes=(row["duration_minutes"] or 0), seconds=60)
    if datetime.utcnow() > deadline:
        connection.execute("UPDATE exam_sessions SET status='expired' WHERE id=?", (exam_id,))
        connection.commit()
        return _result(connection, exam_id)
    qids = json.loads(row["question_ids"])
    answered_map = {
        a["question_id"]: a["user_answer"]
        for a in connection.execute("SELECT question_id, user_answer FROM exam_answers WHERE exam_id = ?", (exam_id,))
    }
    correct = wrong = unanswered = 0
    score = 0.0
    max_score = 0.0
    for qid in qids:
        q = connection.execute(
            """SELECT q.id, q.score, q.answer AS correct_key
               FROM questions q
               WHERE q.id = ?""",
            (qid,),
        ).fetchone()
        if q is None:
            continue
        max_score += q["score"] or 0
        user_ans = answered_map.get(qid, "")
        if not user_ans:
            unanswered += 1
        elif user_ans == q["correct_key"]:
            correct += 1
            score += q["score"] or 0
        else:
            wrong += 1
    connection.execute(
        """UPDATE exam_sessions SET status='submitted', submitted_at=?, score=?, max_score=?,
           correct_count=?, wrong_count=?, unanswered_count=?
        WHERE id = ?""",
        (datetime.utcnow().isoformat(timespec="seconds"), round(score, 1), round(max_score, 1),
         correct, wrong, unanswered, exam_id),
    )
    connection.commit()
    # 记录学习行为
    try:
        from ..services.streak import record_activity
        record_activity(connection, "exam_submit", f"exam {exam_id}")
    except Exception:
        pass
    return _result(connection, exam_id)


def _result(connection: sqlite3.Connection, exam_id: int) -> dict:
    row = connection.execute("SELECT * FROM exam_sessions WHERE id = ?", (exam_id,)).fetchone()
    accuracy = (row["correct_count"] / row["total_questions"] * 100) if row["total_questions"] else 0
    # v2.44: 答题用时 + 等级评价 (粉笔式考试报告)
    used_min = 0
    if row["started_at"] and row["submitted_at"]:
        try:
            used_min = round((_parse_dt(row["submitted_at"]) - _parse_dt(row["started_at"])).total_seconds() / 60, 1)
        except Exception:
            used_min = 0
    level = ("优秀" if accuracy >= 85 else "良好" if accuracy >= 70 else
             "合格" if accuracy >= 55 else "待加强")
    return {
        "id": exam_id,
        "title": row["title"],
        "status": row["status"],
        "score": row["score"],
        "max_score": row["max_score"],
        "accuracy": round(accuracy, 1),
        "correct_count": row["correct_count"],
        "wrong_count": row["wrong_count"],
        "unanswered_count": row["unanswered_count"],
        "total_questions": row["total_questions"],
        "submitted_at": row["submitted_at"],
        "duration_minutes": row["duration_minutes"] or 0,
        "used_minutes": used_min,
        "time_ratio": round(used_min / (row["duration_minutes"] or 1) * 100) if row["duration_minutes"] else 0,
        "level": level,
    }


@router.get("/history")
def history(connection: sqlite3.Connection = Depends(get_db),
            user: dict | None = Depends(maybe_require_user)) -> dict:
    scope, scope_params = _user_scope(user)
    rows = connection.execute(
        f"""SELECT id, title, total_questions, duration_minutes, score, max_score,
                  correct_count, wrong_count, unanswered_count, submitted_at
           FROM exam_sessions WHERE status = 'submitted'{scope}
           ORDER BY id DESC LIMIT 30""",
        (*scope_params,),
    ).fetchall()
    items = []
    for r in rows:
        items.append({
            **dict(r),
            "accuracy": round((r["correct_count"] / r["total_questions"] * 100) if r["total_questions"] else 0, 1),
        })
    # 平均正确率
    avg = 0.0
    if items:
        avg = round(sum(i["accuracy"] for i in items) / len(items), 1)
    return {"items": items, "average_accuracy": avg, "count": len(items)}
