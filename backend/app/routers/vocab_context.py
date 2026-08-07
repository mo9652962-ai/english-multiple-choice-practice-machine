"""词文串学 (v2.23) — 扇贝式: 学词后在真题语境中巩固
搜索该词在题库 passage 中出现的句子 + 出处
"""
from __future__ import annotations

import re
import sqlite3
from fastapi import APIRouter, Depends

from ..database import get_db

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


@router.get("/{entry_id}/context")
def get_word_context(
    entry_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> dict:
    """返回该词在真题文章中出现的句子(最多 6 条)"""
    entry = connection.execute(
        "SELECT id, term, lemma FROM vocabulary_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if entry is None:
        return {"contexts": [], "term": ""}

    term = entry["term"]
    lemma = entry["lemma"] or term
    # 匹配词形: 词根/原型/复数等 (简单正则: 词首+词尾, 忽略大小写)
    pattern = re.compile(
        r"\b" + re.escape(lemma) + r"(?:s|es|ed|ing|d|'s)?\b", re.IGNORECASE
    )

    rows = connection.execute(
        """SELECT u.id AS unit_id, u.title, u.unit_type, u.passage,
                  p.year, qb.name AS profile_name
           FROM units u
           JOIN papers p ON p.id = u.paper_id
           JOIN question_bank_profiles qb ON qb.id = p.profile_id
           WHERE u.passage IS NOT NULL AND u.passage != ''
           ORDER BY p.year DESC, u.id DESC
           LIMIT 400"""
    ).fetchall()

    contexts = []
    for row in rows:
        try:
            text = row["passage"]
            if isinstance(text, str):
                text = text
            else:
                continue
        except Exception:
            continue
        # 按句子切分 (简单: 句号/问号/叹号 + 空格)
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            if len(s) < 15 or len(s) > 300:
                continue
            m = pattern.search(s)
            if m:
                contexts.append({
                    "sentence": s.strip(),
                    "highlight": m.group(0),
                    "source": f"{row['profile_name']} {row['year']}年 {row['title']}",
                    "unit_id": row["unit_id"],
                })
                if len(contexts) >= 6:
                    break
        if len(contexts) >= 6:
            break

    return {"term": term, "contexts": contexts}