"""短文填词 (v2.32, 扇贝式借鉴) — 基于已学词汇 + 真题语境自动生成选词填空
取学习中/生词 → 真题文章句子挖空 → 4 选项(正确词+3干扰) → 答题判分
"""
from __future__ import annotations

import random
import re
import sqlite3
from fastapi import APIRouter, Depends

from ..database import get_db
from .auth import maybe_require_user

router = APIRouter(prefix="/vocab/cloze", tags=["vocab-cloze"])


def _current_user_id(user: dict | None) -> int | None:
    return user["id"] if user else None


def _pick_target_words(conn: sqlite3.Connection, limit: int = 8, user_id: int | None = None) -> list[dict]:
    """挑选学习中的单词作为挖空目标 (优先生词/学习中, 避免已掌握)"""
    rows = conn.execute("""
        SELECT id, term AS word, phonetic, part_of_speech,
               COALESCE(common_meaning, contextual_meaning, '') AS meaning,
               study_status
        FROM vocabulary_entries
        WHERE user_id IS ? AND term IS NOT NULL AND term != ''
          AND COALESCE(study_status, '') != 'mastered'
        ORDER BY CASE WHEN COALESCE(study_status,'')='new' THEN 0
                      WHEN COALESCE(study_status,'')='learning' THEN 1 ELSE 2 END,
                 RANDOM()
        LIMIT ?
    """, (user_id, limit)).fetchall()
    if not rows:
        rows = conn.execute("""
            SELECT id, term AS word, phonetic, part_of_speech,
                   COALESCE(common_meaning, contextual_meaning, '') AS meaning,
                   study_status
            FROM vocabulary_entries WHERE user_id IS ? AND term IS NOT NULL AND term != ''
            ORDER BY RANDOM() LIMIT ?
        """, (user_id, limit)).fetchall()
    return [dict(r) for r in rows]


def _find_context_sentence(conn: sqlite3.Connection, word: str) -> str | None:
    """从真题文章 passage 找包含该词(含词形变化)的句子"""
    lemma = word.rstrip("s")
    pattern = re.compile(r"\b" + re.escape(lemma) + r"(?:s|es|ed|ing|d|'s)?\b", re.IGNORECASE)
    rows = conn.execute("""
        SELECT u.passage FROM units u
        JOIN papers p ON p.id = u.paper_id
        WHERE u.passage IS NOT NULL AND u.passage != '' AND p.deleted_at IS NULL
        ORDER BY p.year DESC, u.id DESC LIMIT 400
    """).fetchall()
    for row in rows:
        text = row[0]
        if not isinstance(text, str):
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for s in sentences:
            if len(s) < 15 or len(s) > 300:
                continue
            if pattern.search(s):
                return s.strip()
    return None


def _build_sentence_with_blank(context: str, word: str) -> str:
    """把句子中的目标词(含词形)挖空"""
    lemma = word.rstrip("s")
    pat = re.compile(r"\b" + re.escape(lemma) + r"(?:s|es|ed|ing|d|'s)?\b", re.IGNORECASE)
    return pat.sub("____", context)


def _pick_distractors(conn: sqlite3.Connection, word: str, n: int = 3) -> list[str]:
    """挑干扰词: 同词性优先, 长度相近兜底"""
    distractors: list[str] = []
    pos_row = conn.execute(
        "SELECT part_of_speech FROM vocabulary_entries WHERE term = ? LIMIT 1",
        (word,),
    ).fetchone()
    pos = pos_row[0] if pos_row else ""
    rows = conn.execute("""
        SELECT term FROM vocabulary_entries
        WHERE term != ? AND length(term) BETWEEN length(?) - 5 AND length(?) + 5
          AND (? = '' OR part_of_speech = ?)
        ORDER BY RANDOM() LIMIT ?
    """, (word, word, word, pos, pos, n * 4)).fetchall()
    for r in rows:
        d = r[0]
        if d and d.lower() != word.lower() and d not in distractors:
            distractors.append(d)
        if len(distractors) >= n:
            break
    while len(distractors) < n:
        # 兜底：再随机取任意词（避免 "_____" 废选项）
        extra = conn.execute(
            "SELECT term FROM vocabulary_entries WHERE term != ? AND term != '' ORDER BY RANDOM() LIMIT 20",
            (word,),
        ).fetchall()
        for r in extra:
            d = r[0]
            if d.lower() != word.lower() and d not in distractors:
                distractors.append(d)
            if len(distractors) >= n:
                break
    return distractors[:n]


@router.get("")
def get_cloze(
    count: int = 5,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict | None = Depends(maybe_require_user),
) -> dict:
    """生成短文填词 (count 道选词填空)"""
    user_id = _current_user_id(user)
    count = max(1, min(count, 10))
    words = _pick_target_words(connection, limit=count * 3, user_id=user_id)
    items: list[dict] = []
    for w in words:
        if len(items) >= count:
            break
        context = _find_context_sentence(connection, w["word"])
        if not context:
            continue
        blank_sentence = _build_sentence_with_blank(context, w["word"])
        if "____" not in blank_sentence:
            continue
        distractors = _pick_distractors(connection, w["word"])
        options = [w["word"]] + distractors
        random.shuffle(options)
        items.append({
            "id": w["id"],
            "word": w["word"],
            "phonetic": w.get("phonetic") or "",
            "part_of_speech": w.get("part_of_speech") or "",
            "meaning": w.get("meaning") or "",
            "blank_sentence": blank_sentence,
            "options": options,
            "answer": w["word"],
        })
    return {"items": items, "total": len(items)}
