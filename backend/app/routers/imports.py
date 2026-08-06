from __future__ import annotations

import json
import re
import shutil
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from ..config import UPLOAD_DIR
from ..database import get_active_profile_id, get_db
from ..schemas import DraftUpdate, ImportAnswersUpdate, ModelAssistRequest
from ..services.docx_parser import (
    apply_answers_to_draft,
    create_docx_block_fragment,
    extract_blocks,
    find_companion_answer_pdf,
    objective_question_numbers,
    parse_exam,
    publish_draft,
    validate_draft,
)
from ..services.import_assist import (
    apply_model_assist,
    detect_document_papers,
    document_text,
    extract_attachment_text,
    infer_document_papers,
    run_model_assist,
)
from ..services.ai_client import get_ai_profile
from ..services.trash import trash_import_job


router = APIRouter(prefix="/imports", tags=["imports"])
IMPORT_PIPELINE_REVISION = "word-import-2026.08.05.multi-paper.1"
ALLOWED_AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".ogg"}


def _job_scope_payload(parse_context: str | None) -> dict[str, Any]:
    try:
        context = json.loads(parse_context or "{}")
    except json.JSONDecodeError:
        context = {}
    paper_ids = [
        int(value)
        for value in context.get("published_paper_ids", [])
        if isinstance(value, int) and value > 0
    ]
    return {
        "published_paper_ids": paper_ids,
        "published_scope_title": str(context.get("published_scope_title", "")).strip(),
    }


def _model_identity(
    connection: sqlite3.Connection,
    *,
    profile_id: int | None = None,
    model: str = "",
) -> tuple[str, str]:
    profile = get_ai_profile(connection, profile_id)
    selected_model = (
        model.strip() or str(profile.get("default_model", "")).strip()
    )
    return str(profile.get("name", "")).strip(), selected_model


def _extract_answer_text(
    stored_answer_paths: list[Path],
    selected_answer_files: list[UploadFile],
) -> str:
    if len(stored_answer_paths) == 1:
        return extract_attachment_text(stored_answer_paths[0])
    answer_sections: list[str] = []
    for index, attachment_path in enumerate(stored_answer_paths):
        attachment_name = selected_answer_files[index].filename or attachment_path.name
        extracted = extract_attachment_text(attachment_path)
        if extracted.strip():
            answer_sections.append(
                f"===== answer attachment: {attachment_name} =====\n{extracted}"
            )
    return "\n\n".join(answer_sections)


def _answer_text_for_split(answer_text: str, split_info: dict[str, Any]) -> str:
    """Keep only answer attachments that belong to the current exam and set."""
    if "===== answer attachment:" not in answer_text:
        return answer_text
    year = int(split_info.get("year") or 0)
    month = int(split_info.get("month") or 0)
    set_number = int(split_info.get("set_number") or 0)
    sections = re.split(r"(?=^===== answer attachment:)", answer_text, flags=re.M)
    selected: list[str] = []
    for section in sections:
        header = section.splitlines()[0] if section.splitlines() else ""
        header_year = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", header)
        header_month = re.search(
            r"(?:年|[.\-_])\s*(0?[1-9]|1[0-2])\s*月?",
            header,
        )
        header_set = re.search(r"第\s*([一二三1-9])\s*套", header)
        if year and header_year and int(header_year.group(1)) != year:
            continue
        if month and header_month and int(header_month.group(1)) != month:
            continue
        if set_number and header_set:
            set_token = header_set.group(1)
            parsed_set = (
                int(set_token)
                if set_token.isdigit()
                else {"一": 1, "二": 2, "三": 3}.get(set_token, 0)
            )
            if parsed_set != set_number:
                continue
        selected.append(section)
    return "\n\n".join(selected)


