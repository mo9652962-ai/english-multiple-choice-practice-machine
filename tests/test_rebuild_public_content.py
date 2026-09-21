from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.rebuild_public_content import (
    delete_inactive_paper_content,
    delete_old_package_content,
    sync_offline_content,
)


class RebuildPublicContentTests(unittest.TestCase):
    def test_sync_replaces_content_explanations_without_orphan_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.db"
            target_path = Path(directory) / "target.db"
            schema = """
                CREATE TABLE question_bank_profiles (id INTEGER PRIMARY KEY, name TEXT);
                CREATE TABLE question_bank_packages (package_id TEXT, content_version TEXT);
                CREATE TABLE papers (id INTEGER PRIMARY KEY, package_id TEXT);
                CREATE TABLE units (id INTEGER PRIMARY KEY, paper_id INTEGER);
                CREATE TABLE questions (id INTEGER PRIMARY KEY, unit_id INTEGER);
                CREATE TABLE options (id INTEGER PRIMARY KEY, question_id INTEGER);
                CREATE TABLE question_explanations (question_id INTEGER, content TEXT);
                CREATE TABLE explain_collections (question_id INTEGER, content TEXT);
                CREATE TABLE practice_sessions (id INTEGER PRIMARY KEY, paper_id INTEGER);
                CREATE TABLE practice_answers (id INTEGER PRIMARY KEY, question_id INTEGER);
            """
            for path in (source_path, target_path):
                connection = sqlite3.connect(path)
                try:
                    connection.executescript(schema)
                    connection.commit()
                finally:
                    connection.close()
            connection = sqlite3.connect(source_path)
            try:
                connection.execute("INSERT INTO question_bank_profiles VALUES (1, 'source')")
                connection.execute("INSERT INTO question_bank_packages VALUES ('pkg', '1')")
                connection.execute("INSERT INTO papers VALUES (1, 'pkg')")
                connection.execute("INSERT INTO units VALUES (1, 1)")
                connection.execute("INSERT INTO questions VALUES (1, 1)")
                connection.execute("INSERT INTO options VALUES (1, 1)")
                connection.execute("INSERT INTO question_explanations VALUES (1, 'new')")
                connection.execute("INSERT INTO explain_collections VALUES (1, 'new')")
                connection.commit()
            finally:
                connection.close()
            connection = sqlite3.connect(target_path)
            try:
                connection.execute("INSERT INTO questions VALUES (99, 99)")
                connection.execute("INSERT INTO explain_collections VALUES (99, 'stale')")
                connection.execute("INSERT INTO practice_sessions VALUES (1, 99)")
                connection.execute("INSERT INTO practice_answers VALUES (1, 99)")
                connection.commit()
            finally:
                connection.close()

            sync_offline_content(source_path, target_path)

            connection = sqlite3.connect(target_path)
            try:
                self.assertEqual(
                    connection.execute("SELECT content FROM explain_collections").fetchall(),
                    [("new",)],
                )
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0], 0)
                self.assertEqual(connection.execute("SELECT COUNT(*) FROM practice_answers").fetchone()[0], 0)
                self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            finally:
                connection.close()

    def test_delete_old_package_content_removes_all_known_unpublishable_packages(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(
                """
                CREATE TABLE papers (
                    id INTEGER PRIMARY KEY,
                    package_id TEXT,
                    status TEXT NOT NULL DEFAULT 'published',
                    deleted_at TEXT
                );
                CREATE TABLE units (id INTEGER PRIMARY KEY, paper_id INTEGER);
                CREATE TABLE questions (id INTEGER PRIMARY KEY, unit_id INTEGER);
                CREATE TABLE options (id INTEGER PRIMARY KEY, question_id INTEGER);
                CREATE TABLE question_bank_packages (
                    package_id TEXT,
                    content_version TEXT
                );
                """
            )
            package_ids = [
                "wssfk.postgraduate-english-one.2010-2026",
                "local.english-practice.postgraduate-english-two.2010-2025",
                "gaokao-english-2022-2024",
                "cn.kaoyan2.2025.cloze",
                "cn.cet4.2025.sim",
                "cn.cet6.2025.sim",
                "cn.kaoyan1.2025.sim",
            ]
            for index, package_id in enumerate(package_ids, start=1):
                connection.execute(
                    "INSERT INTO papers(id, package_id) VALUES (?, ?)",
                    (index, package_id),
                )
                connection.execute(
                    "INSERT INTO question_bank_packages(package_id, content_version) VALUES (?, '1.0.0')",
                    (package_id,),
                )
            connection.execute("INSERT INTO papers(id, package_id) VALUES (99, 'motei.public')")
            connection.commit()

            removed = delete_old_package_content(connection)

            self.assertEqual(removed["papers"], len(package_ids))
            remaining = connection.execute("SELECT package_id FROM papers").fetchall()
            self.assertEqual([row[0] for row in remaining], ["motei.public"])
        finally:
            connection.close()

    def test_delete_inactive_paper_content_removes_residual_child_rows(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(
                """
                CREATE TABLE question_bank_profiles (id INTEGER PRIMARY KEY);
                CREATE TABLE papers (
                    id INTEGER PRIMARY KEY,
                    profile_id INTEGER,
                    package_id TEXT,
                    status TEXT NOT NULL DEFAULT 'published',
                    deleted_at TEXT
                );
                CREATE TABLE units (id INTEGER PRIMARY KEY, paper_id INTEGER);
                CREATE TABLE questions (id INTEGER PRIMARY KEY, unit_id INTEGER);
                CREATE TABLE options (id INTEGER PRIMARY KEY, question_id INTEGER);
                CREATE TABLE question_explanations (question_id INTEGER, content TEXT);
                """
            )
            connection.executescript(
                """
                INSERT INTO question_bank_profiles VALUES (1), (2);
                INSERT INTO papers VALUES
                    (1, 1, 'motei.public', 'published', NULL),
                    (2, 2, 'legacy.deleted', 'published', '2026-01-01');
                INSERT INTO units VALUES (1, 1), (2, 2);
                INSERT INTO questions VALUES (1, 1), (2, 2);
                INSERT INTO options VALUES (1, 1), (2, 2);
                INSERT INTO question_explanations VALUES (1, 'keep'), (2, 'remove');
                """
            )
            connection.commit()

            removed = delete_inactive_paper_content(connection)

            self.assertEqual(removed["papers"], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM units").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM options").fetchone()[0], 1)
            self.assertEqual(
                connection.execute("SELECT content FROM question_explanations").fetchall(),
                [("keep",)],
            )
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM question_bank_profiles").fetchone()[0], 1)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
