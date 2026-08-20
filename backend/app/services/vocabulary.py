from __future__ import annotations

import json
import re
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Any

import httpx

from ..database import connect
from .ai_client import chat_completion, parse_json_response


TERM_RE = re.compile(r"^[A-Za-z][A-Za-z'’-]*(?:\s+[A-Za-z][A-Za-z'’-]*){0,4}$")
TRANSLATION_BATCH_SIZE = 8
MAX_TRANSLATIONS_PER_RUN = 100
_TRANSLATION_LOCK = threading.Lock()


def normalize_term(value: str) -> str:
    value = value.strip().replace("’", "'")
    value = re.sub(r"\s+", " ", value)
    return value.lower()


def vocabulary_key(value: str) -> str:
    """Create a conservative local key for common inflected word forms."""
    normalized = normalize_term(value)
    if " " in normalized or "'" in normalized or len(normalized) < 5:
        return normalized
    if normalized.endswith("ies") and len(normalized) > 5:
        return normalized[:-3] + "y"
    if normalized.endswith("ing") and len(normalized) > 6:
        stem = normalized[:-3]
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if normalized.endswith("ed") and len(normalized) > 5:
        stem = normalized[:-2]
        if stem.endswith("i"):
            return stem[:-1] + "y"
        if len(stem) >= 3 and stem[-1] == stem[-2]:
            stem = stem[:-1]
        return stem
    if normalized.endswith("es") and len(normalized) > 5:
        if normalized.endswith(("ses", "xes", "zes", "ches", "shes")):
            return normalized[:-2]
        return normalized[:-1]
    if normalized.endswith("s") and not normalized.endswith("ss"):
        return normalized[:-1]
    return normalized


def _discrimination_list(value: Any, limit: int = 3) -> list[dict[str, str]]:
    """Normalize model-provided synonym/antonym/similar-form entries."""
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
    else:
        parsed = value
    if not isinstance(parsed, list):
        return []
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in parsed:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word", "")).strip()
        note = str(item.get("note", "") or item.get("reason", "")).strip()
        if not word or len(word) > 60:
            continue
        key = word.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append({"word": word[:60], "note": note[:80]})
        if len(result) >= limit:
            break
    return result


def _match_key(term: str) -> str:
    return re.sub(r"[^a-z]", "", term.lower())


