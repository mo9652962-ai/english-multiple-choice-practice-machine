from __future__ import annotations

import sqlite3
import unittest

from backend.app.services.diagnostic_report import build_recommendations


class DiagnosticPracticePathTests(unittest.TestCase):
    def test_recommendation_contains_full_practice_and_review_handoff(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        try:
            connection.executescript(
                """
                CREATE TABLE papers (
                    id INTEGER PRIMARY KEY,
                    profile_id INTEGER,
                    year INTEGER,
                    deleted_at TEXT
                );
                CREATE TABLE units (
                    id INTEGER PRIMARY KEY,
                    paper_id INTEGER,
                    unit_type TEXT,
                    title TEXT
                );
                CREATE TABLE questions (
                    id INTEGER PRIMARY KEY,
                    unit_id INTEGER,
                    question_type TEXT
                );
                CREATE TABLE wrong_stats (
                    question_id INTEGER,
                    wrong_count INTEGER
                );
                INSERT INTO papers VALUES (1, 1, 2026, NULL);
                INSERT INTO units VALUES (1, 1, 'reading', '推荐阅读');
                INSERT INTO questions VALUES (1, 1, 'single_choice');
                INSERT INTO questions VALUES (2, 1, 'single_choice');
                INSERT INTO wrong_stats VALUES (1, 1);
                """
            )

            recommendations = build_recommendations(
                connection,
                {
                    "categories": [
                        {
                            "code": "context",
                            "label": "上下文逻辑",
                            "count": 1,
                            "percentage": 100,
                        }
                    ]
                },
                profile_id=1,
            )

            self.assertEqual(len(recommendations), 1)
            recommendation = recommendations[0]
            self.assertEqual(recommendation["question_ids"], [2])
            self.assertEqual(
                recommendation["practice_path"],
                {
                    "mode": "random",
                    "question_ids": [2],
                    "after_submit": "/review/queue",
                    "evidence_limit": "练习结果用于后续复习记录，不单独证明能力提升",
                },
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
