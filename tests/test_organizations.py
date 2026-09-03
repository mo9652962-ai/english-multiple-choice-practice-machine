from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


class OrganizationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "organization-test.db"
        self.db_patch = patch("backend.app.database.DATABASE_PATH", self.database_path)
        self.db_patch.start()
        from backend.app.database import initialize_database

        initialize_database()
        from backend.app.main import app

        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_local_mode_can_create_and_switch_organizations(self) -> None:
        from backend.app.routers import auth

        with patch.object(auth, "AUTH_ENABLED", False):
            created = self.client.post(
                "/api/organizations", json={"name": "本地教研组", "slug": "teaching"}
            )
            self.assertEqual(created.status_code, 201)
            organization_id = created.json()["id"]
            listed = self.client.get("/api/organizations")
            self.assertEqual(listed.status_code, 200)
            self.assertIn(organization_id, [item["id"] for item in listed.json()])
            switched = self.client.post(f"/api/organizations/{organization_id}/switch")
            self.assertEqual(switched.status_code, 200)

    def test_authenticated_users_get_owner_org_and_non_members_are_forbidden(self) -> None:
        from backend.app.routers import auth

        with patch.object(auth, "AUTH_ENABLED", True):
            first = self.client.post(
                "/api/auth/register",
                json={"username": "alpha", "password": "Passw0rd123"},
            )
            second = self.client.post(
                "/api/auth/register",
                json={"username": "bravo", "password": "Passw0rd123"},
            )
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            alpha = first.json()
            bravo = second.json()
            alpha_headers = {"Authorization": f"Bearer {alpha['token']}"}
            bravo_headers = {"Authorization": f"Bearer {bravo['token']}"}
            alpha_org_id = alpha["user"]["active_organization_id"]

            own = self.client.get("/api/organizations", headers=alpha_headers)
            self.assertEqual(own.status_code, 200)
            self.assertEqual(len(own.json()), 1)
            self.assertEqual(own.json()[0]["role"], "owner")
            forbidden = self.client.get(
                f"/api/organizations/{alpha_org_id}", headers=bravo_headers
            )
            self.assertEqual(forbidden.status_code, 403)
            self.assertEqual(self.client.get("/api/organizations").status_code, 401)

            connection = sqlite3.connect(self.database_path)
            try:
                audit_count = connection.execute(
                    "SELECT COUNT(*) FROM audit_logs WHERE organization_id = ?",
                    (alpha_org_id,),
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertGreaterEqual(audit_count, 1)

    def test_migration_is_idempotent_and_health_reports_version(self) -> None:
        from backend.app.database import connect, initialize_database
        from backend.app.main import health

        initialize_database()
        connection = connect()
        try:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0],
                2,
            )
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM organizations WHERE slug = 'local'").fetchone()[0],
                1,
            )
        finally:
            connection.close()
        result = health()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["database"], "ok")
        self.assertEqual(result["schema_version"], 2)
