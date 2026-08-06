from __future__ import annotations

import sqlite3
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from ..database import get_db
from ..schemas import (
    VocabularyCreate,
    VocabularyReview,
    VocabularyTranslationRunRequest,
    VocabularyUpdate,
)
from ..services.vocabulary import (
    _serialize_entry,
    add_vocabulary,
    local_similar_matches,
    queue_vocabulary_translations,
    review_entry,
    translate_queued_vocabulary,
)


router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.post("")
def create_entry(
    request: VocabularyCreate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        result = add_vocabulary(connection, request.model_dump())
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return result


@router.get("")
def list_entries(
    status: str = "all",
    search: str = "",
    category: str = "",
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    conditions = ["1 = 1"]
    params: list[object] = []
    if category:
        conditions.append("category = ?")
        params.append(category)
    if status == "frequent":
        conditions.append("(encounter_count >= 2 OR manually_frequent = 1)")
    elif status == "review":
        conditions.append(
            "(next_review_at IS NULL OR next_review_at <= ?)"
        )
        params.append(datetime.now().isoformat(timespec="seconds"))
        conditions.append("translation_status = 'ready'")
        conditions.append("study_status != 'mastered'")
    elif status == "learning":
        conditions.append("study_status = 'learning'")
    elif status == "mastered":
        conditions.append("study_status = 'mastered'")
    elif status == "pending":
        conditions.append("translation_status != 'ready'")
    if search.strip():
        conditions.append(
            "(term LIKE ? OR lemma LIKE ? OR contextual_meaning LIKE ? OR common_meaning LIKE ?)"
        )
        needle = f"%{search.strip()}%"
        params.extend([needle] * 4)
    rows = connection.execute(
        f"""
        SELECT *,
               (
                   SELECT context_sentence
                   FROM vocabulary_occurrences
                   WHERE entry_id = vocabulary_entries.id
                   ORDER BY id DESC LIMIT 1
               ) AS latest_sentence,
               CASE WHEN encounter_count >= 2 OR manually_frequent = 1 THEN 1 ELSE 0 END AS is_frequent
        FROM vocabulary_entries
        WHERE {' AND '.join(conditions)}
        ORDER BY
                CASE WHEN datetime(last_seen_at) >= datetime('now', '-7 days') THEN 0 ELSE 1 END,
                 is_frequent DESC, encounter_count DESC, last_seen_at DESC
        LIMIT 800
        """,
        params,
    ).fetchall()
    counts = connection.execute(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(CASE WHEN encounter_count >= 2 OR manually_frequent = 1 THEN 1 ELSE 0 END), 0) AS frequent,
               COALESCE(SUM(CASE WHEN study_status = 'mastered' THEN 1 ELSE 0 END), 0) AS mastered,
               COALESCE(SUM(CASE WHEN translation_status != 'ready' THEN 1 ELSE 0 END), 0) AS pending,
               COALESCE(SUM(CASE WHEN translation_status = 'ready'
                              AND study_status != 'mastered'
                              AND (next_review_at IS NULL OR next_review_at <= CURRENT_TIMESTAMP)
                        THEN 1 ELSE 0 END), 0) AS review
        FROM vocabulary_entries
        """
    ).fetchone()
    items = [dict(row) for row in rows]
    return {"items": items, "counts": dict(counts)}


@router.get("/home")
def home_words(
    limit: int = Query(20, ge=1, le=50),
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    rows = connection.execute(
        """
        SELECT id, term, lemma, contextual_meaning, common_meaning,
               encounter_count, study_status,
               CASE WHEN encounter_count >= 2 OR manually_frequent = 1 THEN 1 ELSE 0 END AS is_frequent
        FROM vocabulary_entries
        WHERE translation_status = 'ready'
        ORDER BY
                 CASE WHEN datetime(created_at) >= datetime('now', '-7 days') THEN 0 ELSE 1 END,
                 is_frequent DESC,
                 CASE WHEN next_review_at IS NULL OR next_review_at <= CURRENT_TIMESTAMP THEN 0 ELSE 1 END,
                 encounter_count DESC,
                 RANDOM()
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return {"items": [dict(row) for row in rows]}


@router.post("/translation-runs")
def create_translation_run(
    request: VocabularyTranslationRunRequest,
    background_tasks: BackgroundTasks,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    queued_ids = queue_vocabulary_translations(
        connection,
        request.entry_ids,
        include_all_pending=request.trigger == "practice_exit",
    )
    if queued_ids:
        background_tasks.add_task(translate_queued_vocabulary)
    return {
        "accepted": True,
        "trigger": request.trigger,
        "queuedCount": len(queued_ids),
    }


@router.get("/due-today")
def due_today(
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """获取今日待复习单词列表（FSRS 调度）"""
    from ..services.fsrs_scheduler import get_due_today
    entries = get_due_today(connection)
    return {"count": len(entries), "entries": entries}


@router.get("/stats/summary")
def vocab_stats(
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """单词本学习统计"""
    from ..services.fsrs_scheduler import get_due_count
    total = connection.execute(
        "SELECT COUNT(*) FROM vocabulary_entries"
    ).fetchone()[0]
    mastered = connection.execute(
        "SELECT COUNT(*) FROM vocabulary_entries WHERE study_status = 'mastered'"
    ).fetchone()[0]
    due = get_due_count(connection)
    return {
        "total": total,
        "mastered": mastered,
        "learning": total - mastered,
        "due_today": due,
        "mastery_rate": round(mastered / total * 100, 1) if total > 0 else 0,
    }


@router.get("/article")
def generate_vocab_article(
    topic: str = "随机",
    word_count: int = 8,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """从单词本选词，AI 生成包含这些词的语境短文（辅助记忆）"""
    from ..services.article_generator import generate_article
    return generate_article(connection, topic, word_count)


@router.get("/{entry_id}")
def read_entry(
    entry_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> dict:
    try:
        return _serialize_entry(connection, entry_id)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@router.put("/{entry_id}")
def update_entry(
    entry_id: int,
    request: VocabularyUpdate,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    fields = request.model_dump(exclude_none=True)
    if not fields:
        return _serialize_entry(connection, entry_id)
    allowed = {
        "contextual_meaning",
        "common_meaning",
        "phonetic",
        "part_of_speech",
        "note",
        "study_status",
        "manually_frequent",
    }
    assignments = []
    values: list[object] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        assignments.append(f"{key} = ?")
        values.append(int(value) if key == "manually_frequent" else value)
    assignments.extend(["user_edited = 1", "updated_at = CURRENT_TIMESTAMP"])
    values.append(entry_id)
    connection.execute(
        f"UPDATE vocabulary_entries SET {', '.join(assignments)} WHERE id = ?",
        values,
    )
    connection.commit()
    return _serialize_entry(connection, entry_id)


@router.delete("/{entry_id}")
def delete_entry(
    entry_id: int, connection: sqlite3.Connection = Depends(get_db)
) -> dict:
    connection.execute("DELETE FROM vocabulary_entries WHERE id = ?", (entry_id,))
    connection.commit()
    return {"ok": True}


@router.post("/{entry_id}/retry")
def retry_translation(
    entry_id: int,
    background_tasks: BackgroundTasks,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    connection.execute(
        """
        UPDATE vocabulary_entries
        SET translation_status = 'queued', translation_error = '',
            user_edited = 0, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (entry_id,),
    )
    connection.commit()
    background_tasks.add_task(translate_queued_vocabulary)
    return {"ok": True}


@router.post("/{entry_id}/review")
def submit_review(
    entry_id: int,
    request: VocabularyReview,
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    try:
        return review_entry(connection, entry_id, request.rating)
    except LookupError as error:
        raise HTTPException(404, str(error)) from error


@router.get("/export/anki")
def export_anki_deck(
    status: str = "all",
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """导出单词本为 Anki .apkg 牌组（返回 JSON 元信息 + 下载端点）"""
    from ..services.anki_export import export_anki
    try:
        result = export_anki(connection, status_filter=status)
    except Exception as error:
        raise HTTPException(500, f"导出失败：{error}") from error
    if result["count"] == 0:
        return {"error": "没有可导出的单词", **result}
    return result


@router.get("/export/anki/download")
def download_anki_deck(
    filename: str,
) -> FileResponse:
    """下载已生成的 Anki 牌组文件"""
    from pathlib import Path
    file = Path("exports") / filename
    if not file.is_file():
        raise HTTPException(404, "文件不存在，请先导出")
    return FileResponse(file, media_type="application/octet-stream", filename=filename)
