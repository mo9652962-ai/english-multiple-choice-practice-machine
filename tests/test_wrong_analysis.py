from __future__ import annotations

import unittest

from backend.app.services.wrong_analysis import aggregate_diagnoses


class WrongAnalysisTests(unittest.TestCase):
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
