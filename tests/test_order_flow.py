from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.database import SCHEMA, _run_migrations, ensure_local_organization
from backend.app.services import order_service


class OrderServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(SCHEMA)
        _run_migrations(self.connection)
        self.organization_id = ensure_local_organization(self.connection)
        self.plan_id = int(
            self.connection.execute(
                """
                INSERT INTO plans(name, price_cents, duration_days, features_json)
                VALUES ('基础版', 19900, 30, '["practice"]')
                """
            ).lastrowid
        )
        self.connection.commit()

    def tearDown(self) -> None:
        self.connection.close()

    def _create(self) -> dict:
        return order_service.create_order(
            self.connection,
            organization_id=self.organization_id,
            buyer_user_id=None,
            plan_id=self.plan_id,
            amount_cents=19900,
        )

    def test_create_and_amount_validation(self) -> None:
        order = self._create()
        self.assertEqual(order["status"], "pending")
        self.assertEqual(order["amount_cents"], 19900)
        self.assertIsInstance(order["amount_cents"], int)
        with self.assertRaises(order_service.OrderValidationError):
            order_service.create_order(
                self.connection,
                organization_id=self.organization_id,
                buyer_user_id=None,
                plan_id=self.plan_id,
                amount_cents=199.0,  # type: ignore[arg-type]
            )
        with self.assertRaises(order_service.OrderValidationError):
            order_service.create_order(
                self.connection,
                organization_id=self.organization_id,
                buyer_user_id=None,
                plan_id=self.plan_id,
                amount_cents=19901,
            )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO plans(name, price_cents, duration_days) VALUES ('浮点', 1.5, 1)"
            )

    def test_mark_paid_is_idempotent_and_records_one_event(self) -> None:
        order = self._create()
        paid = order_service.mark_paid(self.connection, order["id"])
        paid_again = order_service.mark_paid(self.connection, order["id"])
        self.assertEqual(paid["status"], "paid")
        self.assertEqual(paid_again["paid_at"], paid["paid_at"])
        self.assertEqual(paid_again["expires_at"], paid["expires_at"])
        event_rows = self.connection.execute(
            "SELECT event_type, amount_cents FROM payment_events WHERE order_id = ?",
            (order["id"],),
        ).fetchall()
        self.assertEqual([row["event_type"] for row in event_rows], ["manual_paid"])
        self.assertEqual(event_rows[0]["amount_cents"], 19900)

    def test_state_machine_allows_valid_paths_and_rejects_invalid_paths(self) -> None:
        paid = order_service.mark_paid(self.connection, self._create()["id"])
        refunding = order_service.refund(self.connection, paid["id"])
        refunded = order_service.mark_refunded(self.connection, refunding["id"])
        self.assertEqual(refunded["status"], "refunded")
        for action in (
            lambda: order_service.mark_paid(self.connection, refunded["id"]),
            lambda: order_service.refund(self.connection, refunded["id"]),
            lambda: order_service.mark_refunded(self.connection, refunded["id"]),
            lambda: order_service.cancel(self.connection, refunded["id"]),
            lambda: order_service.fail(self.connection, refunded["id"]),
        ):
            with self.assertRaises(order_service.InvalidOrderStateError):
                action()

        cancelled = order_service.cancel(self.connection, self._create()["id"])
        self.assertEqual(cancelled["status"], "cancelled")
        with self.assertRaises(order_service.InvalidOrderStateError):
            order_service.mark_paid(self.connection, cancelled["id"])

        failed = order_service.fail(self.connection, self._create()["id"])
        self.assertEqual(failed["status"], "failed")
        with self.assertRaises(order_service.InvalidOrderStateError):
            order_service.cancel(self.connection, failed["id"])


class OrderApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.database_path = Path(self.temp.name) / "orders-test.db"
        self.db_patch = patch("backend.app.database.DATABASE_PATH", self.database_path)
        self.db_patch.start()
        from backend.app.database import initialize_database
        from backend.app.main import app

        initialize_database()
        self.client = TestClient(app)
        self.plan_id = self._insert_plan()

    def tearDown(self) -> None:
        self.client.close()
        self.db_patch.stop()
        self.temp.cleanup()

    def _insert_plan(self) -> int:
        connection = sqlite3.connect(self.database_path)
        try:
            plan_id = connection.execute(
                """
                INSERT INTO plans(name, price_cents, duration_days, features_json)
                VALUES ('团队版', 50000, 365, '{}')
                """
            ).lastrowid
            connection.commit()
            return int(plan_id)
        finally:
            connection.close()

    def test_api_create_get_and_amount_mismatch(self) -> None:
        from backend.app.routers import auth

        with patch.object(auth, "AUTH_ENABLED", False):
            created = self.client.post(
                "/api/orders",
                json={"plan_id": self.plan_id, "amount_cents": 50000},
            )
            self.assertEqual(created.status_code, 201)
            self.assertEqual(created.json()["status"], "pending")
            order_id = created.json()["id"]
            fetched = self.client.get(f"/api/orders/{order_id}")
            self.assertEqual(fetched.status_code, 200)
            self.assertEqual(fetched.json()["order_no"], created.json()["order_no"])
            mismatch = self.client.post(
                "/api/orders",
                json={"plan_id": self.plan_id, "amount_cents": 50001},
            )
            self.assertEqual(mismatch.status_code, 422)

    def test_non_owner_cannot_mark_paid(self) -> None:
        from backend.app.routers import auth

        with patch.object(auth, "AUTH_ENABLED", True):
            owner = self.client.post(
                "/api/auth/register",
                json={"username": "orderowner", "password": "Passw0rd123"},
            ).json()
            student = self.client.post(
                "/api/auth/register",
                json={"username": "orderstudent", "password": "Passw0rd123"},
            ).json()
            owner_headers = {"Authorization": f"Bearer {owner['token']}"}
            student_headers = {"Authorization": f"Bearer {student['token']}"}
            organization_id = owner["user"]["active_organization_id"]
            connection = sqlite3.connect(self.database_path)
            try:
                connection.execute(
                    """
                    INSERT INTO organization_members(organization_id, user_id, role, status)
                    VALUES (?, ?, 'student', 'active')
                    """,
                    (organization_id, student["user"]["id"]),
                )
                connection.commit()
            finally:
                connection.close()
            created = self.client.post(
                "/api/orders",
                headers=owner_headers,
                json={"plan_id": self.plan_id, "amount_cents": 50000},
            )
            self.assertEqual(created.status_code, 201)
            order_id = created.json()["id"]
            forbidden = self.client.post(
                f"/api/orders/{order_id}/mark-paid",
                headers={**student_headers, "X-Organization-Id": str(organization_id)},
            )
            self.assertEqual(forbidden.status_code, 403)
            paid = self.client.post(
                f"/api/orders/{order_id}/mark-paid",
                headers=owner_headers,
            )
            self.assertEqual(paid.status_code, 200)
            self.assertEqual(paid.json()["status"], "paid")
            self.assertEqual(len(paid.json()["payment_events"]), 1)


if __name__ == "__main__":
    unittest.main()
