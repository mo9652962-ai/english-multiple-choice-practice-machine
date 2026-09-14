from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path

from tools.create_release_content_bundle import _sanitize_database, create_bundle


def _fixture(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE question_bank_profiles (id INTEGER PRIMARY KEY, deleted_at TEXT);
        CREATE TABLE papers (
            id INTEGER PRIMARY KEY,
            profile_id INTEGER,
            status TEXT,
            deleted_at TEXT
        );
        CREATE TABLE units (id INTEGER PRIMARY KEY, paper_id INTEGER);
        CREATE TABLE questions (id INTEGER PRIMARY KEY, unit_id INTEGER);
        CREATE TABLE options (id INTEGER PRIMARY KEY, question_id INTEGER);
        CREATE TABLE question_bank_packages (package_id TEXT PRIMARY KEY);
        CREATE TABLE vocabulary_entries (id INTEGER PRIMARY KEY, user_id INTEGER, term TEXT);
        CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY);
        CREATE TABLE practice_sessions (id INTEGER PRIMARY KEY, user_id INTEGER);
        INSERT INTO question_bank_profiles VALUES (1, NULL), (2, NULL);
        INSERT INTO papers VALUES (1, 1, 'published', NULL), (2, 2, 'published', '2026-01-01');
        INSERT INTO units VALUES (1, 1), (2, 2);
        INSERT INTO questions VALUES (1, 1), (2, 2);
        INSERT INTO options VALUES (1, 1), (2, 2);
        INSERT INTO question_bank_packages VALUES ('motei.ai.sim');
        INSERT INTO vocabulary_entries VALUES (1, NULL, 'study'), (2, 7, 'private');
        INSERT INTO schema_migrations VALUES (2);
        INSERT INTO practice_sessions VALUES (1, 7);
        """
    )
    connection.commit()
    connection.close()


def test_sanitize_database_keeps_published_content_and_clears_runtime(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    target = tmp_path / "clean.db"
    _fixture(source)

    counts = _sanitize_database(source, target)

    assert counts["papers"] == 1
    assert counts["questions"] == 1
    assert counts["vocabulary_entries"] == 1
    connection = sqlite3.connect(target)
    assert connection.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0] == 0
    assert connection.execute("SELECT COUNT(*) FROM vocabulary_entries").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 1
    connection.close()


def test_bundle_contains_manifest_and_two_sanitized_databases(tmp_path: Path) -> None:
    release = tmp_path / "release.db"
    offline = tmp_path / "offline.db"
    output = tmp_path / "bundle.zip"
    _fixture(release)
    _fixture(offline)

    manifest = create_bundle(release, offline, output)

    assert manifest["content_version"]
    with zipfile.ZipFile(output) as bundle:
        assert set(bundle.namelist()) == {
            "manifest.json",
            "release/question_bank.db",
            "offline/question_bank.db",
        }
        assert bundle.read("manifest.json")
