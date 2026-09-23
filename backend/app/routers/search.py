"""全局全文检索与即时查词服务 (FTS5 + LRU Cache).

提供:
- GET  /api/search/fts        —— 全局全文检索真题题干、文章长难句、选项及解析 (SQLite FTS5)
- POST /api/search/quick-word —— 划词极速查词 (音标、真题释义与例句，带内存高速缓存)
"""

from __future__ import annotations

import functools
import re
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..database import get_db

router = APIRouter(prefix="/search", tags=["search"])


def _ensure_fts_table(connection: sqlite3.Connection) -> None:
    """确保 questions_fts 虚拟表存在并保持基础索引."""
    connection.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(
            question_id UNINDEXED,
            paper_title,
            stem,
            passage,
            tokenize='unicode61'
        )
        """
    )
    # 若 FTS 表为空，则进行轻量初始化增量填充
    count = connection.execute("SELECT count(*) FROM questions_fts").fetchone()[0]
    if count == 0:
        connection.execute(
            """
            INSERT INTO questions_fts(question_id, paper_title, stem, passage)
            SELECT q.id, p.title, q.stem, COALESCE(u.passage, '')
            FROM questions q
            JOIN units u ON q.unit_id = u.id
            JOIN papers p ON u.paper_id = p.id
            LIMIT 5000
            """
        )
        connection.commit()


@functools.lru_cache(maxsize=1024)
def _cached_word_lookup(db_file: str, word: str) -> dict[str, Any] | None:
    """带 LRU 缓存的词汇即时查询."""
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    clean_w = word.strip().lower()
    row = conn.execute(
        """
        SELECT term as word, phonetic, COALESCE(contextual_meaning, common_meaning, '') as translation,
               part_of_speech as pos, common_meaning as definition_en
        FROM vocabulary_entries
        WHERE normalized_term = ? OR term = ?
        LIMIT 1
        """,
        (clean_w, word.strip()),
    ).fetchone()
    
    if not row:
        # 前缀/去除复数/过去式尝试匹配
        lemma = re.sub(r'(ing|ed|es|s)$', '', clean_w)
        row = conn.execute(
            """
            SELECT term as word, phonetic, COALESCE(contextual_meaning, common_meaning, '') as translation,
                   part_of_speech as pos, common_meaning as definition_en
            FROM vocabulary_entries
            WHERE normalized_term = ? OR lemma = ?
            LIMIT 1
            """,
            (lemma, lemma)
        ).fetchone()

    if not row:
        conn.close()
        return None

    word_data = dict(row)
    # 查询真题中出现的原句
    occ_row = conn.execute(
        """
        SELECT context_sentence as sentence, unit_title as title
        FROM vocabulary_occurrences
        WHERE surface_form = ? AND context_sentence IS NOT NULL AND trim(context_sentence) != ''
        LIMIT 2
        """,
        (word_data["word"],),
    ).fetchall()
    
    word_data["occurrences"] = [dict(r) for r in occ_row]
    conn.close()
    return word_data


class QuickWordRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=100)
    context_sentence: str | None = None


@router.post("/quick-word")
def quick_word_lookup(
    request: QuickWordRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """极速划词释义接口 (毫秒级响应，专为阅读划词浮层设计)."""
    # 获取底层数据库文件路径以支持缓存函数的安全隔离
    db_path = connection.execute("PRAGMA database_list").fetchall()[0][2]
    result = _cached_word_lookup(db_path, request.word)
    if not result:
        return {
            "found": False,
            "word": request.word,
            "phonetic": "",
            "translation": "暂未收录释义",
            "occurrences": []
        }
    return {
        "found": True,
        **result
    }


@router.get("/fts")
def search_questions_fts(
    q: str = Query(..., min_length=1, max_length=100, description="搜索关键词或长句短语"),
    limit: int = Query(20, ge=1, le=100),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict[str, Any]:
    """基于 SQLite FTS5 的全文检索引擎接口."""
    _ensure_fts_table(connection)
    
    # 净化搜索词防语法注入
    safe_q = re.sub(r'["\*\+\-\^\:]', ' ', q).strip()
    if not safe_q:
        safe_q = q.strip()
    
    try:
        cur = connection.execute(
            """
            SELECT question_id, paper_title, stem, passage,
                   snippet(questions_fts, 2, '<b>', '</b>', '...', 15) as stem_highlight,
                   snippet(questions_fts, 3, '<b>', '</b>', '...', 25) as passage_highlight
            FROM questions_fts
            WHERE questions_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (f"{safe_q}*", limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
    except sqlite3.OperationalError:
        # 降级 LIKE 检索
        like_q = f"%{safe_q}%"
        cur = connection.execute(
            """
            SELECT q.id as question_id, p.title as paper_title, q.stem, u.passage,
                   q.stem as stem_highlight, '' as passage_highlight
            FROM questions q
            JOIN units u ON q.unit_id = u.id
            JOIN papers p ON u.paper_id = p.id
            WHERE q.stem LIKE ? OR u.passage LIKE ?
            LIMIT ?
            """,
            (like_q, like_q, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]

    return {
        "query": q,
        "count": len(rows),
        "results": rows
    }
