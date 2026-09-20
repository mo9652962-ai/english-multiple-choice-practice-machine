"""Rebuild public content databases after replacing unpublishable packages.

The script keeps a SQLite backup before every write, removes only the explicitly
listed unpublishable package identities, installs the current public ESQ starter
packages, and synchronises content tables into the offline seed database.
It deliberately does not alter ESQ manifests or invent provenance evidence.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
UNPUBLISHABLE_PACKAGE_IDS = (
    "cet4-2023",
    "cet6-2023",
    "cn.cet4.2025.sim",
    "cn.cet4.2026.sim.cloze",
    "cn.cet4.2026.sim.listening",
    "cn.cet4.2026.sim.reading",
    "cn.cet4.banked.2023.12.1",
    "cn.cet4.banked.2023.12.2",
    "cn.cet4.banked.2023.12.3",
    "cn.cet4.banked.2023.6.1",
    "cn.cet4.listen.2023.6.1",
    "cn.cet4.listen.2026",
    "cn.cet6.2025.sim",
    "cn.cet6.2026.sim.cloze",
    "cn.cet6.2026.sim.listening",
    "cn.cet6.2026.sim.reading",
    "cn.cet6.banked.2023.12.1",
    "cn.cet6.banked.2023.12.2",
    "cn.cet6.banked.2023.6.1",
    "cn.cet6.listen.2023.6.1",
    "cn.cet6.listen.2026",
    "cn.gaokao.2026.sim.cloze",
    "cn.gaokao.2026.sim.part_b",
    "cn.gaokao.2026.sim.reading",
    "cn.gaokao.7of5.2023-2024",
    "cn.gaokao.7of5.2024",
    "cn.gaokao.cloze.2023-2024",
    "cn.gaokao.cloze.2024",
    "cn.gaokao.english.7of5",
    "cn.gaokao.english.cloze",
    "cn.kaoyan1.2024",
    "cn.kaoyan1.2025",
    "cn.kaoyan1.2025.sim",
    "cn.kaoyan1.2026.sim.cloze",
    "cn.kaoyan1.2026.sim.part_b",
    "cn.kaoyan1.2026.sim.reading",
    "cn.kaoyan2.2025.cloze",
    "cn.kaoyan2.2025.newtype",
    "cn.kaoyan2.2025.text1",
    "cn.kaoyan2.2025.text2",
    "cn.kaoyan2.2025.text3",
    "cn.kaoyan2.2025.text4",
    "cn.kaoyan2.2026.sim.cloze",
    "cn.kaoyan2.2026.sim.part_b",
    "cn.kaoyan2.2026.sim.reading",
    "gaokao-english-2022-2024",
    "local.english-practice.postgraduate-english-two.2010-2025",
    "wssfk.postgraduate-english-one.2010-2026",
)
CONTENT_TABLES = (
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
    "explain_collections",
)
OFFLINE_RUNTIME_TABLES = (
    "practice_sessions",
    "practice_answers",
    "practice_answer_events",
    "practice_unit_submissions",
    "exam_sessions",
    "exam_answers",
    "annotations",
    "wrong_cause_diagnoses",
    "wrong_stats",
    "spaced_repetition_records",
    "wrong_analysis_states",
    "wrong_analysis_reports",
    "diagnostic_reports",
    "local_metrics_events",
    "learning_days",
    "vocabulary_occurrences",
)


def backup_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection, sqlite3.connect(destination) as backup:
        source_connection.backup(backup)


def table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }


def column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}


def _delete_paper_content(
    connection: sqlite3.Connection,
    paper_ids: list[int],
    package_ids: tuple[str, ...] = (),
) -> dict[str, int]:
    tables = table_names(connection)
    if not paper_ids:
        return {"papers": 0, "units": 0, "questions": 0, "packages": 0}

    package_placeholders = ",".join("?" for _ in package_ids) or "NULL"
    id_placeholders = ",".join("?" for _ in paper_ids)
    unit_ids = [
        int(row[0])
        for row in connection.execute(
            f"SELECT id FROM units WHERE paper_id IN ({id_placeholders})",
            paper_ids,
        ).fetchall()
    ]
    unit_placeholders = ",".join("?" for _ in unit_ids) or "NULL"
    question_ids = [
        int(row[0])
        for row in connection.execute(
            f"SELECT id FROM questions WHERE unit_id IN ({unit_placeholders})",
            unit_ids,
        ).fetchall()
    ] if unit_ids else []

    # Remove child rows from every table that declares one of the content FKs.
    # This covers optional explanation/label/revision tables without hardcoding
    # every version of the local schema.
    for table in sorted(tables):
        if table in {"papers", "units", "questions", "question_bank_packages"}:
            continue
        columns = column_names(connection, table)
        if "question_id" in columns and question_ids:
            placeholders = ",".join("?" for _ in question_ids)
            connection.execute(
                f'DELETE FROM "{table}" WHERE question_id IN ({placeholders})', question_ids
            )
        if "unit_id" in columns and unit_ids:
            placeholders = ",".join("?" for _ in unit_ids)
            connection.execute(
                f'DELETE FROM "{table}" WHERE unit_id IN ({placeholders})', unit_ids
            )
        if "paper_id" in columns and paper_ids:
            placeholders = ",".join("?" for _ in paper_ids)
            connection.execute(
                f'DELETE FROM "{table}" WHERE paper_id IN ({placeholders})', paper_ids
            )
        if package_ids and "package_id" in columns:
            connection.execute(
                f'DELETE FROM "{table}" WHERE package_id IN ({package_placeholders})',
                package_ids,
            )

    if question_ids and "questions" in tables:
        placeholders = ",".join("?" for _ in question_ids)
        connection.execute(f"DELETE FROM questions WHERE id IN ({placeholders})", question_ids)
    if unit_ids and "units" in tables:
        placeholders = ",".join("?" for _ in unit_ids)
        connection.execute(f"DELETE FROM units WHERE id IN ({placeholders})", unit_ids)
    connection.execute(f"DELETE FROM papers WHERE id IN ({id_placeholders})", paper_ids)
    package_count = 0
    if package_ids and "question_bank_packages" in tables:
        package_count = connection.execute(
            f"DELETE FROM question_bank_packages WHERE package_id IN ({package_placeholders})",
            package_ids,
        ).rowcount
    return {
        "papers": len(paper_ids),
        "units": len(unit_ids),
        "questions": len(question_ids),
        "packages": int(package_count),
    }


def delete_old_package_content(connection: sqlite3.Connection) -> dict[str, int]:
    tables = table_names(connection)
    if "papers" not in tables:
        return {"papers": 0, "units": 0, "questions": 0, "packages": 0}

    package_placeholders = ",".join("?" for _ in UNPUBLISHABLE_PACKAGE_IDS)
    paper_rows = connection.execute(
        f"SELECT id FROM papers WHERE package_id IN ({package_placeholders})",
        UNPUBLISHABLE_PACKAGE_IDS,
    ).fetchall()
    return _delete_paper_content(
        connection,
        [int(row[0]) for row in paper_rows],
        UNPUBLISHABLE_PACKAGE_IDS,
    )


def delete_inactive_paper_content(connection: sqlite3.Connection) -> dict[str, int]:
    """Remove child rows belonging to deleted or non-published papers.

    Soft deletion is useful for runtime history, but public release databases
    must not retain those paper's units/questions/options.  This intentionally
    applies to every inactive paper, not only the known package quarantine list.
    """
    tables = table_names(connection)
    if "papers" not in tables:
        return {"papers": 0, "units": 0, "questions": 0, "packages": 0, "profiles": 0}
    columns = column_names(connection, "papers")
    where = "deleted_at IS NOT NULL" if "deleted_at" in columns else "1 = 0"
    if "status" in columns:
        where += " OR COALESCE(status, '') <> 'published'"
    paper_ids = [
        int(row[0])
        for row in connection.execute(f"SELECT id FROM papers WHERE {where}").fetchall()
    ]
    removed = _delete_paper_content(connection, paper_ids)
    profile_count = 0
    if "question_bank_profiles" in tables and "profile_id" in columns:
        profile_count = int(
            connection.execute(
                "DELETE FROM question_bank_profiles "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM papers WHERE papers.profile_id = question_bank_profiles.id"
                ")"
            ).rowcount
        )
    removed["profiles"] = profile_count
    return removed


def install_public_packages(database_path: Path) -> list[dict[str, object]]:
    import backend.app.database as database
    from backend.app.database import initialize_database
    from backend.app.services.bundled_banks import install_bundled_question_banks

    database.DATABASE_PATH = database_path
    initialize_database()
    return install_bundled_question_banks()


def sync_offline_content(source: Path, target: Path) -> None:
    source_connection = sqlite3.connect(source)
    target_connection = sqlite3.connect(target)
    try:
        source_tables = table_names(source_connection)
        target_tables = table_names(target_connection)
        target_connection.execute("PRAGMA foreign_keys = OFF")
        for table in OFFLINE_RUNTIME_TABLES:
            if table in target_tables:
                target_connection.execute(f'DELETE FROM "{table}"')
        for table in reversed(CONTENT_TABLES):
            if table in target_tables:
                target_connection.execute(f'DELETE FROM "{table}"')
        for table in CONTENT_TABLES:
            if table not in source_tables or table not in target_tables:
                continue
            columns = [
                str(row[1])
                for row in target_connection.execute(f'PRAGMA table_info("{table}")')
                if str(row[1]) in column_names(source_connection, table)
            ]
            column_sql = ",".join(f'"{column}"' for column in columns)
            rows = source_connection.execute(
                f'SELECT {column_sql} FROM "{table}"'
            ).fetchall()
            if rows:
                placeholders = ",".join("?" for _ in columns)
                target_connection.executemany(
                    f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders})', rows
                )
        target_connection.commit()
        violations = target_connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(f"offline database foreign-key check failed: {violations[:3]}")
    finally:
        source_connection.close()
        target_connection.close()


def rebuild(release_db: Path, offline_db: Path, backup_dir: Path) -> dict[str, object]:
    backup_database(release_db, backup_dir / "release-before.db")
    backup_database(offline_db, backup_dir / "offline-before.db")
    with sqlite3.connect(release_db) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        removed = {
            "unpublishable_packages": delete_old_package_content(connection),
            "inactive_papers": delete_inactive_paper_content(connection),
        }
        connection.commit()
    installed = install_public_packages(release_db)
    sync_offline_content(release_db, offline_db)
    with sqlite3.connect(release_db) as connection:
        remaining_old = connection.execute(
            f"SELECT COUNT(*) FROM question_bank_packages WHERE package_id IN ({','.join('?' for _ in UNPUBLISHABLE_PACKAGE_IDS)})",
            UNPUBLISHABLE_PACKAGE_IDS,
        ).fetchone()[0]
        package_rows = connection.execute(
            "SELECT package_id, content_version FROM question_bank_packages ORDER BY package_id"
        ).fetchall()
    if remaining_old:
        raise RuntimeError("old unlicensed package identities remain in release database")
    return {
        "backup_dir": str(backup_dir),
        "removed": removed,
        "installed": installed,
        "release_packages": package_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-db", type=Path, default=ROOT / "backend" / "data" / "question_bank.db")
    parser.add_argument("--offline-db", type=Path, default=ROOT / "frontend" / "public" / "question_bank.db")
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=ROOT / "work" / f"public-content-backups-{date.today().isoformat()}",
    )
    args = parser.parse_args()
    result = rebuild(args.release_db, args.offline_db, args.backup_dir)
    print(result)


if __name__ == "__main__":
    main()