def _edit_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, 1):
        current = [index]
        for right_index, right_char in enumerate(right, 1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[right_index - 1] + 1,
                    previous[right_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def local_similar_matches(
    connection: sqlite3.Connection,
    entry_ids: list[int],
    *,
    max_distance: int = 2,
    limit: int = 4,
) -> dict[int, list[dict[str, str]]]:
    """Find words already in the wordbook whose spelling is close to each entry."""
    if not entry_ids:
        return {}
    # v9.25: 性能修复——不再全表拉取 + 全量 Levenshtein（数万词 OOM/CPU 100%）
    # 改为 SQL 前缀匹配候选池（按 term 首字符粗筛 + LIMIT 200）
    pool_by_id: dict[int, dict] = {}
    buckets: dict[int, list[tuple[int, str, str]]] = {}
    for entry_id in {int(value) for value in entry_ids}:
        row = connection.execute(
            "SELECT id, term FROM vocabulary_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if row is None:
            continue
        pool_by_id[row["id"]] = row
        own_key = _match_key(row["term"])
        prefix = own_key[:2] if len(own_key) >= 2 else (own_key[:1] or "")
        if prefix:
            cands = connection.execute(
                "SELECT id, term FROM vocabulary_entries WHERE term LIKE ? LIMIT 200",
                (prefix + "%",),
            ).fetchall()
        else:
            cands = connection.execute(
                "SELECT id, term FROM vocabulary_entries LIMIT 200"
            ).fetchall()
        for crow in cands:
            if crow["id"] in buckets:
                continue
            key = _match_key(crow["term"])
            buckets.setdefault(len(key), []).append((crow["id"], key, crow["term"]))
    result: dict[int, list[dict[str, str]]] = {}
    for entry_id, term_row in pool_by_id.items():
        own_key = _match_key(term_row["term"])
        candidates: list[tuple[int, str]] = []
        for length in range(max(1, len(own_key) - 2), len(own_key) + 3):
            for pool_id, pool_key, pool_term in buckets.get(length, []):
                if pool_id == entry_id:
                    continue
                if abs(len(pool_key) - len(own_key)) > 2:
                    continue
                distance = _edit_distance(own_key, pool_key)
                if distance <= max_distance:
                    candidates.append((distance, pool_term))
        candidates.sort(key=lambda item: (item[0], item[1]))
        result[entry_id] = [
            {"word": term, "note": "本地匹配", "source": "本地匹配"}
            for _, term in candidates[:limit]
        ]
    return result


def _enrich_discrimination(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
) -> None:
    """Parse stored JSON columns and attach local wordbook matches."""
    model_similar = _discrimination_list(payload.get("similar_forms"))
    payload["synonyms"] = _discrimination_list(payload.get("synonyms"))
    payload["antonyms"] = _discrimination_list(payload.get("antonyms"))
    payload["similar_forms"] = model_similar
    local = local_similar_matches(connection, [int(payload["id"])]).get(
        int(payload["id"]), []
    )
    model_words = {item["word"].lower() for item in model_similar}
    payload["local_similar"] = [
        item for item in local if item["word"].lower() not in model_words
    ]


def validate_term(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip())
    if not TERM_RE.fullmatch(normalized):
        raise ValueError("请选择一个英文单词或不超过 5 个词的英文短语")
    return normalized


def model_text(value: Any, limit: int) -> str:
    """Normalize model JSON fields into clean, readable text for the UI."""
    if isinstance(value, list):
        value = "、".join(str(item).strip() for item in value if str(item).strip())
    elif isinstance(value, dict):
        value = "；".join(
            f"{key}: {item}" for key, item in value.items() if str(item).strip()
        )
    return str(value or "").strip()[:limit]


def clean_meaning(value: Any, limit: int = 1000) -> str:
    """Keep vocabulary meanings concise and remove model-added annotations."""
    text = model_text(value, limit * 2)
    text = re.sub(r"^\s*[（(][^（）()]{0,200}[）)]\s*", "", text)
    text = re.sub(r"^\s*[【\[][^【】\[\]]{0,200}[】\]]\s*", "", text)
    text = re.sub(
        r"^\s*(?:当前语境(?:中)?(?:的)?(?:意思|含义|释义)|"
        r"语境(?:意思|含义|释义)|在(?:本句|此处|这里)(?:中)?(?:意为|表示)?|"
        r"常见(?:意思|含义|释义))\s*[：:]\s*",
        "",
        text,
    )
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\s*[（(][^（）()]{0,160}[）)]\s*$", "", text)
        text = re.sub(r"\s*[【\[][^【】\[\]]{0,160}[】\]]\s*$", "", text)
    text = re.sub(
        r"\s*[，,；;]\s*(?:(?:在)?(?:本句|句子|原句|本文|此处|这里)(?:中)?"
        r"(?:通常|具体)?\s*)?(?:通常|具体)?\s*(?:指|表示|强调|说明).*$",
        "",
        text,
    )
    return text.strip(" \t\r\n，,；;：:")[:limit]


def clean_machine_meanings(connection: sqlite3.Connection) -> int:
    """Clean existing model translations without touching user-edited entries."""
    rows = connection.execute(
        """
        SELECT id, contextual_meaning, common_meaning
        FROM vocabulary_entries
        WHERE user_edited = 0 AND translation_status = 'ready'
        """
    ).fetchall()
    changed = 0
    for row in rows:
        contextual = clean_meaning(row["contextual_meaning"])
        common = clean_meaning(row["common_meaning"])
        if (
            contextual == row["contextual_meaning"]
            and common == row["common_meaning"]
        ):
            continue
        connection.execute(
            """
            UPDATE vocabulary_entries
            SET contextual_meaning = ?, common_meaning = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_edited = 0
            """,
            (contextual, common, row["id"]),
        )
        changed += 1
    if changed:
        connection.commit()
    return changed


def _serialize_entry(connection: sqlite3.Connection, entry_id: int) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM vocabulary_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if row is None:
        raise LookupError("单词不存在")
    payload = dict(row)
    payload["is_frequent"] = bool(
        payload["manually_frequent"] or payload["encounter_count"] >= 2
    )
    payload["occurrences"] = [
        dict(item)
        for item in connection.execute(
            """
            SELECT * FROM vocabulary_occurrences
            WHERE entry_id = ? ORDER BY id DESC
            """,
            (entry_id,),
        ).fetchall()
    ]
    _enrich_discrimination(connection, payload)
    return payload


def add_vocabulary(
    connection: sqlite3.Connection, data: dict[str, Any], user_id: int | None = None
) -> dict[str, Any]:
    term = validate_term(data["term"])
    normalized = vocabulary_key(term)
    # v9.24: 多用户——按 user_id 查重（user_id None = 匿名/本地单用户）
    if user_id is not None:
        row = connection.execute(
            """SELECT id, encounter_count, study_status, translation_status, user_edited
            FROM vocabulary_entries WHERE normalized_term = ? AND user_id = ?""",
            (normalized, user_id),
        ).fetchone()
    else:
        row = connection.execute(
            """SELECT id, encounter_count, study_status, translation_status, user_edited
            FROM vocabulary_entries WHERE normalized_term = ? AND user_id IS NULL""",
            (normalized,),
        ).fetchone()
    is_new = row is None
    if is_new:
        cursor = connection.execute(
            """INSERT INTO vocabulary_entries
                (term, normalized_term, translation_status, user_id)
            VALUES (?, ?, 'pending', ?)
            ON CONFLICT(user_id, normalized_term) DO NOTHING""",
            (term, normalized, user_id),
        )
        # v9.25: 并发双击竞态——ON CONFLICT DO NOTHING 后 lastrowid 为 None → 走已存在路径
        if cursor.lastrowid is None:
            is_new = False
            if user_id is not None:
                row = connection.execute(
                    """SELECT id, encounter_count, study_status, translation_status, user_edited
                    FROM vocabulary_entries WHERE normalized_term = ? AND user_id = ?""",
                    (normalized, user_id),
                ).fetchone()
            else:
                row = connection.execute(
                    """SELECT id, encounter_count, study_status, translation_status, user_edited
                    FROM vocabulary_entries WHERE normalized_term = ? AND user_id IS NULL""",
                    (normalized,),
                ).fetchone()
        entry_id = cursor.lastrowid if cursor.lastrowid is not None else (row["id"] if row is not None else None)
    else:
        entry_id = row["id"]
        next_status = (
            "pending"
            if row["translation_status"] in {"pending", "failed"} and not row["user_edited"]
            else row["translation_status"]
        )
        connection.execute(
            """
            UPDATE vocabulary_entries
            SET encounter_count = encounter_count + 1,
                study_status = 'learning',
                translation_status = ?,
                translation_error = CASE WHEN ? = 'pending' THEN '' ELSE translation_error END,
                last_seen_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (next_status, next_status, entry_id),
        )
    connection.execute(
        """
        INSERT INTO vocabulary_occurrences
            (entry_id, surface_form, context_sentence, context_before,
             context_after, unit_id, question_id, year, unit_title, unit_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            term,
            data.get("context_sentence", "")[:1500],
            data.get("context_before", "")[:1000],
            data.get("context_after", "")[:1000],
            data.get("unit_id"),
            data.get("question_id"),
            data.get("year"),
            data.get("unit_title", ""),
            data.get("unit_type", ""),
        ),
    )
    connection.commit()
    entry = _serialize_entry(connection, entry_id)
    return {
        "entry_id": entry_id,
        "is_new": is_new,
        "encounter_count": entry["encounter_count"],
        "is_frequent": entry["is_frequent"],
        "translation_status": entry["translation_status"],
    }


def _has_translation_model(connection: sqlite3.Connection) -> bool:
    profile = connection.execute(
        """
        SELECT 1
        FROM ai_profiles
        WHERE enabled = 1 AND TRIM(default_model) <> ''
        LIMIT 1
        """
    ).fetchone()
    if profile:
        return True
    legacy = connection.execute(
        """
        SELECT 1
        FROM ai_settings
        WHERE id = 1 AND TRIM(model) <> ''
        LIMIT 1
        """
    ).fetchone()
    return legacy is not None


def queue_vocabulary_translations(
    connection: sqlite3.Connection,
    entry_ids: list[int],
    *,
    include_all_pending: bool = False,
) -> list[int]:
    unique_ids = list(dict.fromkeys(int(entry_id) for entry_id in entry_ids if int(entry_id) > 0))[:100]
    if include_all_pending:
        pending_rows = connection.execute(
            """
            SELECT id FROM vocabulary_entries
            WHERE user_edited = 0 AND translation_status IN ('pending', 'queued')
            ORDER BY updated_at, id
            LIMIT ?
            """,
            (MAX_TRANSLATIONS_PER_RUN,),
        ).fetchall()
        unique_ids = list(
            dict.fromkeys(
                [*unique_ids, *(int(row["id"]) for row in pending_rows)]
            )
        )[:100]
    if unique_ids:
        placeholders = ",".join("?" for _ in unique_ids)
        connection.execute(
            f"""
            UPDATE vocabulary_entries
            SET translation_status = 'queued', translation_error = '',
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
              AND user_edited = 0
              AND translation_status IN ('pending', 'queued', 'failed')
            """,
            unique_ids,
        )
        rows = connection.execute(
            f"""
            SELECT id
            FROM vocabulary_entries
            WHERE id IN ({placeholders})
              AND user_edited = 0
              AND translation_status = 'queued'
            ORDER BY id
            """,
            unique_ids,
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT id
            FROM vocabulary_entries
            WHERE user_edited = 0
              AND translation_status IN ('pending', 'queued')
            ORDER BY updated_at, id
            LIMIT ?
            """,
            (MAX_TRANSLATIONS_PER_RUN,),
        ).fetchall()
    connection.commit()
    return [row["id"] for row in rows]


def _translation_rows(
    connection: sqlite3.Connection,
    entry_ids: list[int],
) -> list[dict[str, Any]]:
    if not entry_ids:
        return []
    placeholders = ",".join("?" for _ in entry_ids)
    rows = connection.execute(
        f"""
        SELECT vocabulary_entries.*,
               (
                   SELECT context_sentence
                   FROM vocabulary_occurrences
                   WHERE entry_id = vocabulary_entries.id
                   ORDER BY id DESC LIMIT 1
               ) AS context_sentence,
               (
                   SELECT context_before
                   FROM vocabulary_occurrences
                   WHERE entry_id = vocabulary_entries.id
                   ORDER BY id DESC LIMIT 1
               ) AS context_before,
               (
                   SELECT context_after
                   FROM vocabulary_occurrences
                   WHERE entry_id = vocabulary_entries.id
                   ORDER BY id DESC LIMIT 1
               ) AS context_after,
               (
                   SELECT year
                   FROM vocabulary_occurrences
                   WHERE entry_id = vocabulary_entries.id
                   ORDER BY id DESC LIMIT 1
               ) AS source_year,
               (
                   SELECT unit_title
                   FROM vocabulary_occurrences
                   WHERE entry_id = vocabulary_entries.id
                   ORDER BY id DESC LIMIT 1
               ) AS source_unit_title,
               (
                   SELECT unit_type
                   FROM vocabulary_occurrences
                   WHERE entry_id = vocabulary_entries.id
                   ORDER BY id DESC LIMIT 1
               ) AS source_unit_type
        FROM vocabulary_entries
        WHERE id IN ({placeholders})
          AND user_edited = 0
          AND translation_status = 'translating'
        ORDER BY id
        """,
        entry_ids,
    ).fetchall()
    return [dict(row) for row in rows]


def _mark_translation_failed(
    connection: sqlite3.Connection,
    entry_ids: list[int],
    error: Exception,
) -> None:
    if not entry_ids:
        return
    placeholders = ",".join("?" for _ in entry_ids)
    connection.execute(
        f"""
        UPDATE vocabulary_entries
        SET translation_status = 'failed', translation_error = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders})
          AND user_edited = 0
          AND translation_status = 'translating'
        """,
        (str(error)[:800], *entry_ids),
    )
    connection.commit()


def _translate_vocabulary_batch(
    connection: sqlite3.Connection,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        return
    prompt = """
你是考研英语语境词汇助手。请批量分析用户标记的单词或短语，并结合各自真题原句判断含义。
只返回 JSON，不要使用 Markdown。格式必须为：
{
  "translations": [
    {
      "entryId": 123,
      "lemma": "词形还原；短语保持原形",
      "phonetic": "常见英式或美式音标；不确定则留空",
      "partOfSpeech": "简短词性",
      "contextualMeaning": "该原句中的准确中文释义",
      "commonMeaning": "一到三个常见中文释义",
      "memoryHint": "一句简短记忆提示，不编造词源",
      "synonyms": [{"word": "同义词", "note": "一句极简辨析"}],
      "antonyms": [{"word": "反义词", "note": "一句极简辨析"}],
      "similarForms": [{"word": "形近词", "note": "一句极简辨析"}]
    }
  ]
}
必须原样返回每个 entryId，不能增加不存在的 ID。释义只填写可直接背诵的简洁中文词义，
不得加入括号、方括号、语境说明、来源说明、例句解释或“在本文中”“这里指”等标注。
同义词/反义词/形近词每组 0-3 条，辨析各用一句话（30 字以内）说明差别或易混点；
如果该词没有自然的同义、反义或形近词，对应数组返回空数组 []，不要强行编造或凑数。
"""
    items = [
        {
            "entryId": row["id"],
            "term": row["term"],
            "sentence": row.get("context_sentence", ""),
            "before": row.get("context_before", ""),
            "after": row.get("context_after", ""),
            "source": {
                "year": row.get("source_year"),
                "unitTitle": row.get("source_unit_title"),
                "unitType": row.get("source_unit_type"),
            },
        }
        for row in rows
    ]
    expected_ids = {row["id"] for row in rows}
    try:
        content = chat_completion(
            connection,
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            max_tokens=None,
        )
        parsed = parse_json_response(content)
        translations = parsed.get("translations") if isinstance(parsed, dict) else None
        if not isinstance(translations, list):
            raise ValueError("模型没有返回 translations 数组")
        received_ids: set[int] = set()
        for item in translations:
            if not isinstance(item, dict):
                continue
            entry_id = item.get("entryId")
            if not isinstance(entry_id, int) or entry_id not in expected_ids or entry_id in received_ids:
                continue
            contextual = clean_meaning(item.get("contextualMeaning", ""), 1000)
            if not contextual:
                continue
            received_ids.add(entry_id)
            connection.execute(
                """
                UPDATE vocabulary_entries
                SET lemma = ?, phonetic = ?, part_of_speech = ?,
                    contextual_meaning = ?, common_meaning = ?, memory_hint = ?,
                    synonyms = ?, antonyms = ?, similar_forms = ?,
                    translation_status = 'ready', translation_error = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_edited = 0
                  AND translation_status = 'translating'
                """,
                (
                    model_text(item.get("lemma", ""), 120),
                    model_text(item.get("phonetic", ""), 120),
                    model_text(item.get("partOfSpeech", ""), 80),
                    contextual,
                    clean_meaning(item.get("commonMeaning", ""), 1000),
                    model_text(item.get("memoryHint", ""), 1000),
                    json.dumps(_discrimination_list(item.get("synonyms")), ensure_ascii=False),
                    json.dumps(_discrimination_list(item.get("antonyms")), ensure_ascii=False),
                    json.dumps(_discrimination_list(item.get("similarForms")), ensure_ascii=False),
                    entry_id,
                ),
            )
        missing_ids = sorted(expected_ids - received_ids)
        connection.commit()
        if missing_ids:
            raise ValueError(f"模型漏掉了 {len(missing_ids)} 个单词")
    except (ValueError, LookupError, json.JSONDecodeError, httpx.HTTPError) as error:
        if len(rows) > 1:
            middle = len(rows) // 2
            _translate_vocabulary_batch(connection, rows[:middle])
            _translate_vocabulary_batch(connection, rows[middle:])
            return
        _mark_translation_failed(connection, [rows[0]["id"]], error)


def translate_queued_vocabulary() -> dict[str, int]:
    # v9.23: 非阻塞互斥——已有翻译任务在跑时跳过本次触发（防后台任务堆积/重复翻译）
    if not _TRANSLATION_LOCK.acquire(blocking=False):
        return {"translated": 0, "remaining": 0, "skipped": True}
    translated = 0
    try:
        with connect() as connection:
            if not _has_translation_model(connection):
                return {"translated": 0, "remaining": 0}
            # v9.25: 原子认领（去掉 BEGIN IMMEDIATE——避免与 sqlite3 隐式事务冲突）
            # 认领条件含僵尸自愈: 超时 10 分钟的 translating 任务重新入队
            cursor = connection.execute(
                """
                UPDATE vocabulary_entries
                SET translation_status = 'translating',
                    translation_error = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id IN (
                    SELECT id FROM vocabulary_entries
                    WHERE user_edited = 0
                      AND (
                        translation_status = 'queued'
                        OR (translation_status = 'translating'
                            AND updated_at < datetime('now', '-10 minutes'))
                      )
                    ORDER BY updated_at, id
                    LIMIT ?
                )
                """,
                (MAX_TRANSLATIONS_PER_RUN,),
            )
            connection.commit()
            claimed = cursor.rowcount
            if claimed == 0:
                return {"translated": 0, "remaining": 0}
            entry_ids = [
                r["id"]
                for r in connection.execute(
                    f"""
                    SELECT id FROM vocabulary_entries
                    WHERE translation_status = 'translating'
                    ORDER BY updated_at, id
                    LIMIT {claimed}
                    """
                ).fetchall()
            ]
            if not entry_ids:
                return {"translated": 0, "remaining": 0}
            claimed_rows = _translation_rows(connection, entry_ids)
            for index in range(0, len(claimed_rows), TRANSLATION_BATCH_SIZE):
                batch = claimed_rows[index:index + TRANSLATION_BATCH_SIZE]
                _translate_vocabulary_batch(connection, batch)
            translated = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM vocabulary_entries
                WHERE id IN ({placeholders}) AND translation_status = 'ready'
                """,
                entry_ids,
            ).fetchone()[0]
            remaining = connection.execute(
                """
                SELECT COUNT(*)
                FROM vocabulary_entries
                WHERE user_edited = 0
                  AND translation_status = 'queued'
                """
            ).fetchone()[0]
            return {"translated": translated, "remaining": remaining}
    finally:
        _TRANSLATION_LOCK.release()


def translate_vocabulary_entry(entry_id: int) -> None:
    with connect() as connection:
        entry = connection.execute(
            "SELECT * FROM vocabulary_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if entry is None or entry["user_edited"]:
            return
        occurrence = connection.execute(
            """
            SELECT * FROM vocabulary_occurrences
            WHERE entry_id = ? ORDER BY id DESC LIMIT 1
            """,
            (entry_id,),
        ).fetchone()
        context = dict(occurrence) if occurrence else {}
        prompt = """
你是考研英语语境词汇助手。请分析用户标记的单词或短语，必须结合真题原句判断含义。
只返回 JSON，不要使用 Markdown。字段必须为：
{
  "lemma": "词形还原；短语保持原形",
  "phonetic": "常见英式或美式音标；不确定则留空",
  "part_of_speech": "简短词性",
  "contextual_meaning": "该原句中的准确中文释义",
  "common_meaning": "一到三个常见中文释义",
  "memory_hint": "一句简短记忆提示，不编造词源",
  "synonyms": [{"word": "同义词", "note": "一句极简辨析"}],
  "antonyms": [{"word": "反义词", "note": "一句极简辨析"}],
  "similar_forms": [{"word": "形近词", "note": "一句极简辨析"}]
}
释义字段只允许填写可直接背诵的简洁中文词义。不得添加括号、方括号、语境说明、
来源说明、适用对象、例句解释或“在本文中”“这里指”等标注。
例如只写“随机地；任意地”，不要写“随机地（指面试者的选择方式）”。
同义词/反义词/形近词每组 0-3 条，辨析各用一句话（30 字以内）说明差别或易混点；
如果该词没有自然的同义、反义或形近词，对应数组返回空数组 []，不要强行编造或凑数。
"""
        user_payload = {
            "term": entry["term"],
            "sentence": context.get("context_sentence", ""),
            "before": context.get("context_before", ""),
            "after": context.get("context_after", ""),
            "source": {
                "year": context.get("year"),
                "unit_title": context.get("unit_title"),
                "unit_type": context.get("unit_type"),
            },
        }
        try:
            content = chat_completion(
                connection,
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
            )
            result = parse_json_response(content)
            if not isinstance(result, dict) or not result.get("contextual_meaning"):
                raise ValueError("模型没有返回有效的语境释义")
            connection.execute(
                """
                UPDATE vocabulary_entries
                SET lemma = ?, phonetic = ?, part_of_speech = ?,
                    contextual_meaning = ?, common_meaning = ?, memory_hint = ?,
                    synonyms = ?, antonyms = ?, similar_forms = ?,
                    translation_status = 'ready', translation_error = '',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_edited = 0
                """,
                (
                    model_text(result.get("lemma", ""), 120),
                    model_text(result.get("phonetic", ""), 120),
                    model_text(result.get("part_of_speech", ""), 80),
                    clean_meaning(result.get("contextual_meaning", ""), 1000),
                    clean_meaning(result.get("common_meaning", ""), 1000),
                    model_text(result.get("memory_hint", ""), 1000),
                    json.dumps(_discrimination_list(result.get("synonyms")), ensure_ascii=False),
                    json.dumps(_discrimination_list(result.get("antonyms")), ensure_ascii=False),
                    json.dumps(_discrimination_list(result.get("similar_forms")), ensure_ascii=False),
                    entry_id,
                ),
            )
        except (ValueError, LookupError, json.JSONDecodeError, httpx.HTTPError) as error:
            connection.execute(
                """
                UPDATE vocabulary_entries
                SET translation_status = 'failed', translation_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (str(error)[:800], entry_id),
            )
        connection.commit()


def review_entry(
    connection: sqlite3.Connection, entry_id: int, rating: str
) -> dict[str, Any]:
    """复习单词，使用 FSRS 算法安排下次复习
    
    评分映射: again→Again(不认识) hard→Hard(有点印象) mastered→Good(已掌握)
    """
    from .fsrs_scheduler import review_card, card_from_db, card_to_dict
    
    now = datetime.now()
    
    # 尝试从数据库读取 FSRS Card 状态
    row = connection.execute(
        "SELECT * FROM vocabulary_entries WHERE id = ?", (entry_id,)
    ).fetchone()
    if not row:
        raise LookupError(f"单词 id={entry_id} 不存在")
    
    # 恢复 FSRS Card
    card = card_from_db(dict(row))
    new_card, retrievability, interval_desc = review_card(card, rating)
    fsrs_data = card_to_dict(new_card)
    
    # 旧字段兼容
    delays = {"again": 1, "hard": 3, "mastered": 7}
    next_review = datetime.fromisoformat(fsrs_data["fsrs_due"]) if fsrs_data["fsrs_due"] else (now + timedelta(days=delays[rating]))
    status = "mastered" if rating == "mastered" else "learning"
    
    connection.execute(
        """UPDATE vocabulary_entries
           SET study_status = ?, last_reviewed_at = ?, next_review_at = ?,
               fsrs_due = ?, fsrs_stability = ?, fsrs_difficulty = ?,
               fsrs_state = ?, fsrs_step = ?, fsrs_last_review = ?,
               updated_at = CURRENT_TIMESTAMP
           WHERE id = ?""",
        (
            status,
            now.isoformat(timespec="seconds"),
            next_review.isoformat(timespec="seconds"),
            fsrs_data["fsrs_due"],
            fsrs_data["fsrs_stability"],
            fsrs_data["fsrs_difficulty"],
            fsrs_data["fsrs_state"],
            fsrs_data["fsrs_step"],
            fsrs_data["fsrs_last_review"],
            entry_id,
        ),
    )
    connection.execute(
        """INSERT INTO vocabulary_reviews (entry_id, rating, next_review_at)
           VALUES (?, ?, ?)""",
        (entry_id, rating, next_review.isoformat(timespec="seconds")),
    )
    connection.commit()
    # v9.19: 记录 streak 学习行为
    try:
        from .streak import record_activity
        record_activity(connection, "vocab_review", f"entry {entry_id}")
    except Exception:
        pass
    return _serialize_entry(connection, entry_id)
