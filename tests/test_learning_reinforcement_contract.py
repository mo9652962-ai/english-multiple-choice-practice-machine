from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LearningReinforcementContractTests(unittest.TestCase):
    def test_wrong_view_can_start_the_loaded_due_queue_as_one_session(self) -> None:
        source = (ROOT / "frontend" / "src" / "views" / "WrongView.vue").read_text(
            encoding="utf-8"
        )

        self.assertIn("async function startReview()", source)
        self.assertIn("question_ids: reviewItems.value.map(item => item.question_id)", source)
        self.assertIn("今日复习全部", source)

if __name__ == "__main__":
    unittest.main()
