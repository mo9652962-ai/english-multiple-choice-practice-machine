from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


class FeedbackPrivacyApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "feedback-test.db"
        self.db_patch = patch("backend.app.database.DATABASE_PATH", self.database_path)
        self.db_patch.start()
        from backend.app.database import initialize_database
        from backend.app.main import app

        initialize_database()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_feedback_submission_is_public_but_listing_is_admin_only(self) -> None:
        from backend.app.routers import auth

        with patch.object(auth, "AUTH_ENABLED", True), patch.object(
            auth, "ADMIN_USERNAME", "feedbackadmin"
        ):
            submitted = self.client.post(
                "/api/feedback",
                json={
                    "category": "bug",
                    "content": "反馈内容不应被未授权读取",
                    "contact": "user@example.test",
                    "page": "/settings",
                    "participant_code": "P01",
                    "difficulty_rating": 4,
                    "explanation_rating": 3,
                    "coverage_rating": 4,
                    "continue_intent": "yes",
                },
            )
            self.assertEqual(submitted.status_code, 200, submitted.text)

            self.assertEqual(self.client.get("/api/feedback").status_code, 401)

            ordinary = self.client.post(
                "/api/auth/register",
                json={"username": "feedbackreader", "password": "Passw0rd123"},
            ).json()
            ordinary_list = self.client.get(
                "/api/feedback",
                headers={"Authorization": f"Bearer {ordinary['token']}"},
            )
            self.assertEqual(ordinary_list.status_code, 403)

            administrator = self.client.post(
                "/api/auth/register",
                json={"username": "feedbackadmin", "password": "Passw0rd123"},
            ).json()
            administrator_list = self.client.get(
                "/api/feedback",
                headers={"Authorization": f"Bearer {administrator['token']}"},
            )
            self.assertEqual(administrator_list.status_code, 200)
            self.assertEqual(administrator_list.json()[0]["contact"], "user@example.test")
            self.assertEqual(administrator_list.json()[0]["participant_code"], "P01")
            self.assertEqual(administrator_list.json()[0]["difficulty_rating"], 4)
            self.assertEqual(administrator_list.json()[0]["explanation_rating"], 3)
            self.assertEqual(administrator_list.json()[0]["coverage_rating"], 4)
            self.assertEqual(administrator_list.json()[0]["continue_intent"], "yes")

    def test_structured_rating_is_validated_and_anonymous_code_is_constrained(self) -> None:
        invalid_rating = self.client.post(
            "/api/feedback",
            json={
                "content": "这条反馈不会被写入",
                "difficulty_rating": 6,
            },
        )
        self.assertEqual(invalid_rating.status_code, 422)

        invalid_code = self.client.post(
            "/api/feedback",
            json={
                "content": "这条反馈不会被写入",
                "participant_code": "姓名 01",
            },
        )
        self.assertEqual(invalid_code.status_code, 422)

    def test_existing_legacy_feedback_table_is_upgraded_on_submit(self) -> None:
        from backend.app.database import connect

        connection = connect()
        connection.execute(
            """CREATE TABLE feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'other',
                content TEXT NOT NULL,
                contact TEXT DEFAULT '',
                page TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL
            )"""
        )
        connection.commit()
        connection.close()

        response = self.client.post(
            "/api/feedback",
            json={
                "content": "旧反馈表升级后仍可提交",
                "participant_code": "P02",
                "continue_intent": "unsure",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)

        connection = connect()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(feedback)")}
        self.assertTrue({
            "participant_code",
            "difficulty_rating",
            "explanation_rating",
            "coverage_rating",
            "continue_intent",
        }.issubset(columns))
        connection.close()


if __name__ == "__main__":
    unittest.main()
