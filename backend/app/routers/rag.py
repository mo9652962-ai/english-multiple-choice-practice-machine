"""Phase 2 RAG knowledge-base API."""
from __future__ import annotations

import io
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from pypdf import PdfReader

from ..database import get_db
from ..services.docx_parser import extract_blocks
from ..services.rag_pipeline import (
    answer_from_knowledge,
    index_document,
    search_chunks,
)
from .auth import maybe_require_user

router = APIRouter(prefix="/rag", tags=["rag"])


def _user_id(user: dict[str, Any] | None) -> int | None:
    return int(user["id"]) if user else None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    source_filter: str | None = Field(default=None, max_length=500)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10000)


def _decode_text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(page for page in pages if page)


def _extract_document_text(data: bytes, suffix: str) -> tuple[str, str]:
    if suffix == ".pdf":
        return _extract_pdf_text(data), "pdf"
    if suffix in {".md", ".markdown"}:
        return _decode_text(data), "markdown"
    if suffix == ".txt":
        return _decode_text(data), "text"
    if suffix == ".docx":
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
                temporary.write(data)
                temporary_path = Path(temporary.name)
            blocks, _, _ = extract_blocks(temporary_path)
            return "\n\n".join(blocks), "docx"
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink()
                except OSError:
                    pass
    raise ValueError("仅支持 md、pdf、docx、txt 文件")


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    connection: sqlite3.Connection = Depends(get_db),
    user: dict[str, Any] | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    source_name = Path(file.filename or "未命名文档").name or "未命名文档"
    suffix = Path(source_name).suffix.lower()
    try:
        data = await file.read()
        text, source_type = _extract_document_text(data, suffix)
        result = index_document(connection, _user_id(user), source_name, source_type, text)
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"文档解析失败：{error}") from error
    return {
        **result,
        "source_name": source_name,
        "source_type": source_type,
        "size": len(data),
    }


@router.get("/documents")
def list_documents(
    connection: sqlite3.Connection = Depends(get_db),
    user: dict[str, Any] | None = Depends(maybe_require_user),
) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT id, user_id, source_name, source_type, size, chunk_count, created_at
        FROM knowledge_docs
        WHERE user_id IS ?
        ORDER BY id DESC
        """,
        (_user_id(user),),
    ).fetchall()
    return [dict(row) for row in rows]


@router.delete("/documents/{doc_id}")
def delete_document(
    doc_id: int,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict[str, Any] | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    user_id = _user_id(user)
    row = connection.execute(
        "SELECT id FROM knowledge_docs WHERE id = ? AND user_id IS ?",
        (doc_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="知识库文档不存在")
    connection.execute("DELETE FROM knowledge_chunks WHERE doc_id = ?", (doc_id,))
    connection.execute("DELETE FROM knowledge_docs WHERE id = ? AND user_id IS ?", (doc_id, user_id))
    connection.commit()
    return {"ok": True, "doc_id": doc_id}


@router.post("/search")
def search_document_chunks(
    payload: SearchRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict[str, Any] | None = Depends(maybe_require_user),
) -> list[dict[str, Any]]:
    try:
        return search_chunks(
            connection,
            _user_id(user),
            payload.query,
            top_k=payload.top_k,
            source_filter=payload.source_filter,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/ask")
def ask_knowledge_base(
    payload: AskRequest,
    connection: sqlite3.Connection = Depends(get_db),
    user: dict[str, Any] | None = Depends(maybe_require_user),
) -> dict[str, Any]:
    try:
        return answer_from_knowledge(connection, _user_id(user), payload.question)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
