from __future__ import annotations

import unittest
from fastapi.testclient import TestClient

from backend.app.database import connect
from backend.app.main import app


class LocalFirstSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        from backend.app.database import initialize_database
        initialize_database()
        self.client = TestClient(app)

    def test_sync_status_endpoint(self) -> None:
        resp = self.client.get("/api/sync/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("server_counts", data)
        self.assertIn("learning_days", data["server_counts"])

    def test_sync_exchange_push_and_pull(self) -> None:
        with connect() as conn:
            q = conn.execute("SELECT id FROM questions LIMIT 1").fetchone()
            if not q:
                conn.execute(
                    "INSERT INTO papers (profile_id, year, title, status) VALUES (1, 2026, '测试同步试卷', 'published')"
                )
                paper_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO units (paper_id, unit_type, number, title) VALUES (?, 'reading', 1, 'Unit 1')",
                    (paper_id,),
                )
                unit_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
                conn.execute(
                    "INSERT INTO questions (unit_id, number, stem, answer) VALUES (?, 1, 'Question 1', 'A')",
                    (unit_id,),
                )
                conn.commit()
                q = conn.execute("SELECT id FROM questions LIMIT 1").fetchone()
            qid = q["id"]

        payload = {
            "client_time": "2026-10-04T12:00:00",
            "push": {
                "learning_days": [
                    {"day": "2026-10-04", "activity_type": "sync_test", "detail": "test sync"}
                ],
                "wrong_stats": [
                    {
                        "question_id": qid,
                        "attempt_count": 3,
                        "wrong_count": 2,
                        "last_wrong_at": "2026-10-04T11:00:00",
                        "note": "测试错题同步",
                    }
                ],
                "fsrs_records": [
                    {
                        "question_id": qid,
                        "due_date": "2026-10-06T00:00:00",
                        "fsrs_due": "2026-10-06T00:00:00",
                        "fsrs_stability": 3.5,
                        "fsrs_difficulty": 4.0,
                        "fsrs_state": 1,
                        "fsrs_last_review": "2026-10-04T11:00:00",
                    }
                ],
            },
        }

        resp = self.client.post("/api/sync/exchange", json=payload)
        self.assertEqual(resp.status_code, 200)
        result = resp.json()

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["pushed_summary"]["learning_days"], 1)
        self.assertEqual(result["pushed_summary"]["wrong_stats"], 1)
        self.assertEqual(result["pushed_summary"]["fsrs_records"], 1)

        # 验证 pull 出来的结果包含刚刚同步的内容
        pull = result["pull"]
        self.assertTrue(any(d["day"] == "2026-10-04" for d in pull["learning_days"]))
        self.assertTrue(any(w["question_id"] == qid for w in pull["wrong_stats"]))
        self.assertTrue(any(f["question_id"] == qid for f in pull["fsrs_records"]))

        # 清理测试数据
        with connect() as conn:
            conn.execute("DELETE FROM learning_days WHERE activity_type = 'sync_test'")
            conn.execute("DELETE FROM wrong_stats WHERE question_id = ?", (qid,))
            conn.execute("DELETE FROM spaced_repetition_records WHERE question_id = ?", (qid,))
            conn.commit()


if __name__ == "__main__":
    unittest.main()
