from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
DEMO_PACKAGE = ROOT / "examples" / "demo-bank.esq"
CONTENT_VERSION = (ROOT / "CONTENT_VERSION").read_text(encoding="utf-8").strip()


class LearningFlowTests(unittest.TestCase):
    """Deterministic smoke test for the local-first learning loop.

    This deliberately uses a tiny in-memory-equivalent SQLite fixture rather
    than a private corpus. It proves the user-facing API contract without
    requiring an external question bank or an AI provider.
    """

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.database_path = Path(self.temp.name) / "learning-flow.db"
        self.db_patch = patch("backend.app.database.DATABASE_PATH", self.database_path)
        self.db_patch.start()

        from backend.app.database import connect, initialize_database
        from backend.app.main import app

        initialize_database()
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO papers (profile_id, year, title, status)
                VALUES (1, 2026, '学习闭环冒烟题库', 'published')
                """
            )
            paper_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute(
                """
                INSERT INTO units (paper_id, unit_type, subtype, title, sequence, passage)
                VALUES (?, 'reading', 'single_choice', '第一篇阅读', 1, 'A short passage.')
                """,
                (paper_id,),
            )
            unit_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.execute(
                """
                INSERT INTO questions
                    (unit_id, number, stem, question_type, answer, score, sequence)
                VALUES (?, 1, 'Which option is correct?', 'single_choice', 'A', 2, 1)
                """,
                (unit_id,),
            )
            question_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            for sequence, stable_key in enumerate(("A", "B", "C", "D"), start=1):
                connection.execute(
                    """
                    INSERT INTO options
                        (question_id, stable_key, original_label, content, sequence)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (question_id, stable_key, stable_key, f"Option {stable_key}", sequence),
                )
            connection.commit()
        self.paper_id = int(paper_id)
        self.unit_id = int(unit_id)
        self.question_id = int(question_id)
        self.translation_patch = patch(
            "backend.app.main.translate_queued_vocabulary",
            return_value={"translated": 0, "remaining": 0},
        )
        self.translation_patch.start()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.translation_patch.stop()
        self.db_patch.stop()
        self.temp.cleanup()

    def test_practice_wrong_review_and_vocabulary_survive_api_round_trip(self) -> None:
        release = self.client.get("/api/content/version")
        self.assertEqual(release.status_code, 200)
        release_payload = release.json()
        self.assertEqual(release_payload["version"], "2.1.3")
        self.assertEqual(release_payload["content_version"], CONTENT_VERSION)
        self.assertEqual(release_payload["schema_version"], 2)
        self.assertEqual(release_payload["counts"]["questions"], 1)
        self.assertTrue(release_payload["database_sha256"].startswith("structural:") or len(release_payload["database_sha256"]) == 64)
        version_payload = self.client.get("/api/version").json()
        self.assertEqual(version_payload["version"], "2.1.3")
        self.assertEqual(version_payload["content_version"], CONTENT_VERSION)
        self.assertEqual(version_payload["schema_version"], 2)

        # The dashboard must explain why each task is recommended and how
        # much local evidence supports it; empty evidence must be explicit.
        today_plan = self.client.get("/api/startup").json()["today_plan"]
        self.assertTrue(today_plan["evidence_policy"])
        self.assertEqual(len(today_plan["plan"]), 3)
        for task in today_plan["plan"]:
            self.assertTrue(task["reason"])
            self.assertTrue(task["expected_effect"])
            self.assertIn("evidence_status", task)
            self.assertIsInstance(task["evidence_count"], int)

        session_response = self.client.post(
            "/api/practice/sessions",
            json={"mode": "unit", "unit_ids": [self.unit_id], "shuffle_options": False},
        )
        self.assertEqual(session_response.status_code, 200)
        session = session_response.json()
        self.assertEqual(session["progress"]["total"], 1)

        question = session["units"][0]["questions"][0]
        saved = self.client.put(
            f"/api/practice/sessions/{session['id']}/answers/{self.question_id}",
            json={"answer": "B", "option_order": question["option_order"]},
        )
        self.assertEqual(saved.status_code, 200)

        submitted = self.client.post(f"/api/practice/sessions/{session['id']}/submit")
        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["result_summary"]["wrong_count"], 1)
        self.assertEqual(len(self.client.get("/api/wrong").json()), 1)
        review_queue = self.client.get("/api/review/queue")
        self.assertEqual(review_queue.status_code, 200)
        self.assertGreaterEqual(review_queue.json()["due_count"], 1)
        self.assertEqual(review_queue.json()["items"][0]["algorithm"], "fsrs")

        retry_response = self.client.post(
            "/api/practice/sessions",
            json={
                "mode": "wrong",
                "question_ids": [self.question_id],
                "count": 1,
                "shuffle_options": False,
            },
        )
        self.assertEqual(retry_response.status_code, 200)
        retry = retry_response.json()
        retry_question = retry["units"][0]["questions"][0]
        self.assertEqual(
            self.client.put(
                f"/api/practice/sessions/{retry['id']}/answers/{self.question_id}",
                json={"answer": "A", "option_order": retry_question["option_order"]},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/practice/sessions/{retry['id']}/submit").status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/wrong").json(), [])

        vocab = self.client.post(
            "/api/vocabulary",
            json={
                "term": "focus",
                "context_sentence": "Focus on the evidence.",
                "unit_id": self.unit_id,
                "question_id": self.question_id,
                "year": 2026,
                "unit_title": "第一篇阅读",
                "unit_type": "reading",
            },
        )
        self.assertEqual(vocab.status_code, 200)
        self.assertTrue(vocab.json()["is_new"])
        self.assertEqual(self.client.get("/api/vocabulary").json()["counts"]["total"], 1)

        with self.client as client:
            restored = client.get(f"/api/practice/sessions/{session['id']}")
        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["status"], "submitted")

    def test_local_metrics_are_opt_in_and_reset_when_disabled(self) -> None:
        self.assertEqual(self.client.get("/api/metrics/consent").json(), {"enabled": False})
        self.assertEqual(
            self.client.post(
                "/api/metrics/events",
                json={"event_name": "app_launch", "detail": {"version": "test"}},
            ).json(),
            {"recorded": False},
        )
        self.assertEqual(
            self.client.put("/api/metrics/consent", json={"enabled": True}).json(),
            {"enabled": True},
        )
        self.assertEqual(
            self.client.post(
                "/api/metrics/events",
                json={"event_name": "app_launch", "detail": {"version": "test"}},
            ).json(),
            {"recorded": True},
        )
        for event_name, detail in (
            ("first_launch", {"version": "test"}),
            ("practice_started", {"mode": "wrong", "question_count": 2}),
            ("vocabulary_review_started", {"mode": "vocabulary", "question_count": 3}),
            ("first_practice_completed", {"mode": "random", "question_count": 3}),
            ("practice_completed", {"mode": "random", "question_count": 3}),
            ("wrong_review_completed", {"mode": "wrong", "question_count": 2}),
            ("vocabulary_review_completed", {"rating": "mastered", "question_count": 1}),
            ("ai_call_failed", {"task": "chat_explain", "provider": "test"}),
            ("feedback_submitted", {"category": "bug"}),
            ("app_error", {"route": "/practice/1"}),
            ("install_failed", {"source": "about"}),
        ):
            self.assertEqual(
                self.client.post(
                    "/api/metrics/events",
                    json={"event_name": event_name, "detail": detail},
                ).json(),
                {"recorded": True},
            )
        summary = self.client.get("/api/metrics/summary?days=30").json()
        self.assertEqual(summary["total_events"], 12)
        self.assertEqual(summary["total_questions"], 3)
        self.assertEqual(summary["wrong_review_started"], 2)
        self.assertEqual(summary["wrong_review_completed"], 2)
        self.assertEqual(summary["wrong_review_rate"], 1.0)
        self.assertEqual(summary["vocabulary_review_started"], 3)
        self.assertEqual(summary["vocabulary_review_completed"], 1)
        self.assertEqual(summary["vocabulary_review_rate"], 0.3333)
        self.assertEqual(summary["active_days_7d"], 1)
        self.assertFalse(summary["returned_after_first_activity_7d"])
        self.assertEqual({item["event_name"] for item in summary["by_event"]}, {
            "first_launch",
            "first_practice_completed",
            "app_launch",
            "practice_started",
            "vocabulary_review_started",
            "practice_completed",
            "wrong_review_completed",
            "vocabulary_review_completed",
            "ai_call_failed",
            "feedback_submitted",
            "app_error",
            "install_failed",
        })
        self.assertEqual(
            self.client.put("/api/metrics/consent", json={"enabled": False}).json(),
            {"enabled": False},
        )
        self.assertEqual(self.client.get("/api/metrics/summary?days=30").json()["total_events"], 0)

    def test_local_metrics_consent_and_delete_are_isolated_by_user(self) -> None:
        from backend.app.database import connect
        from backend.app.services.metrics import get_consent, record_event, set_consent, summarize

        with connect() as connection:
            self.assertTrue(set_consent(connection, True, user_id=101))
            self.assertTrue(set_consent(connection, True, user_id=202))
            self.assertTrue(record_event(connection, "app_launch", user_id=101))
            self.assertTrue(record_event(connection, "app_launch", user_id=202))

            self.assertFalse(set_consent(connection, False, user_id=101))
            self.assertFalse(get_consent(connection, user_id=101))
            self.assertTrue(get_consent(connection, user_id=202))
            self.assertEqual(summarize(connection, user_id=101)["total_events"], 0)
            self.assertEqual(summarize(connection, user_id=202)["total_events"], 1)

    def test_practice_metrics_are_first_use_and_idempotent(self) -> None:
        self.assertEqual(
            self.client.put("/api/metrics/consent", json={"enabled": True}).json(),
            {"enabled": True},
        )
        session_response = self.client.post(
            "/api/practice/sessions",
            json={"mode": "unit", "unit_ids": [self.unit_id], "shuffle_options": False},
        )
        self.assertEqual(session_response.status_code, 200, session_response.text)
        session = session_response.json()
        question = session["units"][0]["questions"][0]
        self.assertEqual(
            self.client.put(
                f"/api/practice/sessions/{session['id']}/answers/{self.question_id}",
                json={"answer": "A", "option_order": question["option_order"]},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/practice/sessions/{session['id']}/submit").status_code,
            200,
        )
        summary = self.client.get("/api/metrics/summary?days=30").json()
        self.assertEqual(summary["total_questions"], 1)
        self.assertEqual(summary["total_events"], 3)
        self.assertEqual(
            {item["event_name"] for item in summary["by_event"]},
            {"practice_started", "practice_completed", "first_practice_completed"},
        )

        # A repeated submit is idempotent and must not inflate activation metrics.
        self.assertEqual(
            self.client.post(f"/api/practice/sessions/{session['id']}/submit").status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/metrics/summary?days=30").json()["total_events"],
            3,
        )

    def test_diagnostic_recommendation_exposes_practice_to_fsrs_path(self) -> None:
        """A diagnosed weakness must carry an executable practice handoff."""
        from backend.app.database import connect

        with connect() as connection:
            connection.execute(
                """
                INSERT INTO questions
                    (unit_id, number, stem, question_type, answer, score, sequence)
                VALUES (?, 2, 'Which detail is supported?', 'single_choice', 'A', 2, 2)
                """,
                (self.unit_id,),
            )
            recommended_question_id = int(connection.execute("SELECT last_insert_rowid()").fetchone()[0])
            for sequence, stable_key in enumerate(("A", "B", "C", "D"), start=1):
                connection.execute(
                    """
                    INSERT INTO options
                        (question_id, stable_key, original_label, content, sequence)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        recommended_question_id,
                        stable_key,
                        stable_key,
                        f"Recommended option {stable_key}",
                        sequence,
                    ),
                )
            connection.commit()

        initial = self.client.post(
            "/api/practice/sessions",
            json={"mode": "unit", "unit_ids": [self.unit_id], "shuffle_options": False},
        )
        self.assertEqual(initial.status_code, 200, initial.text)
        initial_question = initial.json()["units"][0]["questions"][0]
        self.assertEqual(
            self.client.put(
                f"/api/practice/sessions/{initial.json()['id']}/answers/{self.question_id}",
                json={"answer": "B", "option_order": initial_question["option_order"]},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.put(
                f"/api/practice/sessions/{initial.json()['id']}/answers/{recommended_question_id}",
                json={"answer": "A", "option_order": initial.json()["units"][0]["questions"][1]["option_order"]},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/practice/sessions/{initial.json()['id']}/submit").status_code,
            200,
        )

        diagnoses = ([
            {
                "question_id": self.question_id,
                "primary_cause": "context",
                "secondary_causes": [],
                "confidence": 0.9,
                "reason_codes": ["证据不足"],
                "recommended_actions": ["先回到原文定位依据"],
            }
        ], "")
        with patch(
            "backend.app.services.diagnostic_report.diagnose_wrong_answers",
            return_value=diagnoses,
        ), patch(
            "backend.app.services.diagnostic_report.assess_level",
            return_value={"overall": 3, "label": "基础扎实，进阶提升", "by_dimension": {}},
        ):
            report_response = self.client.post(
                "/api/diagnostic/report",
                json={"question_ids": [self.question_id]},
            )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        report = report_response.json()
        self.assertTrue(report["recommendations"])
        recommendation = report["recommendations"][0]
        self.assertEqual(recommendation["practice_path"]["mode"], "random")
        self.assertEqual(
            recommendation["practice_path"]["question_ids"],
            [recommended_question_id],
        )
        self.assertEqual(
            recommendation["practice_path"]["after_submit"],
            "/review/queue",
        )

        targeted = self.client.post(
            "/api/practice/sessions",
            json={
                "mode": recommendation["practice_path"]["mode"],
                "question_ids": recommendation["practice_path"]["question_ids"],
                "count": len(recommendation["practice_path"]["question_ids"]),
                "shuffle_options": False,
            },
        )
        self.assertEqual(targeted.status_code, 200, targeted.text)
        self.assertEqual(
            [question["id"] for unit in targeted.json()["units"] for question in unit["questions"]],
            [recommended_question_id],
        )
        targeted_question = targeted.json()["units"][0]["questions"][0]
        self.assertEqual(
            self.client.put(
                f"/api/practice/sessions/{targeted.json()['id']}/answers/{recommended_question_id}",
                json={"answer": "A", "option_order": targeted_question["option_order"]},
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/practice/sessions/{targeted.json()['id']}/submit").status_code,
            200,
        )
        queue = self.client.get("/api/review/queue")
        self.assertEqual(queue.status_code, 200)
        self.assertIn(self.question_id, [item["question_id"] for item in queue.json()["items"]])


class ImportedEsqLearningFlowTests(unittest.TestCase):
    """Prove the real ESQ import path feeds the local learning loop."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)
        self.upload_dir = self.root / "uploads"
        self.question_bank_dir = self.root / "question_banks"
        self.upload_dir.mkdir()
        self.question_bank_dir.mkdir()
        self.database_path = self.root / "esq-learning-flow.db"
        self.patches = [
            patch("backend.app.config.DATA_DIR", self.root),
            patch("backend.app.config.UPLOAD_DIR", self.upload_dir),
            patch("backend.app.config.QUESTION_BANK_DIR", self.question_bank_dir),
            patch("backend.app.database.DATABASE_PATH", self.database_path),
            patch("backend.app.services.esq.QUESTION_BANK_DIR", self.question_bank_dir),
            patch("backend.app.routers.question_banks.UPLOAD_DIR", self.upload_dir),
            patch(
                "backend.app.routers.question_banks.QUESTION_BANK_DIR",
                self.question_bank_dir,
            ),
            patch("backend.app.main.install_bundled_question_banks", return_value=[]),
        ]
        for active_patch in self.patches:
            active_patch.start()

        from backend.app.database import initialize_database
        from backend.app.main import app

        initialize_database()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        for active_patch in reversed(self.patches):
            active_patch.stop()
        self.temp.cleanup()

    def test_imported_esq_reaches_wrong_review_vocab_and_restart(self) -> None:
        with DEMO_PACKAGE.open("rb") as package:
            imported = self.client.post(
                "/api/question-banks/imports",
                files={
                    "file": (
                        DEMO_PACKAGE.name,
                        package,
                        "application/vnd.english-study-question-bank",
                    )
                },
            )
        self.assertEqual(imported.status_code, 200, imported.text)
        self.assertEqual(imported.json()["preview"]["totals"]["questions"], 1)
        provenance = imported.json()["preview"]["provenance"]
        self.assertEqual(provenance["status"], "pending")
        self.assertIn("license.verified", provenance["missing"])
        self.assertTrue(provenance["license_declared"])
        self.assertTrue(provenance["source_declared"])

        package_id = imported.json()["id"]
        published = self.client.post(
            f"/api/question-banks/imports/{package_id}/publish",
            json={"resolutions": [], "import_ai_labels": False},
        )
        self.assertEqual(published.status_code, 200, published.text)

        from backend.app.database import connect

        with connect() as connection:
            question = connection.execute(
                """
                SELECT q.id AS question_id, u.id AS unit_id
                FROM questions AS q
                JOIN units AS u ON u.id = q.unit_id
                WHERE q.external_key = 'org.example.english.demo.2026.q01'
                """
            ).fetchone()
        self.assertIsNotNone(question)
        question_id = int(question["question_id"])
        unit_id = int(question["unit_id"])

        session_response = self.client.post(
            "/api/practice/sessions",
            json={"mode": "unit", "unit_ids": [unit_id], "shuffle_options": False},
        )
        self.assertEqual(session_response.status_code, 200, session_response.text)
        session = session_response.json()
        practice_question = session["units"][0]["questions"][0]
        self.assertEqual(
            self.client.put(
                f"/api/practice/sessions/{session['id']}/answers/{question_id}",
                json={
                    "answer": "A",
                    "option_order": practice_question["option_order"],
                },
            ).status_code,
            200,
        )
        submitted = self.client.post(f"/api/practice/sessions/{session['id']}/submit")
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()["result_summary"]["wrong_count"], 1)
        self.assertEqual(len(self.client.get("/api/wrong").json()), 1)

        retry = self.client.post(
            "/api/practice/sessions",
            json={
                "mode": "wrong",
                "question_ids": [question_id],
                "count": 1,
                "shuffle_options": False,
            },
        )
        self.assertEqual(retry.status_code, 200, retry.text)
        retry_question = retry.json()["units"][0]["questions"][0]
        self.assertEqual(
            self.client.put(
                f"/api/practice/sessions/{retry.json()['id']}/answers/{question_id}",
                json={
                    "answer": "B",
                    "option_order": retry_question["option_order"],
                },
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(f"/api/practice/sessions/{retry.json()['id']}/submit").status_code,
            200,
        )
        self.assertEqual(self.client.get("/api/wrong").json(), [])

        vocabulary = self.client.post(
            "/api/vocabulary",
            json={
                "term": "evidence",
                "context_sentence": "The evidence supports the answer.",
                "question_id": question_id,
                "unit_id": unit_id,
                "year": 2026,
                "unit_title": "Reading Passage",
                "unit_type": "reading",
            },
        )
        self.assertEqual(vocabulary.status_code, 200, vocabulary.text)
        self.assertTrue(vocabulary.json()["is_new"])

        self.client.close()
        from backend.app.database import initialize_database
        from backend.app.main import app

        initialize_database()
        restarted = TestClient(app)
        try:
            self.assertEqual(restarted.get("/api/wrong").json(), [])
            self.assertEqual(restarted.get("/api/vocabulary").json()["counts"]["total"], 1)
            restored = restarted.get(f"/api/practice/sessions/{session['id']}")
            self.assertEqual(restored.status_code, 200, restored.text)
            self.assertEqual(restored.json()["status"], "submitted")
        finally:
            restarted.close()


if __name__ == "__main__":
    unittest.main()
