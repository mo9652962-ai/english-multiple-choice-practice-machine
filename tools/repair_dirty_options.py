"""Repair options rows containing multiple labelled choices.

The command is intentionally conservative: it only rewrites questions for
which a tab/newline followed by an A-D marker can be split unambiguously. A
SQLite backup is created before every mutating run, and running the command
again is a no-op because repaired rows no longer match the dirty pattern.

Examples:
    python tools/repair_dirty_options.py
    python tools/repair_dirty_options.py --db path/to/question_bank.db --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.option_cleanup import split_embedded_option_content


EXPECTED_KEYS = {"A", "B", "C", "D"}


def _backup_database(db_path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = backup_dir / f"question_bank_dirty_options_{stamp}.db"
    if destination.exists():
        destination = backup_dir / (
            f"question_bank_dirty_options_{stamp}_{datetime.now().microsecond:06d}.db"
        )
    source = sqlite3.connect(str(db_path))
    target = sqlite3.connect(str(destination))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination


def _load_question_options(
    connection: sqlite3.Connection, question_id: int
) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM options WHERE question_id = ? ORDER BY sequence, id",
        (question_id,),
    ).fetchall()


def _repaired_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]] | None:
    repaired: list[dict[str, Any]] = []
    changed = False
    for row in rows:
        pieces = split_embedded_option_content(row["stable_key"], row["content"])
        changed = changed or len(pieces) > 1 or pieces[0][1] != row["content"].strip()
        for key, content in pieces:
            if not key or not content:
                return None
            item = dict(row)
            item["stable_key"] = key
            item["original_label"] = key
            item["content"] = content
            repaired.append(item)
    if not changed:
        return None
    keys = [item["stable_key"] for item in repaired]
    if len(keys) != len(set(keys)) or not set(keys).issubset(EXPECTED_KEYS):
        return None
    return repaired


def _repair_answer(answer: Any, rows: list[dict[str, Any]]) -> str | None:
    """Map legacy numeric answers to the rebuilt option stable keys."""

    value = str(answer or "").strip().upper()
    keys = [row["stable_key"] for row in rows]
    if value in keys:
        return value
    if value.isdigit():
        index = int(value) - 1
        if 0 <= index < len(keys):
            return keys[index]
    return None


def repair_database(
    db_path: Path, *, backup_dir: Path, dry_run: bool = False
) -> dict[str, Any]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        question_ids = [
            int(row["question_id"])
            for row in connection.execute(
                """
                SELECT DISTINCT question_id FROM options
                WHERE instr(content, char(9)) > 0
                   OR (instr(content, char(10)) > 0 AND content GLOB '*[A-D].*')
                ORDER BY question_id
                """
            )
        ]
        plans: list[tuple[int, list[dict[str, Any]], str | None]] = []
        skipped: list[int] = []
        answer_updates = 0
        for question_id in question_ids:
            original_rows = _load_question_options(connection, question_id)
            rows = _repaired_rows(original_rows)
            if rows is None:
                skipped.append(question_id)
            else:
                question = connection.execute(
                    "SELECT answer FROM questions WHERE id = ?", (question_id,)
                ).fetchone()
                answer = _repair_answer(question["answer"] if question else "", rows)
                if question and answer is None:
                    skipped.append(question_id)
                    continue
                if question and answer != question["answer"]:
                    answer_updates += 1
                plans.append((question_id, rows, answer))
        result: dict[str, Any] = {
            "database": str(db_path),
            "questions_changed": len(plans),
            "options_before": sum(
                len(_load_question_options(connection, qid)) for qid, _, _ in plans
            ),
            "options_after": sum(len(rows) for _, rows, _ in plans),
            "answer_updates": answer_updates,
            "skipped_question_ids": skipped,
            "dry_run": dry_run,
        }
        if dry_run or not plans:
            return result

        backup_path = _backup_database(db_path, backup_dir)
        result["backup"] = str(backup_path)
        try:
            connection.execute("BEGIN")
            for question_id, rows, answer in plans:
                connection.execute(
                    "DELETE FROM options WHERE question_id = ?", (question_id,)
                )
                for sequence, row in enumerate(rows, 1):
                    columns = [
                        "question_id",
                        "stable_key",
                        "original_label",
                        "content",
                        "sequence",
                    ]
                    values: list[Any] = [
                        question_id,
                        row["stable_key"],
                        row["original_label"],
                        row["content"],
                        sequence,
                    ]
                    if "metadata" in row.keys():
                        columns.append("metadata")
                        values.append(row["metadata"] or "{}")
                    placeholders = ", ".join("?" for _ in columns)
                    connection.execute(
                        f"INSERT INTO options ({', '.join(columns)}) VALUES ({placeholders})",
                        values,
                    )
                if answer is not None:
                    connection.execute(
                        "UPDATE questions SET answer = ? WHERE id = ?",
                        (answer, question_id),
                    )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        return result
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "backend"
        / "data"
        / "question_bank.db",
    )
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    backup_dir = args.backup_dir or args.db.parent / "backups"
    result = repair_database(args.db, backup_dir=backup_dir, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
