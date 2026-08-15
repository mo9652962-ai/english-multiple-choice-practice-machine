"""学习诊断报告服务（P0）。

在 wrong_analysis（逐题归因 + 聚合）之上补齐：
- level：当前水平 1-5（AI 只输入匿名统计，防泄漏）
- recommendations：按薄弱 cause 从题库筛选推荐练习（本地 SQL，不调 AI）
- trend：与上次报告对比（本地计算）
- 持久化：diagnostic_reports 表
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date
from typing import Any

from .ai_router import chat_with_routing
from .wrong_analysis import CAUSE_GUIDANCE, CAUSE_LABELS, aggregate_diagnoses, diagnose_wrong_answers

# 薄弱 cause → 题库筛选（unit_type / question_type / 标签）
_CAUSE_TO_UNIT_TYPE: dict[str, str] = {
    "vocabulary": "cloze",
    "collocation": "cloze",
    "grammar": "cloze",
    "context": "reading",
    "discourse": "reading",
    "detail": "reading",
    "inference": "reading",
    "main_idea": "reading",
    "attitude": "reading",
    "trap": "",
    "carelessness": "",
    "uncertain": "",
}

_LEVEL_LABELS = {
    1: "基础薄弱，建议先巩固词汇与语法",
    2: "基础欠稳，需要系统补强",
    3: "基础扎实，进阶提升",
    4: "水平良好，冲刺高分",
    5: "优秀，保持稳定输出",
}


def assess_level(connection: sqlite3.Connection, aggregate: dict[str, Any]) -> dict[str, Any]:
    """基于匿名聚合统计做水平评估（1-5 分）。

    prompt 只输入 cause 分布与占比，绝不包含题目/选项/原文。
    """
    prompt = """
