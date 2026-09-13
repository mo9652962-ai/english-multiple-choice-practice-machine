from __future__ import annotations

import sqlite3
import unittest

from backend.app.database import SCHEMA, _migrate_add_user_id


class DatabaseMigrationTests(unittest.TestCase):
    def test_fresh_schema_has_user_scoped_practice_sessions(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA)
            _migrate_add_user_id(connection)
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(practice_sessions)")
            }
            self.assertIn("user_id", columns)
            srs_columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(spaced_repetition_records)"
                )
            }
            self.assertTrue(
                {
                    "fsrs_due",
                    "fsrs_stability",
                    "fsrs_difficulty",
                    "fsrs_state",
                    "fsrs_step",
                    "fsrs_last_review",
                }.issubset(srs_columns)
            )
        finally:
            connection.close()

    def test_legacy_practice_sessions_get_user_id(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.execute(
                """
                CREATE TABLE practice_sessions (
                    id INTEGER PRIMARY KEY,
                    mode TEXT NOT NULL,
                    unit_ids TEXT NOT NULL
                )
                """
            )
            _migrate_add_user_id(connection)
            columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(practice_sessions)")
            }
            self.assertIn("user_id", columns)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
