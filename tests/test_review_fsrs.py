from __future__ import annotations

import sqlite3
import unittest

from backend.app.services.review import count_due, get_due_queue, update_srs_record


class QuestionFsrsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE questions (id INTEGER PRIMARY KEY, stem TEXT NOT NULL);
            CREATE TABLE wrong_stats (
                user_id INTEGER,
                question_id INTEGER NOT NULL,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, question_id)
            );
            CREATE TABLE spaced_repetition_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_id INTEGER NOT NULL,
                interval_days INTEGER NOT NULL DEFAULT 1,
                ease_factor REAL NOT NULL DEFAULT 2.5,
                review_date TEXT,
                due_date TEXT NOT NULL,
                fsrs_due TEXT,
                fsrs_stability REAL,
                fsrs_difficulty REAL,
                fsrs_state INTEGER DEFAULT 0,
                fsrs_step INTEGER DEFAULT 0,
                fsrs_last_review TEXT,
                UNIQUE (user_id, question_id)
            );
            INSERT INTO questions(id, stem) VALUES (1, 'Which answer is correct?');
            INSERT INTO wrong_stats(user_id, question_id, wrong_count) VALUES (NULL, 1, 1);
            """
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_wrong_question_enters_fsrs_and_due_queue(self) -> None:
        result = update_srs_record(self.connection, 1, quality_score=1)
        self.connection.commit()

        self.assertEqual(result["algorithm"], "fsrs")
        self.assertIsNotNone(result["due"])
        row = self.connection.execute(
            "SELECT fsrs_due, fsrs_stability, fsrs_difficulty, fsrs_state "
            "FROM spaced_repetition_records WHERE question_id = 1"
        ).fetchone()
        self.assertIsNotNone(row["fsrs_due"])
        self.assertGreater(float(row["fsrs_stability"]), 0)
        self.assertGreater(float(row["fsrs_difficulty"]), 0)
        self.assertIn(int(row["fsrs_state"]), (1, 2, 3, 4))
        self.assertEqual(count_due(self.connection), 1)
        queue = get_due_queue(self.connection)
        self.assertEqual(queue[0]["question_id"], 1)
        self.assertEqual(queue[0]["algorithm"], "fsrs")

    def test_second_review_updates_same_card(self) -> None:
        update_srs_record(self.connection, 1, quality_score=1)
        first = self.connection.execute(
            "SELECT id, fsrs_due FROM spaced_repetition_records WHERE question_id = 1"
        ).fetchone()
        update_srs_record(self.connection, 1, quality_score=4)
        second = self.connection.execute(
            "SELECT id, fsrs_due FROM spaced_repetition_records WHERE question_id = 1"
        ).fetchone()
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["fsrs_due"], second["fsrs_due"])


if __name__ == "__main__":
    unittest.main()
