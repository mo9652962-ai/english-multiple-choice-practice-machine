#!/usr/bin/env python3
"""Import reviewed bilingual vocabulary examples without overwriting user data.

Input is JSONL (or a JSON array) with entries like::

    {"term": "abandon", "examples": [{"english": "...", "chinese": "...",
      "source": "...", "source_url": "...", "verified": true}]}

The importer deliberately accepts source data as an input artifact instead of
scraping a provider in the release process. This keeps licensing, retries, and
translation provenance visible and makes the same dataset usable by Windows,
web, and Android builds.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Iterable


def _records(path: Path) -> Iterable[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("items", [data])
        if not isinstance(data, list):
            raise ValueError("JSON 根节点必须是数组或包含 items 数组")
        yield from (item for item in data if isinstance(item, dict))
        return
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"第 {line_number} 行不是有效 JSON: {error}") from error
        if not isinstance(item, dict):
            raise ValueError(f"第 {line_number} 行必须是 JSON 对象")
        yield item


def _examples(item: dict[str, Any]) -> list[dict[str, Any]]:
    values = item.get("examples", item.get("example", []))
    if isinstance(values, dict):
        values = [values]
    if not isinstance(values, list):
        raise ValueError(f"{item.get('term', '<unknown>')} 的 examples 必须是数组")
    result = []
    for example in values:
        if not isinstance(example, dict):
            raise ValueError(f"{item.get('term', '<unknown>')} 的例句必须是对象")
        english = str(example.get("english", example.get("sentence", ""))).strip()
        chinese = str(example.get("chinese", example.get("translation", ""))).strip()
        if not 10 <= len(english) <= 500:
            raise ValueError(f"{item.get('term', '<unknown>')} 的英文例句长度必须为 10-500")
        if not 2 <= len(chinese) <= 500:
            raise ValueError(f"{item.get('term', '<unknown>')} 的中文翻译长度必须为 2-500")
        result.append(
            {
                "english": english,
                "chinese": chinese,
                "source": str(example.get("source", item.get("source", ""))).strip()[:300],
                "source_url": str(example.get("source_url", item.get("source_url", ""))).strip()[:500],
                "verified": int(bool(example.get("verified", item.get("verified", False)))),
            }
        )
    return result


def import_examples(connection: sqlite3.Connection, records: Iterable[dict[str, Any]], *, dry_run: bool = False) -> dict[str, int]:
    stats = {"words": 0, "examples": 0, "inserted_or_updated": 0, "missing_words": 0}
    errors: list[str] = []
    for item in records:
        term = str(item.get("term", item.get("word", ""))).strip().lower()
        if not term:
            errors.append("缺少 term")
            continue
        row = connection.execute(
            "SELECT id FROM vocabulary_entries WHERE normalized_term = ? OR lower(term) = ? LIMIT 1",
            (term, term),
        ).fetchone()
        if row is None:
            stats["missing_words"] += 1
            errors.append(f"词库不存在: {term}")
            continue
        examples = _examples(item)
        stats["words"] += 1
        stats["examples"] += len(examples)
        for example in examples:
            if not dry_run:
                connection.execute(
                    """
                    INSERT INTO vocabulary_examples
                        (entry_id, english_sentence, chinese_translation, source, source_url, is_verified)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(entry_id, english_sentence) DO UPDATE SET
                        chinese_translation = CASE WHEN vocabulary_examples.is_verified = 1
                            THEN vocabulary_examples.chinese_translation ELSE excluded.chinese_translation END,
                        source = excluded.source,
                        source_url = excluded.source_url,
                        is_verified = MAX(vocabulary_examples.is_verified, excluded.is_verified),
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (row["id"], example["english"], example["chinese"], example["source"], example["source_url"], example["verified"]),
                )
            stats["inserted_or_updated"] += 1
    if errors:
        raise ValueError("; ".join(errors[:10]) + (f"（另有 {len(errors) - 10} 项）" if len(errors) > 10 else ""))
    if not dry_run:
        connection.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="导入有来源、可核验的词汇双语例句")
    parser.add_argument("input", type=Path, help="JSONL 或 JSON 文件")
    parser.add_argument("--db", type=Path, default=Path("backend/data/question_bank.db"))
    parser.add_argument("--dry-run", action="store_true", help="只校验和统计，不写入数据库")
    args = parser.parse_args()
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    try:
        stats = import_examples(connection, _records(args.input), dry_run=args.dry_run)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1
    finally:
        connection.close()
    print(json.dumps(stats, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
