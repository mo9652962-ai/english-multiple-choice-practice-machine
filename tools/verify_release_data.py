#!/usr/bin/env python3
"""Verify release-data contracts and report coverage metrics.

The command is intentionally data-source agnostic. It validates that a build
contains the new schema and template registry, while optional thresholds let a
maintainer gate a private/licensed vocabulary or CET data bundle in CI.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Keep the command runnable as `python tools/verify_release_data.py` from the
# repository root as well as via `PYTHONPATH=backend` in CI.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.exam_templates import supported_exam_types


def _coverage(connection: sqlite3.Connection) -> dict[str, int]:
    total = int(connection.execute("SELECT COUNT(*) FROM vocabulary_entries").fetchone()[0])
    phonetic = int(connection.execute(
        "SELECT COUNT(*) FROM vocabulary_entries WHERE TRIM(phonetic) <> ''"
    ).fetchone()[0])
    paired = int(connection.execute(
        """
        SELECT COUNT(*)
        FROM vocabulary_entries e
        WHERE EXISTS (
            SELECT 1 FROM vocabulary_examples x
            WHERE x.entry_id = e.id
              AND TRIM(x.english_sentence) <> ''
              AND TRIM(x.chinese_translation) <> ''
        )
        """
    ).fetchone()[0])
    cet_papers = int(connection.execute(
        """
        SELECT COUNT(*)
        FROM papers p
        JOIN question_bank_profiles q ON q.id = p.profile_id
        WHERE p.deleted_at IS NULL
          AND q.name IN ('大学英语四级', '大学英语六级')
          AND p.source_file NOT LIKE '%模拟%'
          AND p.source_file NOT LIKE '%ai-generated%'
        """
    ).fetchone()[0])
    return {"vocabulary": total, "phonetic": phonetic, "bilingual_words": paired, "published_cet_papers": cet_papers}


def main() -> int:
    parser = argparse.ArgumentParser(description="检查发布题库结构与数据覆盖率")
    parser.add_argument("--db", type=Path, default=Path("backend/data/question_bank.db"))
    parser.add_argument("--min-phonetic", type=float, default=0.0)
    parser.add_argument("--min-bilingual-examples", type=float, default=0.0)
    parser.add_argument("--min-published-cet-papers", type=int, default=0)
    parser.add_argument("--check-templates", action="store_true")
    args = parser.parse_args()
    connection = sqlite3.connect(args.db)
    try:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
        if "vocabulary_examples" not in tables:
            raise RuntimeError("缺少 vocabulary_examples 表，请先运行数据库迁移")
        metrics = _coverage(connection)
    finally:
        connection.close()
    if args.check_templates and not {"gaokao", "tem4", "tem8"}.issubset(supported_exam_types()):
        raise RuntimeError("考试模板注册表未包含高考、TEM-4、TEM-8")
    total = metrics["vocabulary"] or 1
    if metrics["phonetic"] / total < args.min_phonetic:
        raise RuntimeError(f"音标覆盖率不足: {metrics['phonetic']}/{metrics['vocabulary']}")
    if metrics["bilingual_words"] / total < args.min_bilingual_examples:
        raise RuntimeError(f"双语例句覆盖率不足: {metrics['bilingual_words']}/{metrics['vocabulary']}")
    if metrics["published_cet_papers"] < args.min_published_cet_papers:
        raise RuntimeError(f"已发布四六级真题套数不足: {metrics['published_cet_papers']}")
    print(json.dumps({**metrics, "phonetic_rate": round(metrics["phonetic"] / total, 4), "bilingual_rate": round(metrics["bilingual_words"] / total, 4)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
