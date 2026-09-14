from __future__ import annotations

import unittest
import sqlite3

from backend.app.services.wrong_analysis import (
    aggregate_diagnoses,
    build_diagnostic_payload,
)


class WrongAnalysisTests(unittest.TestCase):
    def test_diagnostic_payload_is_scoped_to_user_stats_and_history(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE papers (id INTEGER PRIMARY KEY, year INTEGER);
            CREATE TABLE units (
                id INTEGER PRIMARY KEY, paper_id INTEGER, title TEXT,
                unit_type TEXT, passage TEXT, sequence INTEGER
            );
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY, unit_id INTEGER, number INTEGER,
                stem TEXT, answer TEXT, question_type TEXT, sequence INTEGER
            );
            CREATE TABLE options (
                question_id INTEGER, stable_key TEXT, content TEXT, sequence INTEGER
            );
            CREATE TABLE wrong_stats (
                user_id INTEGER, question_id INTEGER, attempt_count INTEGER,
                wrong_count INTEGER
            );
            CREATE TABLE question_ai_labels (
                question_id INTEGER, primary_skill TEXT, secondary_skills TEXT,
                trap_types TEXT, attention_points TEXT, vocabulary_demand TEXT,
                context_dependency TEXT, grammar_dependency TEXT, confidence REAL
            );
            CREATE TABLE practice_sessions (
                id INTEGER PRIMARY KEY, user_id INTEGER, started_at TEXT,
                submitted_at TEXT
            );
            CREATE TABLE practice_answers (
                id INTEGER PRIMARY KEY, session_id INTEGER, question_id INTEGER,
                user_answer TEXT, is_correct INTEGER, answered_at TEXT
            );
            CREATE TABLE practice_answer_events (
                id INTEGER PRIMARY KEY, session_id INTEGER, question_id INTEGER,
                user_answer TEXT, changed_at TEXT
            );
            INSERT INTO papers VALUES (1, 2026);
            INSERT INTO units VALUES (1, 1, 'Unit 1', 'reading', 'passage', 1);
            INSERT INTO questions VALUES (1, 1, 1, 'stem', 'A', 'single', 1);
            INSERT INTO options VALUES (1, 'A', 'option A', 1);
            INSERT INTO options VALUES (1, 'B', 'option B', 2);
            INSERT INTO wrong_stats VALUES (101, 1, 2, 1);
            INSERT INTO wrong_stats VALUES (202, 1, 9, 8);
            INSERT INTO practice_sessions VALUES (11, 101, '2026-09-13', '2026-09-13');
            INSERT INTO practice_sessions VALUES (22, 202, '2026-09-13', '2026-09-13');
            INSERT INTO practice_answers VALUES (111, 11, 1, 'B', 0, '2026-09-13');
            INSERT INTO practice_answers VALUES (222, 22, 1, 'A', 1, '2026-09-13');
            INSERT INTO practice_answer_events VALUES (1111, 11, 1, 'B', '2026-09-13');
            INSERT INTO practice_answer_events VALUES (2222, 22, 1, 'A', '2026-09-13');
            """
        )

        user_payload = build_diagnostic_payload(connection, [1], user_id=101)
        question = user_payload[0]["questions"][0]

        self.assertEqual(question["attempt_count"], 2)
        self.assertEqual(question["wrong_count"], 1)
        self.assertEqual(
            [item["selected"] for item in question["history_newest_first"] if "selected" in item],
            ["B"],
        )
        self.assertEqual(
            question["history_newest_first"][-1]["answer_changes"][0]["selected"],
            "B",
        )
        connection.close()

    def test_aggregate_keeps_uncertainty_and_uses_anonymous_categories(self) -> None:
        result = aggregate_diagnoses(
            [
                {
                    "question_id": 11,
                    "primary_cause": "vocabulary",
                    "confidence": 0.8,
                    "reason_codes": ["词义边界不清"],
                    "recommended_actions": ["结合上下文判断词义"],
                },
                {
                    "question_id": 12,
                    "primary_cause": "vocabulary",
                    "confidence": 0.6,
                    "reason_codes": ["词义边界不清"],
                    "recommended_actions": ["结合上下文判断词义"],
                },
                {
                    "question_id": 13,
                    "primary_cause": "uncertain",
                    "confidence": 0.2,
                    "reason_codes": ["记录不足"],
                    "recommended_actions": ["继续积累作答记录"],
                },
            ]
        )
        self.assertEqual(result["question_count"], 3)
        self.assertEqual(result["categories"][0]["label"], "词汇基础与词义辨析")
        self.assertEqual(result["categories"][0]["percentage"], 67)
        self.assertEqual(result["uncertain_count"], 1)
        self.assertNotIn("question_id", result)
        self.assertNotIn("common_reason_codes", result)
        self.assertTrue(
            all("第" not in action for action in result["recommended_actions"])
        )


if __name__ == "__main__":
    unittest.main()
