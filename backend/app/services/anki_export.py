# -*- coding: utf-8 -*-
"""AI 英语刷题机 — 单词本导出 Anki 牌组 (.apkg)

参考 (2026-08 研究):
  - genanki: Python 生成 Anki 牌组的标准库
  - SelectAndTranslate: 从阅读中自动收集词汇 + 上下文导出 Anki
  - Anki 600M+ 用户生态: 导出后可用 Anki/AnkiMobile 复习，FSRS 兼容

设计:
  - 单词本 → Anki 卡片: 正面=单词, 背面=释义+真题原句+语境
  - 支持按状态过滤 (all/mastered/learning)
  - 输出 .apkg 文件到本地 exports/ 目录
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date
from pathlib import Path

import genanki

# Anki 模型: 单词卡 (正面单词, 背面释义+语境)
_MODEL_ID = 1970010101
_MODEL = genanki.Model(
    _MODEL_ID,
    "AI 英语刷题机单词卡",
    fields=[
        {"name": "Word"},
        {"name": "Phonetic"},
        {"name": "Meaning"},
        {"name": "Context"},
        {"name": "Source"},
    ],
    templates=[
        {
            "name": "Card 1",
            "qfmt": "<div style='font-size:28px;font-weight:bold'>{{Word}}</div>"
                    "<div style='color:#888'>{{Phonetic}}</div>",
            "afmt": "{{FrontSide}}<hr id=answer>"
                    "<div style='font-size:18px'>{{Meaning}}</div>"
                    "<div style='color:#666;font-style:italic;margin-top:8px'>{{Context}}</div>"
                    "<div style='color:#999;font-size:12px;margin-top:6px'>{{Source}}</div>",
        }
    ],
    css="""
    .card { font-family: 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif; }
    """,
)


def export_anki(
    connection: sqlite3.Connection,
    status_filter: str = "all",
    output_dir: str | None = None,
    user_id: int | None = None,
) -> dict:
    """导出单词本为 Anki .apkg 文件
    
    Args:
        connection: 数据库连接
        status_filter: "all" | "mastered" | "learning"
        output_dir: 输出目录 (默认 exports/)
    
    Returns:
        {"file": path, "count": N, "notes": [...]}
    """
    # 查询单词
    where = "WHERE user_id IS ?"
    params: list = [user_id]
    if status_filter in ("mastered", "learning"):
        where += " AND study_status = ?"
        params.append(status_filter)

    rows = connection.execute(
        f"""SELECT term, lemma, phonetic, common_meaning, contextual_meaning,
                   part_of_speech, study_status, encounter_count,
                   (SELECT context_sentence FROM vocabulary_occurrences
                    WHERE entry_id = vocabulary_entries.id
                    ORDER BY id DESC LIMIT 1) AS latest_sentence
            FROM vocabulary_entries
            {where}
            ORDER BY encounter_count DESC""",
        params,
    ).fetchall()

    if not rows:
        return {"file": None, "count": 0, "notes": []}

    # 生成牌组 (每次用固定 ID 以便重复导入覆盖)
    deck_id = 2059400110
    deck = genanki.Deck(deck_id, "AI英语刷题机-单词本")

    notes = []
    for row in rows:
        word = row["lemma"] or row["term"]
        phonetic = row["phonetic"] or ""
        meaning = row["common_meaning"] or row["contextual_meaning"] or ""
        context = row["latest_sentence"] or ""
        pos = row["part_of_speech"] or ""
        source = f"真题遇见 {row['encounter_count']} 次"

        # 语境释义作为补充
        if (
            row["contextual_meaning"]
            and row["contextual_meaning"] != row["common_meaning"]
        ):
            meaning += f"<br><b>语境:</b> {row['contextual_meaning']}"
        if pos:
            meaning = f"<i>{pos}</i><br>{meaning}"

        note = genanki.Note(
            model=_MODEL,
            fields=[word, phonetic, meaning, context, source],
        )
        notes.append(note)
        deck.add_note(note)

    # 输出路径
    out_dir = Path(output_dir) if output_dir else Path("exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"vocabulary-{date.today().isoformat()}-{status_filter}.apkg"
    out_path = out_dir / fname

    package = genanki.Package(deck)
    package.write_to_file(str(out_path))

    return {
        "file": str(out_path.resolve()),
        "filename": fname,
        "count": len(notes),
        "deck": "AI英语刷题机-单词本",
    }
