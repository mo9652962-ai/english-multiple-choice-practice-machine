"""Create a sanitized, reproducible content bundle for release CI.

The local release and offline databases are intentionally git-ignored because
they are mutable runtime files.  This command makes a transportable bundle
from them without carrying accounts, AI state, practice history, diagnostics,
or other user data into a CI content input.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CONTENT_VERSION_FILE = ROOT / "CONTENT_VERSION"
OFFLINE_CONTENT_VERSION_FILE = ROOT / "OFFLINE_CONTENT_VERSION"

# These tables describe public content or the schema itself.  Everything else
# is cleared from the bundle, even if it currently happens to be empty.
PRESERVED_TABLES = {
    "question_bank_profiles",
    "question_bank_packages",
    "papers",
    "units",
    "questions",
    "options",
    "question_bank_assets",
    "question_bank_revisions",
    "question_ai_labels",
    "question_label_run_items",
    "question_explanations",
    "vocabulary_entries",
    "vocabulary_examples",
    "schema_migrations",
}


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _tables(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({_quote(table)})")
    }


def _delete_by_ids(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    values: list[int] | list[str],
) -> int:
    if not values or column not in _columns(connection, table):
        return 0
    placeholders = ",".join("?" for _ in values)
    cursor = connection.execute(
        f"DELETE FROM {_quote(table)} WHERE {_quote(column)} IN ({placeholders})",
        values,
    )
    return int(cursor.rowcount if cursor.rowcount >= 0 else 0)


def _sanitize_database(source: Path, target: Path) -> dict[str, object]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as source_connection, closing(
        sqlite3.connect(target)
    ) as target_connection:
        source_connection.backup(target_connection)

    with closing(sqlite3.connect(target)) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        tables = _tables(connection)
        removed: dict[str, int] = {}

        if "papers" in tables:
            paper_columns = _columns(connection, "papers")
            where = "deleted_at IS NOT NULL"
            if "status" in paper_columns:
                where += " OR COALESCE(status, '') <> 'published'"
            stale_papers = [
                int(row[0])
                for row in connection.execute(
                    f"SELECT id FROM {_quote('papers')} WHERE {where}"
                ).fetchall()
            ]
        else:
            stale_papers = []

        stale_units = (
            [
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM units WHERE paper_id IN ({})".format(
                        ",".join("?" for _ in stale_papers)
                    ),
                    stale_papers,
                ).fetchall()
            ]
            if stale_papers and "units" in tables
            else []
        )
        stale_questions = (
            [
                int(row[0])
                for row in connection.execute(
                    "SELECT id FROM questions WHERE unit_id IN ({})".format(
                        ",".join("?" for _ in stale_units)
                    ),
                    stale_units,
                ).fetchall()
            ]
            if stale_units and "questions" in tables
            else []
        )

        for table in sorted(tables):
            for column, values in (
                ("question_id", stale_questions),
                ("unit_id", stale_units),
                ("paper_id", stale_papers),
            ):
                count = _delete_by_ids(connection, table, column, values)
                if count:
                    removed[table] = removed.get(table, 0) + count

        for table, values in (
            ("questions", stale_questions),
            ("units", stale_units),
            ("papers", stale_papers),
        ):
            count = _delete_by_ids(connection, table, "id", values)
            if count:
                removed[table] = removed.get(table, 0) + count

        if "question_bank_profiles" in tables and "papers" in tables:
            active_profiles = {
                int(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT profile_id FROM papers "
                    "WHERE deleted_at IS NULL AND status = 'published'"
                ).fetchall()
            }
            profile_rows = connection.execute(
                "SELECT id FROM question_bank_profiles"
            ).fetchall()
            stale_profiles = [
                int(row[0]) for row in profile_rows if int(row[0]) not in active_profiles
            ]
            count = _delete_by_ids(connection, "question_bank_profiles", "id", stale_profiles)
            if count:
                removed["question_bank_profiles"] = removed.get(
                    "question_bank_profiles", 0
                ) + count

        for table in sorted(tables - PRESERVED_TABLES):
            count = int(connection.execute(f"DELETE FROM {_quote(table)}").rowcount)
            if count:
                removed[table] = removed.get(table, 0) + count

        if "vocabulary_entries" in tables and "user_id" in _columns(connection, "vocabulary_entries"):
            count = int(
                connection.execute(
                    "DELETE FROM vocabulary_entries WHERE user_id IS NOT NULL"
                ).rowcount
            )
            if count:
                removed["vocabulary_entries"] = removed.get("vocabulary_entries", 0) + count

        connection.commit()
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"sanitized database foreign-key check failed: {violations[:3]}")

        active_papers = int(
            connection.execute(
                "SELECT COUNT(*) FROM papers "
                "WHERE deleted_at IS NULL AND status = 'published'"
            ).fetchone()[0]
        )
        questions = int(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
        vocabulary = int(
            connection.execute("SELECT COUNT(*) FROM vocabulary_entries").fetchone()[0]
        )
        return {
            "papers": active_papers,
            "questions": questions,
            "vocabulary_entries": vocabulary,
            "removed_rows": removed,
        }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _zip_file(bundle: zipfile.ZipFile, source: Path, name: str) -> None:
    info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    bundle.writestr(info, source.read_bytes())


def create_bundle(release_db: Path, offline_db: Path, output: Path) -> dict[str, object]:
    if not release_db.is_file() or not offline_db.is_file():
        raise FileNotFoundError("release/offline database input is missing")
    content_version = CONTENT_VERSION_FILE.read_text(encoding="utf-8").strip()
    offline_version = OFFLINE_CONTENT_VERSION_FILE.read_text(encoding="utf-8").strip()
    with TemporaryDirectory(prefix="epm-content-bundle-") as temp:
        temp_root = Path(temp)
        clean_release = temp_root / "release-question_bank.db"
        clean_offline = temp_root / "offline-question_bank.db"
        release_counts = _sanitize_database(release_db, clean_release)
        offline_counts = _sanitize_database(offline_db, clean_offline)
        content_keys = ("papers", "questions", "vocabulary_entries")
        release_content_counts = {
            key: release_counts[key] for key in content_keys
        }
        offline_content_counts = {
            key: offline_counts[key] for key in content_keys
        }
        if release_content_counts != offline_content_counts:
            raise RuntimeError(
                "sanitized release/offline content counts differ: "
                f"release={release_content_counts}, offline={offline_content_counts}"
            )

        manifest = {
            "manifest_version": 1,
            "content_version": content_version,
            "offline_seed_version": offline_version,
            "release": {
                "file": "release/question_bank.db",
                "sha256": _sha256(clean_release),
                "size_bytes": clean_release.stat().st_size,
                "counts": release_counts,
            },
            "offline": {
                "file": "offline/question_bank.db",
                "sha256": _sha256(clean_offline),
                "size_bytes": clean_offline.stat().st_size,
                "counts": offline_counts,
            },
            "sanitization": {
                "preserved_tables": sorted(PRESERVED_TABLES),
                "runtime_tables_cleared": True,
            },
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            info = zipfile.ZipInfo("manifest.json", date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            bundle.writestr(
                info,
                (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )
            _zip_file(bundle, clean_release, "release/question_bank.db")
            _zip_file(bundle, clean_offline, "offline/question_bank.db")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="生成去除本机运行数据的发布内容 bundle")
    parser.add_argument("--release-db", type=Path, default=ROOT / "backend/data/question_bank.db")
    parser.add_argument("--offline-db", type=Path, default=ROOT / "frontend/public/question_bank.db")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "work/release-content-bundle.zip"
    )
    args = parser.parse_args()
    manifest = create_bundle(args.release_db, args.offline_db, args.output)
    print(json.dumps({"output": str(args.output), "manifest": manifest}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
