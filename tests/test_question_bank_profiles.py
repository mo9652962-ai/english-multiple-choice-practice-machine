from __future__ import annotations

import sqlite3
import unittest

from backend.app.database import SCHEMA, _run_migrations, get_active_profile_id
from backend.app.services.trash import (
    list_trash,
    purge_trash,
    restore_trash,
    trash_paper,
    trash_profile,
)
from backend.app.services.practice import create_session
from backend.app.schemas import PracticeCreate


class QuestionBankProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        _run_migrations(self.connection)
        self.default_profile_id = get_active_profile_id(self.connection)
        self.other_profile_id = int(
            self.connection.execute(
                "INSERT INTO question_bank_profiles(name) VALUES ('托福练习')"
            ).lastrowid
        )
        self.connection.commit()

    def tearDown(self) -> None:
        self.connection.close()

    def _paper(self, profile_id: int, title: str, external_key: str) -> int:
        return int(
            self.connection.execute(
                """
                INSERT INTO papers
                    (profile_id, year, subject, title, status, external_key)
                VALUES (?, 2002, '英语', ?, 'published', ?)
                """,
                (profile_id, title, external_key),
            ).lastrowid
        )

    def test_same_year_is_allowed_in_different_profiles(self) -> None:
        first = self._paper(self.default_profile_id, "2002 年试卷", "paper:2002")
        second = self._paper(self.other_profile_id, "2002 年试卷", "paper:2002")
        self.connection.commit()
        self.assertNotEqual(first, second)
        self.assertEqual(
            self.connection.execute(
                "SELECT COUNT(*) FROM papers WHERE year = 2002"
            ).fetchone()[0],
            2,
        )

    def test_practice_rejects_paper_outside_active_profile(self) -> None:
        paper_id = self._paper(
            self.other_profile_id,
            "2002 年试卷",
            "paper:2002",
        )
        self.connection.commit()
        with self.assertRaises(ValueError):
            create_session(
                self.connection,
                PracticeCreate(mode="paper", paper_id=paper_id),
            )
        self.connection.rollback()

    def test_paper_restore_falls_back_and_renames_conflict(self) -> None:
        paper_id = self._paper(
            self.other_profile_id,
            "2002 年试卷",
            "paper:2002",
        )
        self.connection.commit()
        result = trash_paper(self.connection, paper_id)
        self.connection.commit()
        self.connection.execute(
            "UPDATE question_bank_profiles SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?",
            (self.other_profile_id,),
        )
        self._paper(self.default_profile_id, "2002 年试卷", "paper:2002")
        self.connection.commit()
        trash_id = self.connection.execute(
            "SELECT id FROM trash_entries WHERE deletion_batch_id = ?",
            (result["batch_id"],),
        ).fetchone()["id"]

        restore_trash(self.connection, int(trash_id))
        restored = self.connection.execute(
            "SELECT profile_id, title, external_key, status, deleted_at FROM papers WHERE id = ?",
            (paper_id,),
        ).fetchone()
        self.assertEqual(restored["profile_id"], self.default_profile_id)
        self.assertEqual(restored["title"], "2002 年试卷（恢复）")
        self.assertIn(":restored:", restored["external_key"])
        self.assertEqual(restored["status"], "published")
        self.assertIsNone(restored["deleted_at"])

    def test_profile_restore_keeps_batch_together_and_renames_conflict(self) -> None:
        paper_id = self._paper(
            self.other_profile_id,
            "托福试卷",
            "toefl:paper",
        )
        self.connection.execute(
            """
            INSERT INTO import_jobs
                (profile_id, filename, stored_path, status)
            VALUES (?, 'toefl.docx', '', 'published')
            """,
            (self.other_profile_id,),
        )
        self.connection.commit()
        result = trash_profile(self.connection, self.other_profile_id)
        self.connection.commit()
        self.connection.execute(
            "INSERT INTO question_bank_profiles(name) VALUES ('托福练习')"
        )
        self.connection.commit()
        root = next(item for item in list_trash(self.connection) if item["resource_type"] == "profile")

        restore_trash(
            self.connection,
            int(root["id"]),
            target_profile_id=self.default_profile_id,
        )
        profile = self.connection.execute(
            "SELECT name, deleted_at FROM question_bank_profiles WHERE id = ?",
            (self.other_profile_id,),
        ).fetchone()
        paper = self.connection.execute(
            "SELECT profile_id, status, deleted_at FROM papers WHERE id = ?",
            (paper_id,),
        ).fetchone()
        job = self.connection.execute(
            "SELECT profile_id, status, deleted_at FROM import_jobs WHERE filename = 'toefl.docx'"
        ).fetchone()
        self.assertEqual(profile["name"], "托福练习（恢复）")
        self.assertIsNone(profile["deleted_at"])
        self.assertEqual(paper["profile_id"], self.other_profile_id)
        self.assertEqual(paper["status"], "published")
        self.assertIsNone(paper["deleted_at"])
        self.assertEqual(job["profile_id"], self.other_profile_id)
        self.assertEqual(job["status"], "published")
        self.assertIsNone(job["deleted_at"])
        self.assertEqual(result["moved_papers"], 1)
        self.assertEqual(result["moved_import_jobs"], 1)

    def test_purge_deletes_paper_and_children(self) -> None:
        paper_id = self._paper(
            self.default_profile_id,
            "待永久删除试卷",
            "delete:paper",
        )
        unit_id = int(
            self.connection.execute(
                """
                INSERT INTO units
                    (paper_id, unit_type, title, sequence, external_key)
                VALUES (?, 'reading', '阅读', 1, 'unit:1')
                """,
                (paper_id,),
            ).lastrowid
        )
        self.connection.execute(
            """
            INSERT INTO questions
                (unit_id, number, answer, score, sequence, external_key)
            VALUES (?, 1, 'A', 1, 1, 'q:1')
            """,
            (unit_id,),
        )
        self.connection.commit()
        result = trash_paper(self.connection, paper_id)
        self.connection.commit()
        trash_id = self.connection.execute(
            "SELECT id FROM trash_entries WHERE deletion_batch_id = ?",
            (result["batch_id"],),
        ).fetchone()["id"]

        purge_trash(self.connection, int(trash_id))
        self.assertIsNone(
            self.connection.execute(
                "SELECT id FROM papers WHERE id = ?", (paper_id,)
            ).fetchone()
        )
        self.assertIsNone(
            self.connection.execute(
                "SELECT id FROM units WHERE id = ?", (unit_id,)
            ).fetchone()
        )

    def test_legacy_papers_rebuild_preserves_child_data(self) -> None:
        import os
        import tempfile

        from unittest.mock import patch

        from backend.app.database import connect, initialize_database

        fd, database_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            legacy = sqlite3.connect(database_path)
            legacy.execute("PRAGMA foreign_keys = ON")
            legacy.executescript(
                """
                CREATE TABLE papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    year INTEGER NOT NULL UNIQUE,
                    subject TEXT NOT NULL DEFAULT '英语一',
                    title TEXT NOT NULL,
                    source_file TEXT,
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE units (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    paper_id INTEGER NOT NULL,
                    unit_type TEXT NOT NULL,
                    subtype TEXT,
                    title TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    passage TEXT NOT NULL DEFAULT '',
                    shared_data TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
                    UNIQUE (paper_id, sequence)
                );
                CREATE TABLE questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    unit_id INTEGER NOT NULL,
                    number INTEGER NOT NULL,
                    stem TEXT NOT NULL DEFAULT '',
                    question_type TEXT NOT NULL DEFAULT 'single_choice',
                    answer TEXT NOT NULL,
                    score REAL NOT NULL,
                    sequence INTEGER NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE,
                    UNIQUE (unit_id, number)
                );
                CREATE TABLE options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    stable_key TEXT NOT NULL,
                    original_label TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
                    UNIQUE (question_id, stable_key)
                );
                CREATE TABLE wrong_stats (
                    question_id INTEGER PRIMARY KEY,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    wrong_count INTEGER NOT NULL DEFAULT 0,
                    recent_results TEXT NOT NULL DEFAULT '[]',
                    consecutive_correct INTEGER NOT NULL DEFAULT 0,
                    manually_frequent INTEGER NOT NULL DEFAULT 0,
                    last_wrong_at TEXT,
                    last_attempt_at TEXT,
                    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
                );
                """
            )
            legacy.execute(
                """
                INSERT INTO papers(year, subject, title, status)
                VALUES (2002, '英语一', '2002年真题', 'published')
                """
            )
            legacy.execute(
                """
                INSERT INTO units(paper_id, unit_type, title, sequence)
                VALUES (1, 'cloze', '完型填空', 1)
                """
            )
            legacy.execute(
                """
                INSERT INTO questions(unit_id, number, stem, answer, score, sequence)
                VALUES (1, 1, 'Test', 'A', 1, 1)
                """
            )
            legacy.execute(
                """
                INSERT INTO options(question_id, stable_key, original_label, content, sequence)
                VALUES (1, 'A', 'A', 'opt-a', 1)
                """
            )
            legacy.execute(
                """
                INSERT INTO wrong_stats(question_id, attempt_count, wrong_count, recent_results)
                VALUES (1, 1, 1, '[0]')
                """
            )
            legacy.commit()
            legacy.close()

            with patch("backend.app.database.DATABASE_PATH", database_path):
                initialize_database()
                connection = connect()
                self.assertEqual(
                    connection.execute("PRAGMA foreign_key_check").fetchall(),
                    [],
                )
                paper = connection.execute(
                    "SELECT year, profile_id FROM papers WHERE id = 1"
                ).fetchone()
                self.assertEqual((paper["year"], paper["profile_id"]), (2002, 1))
                unit = connection.execute(
                    "SELECT paper_id, title FROM units WHERE id = 1"
                ).fetchone()
                self.assertEqual((unit["paper_id"], unit["title"]), (1, "完型填空"))
                question = connection.execute(
                    "SELECT unit_id, answer FROM questions WHERE id = 1"
                ).fetchone()
                self.assertEqual((question["unit_id"], question["answer"]), (1, "A"))
                option = connection.execute(
                    "SELECT question_id, content FROM options WHERE id = 1"
                ).fetchone()
                self.assertEqual((option["question_id"], option["content"]), (1, "opt-a"))
                wrong = connection.execute(
                    "SELECT wrong_count FROM wrong_stats WHERE question_id = 1"
                ).fetchone()
                self.assertEqual(wrong["wrong_count"], 1)
                connection.execute(
                    """
                    INSERT INTO papers(profile_id, year, subject, title, status)
                    VALUES (1, 2002, '英语一', '2002年第二套', 'published')
                    """
                )
                connection.commit()
                connection.close()
        finally:
            try:
                os.remove(database_path)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