你是学习水平评估助手。输入只有匿名错题归因统计（不包含原题）。
请根据错误原因分布判断学习者当前水平：1 到 5 分。
- 1：基础薄弱（词汇/语法类错误占比高且数量多）
- 2：基础欠稳（仍大量词汇/语法错误）
- 3：基础扎实（词汇语法可控，但阅读策略类仍有短板）
- 4：水平良好（错误集中在细节/态度/干扰项等进阶点）
- 5：优秀（错误少且类型分散，多为审题疏忽）
只输出合法 JSON：{"overall": 3, "label": "一句话", "by_dimension": {"vocabulary": 3, "grammar": 3, "reading": 3, "listening": 3}}
by_dimension 只包含输入中出现的维度，取值 1-5。
""".strip()
    # 构建匿名统计：只保留 cause 分布，去掉 question 相关字段
    anonymous = {
        "question_count": aggregate.get("question_count", 0),
        "categories": [
            {"code": c.get("code"), "label": c.get("label"), "count": c.get("count"), "percentage": c.get("percentage")}
            for c in aggregate.get("categories", [])
        ],
        "uncertain_count": aggregate.get("uncertain_count", 0),
    }
    try:
        raw = chat_with_routing(
            connection,
            "wrong_diagnosis",
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(anonymous, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            max_tokens=1000,
        )
        parsed = json.loads(raw)
    except (ValueError, json.JSONDecodeError):
        # AI 失败时本地降级：按词法/语法错误占比估算
        return _fallback_level(aggregate)
    overall = parsed.get("overall") if isinstance(parsed, dict) else None
    try:
        overall = max(1, min(5, int(overall)))
    except (TypeError, ValueError):
        overall = _fallback_level(aggregate)["overall"]
    by_dimension = parsed.get("by_dimension") if isinstance(parsed, dict) else {}
    if not isinstance(by_dimension, dict):
        by_dimension = {}
    clean_dim = {}
    for key, value in by_dimension.items():
        try:
            clean_dim[str(key)[:40]] = max(1, min(5, int(value)))
        except (TypeError, ValueError):
            continue
    return {
        "overall": overall,
        "label": _LEVEL_LABELS.get(overall, "基础扎实，进阶提升"),
        "by_dimension": clean_dim,
    }


def _fallback_level(aggregate: dict[str, Any]) -> dict[str, Any]:
    """本地降级：按基础类错误占比估算水平（不调 AI）。"""
    total = aggregate.get("question_count", 0) or 1
    base_errors = sum(
        c.get("count", 0)
        for c in aggregate.get("categories", [])
        if c.get("code") in {"vocabulary", "collocation", "grammar"}
    )
    ratio = base_errors / total
    if ratio >= 0.5:
        overall = 1
    elif ratio >= 0.35:
        overall = 2
    elif ratio >= 0.2:
        overall = 3
    else:
        overall = 4
    return {"overall": overall, "label": _LEVEL_LABELS.get(overall, ""), "by_dimension": {}}


def build_recommendations(
    connection: sqlite3.Connection,
    aggregate: dict[str, Any],
    *,
    profile_id: int | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """按薄弱 cause 从题库筛选推荐练习（本地 SQL，不调 AI）。"""
    categories = aggregate.get("categories", [])
    if not categories:
        return []
    weak = [c for c in categories if c.get("count", 0) >= 3][:limit]
    if not weak:
        weak = categories[:limit]
    recommendations: list[dict[str, Any]] = []
    for category in weak:
        cause = category.get("code", "")
        unit_type = _CAUSE_TO_UNIT_TYPE.get(cause, "")
        if not unit_type:
            continue
        rows = connection.execute(
            """
            SELECT q.id, q.question_type, u.title, u.unit_type, p.year, p.profile_id
            FROM questions q
            JOIN units u ON u.id = q.unit_id
            JOIN papers p ON p.id = u.paper_id
            WHERE u.unit_type = ? AND p.deleted_at IS NULL
              AND (? = 0 OR p.profile_id = ?)
              AND q.id NOT IN (
                  SELECT question_id FROM wrong_stats WHERE wrong_count > 0
              )
            ORDER BY RANDOM()
            LIMIT 5
            """,
            (unit_type, profile_id or 0, profile_id or 0),
        ).fetchall()
        if not rows:
            # 无未做过的题：退而推荐同类型任意题
            rows = connection.execute(
                """
                SELECT q.id, q.question_type, u.title, u.unit_type, p.year, p.profile_id
                FROM questions q
                JOIN units u ON u.id = q.unit_id
                JOIN papers p ON p.id = u.paper_id
                WHERE u.unit_type = ? AND p.deleted_at IS NULL
                ORDER BY RANDOM()
                LIMIT 5
                """,
                (unit_type,),
            ).fetchall()
        if rows:
            recommendations.append(
                {
                    "cause": cause,
                    "label": CAUSE_LABELS.get(cause, cause),
                    "suggestion": CAUSE_GUIDANCE.get(cause, ""),
                    "question_ids": [row["id"] for row in rows],
                    "sample_questions": [
                        {
                            "id": row["id"],
                            "year": row["year"],
                            "unit": row["title"],
                            "type": row["question_type"],
                        }
                        for row in rows[:3]
                    ],
                }
            )
    return recommendations


def compare_snapshots(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    """与上次报告对比（本地计算，不调 AI）。"""
    if not previous:
        return {"has_previous": False, "improved": [], "worsened": [], "new": []}
    prev_counts = {
        c.get("code"): c.get("count", 0)
        for c in (previous.get("categories") or [])
    }
    curr_counts = {
        c.get("code"): c.get("count", 0)
        for c in (current.get("categories") or [])
    }
    improved = [
        code for code, count in curr_counts.items()
        if count < prev_counts.get(code, 0)
    ]
    worsened = [
        code for code, count in curr_counts.items()
        if count > prev_counts.get(code, 0)
    ]
    new = [
        code for code in curr_counts
        if code not in prev_counts and code != "uncertain"
    ]
    return {
        "has_previous": True,
        "improved": improved,
        "worsened": worsened,
        "new": new,
    }


def build_report_text(
    aggregate: dict[str, Any],
    level: dict[str, Any],
    trend: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> str:
    """本地模板组装文字报告（不调 AI，省一次调用 ~20s）。"""
    total = aggregate.get("question_count", 0)
    categories = aggregate.get("categories", [])
    top = categories[0] if categories else {"code": "uncertain", "label": "证据不足", "percentage": 0}
    lines: list[str] = []

    lines.append("### 1. 当前主要短板")
    if categories:
        parts = "、".join(f"{c.get('label', c.get('code'))}（{c.get('percentage', 0):.0f}%）" for c in categories[:3])
        lines.append(f"本次共诊断 **{total} 题**，归因分布：{parts}。")
    top_guidance = CAUSE_GUIDANCE.get(top.get("code", ""), "")
    if top_guidance:
        lines.append(f"最突出的问题是 **{top.get('label', top.get('code'))}**：{top_guidance}")

    level_num = level.get("overall") if isinstance(level, dict) else None
    lines.append("")
    lines.append("### 2. 当前水平")
    if level_num:
        label = _LEVEL_LABELS.get(level_num, "")
        lines.append(f"评估为 **{level_num}/5**：{label}")

    lines.append("")
    lines.append("### 3. 复习建议")
    if recommendations:
        for rec in recommendations[:3]:
            lines.append(f"- **{rec.get('label')}**：{rec.get('suggestion', '')}（已为你挑选 {len(rec.get('question_ids', []))} 道同类型练习）")
    else:
        lines.append("本次未识别出明确的薄弱环节，建议保持当前节奏，继续积累作答记录后再诊断。")

    if trend.get("has_previous"):
        lines.append("")
        lines.append("### 4. 对比上次")
        if trend.get("improved"):
            lines.append(f"- 改善：{'、'.join(trend['improved'])}")
        if trend.get("worsened"):
            lines.append(f"- 恶化：{'、'.join(trend['worsened'])}")
        if trend.get("new"):
            lines.append(f"- 新增：{'、'.join(trend['new'])}")
        if not trend.get("improved") and not trend.get("worsened") and not trend.get("new"):
            lines.append("- 与上次基本持平")

    if aggregate.get("uncertain_count", 0):
        lines.append("")
        lines.append("### 5. 说明")
        lines.append("有部分题目证据不足未能确定归因——继续作答后可提升诊断准确度。")

    return "\n".join(lines)


def generate_diagnostic_report(
    connection: sqlite3.Connection,
    question_ids: list[int],
    *,
    previous_report_id: int | None = None,
    profile_id: int | None = None,
) -> dict[str, Any]:
    """完整诊断报告流程：归因 → 聚合 → level → recommendations → trend → 持久化。"""
    diagnoses, _ = diagnose_wrong_answers(connection, question_ids)
    aggregate = aggregate_diagnoses(diagnoses)
    level = assess_level(connection, aggregate)
    recommendations = build_recommendations(connection, aggregate, profile_id=profile_id)
    previous = None
    if previous_report_id:
        row = connection.execute(
            "SELECT aggregate_data FROM diagnostic_reports WHERE id = ?",
            (previous_report_id,),
        ).fetchone()
        if row:
            try:
                previous = json.loads(row["aggregate_data"] or "{}")
            except json.JSONDecodeError:
                previous = None
    trend = compare_snapshots(previous, aggregate)
    # 文字报告：本地模板组装（不调 AI，生成速度从 ~80s 降到 ~60s）
    report = build_report_text(aggregate, level, trend, recommendations)
    report_id = _save_report(
        connection,
        question_ids=question_ids,
        aggregate=aggregate,
        level=level,
        recommendations=recommendations,
        trend=trend,
        report=report,
        profile_id=profile_id,
    )
    return {
        "id": report_id,
        "question_count": aggregate["question_count"],
        "aggregate": aggregate,
        "level": level,
        "recommendations": recommendations,
        "trend": trend,
        "report": report,
        "created_at": date.today().isoformat(),
    }


def _save_report(
    connection: sqlite3.Connection,
    *,
    question_ids: list[int],
    aggregate: dict[str, Any],
    level: dict[str, Any],
    recommendations: list[dict[str, Any]],
    trend: dict[str, Any],
    report: str,
    profile_id: int | None = None,
) -> int:
    scope_key = f"diag-{profile_id or 0}-{date.today().isoformat()}"
    cursor = connection.execute(
        """
        INSERT INTO diagnostic_reports
            (scope_key, question_ids, input_snapshot, question_count,
             aggregate_data, level_data, recommendations, trend_data, report)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scope_key,
            json.dumps(question_ids, ensure_ascii=False),
            json.dumps({"profile_id": profile_id}, ensure_ascii=False),
            aggregate.get("question_count", 0),
            json.dumps(aggregate, ensure_ascii=False),
            json.dumps(level, ensure_ascii=False),
            json.dumps(recommendations, ensure_ascii=False),
            json.dumps(trend, ensure_ascii=False),
            report,
        ),
    )
    connection.commit()
    return int(cursor.lastrowid)


def load_diagnostic_report(
    connection: sqlite3.Connection,
    report_id: int,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM diagnostic_reports WHERE id = ?", (report_id,)
    ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "question_count": row["question_count"],
        "aggregate": json.loads(row["aggregate_data"] or "{}"),
        "level": json.loads(row["level_data"] or "{}"),
        "recommendations": json.loads(row["recommendations"] or "[]"),
        "trend": json.loads(row["trend_data"] or "{}"),
        "report": row["report"],
        "created_at": row["created_at"],
    }


def list_diagnostic_reports(
    connection: sqlite3.Connection,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, scope_key, question_count, created_at
        FROM diagnostic_reports
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]
