"""RAG knowledge-base indexing, retrieval, and question answering."""
from __future__ import annotations

import json
import math
import re
import sqlite3
from typing import Any

from .ai_client import chat_completion, embed_texts


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text by paragraphs, then split oversized paragraphs with overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap 必须大于等于 0 且小于 chunk_size")
    if not text or not text.strip():
        return []

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = re.split(r"\n\s*\n", normalized)
    chunks: list[str] = []
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
        if len(paragraph) <= chunk_size:
            chunks.append(paragraph.strip())
            continue
        start = 0
        while start < len(paragraph):
            end = min(start + chunk_size, len(paragraph))
            piece = paragraph[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(paragraph):
                break
            start = end - overlap
    return chunks


def split_markdown(md: str) -> list[str]:
    """Split Markdown into semantic sections beginning at ## or ### headings."""
    if not md or not md.strip():
        return []
    normalized = md.replace("\r\n", "\n").replace("\r", "\n")
    heading = re.compile(r"^\s{0,3}#{2,3}(?:\s+|$)")
    sections: list[str] = []
    current: list[str] = []
    for line in normalized.split("\n"):
        if heading.match(line) and current and "\n".join(current).strip():
            sections.append("\n".join(current).strip())
            current = []
        current.append(line)
    if current and "\n".join(current).strip():
        sections.append("\n".join(current).strip())

    chunks: list[str] = []
    for section in sections:
        if len(section) <= 500:
            chunks.append(section)
        else:
            chunks.extend(split_text(section))
    return chunks


def index_document(
    connection: sqlite3.Connection,
    user_id: int | None,
    source_name: str,
    source_type: str,
    text: str,
) -> dict[str, int]:
    if not text or not text.strip():
        raise ValueError("文档内容不能为空")
    normalized_type = (source_type or "text").strip().lower()
    chunks = split_markdown(text) if normalized_type in {"md", "markdown"} else split_text(text)
    if not chunks:
        raise ValueError("文档没有可索引的文字内容")

    vectors = embed_texts(connection, chunks)
    if len(vectors) != len(chunks):
        raise ValueError("Embedding 返回数量与文档分片数量不一致")

    try:
        cursor = connection.execute(
            """
            INSERT INTO knowledge_docs
                (user_id, source_name, source_type, size, chunk_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                user_id,
                source_name,
                normalized_type or "text",
                len(text.encode("utf-8")),
                len(chunks),
            ),
        )
        doc_id = int(cursor.lastrowid)
        connection.executemany(
            """
            INSERT INTO knowledge_chunks
                (doc_id, user_id, source_name, chunk_index, content, embedding)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    doc_id,
                    user_id,
                    source_name,
                    index,
                    content,
                    json.dumps(vector, ensure_ascii=False, separators=(",", ":")),
                )
                for index, (content, vector) in enumerate(zip(chunks, vectors))
            ],
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return {"doc_id": doc_id, "chunk_count": len(chunks)}


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    length = min(len(left), len(right))
    if length == 0:
        return 0.0
    dot = sum(left[index] * right[index] for index in range(length))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def search_chunks(
    connection: sqlite3.Connection,
    user_id: int | None,
    query: str,
    top_k: int = 10,
    source_filter: str | None = None,
) -> list[dict[str, Any]]:
    if not query or not query.strip():
        raise ValueError("检索关键词不能为空")
    if top_k <= 0:
        return []
    query_vectors = embed_texts(connection, [query.strip()])
    if not query_vectors:
        return []

    sql = """
        SELECT content, source_name, chunk_index, embedding
        FROM knowledge_chunks
        WHERE user_id IS ?
    """
    params: list[Any] = [user_id]
    if source_filter:
        sql += " AND source_name = ?"
        params.append(source_filter)
    rows = connection.execute(sql, params).fetchall()
    matches: list[dict[str, Any]] = []
    for row in rows:
        try:
            vector = json.loads(row["embedding"] or "[]")
            vector = [float(value) for value in vector]
            score = _cosine_similarity(query_vectors[0], vector)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        matches.append(
            {
                "content": row["content"],
                "source_name": row["source_name"],
                "chunk_index": row["chunk_index"],
                "score": score,
            }
        )
    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[:top_k]


def search_knowledge(
    connection: sqlite3.Connection,
    user_id: int | None,
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    return search_chunks(connection, user_id, query, top_k=top_k)


def format_knowledge_for_prompt(results: list[dict[str, Any]]) -> str:
    prefix = "[知识库检索结果 — 请优先基于以下参考资料回答]\n"
    if not results:
        return prefix + "（没有找到相关参考资料）"
    sections = [prefix.rstrip()]
    for index, result in enumerate(results, start=1):
        sections.append(
            f"\n参考资料 {index}（来源：{result.get('source_name') or '未知文档'}，"
            f"分片 {result.get('chunk_index', 0)}，相似度 {float(result.get('score', 0)):.4f}）：\n"
            f"{result.get('content', '')}"
        )
    sections.append("\n请区分参考资料与推测；资料不足时明确说明，不要编造资料中没有的事实。")
    return "".join(sections)


def answer_from_knowledge(
    connection: sqlite3.Connection,
    user_id: int | None,
    question: str,
) -> dict[str, Any]:
    if not question or not question.strip():
        raise ValueError("问题不能为空")
    results = search_knowledge(connection, user_id, question.strip(), top_k=5)
    messages = [
        {
            "role": "system",
            "content": (
                "你是墨题知识库助手。请优先依据用户知识库检索结果回答，"
                "用清晰、简洁的中文说明；若参考资料不足，请诚实说明。\n\n"
                + format_knowledge_for_prompt(results)
            ),
        },
        {"role": "user", "content": question.strip()},
    ]
    answer = chat_completion(connection, messages)
    sources = [
        {
            "source_name": result["source_name"],
            "chunk_index": result["chunk_index"],
            "score": result["score"],
        }
        for result in results
    ]
    return {"answer": answer, "sources": sources}
