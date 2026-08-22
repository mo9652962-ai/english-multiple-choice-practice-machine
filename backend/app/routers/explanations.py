"""任务 E（第 4 部分）：题目解析 API。

- GET /api/questions/{question_id}/explain  获取单题解析
  200 {"available": true,  "content": {...}, "source_model", "updated_at"}  有解析
  200 {"available": false}                                                  暂无解析（题存在）
  404                                                                      题目不存在

content 为结构化 JSON（由 backend/prompts/explain_prompt.py 约定）：
{correct_analysis, wrong_options: [{key, reason}], knowledge_points, study_advice}
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from .auth import AUTH_ENABLED, maybe_require_user

router = APIRouter(tags=["explanations"])


@router.get("/questions/{question_id}/explain")
def get_question_explain(
    question_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    question = connection.execute(
        "SELECT id FROM questions WHERE id = ?", (question_id,)
    ).fetchone()
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    row = connection.execute(
        """
        SELECT content, source_model, updated_at
        FROM question_explanations
        WHERE question_id = ?
        """,
        (question_id,),
    ).fetchone()
    if row is None:
        return {"question_id": question_id, "available": False}

    try:
        content = json.loads(row["content"])
    except (TypeError, json.JSONDecodeError):
        # 历史脏数据兜底：按纯文本解析展示
        content = {"correct_analysis": str(row["content"]), "wrong_options": [],
                   "knowledge_points": [], "study_advice": ""}
    return {
        "question_id": question_id,
        "available": True,
        "content": content,
        "source_model": row["source_model"],
        "updated_at": row["updated_at"],
    }


@router.get("/explanations/coverage")
def explanations_coverage(connection: sqlite3.Connection = Depends(get_db)) -> dict[str, Any]:
    """解析覆盖率（管理端/批量生成进度展示）。"""
    row = connection.execute(
        """
        SELECT COUNT(q.id) AS total,
               SUM(CASE WHEN e.question_id IS NOT NULL THEN 1 ELSE 0 END) AS explained
        FROM questions AS q
        LEFT JOIN question_explanations AS e ON e.question_id = q.id
        """
    ).fetchone()
    total = int(row["total"] or 0)
    explained = int(row["explained"] or 0)
    return {
        "total": total,
        "explained": explained,
        "remaining": max(0, total - explained),
        "percentage": round(explained * 100 / total, 1) if total else 0,
    }


# v9.26: P0 真题精讲——深度解析生成（4 选项逐项解构 + 陷阱标签 + 长难句 + 缓存）
@router.post("/questions/{question_id}/deep-explain")
def deep_explain_question(
    question_id: int,
    request: dict[str, Any] | None = None,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    """生成/获取深度精讲（AI 生成一次，缓存永久复用——95% 请求 0 成本）。

    body: {"force_refresh": bool} 可选；默认读缓存。
    v9.31 安全加固: 挂 maybe_require_user（EPM_AUTH=1 时强制登录）；
    force_refresh 要求登录（匿名只能读缓存，防局域网匿名刷 AI 烧 key）。
    """
    force_refresh = bool((request or {}).get("force_refresh"))
    # v9.31: 仅多人模式（EPM_AUTH=1）下未登录 force_refresh 拒绝；
    # 单用户模式（EPM_AUTH=0）user 恒为 None，放行保持原有体验
    if force_refresh and AUTH_ENABLED and user is None:
        raise HTTPException(status_code=401, detail="强制刷新需要登录")
    question = connection.execute(
        """SELECT q.id, q.number, q.stem, q.answer, q.question_type, q.unit_id,
                  u.title AS unit_title, u.passage, p.year, p.title AS paper_title
           FROM questions q
           JOIN units u ON u.id = q.unit_id
           JOIN papers p ON p.id = u.paper_id
           WHERE q.id = ?""",
        (question_id,),
    ).fetchone()
    if question is None:
        raise HTTPException(status_code=404, detail="题目不存在")

    # 缓存命中（非强制刷新）
    if not force_refresh:
        row = connection.execute(
            "SELECT content, source_model, updated_at FROM question_explanations WHERE question_id = ?",
            (question_id,),
        ).fetchone()
        if row is not None:
            try:
                content = json.loads(row["content"])
                if isinstance(content, dict) and "options_analysis" in content:
                    return {
                        "question_id": question_id,
                        "cached": True,
                        **content,
                        "source_model": row["source_model"],
                        "updated_at": row["updated_at"],
                    }
            except (TypeError, json.JSONDecodeError):
                pass

    # 组装选项
    options = connection.execute(
        "SELECT stable_key AS key, content FROM options WHERE question_id = ? ORDER BY sequence",
        (question_id,),
    ).fetchall()
    from prompts.explain_prompt import DEEP_EXPLAIN_SYSTEM_PROMPT
    from ..services.ai_client import chat_completion, parse_json_response

    user_prompt = (
        "题目：{}\n\n"
        "选项：{}\n\n"
        "正确答案：{}\n\n"
        "文章（片段）：\n{}\n\n"
        "请生成深度精讲 JSON。"
    ).format(
        question["stem"],
        json.dumps(
            [{"key": o["key"], "content": o["content"][:300]} for o in options],
            ensure_ascii=False,
        ),
        question["answer"],
        (question["passage"] or "")[:4000],
    )
    raw = chat_completion(
        connection,
        [
            {"role": "system", "content": DEEP_EXPLAIN_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )
    try:
        parsed = parse_json_response(raw)
    except ValueError:
        raise HTTPException(status_code=502, detail="AI 返回解析失败，请重试")
    # 规范化必填字段
    parsed.setdefault("question_type_label", "")
    parsed.setdefault("core_skill", "")
    parsed.setdefault("locator_sentence", "")
    parsed.setdefault("solution_steps", [])
    parsed.setdefault("options_analysis", {})
    parsed.setdefault("sentence_grammar", {})
    parsed.setdefault("knowledge_points", [])
    parsed.setdefault("study_advice", "")

    # 缓存持久化（content 存完整深度结构，兼容 GET /explain 读取）
    model_name = ""
    try:
        from ..services.ai_client import _settings_with_key
        model_name = _settings_with_key(connection).get("model") or ""
    except Exception:
        pass
    connection.execute(
        """INSERT INTO question_explanations (question_id, content, source_model)
           VALUES (?, ?, ?)
           ON CONFLICT(question_id) DO UPDATE SET
               content = excluded.content,
               source_model = excluded.source_model,
               updated_at = CURRENT_TIMESTAMP""",
        (question_id, json.dumps(parsed, ensure_ascii=False), model_name),
    )
    connection.commit()

    # 同类推荐（同 unit 的其他题——趁热打铁）
    similar = [
        r["id"]
        for r in connection.execute(
            "SELECT id FROM questions WHERE unit_id = ? AND id != ? LIMIT 2",
            (question["unit_id"], question_id),
        ).fetchall()
    ]
    return {
        "question_id": question_id,
        "cached": False,
        **parsed,
        "similar_recommendations": similar,
        "source_model": model_name,
    }
