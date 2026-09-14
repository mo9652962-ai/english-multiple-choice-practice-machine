from __future__ import annotations

import sqlite3
import unittest

from backend.app.routers.annotations import annotation_stats, router


class AnnotationStatsTests(unittest.TestCase):
    def test_stats_preserves_both_client_contracts_and_user_scope(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE annotations (
                id INTEGER PRIMARY KEY,
                unit_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                color TEXT NOT NULL DEFAULT 'amber',
                tag TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                user_id INTEGER
            );
            INSERT INTO annotations
                (id, unit_id, text, tag, created_at, updated_at, user_id)
            VALUES
                (1, 10, 'A', '语法', '2026-09-14 10:00:00', '2026-09-14 10:00:00', 101),
                (2, 11, 'B', '语法', '2026-09-14 11:00:00', '2026-09-14 11:00:00', 202);
            """
        )

        result = annotation_stats(connection, {"id": 101})

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["by_tag"], {"语法": 1})
        self.assertEqual([item["id"] for item in result["recent"]], [1])
        self.assertEqual(len(result["tags"]), 1)
        connection.close()

    def test_stats_route_is_registered_once(self) -> None:
        matches = [
            route
            for route in router.routes
            if getattr(route, "path", "") == "/annotations/stats"
        ]
        self.assertEqual(len(matches), 1)


if __name__ == "__main__":
    unittest.main()
