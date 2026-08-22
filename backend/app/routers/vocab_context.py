"""词文串学 (v2.23) — 扇贝式: 学词后在真题语境中巩固
搜索该词在题库 passage 中出现的句子 + 出处
"""
from __future__ import annotations

import re
import sqlite3
from fastapi import APIRouter, Depends

from ..database import get_db
from .auth import maybe_require_user

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


@router.get("/{entry_id}/context")
def get_word_context(
    entry_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """返回该词在真题文章中出现的句子(最多 6 条)"""
    entry = connection.execute(
        "SELECT id, term, lemma FROM vocabulary_entries WHERE id = ? AND user_id IS ?",
        (entry_id, _current_user_id(user)),
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
        # v2.36: 文章风格分类 (薄荷阅读/可栗式: 按内容特征打风格标签)
        style = _detect_style(text)
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
                    "style": style,
                })
                if len(contexts) >= 6:
                    break
        if len(contexts) >= 6:
            break

    return {"term": term, "contexts": contexts}


def _detect_style(text: str) -> str:
    """v2.36: 规则式文章风格分类 (真题阅读)
    访谈(引号对话)/论述(研究证据)/新闻(数据事实)/故事(叙事)
    """
    t = (text or "")[:600].lower()
    quote_count = t.count('"') + t.count("'")
    if quote_count >= 4 and any(w in t for w in ["said", "says", "asked", "told", "interview"]):
        return "interview"
    if any(w in t for w in ["according to", "research", "study", "found that", "researchers", "survey"]):
        return "argument"
    if any(w in t for w in ["percent", "million", "billion", "data", "report", "statistics"]):
        return "news"
    # v2.36: 词边界匹配 (子串会误判, 如 "concept" 含 "once")
    if any(re.search(r"\b" + re.escape(w) + r"\b", t) for w in ["once", "story", "remember", "childhood", "years ago", "when i was"]):
        return "story"
    return "article"