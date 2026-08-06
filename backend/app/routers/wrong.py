from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_active_profile_id, get_db


router = APIRouter(prefix="/wrong", tags=["wrong"])


@router.get("")
def list_wrong(connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    profile_id = get_active_profile_id(connection)
    rows = connection.execute(
        """
        SELECT questions.id AS question_id, questions.number, questions.stem,
               units.id AS unit_id, units.title AS unit_title, units.unit_type,
               papers.year, wrong_stats.*
        FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE wrong_stats.wrong_count > 0
          AND papers.profile_id = ?
          AND papers.deleted_at IS NULL
        ORDER BY wrong_stats.manually_frequent DESC,
                 wrong_stats.wrong_count DESC,
                 wrong_stats.last_wrong_at DESC
        """,
        (profile_id,),
    ).fetchall()
    result = []
    for row in rows:
        payload = dict(row)
        recent = json.loads(payload.pop("recent_results") or "[]")
        recent_wrong = sum(not value for value in recent)
        payload["recent_results"] = recent
        payload["is_frequent"] = bool(
            payload["manually_frequent"]
            or payload["wrong_count"] >= 3
            or (len(recent) >= 5 and recent_wrong >= 3)
        )
        result.append(payload)
    return result


@router.put("/{question_id}/frequent")
def mark_frequent(
    question_id: int,
    enabled: bool = True,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, bool]:
    cursor = connection.execute(
        """
        UPDATE wrong_stats
        SET manually_frequent = ?
        WHERE question_id = ?
        """,
        (int(enabled), question_id),
    )
    if cursor.rowcount == 0:
        raise HTTPException(404, "错题不存在")
    connection.commit()
    return {"updated": True}


@router.get("/export")
def export_wrong(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """导出错题为 Markdown（可复制到任何 AI 分析/打印）"""
    profile_id = get_active_profile_id(connection)
    rows = connection.execute(
        """
        SELECT questions.id AS question_id, questions.number, questions.stem,
               questions.answer, questions.metadata,
               units.id AS unit_id, units.title AS unit_title, units.unit_type,
               papers.year, wrong_stats.wrong_count, wrong_stats.recent_results
        FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE wrong_stats.wrong_count > 0
          AND papers.profile_id = ?
          AND papers.deleted_at IS NULL
        ORDER BY wrong_stats.wrong_count DESC,
                 wrong_stats.last_wrong_at DESC
        """,
        (profile_id,),
    ).fetchall()

    lines = [
        "# 错题导出",
        "",
        f"> 共 {len(rows)} 道错题 · 生成于 {__import__('datetime').date.today().isoformat()}",
        "",
    ]
    for i, row in enumerate(rows, 1):
        meta = json.loads(row["metadata"] or "{}")
        options = meta.get("options") or {}
        wrong_count = row["wrong_count"]
        lines.append(f"## {i}. {row['year']} {row['unit_type']} · 错 {wrong_count} 次")
        lines.append("")
        lines.append(f"**题干**: {row['stem']}")
        if options:
            lines.append("")
            for key in ("A", "B", "C", "D"):
                if key in options:
                    lines.append(f"- {key}. {options[key]}")
        lines.append("")
        lines.append(f"**正确答案**: {row['answer']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    markdown = "\n".join(lines)
    return {
        "format": "markdown",
        "count": len(rows),
        "markdown": markdown,
    }
