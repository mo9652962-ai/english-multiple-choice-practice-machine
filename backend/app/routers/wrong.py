from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from html import escape as html_escape

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


@router.get("/export/html")
def export_wrong_html(connection: sqlite3.Connection = Depends(get_db)):
    """v2.37: 可打印错题卷 (粉笔式出卷) — A4 打印友好 HTML + 答案附后"""
    profile_id = get_active_profile_id(connection)
    rows = connection.execute(
        """
        SELECT questions.id AS question_id, questions.number, questions.stem,
               questions.answer, questions.metadata,
               units.title AS unit_title, units.unit_type,
               papers.year, wrong_stats.wrong_count
        FROM wrong_stats
        JOIN questions ON questions.id = wrong_stats.question_id
        JOIN units ON units.id = questions.unit_id
        JOIN papers ON papers.id = units.paper_id
        WHERE wrong_stats.wrong_count > 0
          AND papers.profile_id = ?
          AND papers.deleted_at IS NULL
        ORDER BY wrong_stats.wrong_count DESC, wrong_stats.last_wrong_at DESC
        """,
        (profile_id,),
    ).fetchall()

    cards = []
    for i, row in enumerate(rows, 1):
        meta = json.loads(row["metadata"] or "{}")
        options = meta.get("options") or {}
        opts_html = ""
        for key in ("A", "B", "C", "D"):
            if key in options:
                opts_html += f'<div class="opt"><span class="opt-key">{key}.</span> {html_escape(str(options[key]))}</div>'
        analysis = (meta.get("analysis") or meta.get("explanation") or meta.get("解析") or "").strip()
        cards.append(f"""
<div class="paper-item">
  <div class="paper-head"><span class="paper-no">{i}</span><span class="paper-src">{row['year']}年 · {row['unit_type']} · 错 {row['wrong_count']} 次</span></div>
  <div class="paper-stem">{html_escape(row['stem'] or '')}</div>
  <div class="paper-opts">{opts_html}</div>
  <div class="paper-answer-line"><span class="paper-ans">答案：{html_escape(row['answer'] or '')}</span></div>
  {f'<div class="paper-analysis"><b>解析：</b>{html_escape(analysis)}</div>' if analysis else ''}
</div>""")

    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>错题卷 {__import__('datetime').date.today().isoformat()}</title>
<style>
  body {{ font-family: 'SimSun','Songti SC',serif; color:#222; margin:24px; max-width:820px; }}
  h1 {{ font-size:20px; border-bottom:2px solid #c73e3a; padding-bottom:8px; }}
  .paper-meta {{ color:#666; font-size:12px; margin-bottom:18px; }}
  .paper-item {{ margin-bottom:22px; page-break-inside:avoid; }}
  .paper-head {{ display:flex; justify-content:space-between; font-size:13px; color:#888; margin-bottom:6px; }}
  .paper-no {{ font-weight:800; color:#c73e3a; }}
  .paper-stem {{ font-size:14px; line-height:1.8; margin-bottom:8px; }}
  .paper-opts {{ margin:6px 0 8px 18px; }}
  .opt {{ font-size:13px; line-height:1.7; }}
  .opt-key {{ font-weight:700; }}
  .paper-answer-line {{ font-size:12px; color:#3e6b52; margin-top:4px; }}
  .paper-analysis {{ font-size:12px; color:#555; background:#f7f3ee; padding:8px 10px; border-radius:6px; margin-top:6px; }}
  @media print {{ body {{ margin:0; }} .paper-item {{ page-break-inside:avoid; }} }}
</style></head><body>
<h1>📝 英语错题卷</h1>
<div class="paper-meta">共 {len(rows)} 道错题 · 按错误次数排序 · 生成于 {__import__('datetime').date.today().isoformat()} · 打印后可直接自测</div>
{''.join(cards)}
</body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html, headers={"Content-Disposition": "inline; filename=wrong-paper.html"})


@router.get("/stats")
def wrong_stats(connection: sqlite3.Connection = Depends(get_db)) -> dict:
    """v2.42: 错题统计 — 高频错题 TOP10 + 类型分布 + 错因标签 (猿题库考点归因)"""
    top = connection.execute(
        """SELECT q.id, q.stem, q.question_type, q.metadata,
                  ws.wrong_count, ws.attempt_count, ws.recent_results, ws.last_wrong_at,
                  units.title AS unit_title, units.unit_type, papers.year, papers.title AS paper_title
           FROM wrong_stats ws
           JOIN questions q ON q.id = ws.question_id
           LEFT JOIN units ON units.id = q.unit_id
           LEFT JOIN papers ON papers.id = units.paper_id
           WHERE ws.wrong_count > 0
           ORDER BY ws.wrong_count DESC, ws.last_wrong_at DESC
           LIMIT 10""").fetchall()
    items = []
    for r in top:
        meta = {}
        try:
            import json as _json
            meta = _json.loads(r["metadata"] or "{}")
        except Exception:
            pass
        # 错因标签: 基于 recent_results (T/F 序列)
        recent = (r["recent_results"] or "").upper()
        if recent.endswith("T") and r["wrong_count"] <= 1:
            reason = "已掌握"
            reason_icon = "✅"
        elif r["wrong_count"] >= 3:
            reason = "反复出错"
            reason_icon = "🔁"
        elif r["attempt_count"] >= 3:
            reason = "易错点"
            reason_icon = "⚠️"
        else:
            reason = "偶尔失误"
            reason_icon = "🌱"
        items.append({
            "id": r["id"],
            "stem": r["stem"][:60],
            "question_type": r["question_type"],
            "wrong_count": r["wrong_count"],
            "attempt_count": r["attempt_count"],
            "reason": reason,
            "reason_icon": reason_icon,
            "unit_type": r["unit_type"],
            "unit_title": r["unit_title"],
            "year": r["year"],
            "paper_title": r["paper_title"],
            "last_wrong_at": r["last_wrong_at"],
            "has_explanation": bool(meta.get("explanation")),
        })
    # 类型分布
    by_type = connection.execute(
        """SELECT units.unit_type, COUNT(*) n
           FROM wrong_stats ws JOIN questions q ON q.id = ws.question_id
           LEFT JOIN units ON units.id = q.unit_id
           WHERE ws.wrong_count > 0
           GROUP BY units.unit_type ORDER BY n DESC""").fetchall()
    return {"top": items, "by_type": [{"type": r[0], "count": r[1]} for r in by_type]}
