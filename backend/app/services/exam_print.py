"""墨题考场真题与错题攻坚卷双栏排版导出引擎：
生成出版级 A4 标准考场双栏试卷、答题卡与解析册 HTML，支持一键打印与导出为 PDF。
"""

from __future__ import annotations

import html
import re
import sqlite3
from typing import Any

from .questions import serialize_unit


def _format_passage(passage: str | None) -> str:
    if not passage:
        return ""
    paragraphs = [p.strip() for p in passage.split("\n") if p.strip()]
    formatted = []
    for p in paragraphs:
        # 完形填空空位标记美化：将 {blank:N} 或 {{blank:N}} 转为带下划线的考号
        p_clean = re.sub(r"\{+blank:(\d+)\}+", r'<span class="exam-blank">______<b>\1</b>______</span>', p)
        formatted.append(f"<p>{p_clean}</p>")
    return "\n".join(formatted)


def generate_paper_print_html(
    connection: sqlite3.Connection,
    paper_id: int,
    *,
    include_answers: bool = True,
    title_override: str | None = None,
) -> str:
    paper = connection.execute(
        "SELECT * FROM papers WHERE id = ? AND deleted_at IS NULL", (paper_id,)
    ).fetchone()
    if not paper:
        raise LookupError(f"未找到试卷: id={paper_id}")

    unit_rows = connection.execute(
        "SELECT id FROM units WHERE paper_id = ? ORDER BY sequence, id", (paper_id,)
    ).fetchall()

    units = [
        serialize_unit(connection, u["id"], shuffle_options=False, include_answers=True)
        for u in unit_rows
    ]

    title = title_override or paper["title"]
    year = paper["year"]
    subject = paper["subject"] or "英语"

    return render_exam_html(
        title=title,
        year=year,
        subject=subject,
        units=units,
        include_answers=include_answers,
    )


def generate_wrong_questions_print_html(
    connection: sqlite3.Connection,
    question_ids: list[int],
    *,
    title: str = "考研英语 · 错题专项攻坚卷",
    user_id: int | None = None,
) -> str:
    if not question_ids:
        raise ValueError("题目列表不能为空")

    placeholders = ",".join("?" for _ in question_ids)
    rows = connection.execute(
        f"""
        SELECT q.id, q.unit_id, q.number, q.stem, q.score, q.answer, q.metadata,
               u.title AS unit_title, u.unit_type, u.passage,
               p.year, p.subject, p.title AS paper_title
        FROM questions q
        JOIN units u ON u.id = q.unit_id
        JOIN papers p ON p.id = u.paper_id
        WHERE q.id IN ({placeholders})
        ORDER BY p.year DESC, u.sequence, q.sequence
        """,
        question_ids,
    ).fetchall()

    if not rows:
        raise LookupError("未找到匹配的错题记录")

    from .questions import parse_json

    # 按单元聚类
    units_map: dict[int, dict[str, Any]] = {}
    for r in rows:
        uid = r["unit_id"]
        if uid not in units_map:
            units_map[uid] = {
                "id": uid,
                "title": f"{r['year']} {r['paper_title']} · {r['unit_title']}",
                "unit_type": r["unit_type"],
                "passage": r["passage"],
                "questions": [],
            }
        # 查 options
        opt_rows = connection.execute(
            "SELECT stable_key, original_label, content, sequence FROM options WHERE question_id = ? ORDER BY sequence",
            (r["id"],),
        ).fetchall()
        options = [
            {
                "label": o["original_label"] or chr(65 + idx),
                "key": o["stable_key"],
                "content": o["content"],
            }
            for idx, o in enumerate(opt_rows)
        ]
        meta = parse_json(r["metadata"], {})
        analysis = meta.get("analysis") or meta.get("explanation") or meta.get("reasoning") or ""
        units_map[uid]["questions"].append({
            "id": r["id"],
            "number": r["number"],
            "stem": r["stem"],
            "options": options,
            "answer": r["answer"],
            "analysis": analysis,
            "score": r["score"],
        })

    units = list(units_map.values())
    return render_exam_html(
        title=title,
        year=rows[0]["year"],
        subject="考研英语",
        units=units,
        include_answers=True,
    )


