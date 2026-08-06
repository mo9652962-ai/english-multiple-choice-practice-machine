from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from backend.app.services.question_labeling import (
    labeling_status,
    _normalized_label_list,
    _request_batch_with_fallback,
)


class QuestionLabelingTests(unittest.TestCase):
    def test_labeling_status_accepts_explicit_paper_scope(self) -> None:
        class FakeConnection:
            count_sql = ""
            count_params = []

            def execute(self, sql, params=()):
                if "COUNT(q.id)" in sql:
                    self.count_sql = sql
                    self.count_params = list(params)
                    return type("Result", (), {"fetchone": lambda _: {
                        "total": 3,
                        "labeled": 1,
                        "locked": 1,
                        "review_pending": 0,
                    }})()
                return type("Result", (), {"fetchall": lambda _: [{"year": 2002}]})()

        connection = FakeConnection()
        result = labeling_status(connection, paper_ids=[8, 7, 8])
        self.assertEqual(result["paper_ids"], [7, 8])
        self.assertIn("p.id IN (?,?)", connection.count_sql)
        self.assertIn("u.unit_type <> 'listening'", connection.count_sql)
        self.assertEqual(connection.count_params, [7, 8])
        self.assertEqual(result["remaining"], 2)

    def test_invalid_large_batch_is_split_and_retried(self) -> None:
        questions = [{"id": value} for value in range(1, 6)]
        calls: list[int] = []

        def fake_request(connection, *, unit, questions, **kwargs):
            calls.append(len(questions))
            if len(questions) > 2:
                raise json.JSONDecodeError("truncated", "{", 1)
            return [
                {
                    "question_id": question["id"],
                    "primary_skill": "上下文逻辑",
                }
                for question in questions
            ]

        with patch(
            "backend.app.services.question_labeling._request_labels",
            side_effect=fake_request,
        ):
            labels = _request_batch_with_fallback(
                object(),
                unit=object(),
                questions=questions,
            )
        self.assertEqual({label["question_id"] for label in labels}, {1, 2, 3, 4, 5})
        self.assertEqual(calls, [5, 2, 3, 1, 2])

    def test_single_string_label_is_kept_as_one_complete_item(self) -> None:
        self.assertEqual(
            _normalized_label_list("先定位题干关键词，再核对同义替换"),
            ["先定位题干关键词，再核对同义替换"],
        )

    def test_label_list_is_trimmed_deduplicated_and_limited(self) -> None:
        self.assertEqual(
            _normalized_label_list([" 词义辨析 ", "", "词义辨析", "上下文逻辑"], limit=2),
            ["词义辨析", "上下文逻辑"],
        )


if __name__ == "__main__":
    unittest.main()
