from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.database import connect
from backend.app.main import app
from backend.app.services.exam_print import (
    generate_paper_print_html,
    generate_wrong_questions_print_html,
)


class ExamPrintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_export_paper_print_html(self) -> None:
        with connect() as conn:
            paper = conn.execute(
                "SELECT id FROM papers WHERE deleted_at IS NULL LIMIT 1"
            ).fetchone()
            if not paper:
                self.skipTest("No papers in seed database")
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
                self.skipTest("No papers in seed database")
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
                self.skipTest("No questions in seed database")
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
