from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.database import connect, initialize_database
from backend.app.main import app
from backend.app.services.exam_print import (
    generate_paper_print_html,
    generate_wrong_questions_print_html,
)


class ExamPrintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self.temp.name) / "test_print.db"
        self.db_patch = patch("backend.app.database.DATABASE_PATH", self.database_path)
        self.config_patch = patch("backend.app.config.DATABASE_PATH", self.database_path)
        self.db_patch.start()
        self.config_patch.start()
        initialize_database()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.db_patch.stop()
        self.config_patch.stop()
        self.temp.cleanup()

    def test_export_paper_print_html(self) -> None:
        with connect() as conn:
            paper = conn.execute(
                "SELECT id FROM papers WHERE deleted_at IS NULL LIMIT 1"
            ).fetchone()
            if not paper:
                conn.execute(
                    "INSERT INTO papers (profile_id, year, title, status) VALUES (1, 2026, '测试打印试卷', 'published')"
                )
                paper_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO units (paper_id, unit_type, sequence, title) VALUES (?, 'reading', 1, 'Unit 1')",
                    (paper_id,),
                )
                unit_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO questions (unit_id, number, sequence, stem, answer, score) VALUES (?, 1, 1, 'Question 1', 'A', 2.0)",
                    (unit_id,),
                )
                conn.commit()
            else:
                paper_id = paper["id"]

            html = generate_paper_print_html(conn, paper_id)
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("墨题考场打印版", html)
            self.assertIn("绝密 ★ 启用前", html)
            self.assertIn("标准客观题答题卡", html)
            self.assertIn("参考答案与试题精析", html)

    def test_api_export_paper_print_endpoint(self) -> None:
        with connect() as conn:
            paper = conn.execute(
                "SELECT id FROM papers WHERE deleted_at IS NULL LIMIT 1"
            ).fetchone()
            if not paper:
                conn.execute(
                    "INSERT INTO papers (profile_id, year, title, status) VALUES (1, 2026, '测试打印试卷', 'published')"
                )
                paper_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO units (paper_id, unit_type, sequence, title) VALUES (?, 'reading', 1, 'Unit 1')",
                    (paper_id,),
                )
                unit_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO questions (unit_id, number, sequence, stem, answer, score) VALUES (?, 1, 1, 'Question 1', 'A', 2.0)",
                    (unit_id,),
                )
                conn.commit()
            else:
                paper_id = paper["id"]

        resp = self.client.get(f"/api/export/paper/{paper_id}/print")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("全国硕士研究生招生考试", resp.text)
        self.assertIn("paper-columns", resp.text)

    def test_export_wrong_questions_print_endpoint(self) -> None:
        with connect() as conn:
            q_rows = conn.execute("SELECT id FROM questions LIMIT 3").fetchall()
            if not q_rows:
                conn.execute(
                    "INSERT INTO papers (profile_id, year, title, status) VALUES (1, 2026, '测试打印试卷', 'published')"
                )
                paper_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO units (paper_id, unit_type, sequence, title) VALUES (?, 'reading', 1, 'Unit 1')",
                    (paper_id,),
                )
                unit_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO questions (unit_id, number, sequence, stem, answer, score) VALUES (?, 1, 1, 'Question 1', 'A', 2.0)",
                    (unit_id,),
                )
                conn.commit()
                q_rows = conn.execute("SELECT id FROM questions LIMIT 3").fetchall()
            q_ids = [r["id"] for r in q_rows]

        resp = self.client.post(
            "/api/export/wrong-questions/print",
            json={"question_ids": q_ids, "title": "考研攻坚专练"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers["content-type"])
        self.assertIn("考研攻坚专练", resp.text)
        self.assertIn("标准客观题答题卡", resp.text)


if __name__ == "__main__":
    unittest.main()
