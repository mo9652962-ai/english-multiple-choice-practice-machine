from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient


class AppFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        corpus_path = os.environ.get("ENGLISH_PRACTICE_CORPUS")
        if not corpus_path:
            raise unittest.SkipTest(
                "Set ENGLISH_PRACTICE_CORPUS to run full-corpus integration tests."
            )
        folder = Path(corpus_path).expanduser().resolve()
        if not folder.is_dir():
            raise RuntimeError(
                "ENGLISH_PRACTICE_CORPUS must point to an existing directory."
            )

        cls.temp = TemporaryDirectory()
        database_path = Path(cls.temp.name) / "test.db"
        cls.db_patch = patch("backend.app.database.DATABASE_PATH", database_path)
        cls.db_patch.start()

        from backend.app.database import connect, initialize_database
        from backend.app.main import app
        from backend.app.services.docx_parser import import_exam_folder

        initialize_database()
        with connect() as connection:
            import_exam_folder(connection, folder)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        cls.db_patch.stop()
        try:
            cls.temp.cleanup()
        except PermissionError:
            pass

    def test_dashboard_and_library(self) -> None:
        dashboard = self.client.get("/api/startup").json()
        self.assertEqual(dashboard["paper_count"], 17)
        self.assertEqual(dashboard["unit_count"], 102)
        self.assertEqual(dashboard["question_count"], 765)
        papers = self.client.get("/api/papers").json()
        self.assertEqual([paper["year"] for paper in papers][0], 2026)

    def test_2026_whole_paper_grading(self) -> None:
        paper = next(
            item
            for item in self.client.get("/api/papers").json()
            if item["year"] == 2026
        )
        session = self.client.post(
            "/api/practice/sessions",
            json={
                "mode": "paper",
                "paper_id": paper["id"],
                "shuffle_options": True,
            },
        ).json()
        self.assertEqual(session["progress"]["total"], 45)
        self.assertEqual(len(session["units"]), 6)
        part_b = next(unit for unit in session["units"] if unit["unit_type"] == "part_b")
        self.assertEqual(part_b["subtype"], "paragraph_reordering")
        self.assertEqual(len(part_b["questions"]), 5)

        # Use the known 2026 source answers to exercise full autosave and grading.
        from backend.app.database import connect

        with connect() as connection:
            correct = {
                row["id"]: row["answer"]
                for row in connection.execute("SELECT id, answer FROM questions")
            }
        first_question = session["units"][0]["questions"][0]["id"]
        for unit in session["units"]:
            for question in unit["questions"]:
                answer = correct[question["id"]]
                if question["id"] == first_question:
                    answer = next(
                        option["stable_key"]
                        for option in question["options"]
                        if option["stable_key"] != answer
                    )
                response = self.client.put(
                    f"/api/practice/sessions/{session['id']}/answers/{question['id']}",
                    json={
                        "answer": answer,
                        "option_order": question["option_order"],
                    },
                )
                self.assertEqual(response.status_code, 200)

        submitted = self.client.post(
            f"/api/practice/sessions/{session['id']}/submit"
        ).json()
        self.assertEqual(submitted["score"], 59.5)
        self.assertEqual(submitted["max_score"], 60.0)
        self.assertEqual(submitted["result_summary"]["wrong_count"], 1)
        self.assertEqual(submitted["result_summary"]["correct_count"], 44)
        self.assertEqual(submitted["result_summary"]["question_count"], 45)
        self.assertTrue(
            all(unit["submission"]["submitted"] for unit in submitted["units"])
        )
        wrong_unit = next(
            unit
            for unit in submitted["units"]
            if any(
                question["id"] == first_question
                for question in unit["questions"]
            )
        )
        self.assertEqual(wrong_unit["submission"]["wrong_count"], 1)
        self.assertEqual(
            wrong_unit["submission"]["question_count"],
            len(wrong_unit["questions"]),
        )
        wrong = self.client.get("/api/wrong").json()
        self.assertEqual(len(wrong), 1)
        self.assertEqual(wrong[0]["question_id"], first_question)

        retry = self.client.post(
            "/api/practice/sessions",
            json={"mode": "wrong", "count": 10, "shuffle_options": True},
        ).json()
        self.assertEqual(retry["progress"]["total"], 1)
        fetched_retry = self.client.get(
            f"/api/practice/sessions/{retry['id']}"
        ).json()
        self.assertEqual(fetched_retry["progress"]["total"], 1)
        self.assertEqual(len(fetched_retry["units"][0]["questions"]), 1)

    def test_random_mode_returns_whole_unit(self) -> None:
        for unit_type, expected in (("cloze", 20), ("reading", 5), ("part_b", 5)):
            response = self.client.post(
                "/api/practice/sessions",
                json={
                    "mode": "random",
                    "unit_type": unit_type,
                    "count": 1,
                    "shuffle_options": True,
                },
            )
            self.assertEqual(response.status_code, 200)
            session = response.json()
            self.assertEqual(len(session["units"]), 1)
            self.assertEqual(len(session["units"][0]["questions"]), expected)

    def test_paper_unit_can_be_submitted_independently(self) -> None:
        paper = next(
            item
            for item in self.client.get("/api/papers").json()
            if item["year"] == 2013
        )
        session = self.client.post(
            "/api/practice/sessions",
            json={
                "mode": "paper",
                "paper_id": paper["id"],
                "shuffle_options": False,
            },
        ).json()
        unit = session["units"][0]

        incomplete = self.client.post(
            f"/api/practice/sessions/{session['id']}/units/{unit['id']}/submit"
        )
        self.assertEqual(incomplete.status_code, 409)
        self.assertEqual(incomplete.json()["detail"]["code"], "incomplete_submission")
        self.assertEqual(
            incomplete.json()["detail"]["question_id"],
            unit["questions"][0]["id"],
        )

        from backend.app.database import connect

        with connect() as connection:
            correct = {
                row["id"]: row["answer"]
                for row in connection.execute(
                    """
                    SELECT questions.id, questions.answer
                    FROM questions
                    WHERE questions.unit_id = ?
                    """,
                    (unit["id"],),
                )
            }
        for question in unit["questions"]:
            response = self.client.put(
                f"/api/practice/sessions/{session['id']}/answers/{question['id']}",
                json={
                    "answer": correct[question["id"]],
                    "option_order": question["option_order"],
                },
            )
            self.assertEqual(response.status_code, 200)

        submitted = self.client.post(
            f"/api/practice/sessions/{session['id']}/units/{unit['id']}/submit"
        )
        self.assertEqual(submitted.status_code, 200)
        payload = submitted.json()
        submitted_unit = payload["units"][0]
        self.assertTrue(submitted_unit["submission"]["submitted"])
        self.assertEqual(
            submitted_unit["submission"]["score"],
            submitted_unit["submission"]["max_score"],
        )
        self.assertEqual(submitted_unit["submission"]["wrong_count"], 0)
        self.assertEqual(submitted_unit["submission"]["correct_count"], 20)
        self.assertEqual(submitted_unit["submission"]["question_count"], 20)
        self.assertEqual(payload["status"], "active")
        self.assertIsNotNone(submitted_unit["questions"][0]["answer"])

        locked = self.client.put(
            f"/api/practice/sessions/{session['id']}/answers/{unit['questions'][0]['id']}",
            json={
                "answer": correct[unit["questions"][0]["id"]],
                "option_order": unit["questions"][0]["option_order"],
            },
        )
        self.assertEqual(locked.status_code, 400)
        self.assertIn("已经提交", locked.json()["detail"])

        whole_paper = self.client.post(
            f"/api/practice/sessions/{session['id']}/submit"
        )
        self.assertEqual(whole_paper.status_code, 409)
        self.assertEqual(
            whole_paper.json()["detail"]["code"],
            "incomplete_submission",
        )

    def test_unit_then_whole_submit_does_not_repeat_wrong_count(self) -> None:
        paper = next(
            item
            for item in self.client.get("/api/papers").json()
            if item["year"] == 2012
        )
        session = self.client.post(
            "/api/practice/sessions",
            json={
                "mode": "paper",
                "paper_id": paper["id"],
                "shuffle_options": False,
            },
        ).json()

        from backend.app.database import connect

        with connect() as connection:
            correct = {
                row["id"]: row["answer"]
                for row in connection.execute("SELECT id, answer FROM questions")
            }

        first_unit = session["units"][0]
        wrong_question = first_unit["questions"][0]
        for question in first_unit["questions"]:
            answer = correct[question["id"]]
            if question["id"] == wrong_question["id"]:
                answer = next(
                    option["stable_key"]
                    for option in question["options"]
                    if option["stable_key"] != answer
                )
            self.client.put(
                f"/api/practice/sessions/{session['id']}/answers/{question['id']}",
                json={
                    "answer": answer,
                    "option_order": question["option_order"],
                },
            )

        partial = self.client.post(
            f"/api/practice/sessions/{session['id']}/units/{first_unit['id']}/submit"
        ).json()
        self.assertEqual(partial["units"][0]["submission"]["wrong_count"], 1)

        for unit in session["units"][1:]:
            for question in unit["questions"]:
                self.client.put(
                    f"/api/practice/sessions/{session['id']}/answers/{question['id']}",
                    json={
                        "answer": correct[question["id"]],
                        "option_order": question["option_order"],
                    },
                )

        submitted = self.client.post(
            f"/api/practice/sessions/{session['id']}/submit"
        ).json()
        self.assertEqual(submitted["result_summary"]["wrong_count"], 1)
        wrong_row = next(
            row
            for row in self.client.get("/api/wrong").json()
            if row["question_id"] == wrong_question["id"]
        )
        self.assertEqual(wrong_row["wrong_count"], 1)

    def test_wrong_practice_can_be_scoped_to_unit_ids(self) -> None:
        wrong_rows = self.client.get("/api/wrong").json()
        self.assertTrue(wrong_rows)
        selected_unit_id = wrong_rows[0]["unit_id"]
        available_question_ids = [
            row["question_id"]
            for row in wrong_rows
            if row["unit_id"] == selected_unit_id
        ]
        selected_question_ids = available_question_ids[:1]

        response = self.client.post(
            "/api/practice/sessions",
            json={
                "mode": "wrong",
                "unit_ids": [selected_unit_id],
                "question_ids": selected_question_ids,
                "count": 1,
                "shuffle_options": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        session = response.json()
        self.assertEqual([unit["id"] for unit in session["units"]], [selected_unit_id])
        self.assertEqual(
            {
                question["id"]
                for question in session["units"][0]["questions"]
            },
            set(selected_question_ids),
        )

    def test_blank_api_key_does_not_clear_saved_key(self) -> None:
        initial = self.client.put(
            "/api/ai/settings",
            json={
                "name": "Test",
                "base_url": "http://127.0.0.1:11434/v1",
                "api_key": "secret-key",
                "model": "qwen3:8b",
                "temperature": 0.2,
                "max_tokens": 1200,
                "system_prompt": "",
            },
        )
        self.assertEqual(initial.status_code, 200)
        self.assertTrue(initial.json()["has_api_key"])

        updated = self.client.put(
            "/api/ai/settings",
            json={
                "name": "Test",
                "base_url": "http://127.0.0.1:11434/v1",
                "api_key": "",
                "model": "gemma3:4b",
                "temperature": 0.2,
                "max_tokens": 1200,
                "system_prompt": "",
            },
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json()["has_api_key"])

    def test_multiple_ai_profiles_and_model_selector(self) -> None:
        profiles = self.client.get("/api/ai/profiles")
        self.assertEqual(profiles.status_code, 200)
        self.assertGreaterEqual(len(profiles.json()), 1)

        created = self.client.post(
            "/api/ai/profiles",
            json={
                "name": "备用接口",
                "base_url": "http://127.0.0.1:12345/v1",
                "api_key": "backup-secret",
                "enabled": True,
                "is_default": False,
                "default_model": "study-model",
                "temperature": 0.3,
                "max_tokens": 900,
                "system_prompt": "保持简洁",
            },
        )
        self.assertEqual(created.status_code, 200)
        profile_id = created.json()["id"]
        self.assertTrue(created.json()["has_api_key"])

        selector = self.client.get("/api/ai/selector-models").json()["models"]
        self.assertTrue(
            any(
                model["profile_id"] == profile_id
                and model["model_id"] == "study-model"
                for model in selector
            )
        )

        hidden = self.client.put(
            f"/api/ai/profiles/{profile_id}/models",
            json={"model_id": "study-model", "is_visible": False},
        )
        self.assertEqual(hidden.status_code, 200)
        selector = self.client.get("/api/ai/selector-models").json()["models"]
        self.assertFalse(any(model["profile_id"] == profile_id for model in selector))

        disabled_payload = {
            **{
                key: value
                for key, value in created.json().items()
                if key
                in {
                    "name",
                    "base_url",
                    "default_model",
                    "temperature",
                    "max_tokens",
                    "system_prompt",
                }
            },
            "api_key": "",
            "enabled": False,
            "is_default": False,
        }
        disabled = self.client.put(
            f"/api/ai/profiles/{profile_id}",
            json=disabled_payload,
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertTrue(disabled.json()["has_api_key"])
        self.assertFalse(disabled.json()["enabled"])

    def test_selector_recovers_saved_default_model_without_sync(self) -> None:
        created = self.client.post(
            "/api/ai/profiles",
            json={
                "name": "冷启动恢复",
                "base_url": "http://127.0.0.1:12345/v1",
                "api_key": "",
                "enabled": True,
                "is_default": False,
                "default_model": "cached-default-model",
                "temperature": 0.2,
                "max_tokens": 800,
                "system_prompt": "",
            },
        ).json()
        from backend.app.database import connect

        with connect() as connection:
            connection.execute(
                "DELETE FROM ai_profile_models WHERE profile_id = ?",
                (created["id"],),
            )
            connection.commit()

        selector = self.client.get("/api/ai/selector-models")
        self.assertEqual(selector.status_code, 200)
        self.assertTrue(
            any(
                model["profile_id"] == created["id"]
                and model["model_id"] == "cached-default-model"
                for model in selector.json()["models"]
            )
        )

        with connect() as connection:
            connection.execute(
                """
                UPDATE ai_profile_models
                SET is_available = 0
                WHERE profile_id = ? AND model_id = ?
                """,
                (created["id"], "cached-default-model"),
            )
            connection.commit()
        selector = self.client.get("/api/ai/selector-models").json()["models"]
        self.assertTrue(
            any(
                model["profile_id"] == created["id"]
                and model["model_id"] == "cached-default-model"
                for model in selector
            )
        )

    def test_database_connection_can_resume_on_worker_thread(self) -> None:
        from backend.app.database import connect

        connection = connect()
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                result = executor.submit(
                    lambda: connection.execute("SELECT 1").fetchone()[0]
                ).result()
            self.assertEqual(result, 1)
        finally:
            connection.close()

    def test_wrong_analysis_groups_shared_passage_and_returns_report(self) -> None:
        from backend.app.database import connect

        with connect() as connection:
            unit = connection.execute(
                """
                SELECT units.id
                FROM units
                JOIN questions ON questions.unit_id = units.id
                GROUP BY units.id
                HAVING COUNT(questions.id) >= 3
                ORDER BY units.id
                LIMIT 1
                """
            ).fetchone()
            question_ids = [
                row["id"]
                for row in connection.execute(
                    """
                    SELECT id FROM questions
                    WHERE unit_id = ?
                    ORDER BY sequence
                    LIMIT 3
                    """,
                    (unit["id"],),
                ).fetchall()
            ]
            connection.executemany(
                """
                INSERT INTO wrong_stats
                    (question_id, attempt_count, wrong_count, recent_results)
                VALUES (?, 1, 1, '[false]')
                ON CONFLICT(question_id) DO UPDATE SET
                    attempt_count = 1, wrong_count = 1,
                    recent_results = '[false]'
                """,
                [(question_id,) for question_id in question_ids],
            )
            connection.commit()
        diagnoses = [
            {
                "question_id": question_id,
                "primary_cause": "context",
                "secondary_causes": [],
                "confidence": 0.8,
                "reason_codes": ["上下文关系判断不稳定"],
                "recommended_actions": ["先判断逻辑关系再比较选项"],
            }
            for question_id in question_ids
        ]
        with (
            patch(
                "backend.app.routers.ai.diagnose_wrong_answers",
                return_value=(diagnoses, "{}"),
            ),
            patch(
                "backend.app.routers.ai.write_anonymous_report",
                return_value="薄弱点分析结果",
            ),
        ):
            response = self.client.post(
                "/api/ai/analyze-wrong",
                json={
                    "question_ids": question_ids,
                    "focus": "测试",
                    "scope_title": "测试篇目",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["analysis"], "薄弱点分析结果")
        aggregate = response.json()["aggregate"]
        self.assertEqual(aggregate["question_count"], len(question_ids))
        self.assertEqual(aggregate["categories"][0]["code"], "context")
        self.assertEqual(aggregate["categories"][0]["percentage"], 100)

    def test_ai_conversation_lifecycle(self) -> None:
        created = self.client.post("/api/ai/conversations")
        self.assertEqual(created.status_code, 200)
        conversation_id = created.json()["id"]
        self.assertEqual(created.json()["messages"], [])

        listed = self.client.get("/api/ai/conversations")
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(
            any(item["id"] == conversation_id for item in listed.json())
        )

        deleted = self.client.delete(
            f"/api/ai/conversations/{conversation_id}"
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(
            self.client.get(
                f"/api/ai/conversations/{conversation_id}"
            ).status_code,
            404,
        )

    def test_ai_chat_persists_messages(self) -> None:
        profile = self.client.post(
            "/api/ai/profiles",
            json={
                "name": "对话测试",
                "base_url": "http://127.0.0.1:12345/v1",
                "api_key": "",
                "enabled": True,
                "is_default": False,
                "default_model": "chat-model",
                "temperature": 0.2,
                "max_tokens": 800,
                "system_prompt": "",
            },
        ).json()
        with patch(
            "backend.app.routers.ai.chat_completion",
            return_value="这是一条测试回答。",
        ):
            response = self.client.post(
                "/api/ai/chat",
                json={
                    "conversation_id": None,
                    "profile_id": profile["id"],
                    "model": "chat-model",
                    "message": "如何区分两个选项？",
                },
            )
        self.assertEqual(response.status_code, 200)
        conversation_id = response.json()["conversation_id"]
        conversation = self.client.get(
            f"/api/ai/conversations/{conversation_id}"
        ).json()
        self.assertEqual(
            [message["role"] for message in conversation["messages"]],
            ["user", "assistant"],
        )
        self.assertEqual(
            conversation["messages"][1]["content"],
            "这是一条测试回答。",
        )


if __name__ == "__main__":
    unittest.main()
