# -*- coding: utf-8 -*-
"""AI 英语刷题机 — AI 相似题生成（从错题考点生成变体题）

参考 (2026-08 研究):
  - 作业帮 AI 超级老师: 答对出变式题验证 → 巩固考点
  - 有道智能错题本: 根据错误知识点推荐同类习题
  - Prometric Finetune Generate: 从源材料生成同考点题目

流程:
  1. 取错题的题干 + 考点标签 (primary_skill / trap_types / vocabulary_demand)
  2. 调 DeepSeek V4-Flash 生成同考点变体题（不复制原题）
  3. 返回新题 + 考点说明，用户可添加到练习
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from .ai_client import chat_completion, parse_json_response

SIMILAR_QUESTION_PROMPT = """你是一名考研英语命题专家。请根据下面这道真题的考点，生成 3 道风格一致的变体题（新文章、新题干、新选项），用于巩固同一考点。

原题信息:
- 年份: {year}
- 题型: {unit_type}
- 考点: {primary_skill}
- 陷阱: {trap_types}
- 词汇要求: {vocabulary_demand}
- 原文段落: {passage}

要求:
1. 不要复制原题的题干和选项，要创作新的
2. 3 道题保持相同考点和相似难度
3. 每道题提供: stem(题干), options(4个选项ABCD), answer(正确选项字母), explanation(解析，说明考什么)
4. 用 JSON 数组返回，格式:
[{{"stem": "...", "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}}, "answer": "A", "explanation": "..."}}]
"""


def generate_similar_questions(
    connection: sqlite3.Connection,
    question_id: int,
    count: int = 3,
) -> dict[str, Any]:
    """从错题考点生成同考点变体题
    
    Args:
        connection: 数据库连接
        question_id: 错题 ID
        count: 生成数量 (1-5)
    
    Returns:
        {"question_id": N, "questions": [...], "error": optional}
    """
    # 查原题 + 考点标签
    row = connection.execute(
        """SELECT q.id, q.stem, q.answer, q.question_type,
                  u.title, u.unit_type, u.passage,
                  p.year,
                  l.primary_skill, l.secondary_skills, l.trap_types,
                  l.attention_points, l.vocabulary_demand
           FROM questions AS q
           JOIN units AS u ON u.id = q.unit_id
           JOIN papers AS p ON p.id = u.paper_id
           LEFT JOIN question_ai_labels AS l ON l.question_id = q.id
           WHERE q.id = ?""",
        (question_id,),
    ).fetchone()
    if not row:
        return {"error": f"题目 id={question_id} 不存在", "questions": []}
    
    # 考点信息
    primary_skill = row["primary_skill"] or "阅读理解"
    trap_types = row["trap_types"] or "[]"
    if isinstance(trap_types, str):
        try:
            trap_types = json.loads(trap_types)
        except Exception:
            trap_types = []
    
    prompt = SIMILAR_QUESTION_PROMPT.format(
        year=row["year"],
        unit_type=row["unit_type"],
        primary_skill=primary_skill,
        trap_types="、".join(trap_types[:3]) if trap_types else "无特殊陷阱",
        vocabulary_demand=row["vocabulary_demand"] or "medium",
        passage=(row["passage"] or "")[:1500],
    )
    
    try:
        response = chat_completion(
            connection,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1200,
        )
        text = response if isinstance(response, str) else response.get("content", "")
        questions = parse_json_response(text)
        if not isinstance(questions, list):
            questions = [questions] if questions else []
        # 校验每道题结构
        valid = []
        for q in questions[:count]:
            if isinstance(q, dict) and q.get("stem") and q.get("options") and q.get("answer"):
                valid.append({
                    "stem": q["stem"],
                    "options": q["options"],
                    "answer": q["answer"],
                    "explanation": q.get("explanation", ""),
                })
        return {
            "question_id": question_id,
            "original_skill": primary_skill,
            "questions": valid,
        }
    except Exception as e:
        return {"error": f"AI 生成失败: {e}", "questions": []}