def render_exam_html(
    *,
    title: str,
    year: int,
    subject: str,
    units: list[dict[str, Any]],
    include_answers: bool = True,
) -> str:
    all_questions: list[dict[str, Any]] = []
    for u in units:
        all_questions.extend(u.get("questions", []))

    total_q = len(all_questions)

    # 渲染试卷主体
    sections_html = []
    for idx, u in enumerate(units):
        u_type = u.get("unit_type", "")
        u_title = u.get("title", f"Unit {idx+1}")
        passage_html = _format_passage(u.get("passage"))

        q_items = []
        for q in u.get("questions", []):
            q_num = q.get("number") or ""
            stem = html.escape(q.get("stem") or "")
            opts_html = []
            for opt in q.get("options", []):
                lbl = html.escape(str(opt.get("label") or opt.get("key") or ""))
                content = html.escape(str(opt.get("content") or ""))
                opts_html.append(f'<span class="exam-option"><b>[{lbl}]</b> {content}</span>')

            q_items.append(f"""
            <div class="exam-question-item">
              <div class="exam-q-stem"><b>{q_num}.</b> {stem}</div>
              <div class="exam-options-grid">{' '.join(opts_html)}</div>
            </div>
            """)

        sections_html.append(f"""
        <section class="exam-section">
          <div class="exam-section-title">■ {html.escape(u_title)}</div>
          {f'<div class="exam-passage">{passage_html}</div>' if passage_html else ''}
          <div class="exam-questions-list">
            {''.join(q_items)}
          </div>
        </section>
        """)

    # 渲染标准答题卡
    bubble_rows = []
    for q in all_questions:
        q_num = q.get("number") or ""
        bubble_rows.append(f"""
        <div class="bubble-card-item">
          <span class="q-no">{q_num}</span>
          <span class="bubble">[A]</span>
          <span class="bubble">[B]</span>
          <span class="bubble">[C]</span>
          <span class="bubble">[D]</span>
        </div>
        """)

    # 渲染参考答案与试题精析
    answer_items = []
    for q in all_questions:
        q_num = q.get("number") or ""
        ans = html.escape(str(q.get("answer") or "略"))
        analysis = html.escape(str(q.get("analysis") or "暂无详细解析"))
        answer_items.append(f"""
        <div class="answer-key-row">
          <div class="key-head"><b>第 {q_num} 题</b> <span class="badge-ans">正确答案: {ans}</span></div>
          <div class="key-analysis">{analysis}</div>
        </div>
        """)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)} - 墨题考场打印版</title>
  <style>
    @page {{
      size: A4;
      margin: 14mm 12mm 14mm 12mm;
    }}
    * {{
      box-sizing: border-box;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    body {{
      font-family: "Times New Roman", "SimSun", "Songti SC", serif;
      font-size: 10.5pt;
      line-height: 1.5;
      color: #111;
      background: #fdfdfd;
      margin: 0;
      padding: 0;
    }}
    .no-print {{
      position: sticky;
      top: 0;
      z-index: 999;
      background: #1e293b;
      color: #f8fafc;
      padding: 10px 20px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 10px rgba(0,0,0,0.15);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }}
    .no-print button {{
      background: #3b82f6;
      color: #fff;
      border: none;
      padding: 6px 16px;
      font-size: 13px;
      font-weight: 500;
      border-radius: 4px;
      cursor: pointer;
    }}
    .no-print button:hover {{ background: #2563eb; }}
    @media print {{
      .no-print {{ display: none !important; }}
      body {{ background: #fff; }}
      .page-break {{ page-break-before: always; break-before: page; }}
    }}
    .exam-wrapper {{
      max-width: 210mm;
      margin: 0 auto;
      padding: 10mm 15mm;
    }}
    /* 试卷头 */
    .exam-header {{
      text-align: center;
      border-bottom: 2pt solid #222;
      padding-bottom: 8px;
      margin-bottom: 12px;
    }}
    .secret-tag {{
      font-size: 9pt;
      font-weight: bold;
      letter-spacing: 2px;
      text-align: left;
      margin-bottom: 4px;
    }}
    .exam-main-title {{
      font-size: 16pt;
      font-weight: bold;
      margin: 4px 0;
      letter-spacing: 1px;
    }}
    .exam-sub-title {{
      font-size: 12pt;
      font-weight: bold;
      margin-bottom: 8px;
    }}
    .examinee-bar {{
      display: flex;
      justify-content: space-around;
      font-size: 10pt;
      margin-top: 6px;
      padding: 4px 0;
      border-top: 0.5pt solid #888;
    }}
    .exam-notice {{
      font-size: 8.5pt;
      color: #444;
      border: 0.5pt dashed #999;
      padding: 6px 10px;
      margin-bottom: 14px;
      line-height: 1.4;
    }}
    /* 双栏正文排版 */
    .paper-columns {{
      column-count: 2;
      column-gap: 10mm;
      column-rule: 0.5pt solid #ccc;
      text-align: justify;
    }}
    .exam-section {{
      break-inside: avoid-column;
      margin-bottom: 14px;
    }}
    .exam-section-title {{
      font-size: 11pt;
      font-weight: bold;
      background: #f1f5f9;
      padding: 3px 6px;
      margin-bottom: 6px;
      border-left: 3pt solid #334155;
    }}
    .exam-passage {{
      font-size: 9.5pt;
      line-height: 1.45;
      margin-bottom: 10px;
    }}
    .exam-passage p {{
      text-indent: 2em;
      margin: 4px 0;
    }}
    .exam-blank {{
      text-decoration: underline;
      font-weight: bold;
      padding: 0 4px;
    }}
    .exam-question-item {{
      break-inside: avoid;
      margin-bottom: 8px;
      font-size: 9.5pt;
    }}
    .exam-q-stem {{
      margin-bottom: 3px;
    }}
    .exam-options-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 2px 6px;
      font-size: 9pt;
      padding-left: 8px;
    }}
    .exam-option {{
      white-space: normal;
    }}
    /* 答题卡 */
    .answer-sheet-container {{
      border: 1pt solid #222;
      padding: 10px;
      margin-top: 15px;
      background: #fafafa;
    }}
    .sheet-title {{
      text-align: center;
      font-size: 12pt;
      font-weight: bold;
      margin-bottom: 8px;
    }}
    .sheet-grid {{
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 6px 8px;
      font-size: 8.5pt;
    }}
    .bubble-card-item {{
      display: flex;
      align-items: center;
      gap: 3px;
      border: 0.5pt solid #ddd;
      padding: 2px 4px;
      background: #fff;
    }}
    .q-no {{
      font-weight: bold;
      width: 20px;
      text-align: right;
    }}
    .bubble {{
      font-family: monospace;
      color: #555;
    }}
    /* 参考答案与解析册 */
    .answer-key-wrapper {{
      margin-top: 20px;
      padding-top: 12px;
      border-top: 2pt solid #222;
    }}
    .answer-key-row {{
      break-inside: avoid;
      border-bottom: 0.5pt solid #eee;
      padding: 6px 0;
      font-size: 9.5pt;
    }}
    .badge-ans {{
      color: #059669;
      font-weight: bold;
      margin-left: 8px;
    }}
    .key-analysis {{
      font-size: 8.5pt;
      color: #444;
      margin-top: 2px;
      line-height: 1.4;
    }}
  </style>
</head>
<body>
  <div class="no-print">
    <span>🖨️ <b>墨题考场试卷排版系统</b>（已自动对齐 A4 双栏规格）</span>
    <div>
      <button onclick="window.print()">立即打印 / 存为 PDF (Ctrl+P)</button>
    </div>
  </div>

  <div class="exam-wrapper">
    <div class="secret-tag">绝密 ★ 启用前</div>
    <header class="exam-header">
      <div class="exam-main-title">{year} 年全国硕士研究生招生考试</div>
      <div class="exam-sub-title">{html.escape(title)}</div>
      <div class="examinee-bar">
        <span>考生姓名：____________________</span>
        <span>准考证号：____________________</span>
        <span>得分：________</span>
      </div>
    </header>

    <div class="exam-notice">
      <b>考生须知：</b><br>
      1. 答题前，考生务必将姓名、准考证号填写清楚。<br>
      2. 客观选择题必须使用 2B 铅笔填涂；严禁折叠答题卡。<br>
      3. 考试时间 180 分钟，满分 100 分。严格遵守考场纪律，诚信应考。
    </div>

    <!-- 双栏试卷主体 -->
    <div class="paper-columns">
      {''.join(sections_html)}
    </div>

    <!-- 答题卡区 -->
    <div class="page-break"></div>
    <div class="answer-sheet-container">
      <div class="sheet-title">标准客观题答题卡（共 {total_q} 题）</div>
      <div class="sheet-grid">
        {''.join(bubble_rows)}
      </div>
    </div>

    <!-- 参考答案与解析册 -->
    <div class="page-break"></div>
    <div class="answer-key-wrapper">
      <div class="exam-main-title" style="font-size: 14pt; margin-bottom: 12px;">参考答案与试题精析</div>
      <div class="paper-columns">
        {''.join(answer_items)}
      </div>
    </div>
  </div>
</body>
</html>
"""