def _build_uploaded_draft(
    connection: sqlite3.Connection,
    *,
    source_path: Path,
    source_name: str,
    primary_answer_path: Path | None,
    selected_answer_files: list[UploadFile],
    stored_answer_paths: list[Path],
    audio_paths: list[Path],
    use_model_assist: bool,
    defer_model_assist: bool,
    model_assist_correct_structure: bool,
    answer_text: str,
    split_info: dict[str, Any],
    split_source: str,
    split_error: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    diagnostics: dict[str, Any] = {
        "pipeline_revision": IMPORT_PIPELINE_REVISION,
        "use_model_assist_requested": use_model_assist,
        "structure_fix_requested": model_assist_correct_structure,
        "answer_file_received": bool(selected_answer_files),
        "answer_file_count": len(selected_answer_files),
        "answer_file_name": selected_answer_files[0].filename if selected_answer_files else "",
        "answer_file_names": [item.filename for item in selected_answer_files if item.filename],
        "audio_file_count": len(audio_paths),
        "model_call_status": (
            "deferred"
            if use_model_assist and defer_model_assist
            else "pending"
            if use_model_assist
            else "not_requested"
        ),
        "split_source": split_source,
        "split_error": split_error,
        "paper_index": int(split_info.get("paper_index", 1)),
        "paper_count": int(split_info.get("paper_count", 1)),
        "has_objective_questions": bool(
            split_info.get("has_objective_questions", True)
        ),
    }
    local_started = time.perf_counter()
    draft = parse_exam(
        source_path,
        answer_path=primary_answer_path,
        source_name=source_name,
        answer_name=selected_answer_files[0].filename if selected_answer_files else None,
        audio_paths=audio_paths or None,
    )
    draft["title"] = str(split_info.get("title") or draft.get("title") or source_name)
    if split_info.get("year"):
        draft["year"] = int(split_info["year"])
    if split_info.get("month"):
        draft["exam_month"] = int(split_info["month"])
    if split_info.get("set_number"):
        draft["set_number"] = int(split_info["set_number"])
    draft["document_split"] = {
        key: value
        for key, value in split_info.items()
        if key not in {"paper_index", "paper_count"}
    } | {
        "paper_index": int(split_info.get("paper_index", 1)),
        "paper_count": int(split_info.get("paper_count", 1)),
        "source": split_source,
    }
    if not split_info.get("has_objective_questions", True):
        draft["warnings"] = [
            "该套文档未检测到可导入的客观题，可能只包含写作或翻译部分"
        ]
    diagnostics.update(
        {
            "local_parse_elapsed_ms": round((time.perf_counter() - local_started) * 1000),
            "local_answer_count": sum(1 for value in draft.get("answers", {}).values() if value),
            "local_unit_count": len(draft.get("units", [])),
            "local_warning_count": len(draft.get("warnings", [])),
            "answer_text_chars": len(answer_text),
        }
    )
    parse_context: dict[str, Any] = {
        "answer_text": answer_text,
        "answer_paths": [str(path) for path in stored_answer_paths],
        "audio_paths": [str(path) for path in audio_paths],
        "import_diagnostics": diagnostics,
        "document_split": draft["document_split"],
    }
    draft["import_diagnostics"] = diagnostics
    if use_model_assist and not defer_model_assist and split_info.get(
        "has_objective_questions", True
    ):
        model_started = time.perf_counter()
        diagnostics["model_call_status"] = "running"
        diagnostics["model_call_started_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            profile_name, model_name = _model_identity(connection)
            diagnostics["model_profile_name"] = profile_name
            diagnostics["model_name"] = model_name
            result, _ = run_model_assist(
                connection,
                draft,
                document_text(source_path),
                answer_text=answer_text,
                correct_structure=model_assist_correct_structure,
            )
            draft = apply_model_assist(
                draft,
                result,
                model_name=model_name,
                correct_structure=model_assist_correct_structure,
            )
            draft["model_assist"]["phase"] = "upload"
            diagnostics["model_call_status"] = "completed"
        except Exception as error:
            diagnostics["model_call_status"] = "failed"
            diagnostics["model_error"] = str(error)[:400]
            draft["model_assist"] = {
                "status": "failed",
                "phase": "upload",
                "error": str(error)[:400],
                "fell_back_to_local": True,
            }
        diagnostics["model_call_elapsed_ms"] = round(
            (time.perf_counter() - model_started) * 1000
        )
    diagnostics["total_elapsed_ms"] = round((time.perf_counter() - started) * 1000)
    draft["import_diagnostics"] = diagnostics
    parse_context["import_diagnostics"] = diagnostics
    return draft, parse_context


@router.get("")
def list_imports(connection: sqlite3.Connection = Depends(get_db)) -> list[dict]:
    profile_id = get_active_profile_id(connection)
    rows = connection.execute(
        """
        SELECT id, profile_id, filename, detected_year, detected_format, status,
               warnings, parse_context, created_at, updated_at
        FROM import_jobs
        WHERE (detected_format <> 'esq-1.0' OR detected_format IS NULL)
          AND profile_id = ? AND deleted_at IS NULL
        ORDER BY id DESC
        """,
        (profile_id,),
    ).fetchall()
    result = []
    for row in rows:
        payload = dict(row)
        payload["warnings"] = json.loads(payload["warnings"] or "[]")
        payload.update(_job_scope_payload(payload.pop("parse_context", "{}")))
        result.append(payload)
    return result


@router.post("")
async def upload_import(
    file: UploadFile = File(...),
    answer_file: UploadFile | None = File(default=None),
    answer_files: list[UploadFile] | None = File(default=None),
    audio_file: UploadFile | None = File(default=None),
    audio_files: list[UploadFile] | None = File(default=None),
    use_model_assist: bool = Form(False),
    model_assist_correct_structure: bool = Form(False),
    defer_model_assist: bool = Form(False),
    profile_id: int | None = Form(default=None),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    import_started = time.perf_counter()
    if not file.filename or not file.filename.lower().endswith((".docx", ".doc", ".pdf")):
        raise HTTPException(400, "请选择 Word 文件")
    if answer_file and (
        not answer_file.filename
        or not answer_file.filename.lower().endswith((".docx", ".doc", ".pdf"))
    ):
        raise HTTPException(400, "答案文件仅支持 DOC、DOCX 或 PDF")
    selected_answer_files = [
        item
        for item in ([answer_file] if answer_file else []) + list(answer_files or [])
        if item and item.filename
    ]
    for selected_answer in selected_answer_files:
        if not selected_answer.filename or not selected_answer.filename.lower().endswith(
            (".docx", ".doc", ".pdf")
        ):
            raise HTTPException(400, "答案文件仅支持 DOC、DOCX 或 PDF")
    selected_audio_files = [
        item
        for item in ([audio_file] if audio_file else []) + list(audio_files or [])
        if item and item.filename
    ]
    for audio in selected_audio_files:
        suffix = Path(audio.filename or "").suffix.lower()
        if suffix not in ALLOWED_AUDIO_SUFFIXES:
            raise HTTPException(400, "听力音频仅支持 MP3、M4A、WAV 或 OGG")
    audio_paths: list[Path] = []
    for audio in selected_audio_files:
        suffix = Path(audio.filename or "").suffix.lower() or ".mp3"
        audio_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
        with audio_path.open("wb") as target:
            shutil.copyfileobj(audio.file, target)
        audio_paths.append(audio_path)
    suffix = Path(file.filename).suffix or ".docx"
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name
    stored_answer_paths: list[Path] = []
    selected_profile_id = profile_id or get_active_profile_id(connection)
    if not connection.execute(
        "SELECT 1 FROM question_bank_profiles WHERE id = ? AND deleted_at IS NULL",
        (selected_profile_id,),
    ).fetchone():
        raise HTTPException(404, "目标题库配置不存在")
    with stored_path.open("wb") as target:
        shutil.copyfileobj(file.file, target)
    for selected_answer in selected_answer_files:
        answer_suffix = Path(selected_answer.filename or "").suffix or ".docx"
        stored_answer_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{answer_suffix}"
        with stored_answer_path.open("wb") as target:
            shutil.copyfileobj(selected_answer.file, target)
        stored_answer_paths.append(stored_answer_path)
    primary_answer_path = stored_answer_paths[0] if stored_answer_paths else None
    try:
        answer_text = _extract_answer_text(stored_answer_paths, selected_answer_files)
        split_source = "local"
        split_error = ""
        try:
            blocks, _, converted = extract_blocks(stored_path)
            try:
                paper_sections = infer_document_papers(blocks, file.filename)
                if use_model_assist:
                    try:
                        paper_sections, _ = detect_document_papers(
                            connection,
                            blocks,
                            file.filename,
                        )
                        split_source = "model"
                    except Exception as error:
                        split_error = str(error)[:400]
            finally:
                if converted:
                    shutil.rmtree(converted.parent, ignore_errors=True)
        except Exception as error:
            # Preserve the established single-paper error semantics: the
            # parser below remains the source of truth for invalid documents.
            # This also keeps older API clients/tests that provide a parser
            # adapter but no OOXML block extractor working.
            split_error = str(error)[:400]
            paper_sections = [
                {
                    "title": Path(file.filename).stem,
                    "year": None,
                    "month": None,
                    "set_number": 1,
                    "start_block": 0,
                    "end_block": 0,
                    "objective_start_block": 0,
                    "objective_end_block": 0,
                    "has_objective_questions": True,
                }
            ]

        variants: list[tuple[Path, str, dict[str, Any]]] = []
        detected_paper_count = len(paper_sections)
        ignored_paper_count = max(0, detected_paper_count - 1)
        section = paper_sections[0]
        info = dict(section)
        info["paper_index"] = 1
        info["paper_count"] = 1
        info["detected_paper_count"] = detected_paper_count
        info["ignored_paper_count"] = ignored_paper_count
        if detected_paper_count > 1:
            fragment_path = UPLOAD_DIR / f"{uuid.uuid4().hex}.docx"
            create_docx_block_fragment(
                stored_path,
                fragment_path,
                start_block=int(section["start_block"]),
                end_block=int(section["end_block"]),
            )
            variants.append(
                (
                    fragment_path,
                    f"{section['title']}.docx",
                    info,
                )
            )
        else:
            variants.append((stored_path, file.filename, info))

        import_group_id = uuid.uuid4().hex
        created_jobs: list[dict[str, Any]] = []
        for index, (variant_path, variant_name, split_info) in enumerate(variants):
            variant_audio_paths = [audio_paths[0]] if audio_paths else []
            variant_answer_text = _answer_text_for_split(answer_text, split_info)
            draft, parse_context = _build_uploaded_draft(
                connection,
                source_path=variant_path,
                source_name=variant_name,
                primary_answer_path=primary_answer_path,
                selected_answer_files=selected_answer_files,
                stored_answer_paths=stored_answer_paths,
                audio_paths=variant_audio_paths,
                use_model_assist=use_model_assist,
                defer_model_assist=defer_model_assist,
                model_assist_correct_structure=model_assist_correct_structure,
                answer_text=variant_answer_text,
                split_info=split_info,
                split_source=split_source,
                split_error=split_error,
            )
            parse_context["import_group_id"] = import_group_id
            parse_context["source_container_path"] = str(stored_path)
            cursor = connection.execute(
                """
                INSERT INTO import_jobs
                    (profile_id, filename, stored_path, answer_stored_path,
                     detected_year, detected_format, status, draft_data,
                     warnings, parse_context)
                VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?)
                """,
                (
                    selected_profile_id,
                    variant_name,
                    str(variant_path),
                    str(primary_answer_path or ""),
                    draft.get("year"),
                    draft.get("detected_format"),
                    json.dumps(draft, ensure_ascii=False),
                    json.dumps(draft["warnings"], ensure_ascii=False),
                    json.dumps(parse_context, ensure_ascii=False),
                ),
            )
            created_jobs.append(
                {
                    "id": int(cursor.lastrowid),
                    "filename": variant_name,
                    "draft": draft,
                    "warnings": draft["warnings"],
                    "model_assist": draft.get("model_assist"),
                    "profile_id": selected_profile_id,
                    "paper_index": split_info["paper_index"],
                    "paper_count": split_info["paper_count"],
                    "has_objective_questions": split_info.get(
                        "has_objective_questions", True
                    ),
                }
            )
        connection.commit()
        first = dict(created_jobs[0])
        first["split_jobs"] = created_jobs
        first["split_count"] = len(created_jobs)
        first["detected_paper_count"] = detected_paper_count
        first["ignored_paper_count"] = ignored_paper_count
        first["split_source"] = split_source
        first["split_error"] = split_error
        first["total_elapsed_ms"] = round(
            (time.perf_counter() - import_started) * 1000
        )
        return first
    except Exception as error:
        connection.rollback()
        stored_path.unlink(missing_ok=True)
        for stored_answer_path in stored_answer_paths:
            stored_answer_path.unlink(missing_ok=True)
        for audio_path in audio_paths:
            audio_path.unlink(missing_ok=True)
        raise HTTPException(400, f"Word解析失败：{error}") from error


@router.post("/{job_id}/model-assist")
def model_assist_retry(
    job_id: int,
    request: ModelAssistRequest,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = connection.execute(
        "SELECT * FROM import_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "导入任务不存在")
    if row["status"] == "published":
        raise HTTPException(409, "已发布题库不能重新解析")
    draft = json.loads(row["draft_data"])
    try:
        parse_context = json.loads(row["parse_context"] or "{}")
    except json.JSONDecodeError:
        parse_context = {}
    answer_text = str(parse_context.get("answer_text", ""))
    diagnostics = draft.setdefault(
        "import_diagnostics",
        {
            "pipeline_revision": IMPORT_PIPELINE_REVISION,
            "use_model_assist_requested": True,
            "answer_text_chars": len(answer_text),
        },
    )
    model_started = time.perf_counter()
    diagnostics["model_call_status"] = "running"
    diagnostics["model_call_started_at"] = datetime.now().isoformat(
        timespec="seconds"
    )
    try:
        profile_name, model_name = _model_identity(
            connection,
            profile_id=request.profile_id,
            model=request.model,
        )
        diagnostics["model_profile_name"] = profile_name
        diagnostics["model_name"] = model_name
        result, _ = run_model_assist(
            connection,
            draft,
            document_text(Path(row["stored_path"])),
            answer_text=answer_text,
            profile_id=request.profile_id,
            model=request.model.strip() or None,
            correct_structure=request.correct_structure,
            max_tokens=request.max_tokens,
        )
        draft = apply_model_assist(
            draft,
            result,
            model_name=model_name,
            correct_structure=request.correct_structure,
        )
        draft["model_assist"]["phase"] = "retry"
        diagnostics["model_call_status"] = "completed"
        diagnostics["model_call_elapsed_ms"] = round(
            (time.perf_counter() - model_started) * 1000
        )
        diagnostics["structure_fix_requested"] = request.correct_structure
        if not draft.get("answers_confirmed"):
            draft["answer_status"] = {
                "status": "parsed",
                "message": (
                    f"模型辅助解析识别 {draft['model_assist']['answer_total']} 道答案，"
                    "发布前请人工核对"
                ),
            }
    except Exception as error:
        diagnostics["model_call_status"] = "failed"
        diagnostics["model_call_elapsed_ms"] = round(
            (time.perf_counter() - model_started) * 1000
        )
        diagnostics["model_error"] = str(error)[:400]
        draft["import_diagnostics"] = diagnostics
        connection.execute(
            """
            UPDATE import_jobs
            SET draft_data = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (json.dumps(draft, ensure_ascii=False), job_id),
        )
        connection.commit()
        return {
            "draft": draft,
            "warnings": draft.get("warnings", []),
            "model_assist": {
                "status": "failed",
                "phase": "retry",
                "error": str(error)[:400],
                "fell_back_to_local": True,
            },
        }
    connection.execute(
        """
        UPDATE import_jobs
        SET draft_data = ?, warnings = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            json.dumps(draft, ensure_ascii=False),
            json.dumps(draft["warnings"], ensure_ascii=False),
            job_id,
        ),
    )
    connection.execute(
        """
        INSERT INTO revision_log
            (import_job_id, entity_type, entity_ref, field_name,
             old_value, new_value, source, model_name, approved)
        VALUES (?, 'draft', ?, 'answers', ?, ?, 'model-assist', ?, 1)
        """,
        (
            job_id,
            str(job_id),
            json.dumps(
                {str(key): value for key, value in draft.get("answers", {}).items()},
                ensure_ascii=False,
            ),
            json.dumps(draft.get("answer_sources", {}), ensure_ascii=False),
            request.model.strip(),
        ),
    )
    connection.commit()
    return {
        "draft": draft,
        "warnings": draft["warnings"],
        "model_assist": draft["model_assist"],
    }


@router.get("/{job_id}")
def import_detail(
    job_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> dict:
    row = connection.execute(
        "SELECT * FROM import_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "导入任务不存在")
    payload = dict(row)
    payload["draft_data"] = json.loads(payload["draft_data"])
    payload["warnings"] = json.loads(payload["warnings"])
    payload.update(_job_scope_payload(payload.pop("parse_context", "{}")))
    return payload


@router.put("/{job_id}")
def update_draft(
    job_id: int,
    request: DraftUpdate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = connection.execute(
        "SELECT draft_data FROM import_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "导入任务不存在")
    old_data = json.loads(row["draft_data"])
    draft = request.draft_data
    if old_data.get("answers") != draft.get("answers"):
        old_sources = old_data.get("answer_sources", {})
        new_sources = draft.setdefault("answer_sources", {})
        old_answers = old_data.get("answers", {})
        new_answers = draft.get("answers", {})
        for number, answer in new_answers.items():
            if answer and old_answers.get(number) != answer:
                new_sources[number] = "人工录入"
            elif answer and number not in new_sources and number in old_sources:
                new_sources[number] = old_sources[number]
            elif not answer:
                new_sources.pop(number, None)
        draft["answers_confirmed"] = True
        draft["answer_status"] = {
            "status": "confirmed",
            "message": "人工编辑的标准答案已确认",
        }
    apply_answers_to_draft(draft)
    draft["warnings"] = validate_draft(draft)
    connection.execute(
        """
        UPDATE import_jobs
        SET draft_data = ?, warnings = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            json.dumps(draft, ensure_ascii=False),
            json.dumps(draft["warnings"], ensure_ascii=False),
            job_id,
        ),
    )
    connection.execute(
        """
        INSERT INTO revision_log
            (import_job_id, entity_type, entity_ref, field_name,
             old_value, new_value, source, approved)
        VALUES (?, 'draft', ?, 'all', ?, ?, 'user', 1)
        """,
        (
            job_id,
            str(job_id),
            json.dumps(old_data, ensure_ascii=False),
            json.dumps(draft, ensure_ascii=False),
        ),
    )
    connection.commit()
    return {"draft": draft, "warnings": draft["warnings"]}


@router.patch("/{job_id}/answers")
def update_answers(
    job_id: int,
    request: ImportAnswersUpdate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = connection.execute(
        "SELECT draft_data FROM import_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "导入任务不存在")
    draft = json.loads(row["draft_data"])
    old_answers = dict(draft.get("answers", {}))
    answer_sources = draft.setdefault("answer_sources", {})
    allowed_numbers = {
        str(number) for number in objective_question_numbers(draft)
    }
    for number, answer in request.answers.items():
        normalized_number = str(number).strip()
        normalized_answer = str(answer).strip().upper()
        if not normalized_number.isdigit():
            raise HTTPException(422, f"无效题号：{number}")
        if normalized_number not in allowed_numbers:
            raise HTTPException(422, f"第 {normalized_number} 题不属于当前客观题草稿")
        if normalized_answer and normalized_answer not in "ABCDEFGHIJKLMNOT":
            raise HTTPException(422, f"第 {normalized_number} 题答案无效")
        draft.setdefault("answers", {})[normalized_number] = normalized_answer
        if normalized_answer:
            if old_answers.get(normalized_number) != normalized_answer:
                answer_sources[normalized_number] = "人工录入"
            elif normalized_number not in answer_sources:
                answer_sources[normalized_number] = "人工录入"
        else:
            answer_sources.pop(normalized_number, None)
    draft["answers_confirmed"] = True
    source_kinds = {
        source
        for number, source in answer_sources.items()
        if draft.get("answers", {}).get(number)
    }
    if source_kinds == {"人工录入"}:
        draft["answer_source"] = "人工录入"
        draft["answer_status"] = {
            "status": "confirmed",
            "message": "人工录入答案已确认",
        }
    else:
        draft["answer_source"] = (
            "、".join(sorted(source_kinds)) if source_kinds else "人工录入"
        )
        draft["answer_status"] = {
            "status": "confirmed",
            "message": "自动识别与人工校对的答案已确认",
        }
    apply_answers_to_draft(draft)
    draft["warnings"] = validate_draft(draft)
    connection.execute(
        """
        UPDATE import_jobs
        SET draft_data = ?, warnings = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            json.dumps(draft, ensure_ascii=False),
            json.dumps(draft["warnings"], ensure_ascii=False),
            job_id,
        ),
    )
    connection.execute(
        """
        INSERT INTO revision_log
            (import_job_id, entity_type, entity_ref, field_name,
             old_value, new_value, source, approved)
        VALUES (?, 'draft', ?, 'answers', ?, ?, 'user', 1)
        """,
        (
            job_id,
            str(job_id),
            json.dumps(old_answers, ensure_ascii=False),
            json.dumps(draft.get("answers", {}), ensure_ascii=False),
        ),
    )
    connection.commit()
    return {"draft": draft, "warnings": draft["warnings"]}


@router.post("/{job_id}/publish")
def publish(
    job_id: int,
    force: bool = False,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = connection.execute(
        "SELECT * FROM import_jobs WHERE id = ?", (job_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, "导入任务不存在")
    draft = json.loads(row["draft_data"])
    if draft.get("document_split", {}).get("has_objective_questions") is False:
        raise HTTPException(409, "该套文档未检测到客观题，不能发布为空壳题库")
    warnings = validate_draft(draft)
    if warnings and not force:
        raise HTTPException(409, {"message": "仍有校验问题", "warnings": warnings})
    paper_id = publish_draft(
        connection,
        draft,
        row["filename"],
        profile_id=int(row["profile_id"]),
    )
    try:
        parse_context = json.loads(row["parse_context"] or "{}")
    except json.JSONDecodeError:
        parse_context = {}
    parse_context["published_paper_ids"] = [paper_id]
    parse_context["published_scope_title"] = str(draft.get("title") or f"{draft.get('year', '')} 年题库")
    connection.execute(
        """
        UPDATE import_jobs
        SET status = 'published', warnings = ?, parse_context = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            json.dumps(warnings, ensure_ascii=False),
            json.dumps(parse_context, ensure_ascii=False),
            job_id,
        ),
    )
    connection.commit()
    question_count = connection.execute(
        """
        SELECT COUNT(q.id)
        FROM questions AS q
        JOIN units AS u ON u.id = q.unit_id
        WHERE u.paper_id = ?
        """,
        (paper_id,),
    ).fetchone()[0]
    return {
        "published": True,
        "paper_id": paper_id,
        "paper_ids": [paper_id],
        "scope_title": parse_context["published_scope_title"],
        "question_count": int(question_count or 0),
        "warnings": warnings,
    }


@router.delete("/{job_id}")
def delete_import(
    job_id: int,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        result = trash_import_job(connection, job_id)
        connection.commit()
        return {"trashed": True, **result}
    except ValueError as error:
        connection.rollback()
        raise HTTPException(422, str(error)) from error
