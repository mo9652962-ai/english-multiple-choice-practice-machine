"""Supplement local CET vocabulary from a traceable public word-list source.

The selected repositories describe their lists as public research material but
do not expose a clear redistribution license. Imported rows therefore carry an
explicit provenance note and must be reviewed before a formal public release.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "backend" / "data" / "question_bank.db"
SOURCE_URLS = {
    "四级·扩充": "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/3%20%E5%9B%9B%E7%BA%A7-%E4%B9%B1%E5%BA%8F.txt",
    "六级·扩充": "https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/4%20%E5%85%AD%E7%BA%A7-%E4%B9%B1%E5%BA%8F.txt",
}
WORD_PATTERN = re.compile(r"^[a-z][a-z' -]*$", re.IGNORECASE)


@dataclass(frozen=True)
class SourceWord:
    term: str
    meaning: str
    category: str
    source_url: str


def _download(url: str, destination: Path) -> None:
    request = Request(url, headers={"User-Agent": "motei-vocabulary-import/1.0"})
    with urlopen(request, timeout=30) as response:
        destination.write_bytes(response.read())


def _parse_source(path: Path, category: str, source_url: str) -> list[SourceWord]:
    records: list[SourceWord] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        fields = raw_line.strip().split("\t", 1)
        if len(fields) != 2:
            continue
        term = re.sub(r"\s+", " ", fields[0].strip().lower())
        meaning = fields[1].strip()
        if not term or not meaning or not WORD_PATTERN.fullmatch(term):
            continue
        if term in seen:
            continue
        seen.add(term)
        records.append(SourceWord(term, meaning, category, source_url))
    return records


def collect_source_words(source_dir: Path | None = None) -> list[SourceWord]:
    words: list[SourceWord] = []
    with tempfile.TemporaryDirectory(prefix="motei-cet-vocab-") as temporary:
        temporary_dir = Path(temporary)
        for index, (category, url) in enumerate(SOURCE_URLS.items()):
            path = (source_dir / f"{category}.txt") if source_dir else temporary_dir / f"source-{index}.txt"
            if not path.is_file():
                _download(url, path)
            words.extend(_parse_source(path, category, url))
    return words


def import_words(connection: sqlite3.Connection, words: list[SourceWord], *, apply: bool) -> dict[str, int]:
    inserted = 0
    existing = 0
    tagged = 0
    skipped = 0
    provenance_note = "来源为公开第三方词表；原仓库未见明确再分发许可证，正式公开前需人工确认授权。"
    for word in words:
        row = connection.execute(
            "SELECT id, category, note FROM vocabulary_entries WHERE normalized_term = ? AND user_id IS NULL",
            (word.term,),
        ).fetchone()
        if row:
            existing += 1
            labels = [label for label in str(row["category"] or "").split("|") if label]
            if word.category not in labels:
                tagged += 1
                if apply:
                    note = str(row["note"] or "")
                    source_note = f"{word.category} 来源：{word.source_url}（授权待核验）"
                    if source_note not in note:
                        note = f"{note}; {source_note}".strip("; ")
                    connection.execute(
                        "UPDATE vocabulary_entries SET category = ?, note = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        ("|".join([*labels, word.category]), note, row["id"]),
                    )
            continue
        if not apply:
            inserted += 1
            continue
        connection.execute(
            """
            INSERT INTO vocabulary_entries
                (user_id, term, normalized_term, lemma, common_meaning,
                 contextual_meaning, translation_status, study_status,
                 manually_frequent, category, note)
            VALUES (NULL, ?, ?, ?, ?, ?, 'ready', 'new', 0, ?, ?)
            """,
            (
                word.term,
                word.term,
                word.term,
                word.meaning,
                word.meaning,
                word.category,
                f"{provenance_note} URL: {word.source_url}",
            ),
        )
        inserted += 1
    if apply:
        connection.commit()
    return {
        "source_words": len(words),
        "inserted": inserted,
        "existing": existing,
        "tagged": tagged,
        "skipped": skipped,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="补充墨题四级/六级词汇")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--source-dir", type=Path, help="使用已下载的四级·扩充.txt/六级·扩充.txt")
    parser.add_argument("--apply", action="store_true", help="实际写入数据库；默认只统计")
    args = parser.parse_args()

    if not args.db.is_file():
        raise FileNotFoundError(args.db)
    words = collect_source_words(args.source_dir)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    try:
        result = import_words(connection, words, apply=args.apply)
    finally:
        connection.close()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
