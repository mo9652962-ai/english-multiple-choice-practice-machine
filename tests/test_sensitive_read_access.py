from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


class SensitiveReadAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "sensitive-read-test.db"
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

    def test_import_drafts_exports_and_anti_cheat_logs_are_admin_only(self) -> None:
        from backend.app.routers import auth

        protected_paths = (
            "/api/question-banks/imports",
            "/api/question-banks/export",
            "/api/exams/1/anti-cheat",
        )
        with patch.object(auth, "AUTH_ENABLED", True):
            for path in protected_paths:
                self.assertEqual(self.client.get(path).status_code, 401, path)

            ordinary = self.client.post(
                "/api/auth/register",
                json={"username": "readstudent", "password": "Passw0rd123"},
            ).json()
            headers = {"Authorization": f"Bearer {ordinary['token']}"}
            for path in protected_paths:
                self.assertEqual(self.client.get(path, headers=headers).status_code, 403, path)

    def test_public_certificate_detail_does_not_expose_internal_ids(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO certificates
                    (cert_no, user_id, profile_id, exam_id, title, accuracy, score, pass_score, level)
                VALUES ('CERT-PRIVACY-1', 99, 1, 7, '英语模拟考试', 88.5, 53.1, 36, '优秀')
                """
            )
            connection.commit()
        finally:
            connection.close()

        detail = self.client.get("/api/certificates/CERT-PRIVACY-1")
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertNotIn("user_id", detail.json())
        self.assertNotIn("exam_id", detail.json())
        self.assertNotIn("profile_id", detail.json())
        self.assertEqual(detail.json()["cert_no"], "CERT-PRIVACY-1")

    def test_anti_cheat_events_are_scoped_to_exam_owner(self) -> None:
        from backend.app.routers import auth

        with patch.object(auth, "AUTH_ENABLED", True), patch.object(
            auth, "ADMIN_USERNAME", "examadmin"
        ):
            owner = self.client.post(
                "/api/auth/register",
                json={"username": "examowner", "password": "Passw0rd123"},
            ).json()
            other = self.client.post(
                "/api/auth/register",
                json={"username": "examother", "password": "Passw0rd123"},
            ).json()
            connection = sqlite3.connect(self.database_path)
            try:
                exam_id = int(
                    connection.execute(
                        """
                        INSERT INTO exam_sessions
                            (profile_id, title, question_ids, total_questions, duration_minutes, user_id)
                        VALUES (1, 'owner exam', '[]', 0, 30, ?)
                        """,
                        (owner["user"]["id"],),
                    ).lastrowid
                )
                connection.commit()
            finally:
                connection.close()

            other_headers = {"Authorization": f"Bearer {other['token']}"}
            denied = self.client.post(
                f"/api/exams/{exam_id}/anti-cheat",
                headers=other_headers,
                json={"event_type": "screen_switch"},
            )
            self.assertEqual(denied.status_code, 404)

            owner_headers = {"Authorization": f"Bearer {owner['token']}"}
            allowed = self.client.post(
                f"/api/exams/{exam_id}/anti-cheat",
                headers=owner_headers,
                json={"event_type": "screen_switch"},
            )
            self.assertEqual(allowed.status_code, 200, allowed.text)


if __name__ == "__main__":
    unittest.main()
