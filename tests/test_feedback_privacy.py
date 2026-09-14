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


if __name__ == "__main__":
    unittest.main()
