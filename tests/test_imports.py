from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient
from pypdf import PdfWriter


class ImportAnswerFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = TemporaryDirectory()
        temp_root = Path(cls.temp.name)
        cls.database_path = temp_root / "test.db"
        cls.upload_dir = temp_root / "uploads"
        cls.upload_dir.mkdir()
        cls.patches = [
            patch("backend.app.database.DATABASE_PATH", cls.database_path),
            patch("backend.app.config.UPLOAD_DIR", cls.upload_dir),
            patch("backend.app.routers.imports.UPLOAD_DIR", cls.upload_dir),
        ]
        for active_patch in cls.patches:
            active_patch.start()

        from backend.app.database import initialize_database
        from backend.app.main import app

        initialize_database()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        for active_patch in reversed(cls.patches):
            active_patch.stop()
        try:
            cls.temp.cleanup()
        except PermissionError:
            pass

    def test_answer_attachment_extension_is_validated(self) -> None:
        response = self.client.post(
            "/api/imports",
            files={
                "file": ("paper.docx", io.BytesIO(b"paper"), "application/octet-stream"),
                "answer_file": (
                    "answers.txt",
                    io.BytesIO(b"answers"),
                    "text/plain",
                ),
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("答案文件仅支持", response.json()["detail"])

    def test_scanned_pdf_answer_requires_manual_entry(self) -> None:
        from backend.app.services.docx_parser import extract_answer_attachment

        path = Path(self.temp.name) / "scan.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=595, height=842)
        with path.open("wb") as stream:
            writer.write(stream)

        answers, status = extract_answer_attachment(path)
        self.assertEqual(answers, {})
        self.assertEqual(status["status"], "manual_required")

    def test_manual_answer_endpoint_updates_questions_and_confirms(self) -> None:
        from backend.app.database import connect

        draft = {
            "year": 2002,
            "answers": {"1": ""},
            "answer_sources": {"1": "answers.pdf"},
            "answer_status": {"status": "manual_required"},
            "answers_confirmed": False,
            "units": [
                {
                    "unit_type": "reading",
                    "subtype": "reading_a",
                    "title": "阅读 Text 1",
                    "sequence": 2,
                    "passage": "Passage",
                    "shared_data": {},
                    "questions": [
                        {
                            "number": 1,
                            "stem": "Question",
                            "options": [
                                {"key": key, "content": key}
                                for key in ("A", "B", "C", "D")
                            ],
                            "answer": "",
                            "score": 2.0,
                        }
                    ],
                }
            ],
            "warnings": [],
        }
        import json

        with connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO import_jobs
                    (filename, stored_path, detected_year, detected_format,
                     status, draft_data, warnings)
                VALUES (?, ?, ?, ?, 'draft', ?, '[]')
                """,
                (
                    "paper.docx",
                    "paper.docx",
                    2002,
                    "docx",
                    json.dumps(draft, ensure_ascii=False),
                ),
            )
            job_id = cursor.lastrowid
            connection.commit()

        response = self.client.patch(
            f"/api/imports/{job_id}/answers",
            json={"answers": {"1": "B"}},
        )
        self.assertEqual(response.status_code, 200)
        updated = response.json()["draft"]
        self.assertEqual(updated["answers"]["1"], "B")
        self.assertEqual(updated["units"][0]["questions"][0]["answer"], "B")
        self.assertTrue(updated["answers_confirmed"])
        self.assertEqual(updated["answer_sources"]["1"], "人工录入")

        rejected = self.client.patch(
            f"/api/imports/{job_id}/answers",
            json={"answers": {"41": "A"}},
        )
        self.assertEqual(rejected.status_code, 422)
        self.assertIn("不属于当前客观题草稿", rejected.json()["detail"])

    def test_json_draft_answer_edit_is_treated_as_manual_confirmation(self) -> None:
        from backend.app.database import connect
        import json

        draft = {
            "year": 2002,
            "answers": {"1": "A"},
            "answer_sources": {"1": "answers.pdf"},
            "answer_status": {"status": "parsed"},
            "answers_confirmed": False,
            "units": [
                {
                    "unit_type": "reading",
                    "subtype": "reading_a",
                    "title": "阅读 Text 1",
                    "sequence": 2,
                    "passage": "Passage",
                    "shared_data": {},
                    "questions": [
                        {
                            "number": 1,
                            "stem": "Question",
                            "options": [
                                {"key": key, "content": key}
                                for key in ("A", "B", "C", "D")
                            ],
                            "answer": "A",
                            "score": 2.0,
                        }
                    ],
                }
            ],
            "warnings": [],
        }
        with connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO import_jobs
                    (filename, stored_path, detected_year, detected_format,
                     status, draft_data, warnings)
                VALUES (?, ?, ?, ?, 'draft', ?, '[]')
                """,
                (
                    "paper.docx",
                    "paper.docx",
                    2002,
                    "docx",
                    json.dumps(draft, ensure_ascii=False),
                ),
            )
            job_id = cursor.lastrowid
            connection.commit()

        draft["answers"]["1"] = "B"
        response = self.client.put(
            f"/api/imports/{job_id}",
            json={"draft_data": draft, "reason": "JSON 编辑"},
        )
        self.assertEqual(response.status_code, 200)
        updated = response.json()["draft"]
        self.assertTrue(updated["answers_confirmed"])
        self.assertEqual(updated["answer_sources"]["1"], "人工录入")

    def _minimal_draft(self) -> dict:
        return {
            "year": 2020,
            "detected_format": "docx",
            "title": "2020年考研英语一真题",
            "source_file": "paper.docx",
            "answer_source": "未提供",
            "answer_status": {
                "status": "missing",
                "message": "试卷 Word 未检测到标准答案",
            },
            "answers_confirmed": False,
            "answer_sources": {},
            "answers": {},
            "units": [
                {
                    "unit_type": "reading",
                    "subtype": "reading_a",
                    "title": "阅读 Text 1",
                    "sequence": 2,
                    "passage": "Passage",
                    "shared_data": {},
                    "questions": [
                        {
                            "number": 21,
                            "stem": "Question",
                            "options": [
                                {"key": key, "content": key}
                                for key in ("A", "B", "C", "D")
                            ],
                            "answer": "",
                            "score": 2.0,
                        }
                    ],
                }
            ],
            "warnings": [],
        }

    def test_upload_model_assist_applies_answers_directly(self) -> None:
        from backend.app.routers import imports as imports_router

        draft = self._minimal_draft()
        with (
            patch.object(imports_router, "parse_exam", return_value=draft),
            patch.object(imports_router, "document_text", return_value="document"),
            patch.object(
                imports_router,
                "run_model_assist",
                return_value=(
                    {"answer_map": {"21": "B"}, "issues": ["第21题答案来自答案区"]},
                    "raw",
                ),
            ),
        ):
            response = self.client.post(
                "/api/imports",
                files={
                    "file": (
                        "paper.docx",
                        io.BytesIO(b"paper"),
                        "application/octet-stream",
                    )
                },
                data={"use_model_assist": "true"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model_assist"]["status"], "applied")
        self.assertEqual(body["draft"]["answers"]["21"], "B")
        self.assertEqual(body["draft"]["answer_sources"]["21"], "模型辅助")
        self.assertTrue(any("模型辅助" in warning for warning in body["warnings"]))

    def test_model_assist_counts_matching_local_answer_as_verified(self) -> None:
        from backend.app.services.import_assist import apply_model_assist

        draft = self._minimal_draft()
        draft["answers"] = {"21": "B"}
        draft["answer_sources"] = {"21": "answers.pdf"}
        draft["units"][0]["questions"][0]["answer"] = "B"

        result = apply_model_assist(
            draft,
            {"answer_map": {"21": "B"}, "number_map": {}, "issues": []},
        )

        self.assertEqual(result["model_assist"]["applied_answers"], 1)
        self.assertEqual(result["answer_sources"]["21"], "模型辅助")

    def test_model_assist_accepts_true_false_answers(self) -> None:
        from backend.app.services.import_assist import apply_model_assist

        draft = self._minimal_draft()
        question = draft["units"][0]["questions"][0]
        question["number"] = 41
        question["options"] = [
            {"key": "T", "content": "True"},
            {"key": "F", "content": "False"},
        ]
        draft["units"][0]["unit_type"] = "part_b"
        draft["units"][0]["subtype"] = "true_false"

        result = apply_model_assist(
            draft,
            {"answer_map": {"41": "T"}, "number_map": {}, "issues": []},
        )

        self.assertEqual(result["answers"]["41"], "T")
        self.assertEqual(result["answer_sources"]["41"], "模型辅助")

    def test_model_assist_accepts_cet_a_to_o_answers(self) -> None:
        from backend.app.services.import_assist import apply_model_assist

        draft = self._minimal_draft()
        question = draft["units"][0]["questions"][0]
        question["number"] = 26
        question["options"] = [
            {"key": chr(ord("A") + index), "content": f"word-{index}"}
            for index in range(15)
        ]
        draft["units"][0]["unit_type"] = "word_bank"
        draft["units"][0]["subtype"] = "word_bank"

        result = apply_model_assist(
            draft,
            {"answer_map": {"26": "O"}, "number_map": {}, "issues": []},
        )

        self.assertEqual(result["answers"]["26"], "O")
        self.assertEqual(result["answer_sources"]["26"], "模型辅助")

    def test_option_parser_keeps_word_final_letters(self) -> None:
        from backend.app.services.docx_parser import _split_option_text

        self.assertEqual(
            _split_option_text("[C] have a little common sense. [D] another word."),
            [("C", "have a little common sense."), ("D", "another word.")],
        )
        self.assertEqual(
            _split_option_text("[C] first [D] respond independently to a changing world."),
            [("C", "first"), ("D", "respond independently to a changing world.")],
        )

    def test_upload_model_assist_failure_falls_back_to_local(self) -> None:
        from backend.app.routers import imports as imports_router

        draft = self._minimal_draft()
        with (
            patch.object(imports_router, "parse_exam", return_value=draft),
            patch.object(imports_router, "document_text", return_value="document"),
            patch.object(
                imports_router,
                "run_model_assist",
                side_effect=ValueError("模型服务暂时不可用"),
            ),
        ):
            response = self.client.post(
                "/api/imports",
                files={
                    "file": (
                        "paper.docx",
                        io.BytesIO(b"paper"),
                        "application/octet-stream",
                    )
                },
                data={"use_model_assist": "true"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model_assist"]["status"], "failed")
        self.assertEqual(body["model_assist"]["fell_back_to_local"], True)
        self.assertEqual(body["draft"]["answers"], {})

    def test_deferred_model_assist_keeps_answer_text_and_reports_stages(self) -> None:
        from backend.app.database import connect
        from backend.app.routers import imports as imports_router

        draft = self._minimal_draft()
        with (
            patch.object(imports_router, "parse_exam", return_value=draft),
            patch.object(
                imports_router,
                "extract_attachment_text",
                return_value="参考答案 21-25 BACDC",
            ),
            patch.object(imports_router, "run_model_assist") as mocked,
        ):
            response = self.client.post(
                "/api/imports",
                files={
                    "file": (
                        "paper.docx",
                        io.BytesIO(b"paper"),
                        "application/octet-stream",
                    ),
                    "answer_file": (
                        "answers.docx",
                        io.BytesIO(b"answers"),
                        "application/octet-stream",
                    ),
                },
                data={
                    "use_model_assist": "true",
                    "model_assist_correct_structure": "true",
                    "defer_model_assist": "true",
                },
            )
        self.assertEqual(response.status_code, 200)
        mocked.assert_not_called()
        body = response.json()
        diagnostics = body["draft"]["import_diagnostics"]
        self.assertEqual(diagnostics["model_call_status"], "deferred")
        self.assertTrue(diagnostics["answer_file_received"])
        self.assertEqual(diagnostics["answer_text_chars"], len("参考答案 21-25 BACDC"))

        with connect() as connection:
            row = connection.execute(
                "SELECT parse_context FROM import_jobs WHERE id = ?",
                (body["id"],),
            ).fetchone()
        context = json.loads(row["parse_context"])
        self.assertEqual(context["answer_text"], "参考答案 21-25 BACDC")

        with (
            patch.object(imports_router, "document_text", return_value="document"),
            patch.object(
                imports_router,
                "_model_identity",
                return_value=("Default API", "default-model"),
            ),
            patch.object(
                imports_router,
                "run_model_assist",
                return_value=(
                    {"answer_map": {"21": "B"}, "number_map": {}, "issues": []},
                    "raw",
                ),
            ),
        ):
            assisted = self.client.post(
                f"/api/imports/{body['id']}/model-assist",
                json={"profile_id": None, "model": "", "correct_structure": True},
            )
        self.assertEqual(assisted.status_code, 200)
        assisted_body = assisted.json()
        self.assertEqual(assisted_body["model_assist"]["status"], "applied")
        self.assertEqual(
            assisted_body["draft"]["import_diagnostics"]["model_call_status"],
            "completed",
        )
        self.assertEqual(
            assisted_body["draft"]["import_diagnostics"]["model_name"],
            "default-model",
        )

    def test_model_assist_retry_with_other_model(self) -> None:
        from backend.app.database import connect
        from backend.app.routers import imports as imports_router

        draft = self._minimal_draft()
        with connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO import_jobs
                    (filename, stored_path, detected_year, detected_format,
                     status, draft_data, warnings, parse_context)
                VALUES (?, ?, ?, ?, 'draft', ?, '[]', ?)
                """,
                (
                    "paper.docx",
                    "paper.docx",
                    2020,
                    "docx",
                    json.dumps(draft, ensure_ascii=False),
                    json.dumps({"answer_text": "参考答案 21-25 BACDC"}),
                ),
            )
            job_id = cursor.lastrowid
            connection.commit()
        with (
            patch.object(imports_router, "document_text", return_value="document"),
            patch.object(
                imports_router,
                "run_model_assist",
                return_value=(
                    {"answer_map": {"21": "C"}, "issues": []},
                    "raw",
                ),
            ) as mocked,
        ):
            response = self.client.post(
                f"/api/imports/{job_id}/model-assist",
                json={"profile_id": None, "model": "other-model"},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model_assist"]["status"], "applied")
        self.assertEqual(body["draft"]["answers"]["21"], "C")
        self.assertEqual(body["draft"]["answer_sources"]["21"], "模型辅助")
        self.assertEqual(mocked.call_args.kwargs["model"], "other-model")
        with connect() as connection:
            saved = json.loads(
                connection.execute(
                    "SELECT draft_data FROM import_jobs WHERE id = ?",
                    (job_id,),
                ).fetchone()["draft_data"]
            )
        self.assertEqual(saved["answers"]["21"], "C")

    def _upload_with_assist(self, data: dict, result: dict) -> dict:
        from backend.app.routers import imports as imports_router

        draft = self._minimal_draft()
        with (
            patch.object(imports_router, "parse_exam", return_value=draft),
            patch.object(imports_router, "document_text", return_value="document"),
            patch.object(imports_router, "run_model_assist", return_value=(result, "raw")),
        ):
            response = self.client.post(
                "/api/imports",
                files={
                    "file": (
                        "paper.docx",
                        io.BytesIO(b"paper"),
                        "application/octet-stream",
                    )
                },
                data=data,
            )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_upload_model_assist_structure_fix_applied_when_enabled(self) -> None:
        fixes = [
            {
                "number": 21,
                "stem": "修正题干",
                "options": [
                    {"key": "A", "content": "新A"},
                    {"key": "B", "content": "新B"},
                    {"key": "C", "content": "新C"},
                    {"key": "D", "content": "新D"},
                ],
            }
        ]
        body = self._upload_with_assist(
            {
                "use_model_assist": "true",
                "model_assist_correct_structure": "true",
            },
            {"answer_map": {}, "question_fixes": fixes, "issues": []},
        )
        self.assertEqual(body["model_assist"]["status"], "applied")
        self.assertEqual(body["model_assist"]["applied_fixes"], 1)
        question = body["draft"]["units"][0]["questions"][0]
        self.assertEqual(question["stem"], "修正题干")
        self.assertEqual(question["options"][0]["content"], "新A")

    def test_upload_model_assist_structure_fix_ignored_when_disabled(self) -> None:
        fixes = [
            {
                "number": 21,
                "stem": "不应生效",
                "options": [
                    {"key": "A", "content": "不应生效"},
                    {"key": "B", "content": "新B"},
                    {"key": "C", "content": "新C"},
                    {"key": "D", "content": "新D"},
                ],
            }
        ]
        body = self._upload_with_assist(
            {"use_model_assist": "true"},
            {"answer_map": {}, "question_fixes": fixes, "issues": []},
        )
        self.assertEqual(body["model_assist"]["status"], "applied")
        self.assertEqual(body["model_assist"]["applied_fixes"], 0)
        question = body["draft"]["units"][0]["questions"][0]
        self.assertEqual(question["stem"], "Question")
        self.assertEqual(question["options"][0]["content"], "A")

    def test_model_assist_leaves_output_budget_to_provider(self) -> None:
        from backend.app.services import import_assist

        with patch.object(
            import_assist,
            "chat_completion",
            return_value='{"answer_map": {}, "number_map": {}, "issues": []}',
        ) as mocked:
            result, _ = import_assist.run_model_assist(
                object(),
                self._minimal_draft(),
                "document",
            )

        self.assertEqual(result["answer_map"], {})
        self.assertIsNone(mocked.call_args.kwargs["max_tokens"])

    def test_multi_paper_fallback_splits_repeated_writing_sections(self) -> None:
        from backend.app.services.import_assist import infer_document_papers

        blocks = [
            "2019年6月第1套",
            "Part I Writing (30 minutes)",
            "Part II Listening Comprehension (30 minutes)",
            "Part III Reading Comprehension (40 minutes)",
            "2019年6月第2套",
            "Part I Writing (30 minutes)",
            "Part II Listening Comprehension (30 minutes)",
            "Part III Reading Comprehension (40 minutes)",
            "2019年6月第3套",
            "Part I Writing (30 minutes)",
            "Part IV Translation (30 minutes)",
        ]

        papers = infer_document_papers(
            blocks,
            "2019年06月六级真题全3套.docx",
        )

        self.assertEqual(len(papers), 3)
        self.assertEqual([paper["set_number"] for paper in papers], [1, 2, 3])
        self.assertTrue(papers[0]["has_objective_questions"])
        self.assertFalse(papers[2]["has_objective_questions"])

    def test_upload_only_creates_first_paper_from_multi_paper_document(self) -> None:
        from backend.app.routers import imports as imports_router

        blocks = [
            "2019年6月第1套",
            "Part I Writing (30 minutes)",
            "Part II Listening Comprehension (30 minutes)",
            "Part III Reading Comprehension (40 minutes)",
            "2019年6月第2套",
            "Part I Writing (30 minutes)",
            "Part II Listening Comprehension (30 minutes)",
            "Part III Reading Comprehension (40 minutes)",
            "2019年6月第3套",
            "Part I Writing (30 minutes)",
            "Part II Listening Comprehension (30 minutes)",
            "Part III Reading Comprehension (40 minutes)",
        ]
        with (
            patch.object(imports_router, "extract_blocks", return_value=(blocks, {}, None)),
            patch.object(imports_router, "create_docx_block_fragment"),
            patch.object(imports_router, "parse_exam", return_value=self._minimal_draft()),
        ):
            response = self.client.post(
                "/api/imports",
                files={
                    "file": (
                        "2019年06月六级真题全3套.docx",
                        io.BytesIO(b"paper"),
                        "application/octet-stream",
                    )
                },
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["split_count"], 1)
        self.assertEqual(body["detected_paper_count"], 3)
        self.assertEqual(body["ignored_paper_count"], 2)
        self.assertEqual(len(body["split_jobs"]), 1)
        self.assertEqual(body["draft"]["document_split"]["paper_index"], 1)
        self.assertEqual(body["draft"]["document_split"]["paper_count"], 1)
        self.assertEqual(body["draft"]["document_split"]["ignored_paper_count"], 2)

    def test_paper_without_objective_questions_cannot_be_published(self) -> None:
        from backend.app.database import connect

        draft = self._minimal_draft()
        draft["document_split"] = {
            "paper_index": 3,
            "paper_count": 3,
            "has_objective_questions": False,
        }
        with connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO import_jobs
                    (filename, stored_path, detected_year, detected_format,
                     status, draft_data, warnings)
                VALUES (?, ?, ?, ?, 'draft', ?, '[]')
                """,
                (
                    "writing-only.docx",
                    "writing-only.docx",
                    2020,
                    "docx",
                    json.dumps(draft, ensure_ascii=False),
                ),
            )
            job_id = cursor.lastrowid
            connection.commit()

        response = self.client.post(f"/api/imports/{job_id}/publish")
        self.assertEqual(response.status_code, 409)
        self.assertIn("未检测到客观题", response.json()["detail"])

    def test_model_assist_applies_safe_number_map_and_moves_answers(self) -> None:
        from backend.app.services.import_assist import apply_model_assist

        draft = self._minimal_draft()
        first = draft["units"][0]["questions"][0]
        first["answer"] = "A"
        second = json.loads(json.dumps(first))
        second["number"] = 22
        second["answer"] = "B"
        draft["units"][0]["questions"].append(second)
        draft["answers"] = {"21": "A", "22": "B"}
        draft["answer_sources"] = {"21": "local", "22": "local"}

        result = apply_model_assist(
            draft,
            {
                "answer_map": {},
                "number_map": {"21": "22", "22": "21"},
                "issues": [],
            },
        )

        questions = result["units"][0]["questions"]
        self.assertEqual([question["number"] for question in questions], [22, 21])
        self.assertEqual(result["answers"], {"22": "A", "21": "B"})
        self.assertEqual(result["model_assist"]["applied_number_fixes"], 2)

    def test_model_assist_rejects_duplicate_number_map(self) -> None:
        from backend.app.services.import_assist import apply_model_assist

        draft = self._minimal_draft()
        second = json.loads(json.dumps(draft["units"][0]["questions"][0]))
        second["number"] = 22
        draft["units"][0]["questions"].append(second)
        result = apply_model_assist(
            draft,
            {
                "answer_map": {},
                "number_map": {"21": "22"},
                "issues": [],
            },
        )

        self.assertEqual(result["units"][0]["questions"][0]["number"], 21)
        self.assertEqual(result["model_assist"]["applied_number_fixes"], 0)
        self.assertTrue(
            any("重复题号" in warning for warning in result["warnings"])
        )
    def test_multiple_answer_attachments_are_merged_for_model_assist(self) -> None:
        from backend.app.database import connect
        from backend.app.routers import imports as imports_router

        draft = self._minimal_draft()
        with (
            patch.object(imports_router, "parse_exam", return_value=draft),
            patch.object(
                imports_router,
                "extract_attachment_text",
                side_effect=["first answers", "second answers", "third answers"],
            ),
        ):
            response = self.client.post(
                "/api/imports",
                files=[
                    ("file", ("paper.docx", io.BytesIO(b"paper"), "application/octet-stream")),
                    ("answer_files", ("set-1.pdf", io.BytesIO(b"one"), "application/pdf")),
                    ("answer_files", ("set-2.pdf", io.BytesIO(b"two"), "application/pdf")),
                    ("answer_files", ("set-3.pdf", io.BytesIO(b"three"), "application/pdf")),
                ],
                data={"use_model_assist": "true", "defer_model_assist": "true"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["draft"]["import_diagnostics"]["answer_file_count"], 3)
        with connect() as connection:
            row = connection.execute(
                "SELECT parse_context FROM import_jobs WHERE id = ?",
                (body["id"],),
            ).fetchone()
        context = json.loads(row["parse_context"])
        self.assertIn("first answers", context["answer_text"])
        self.assertIn("second answers", context["answer_text"])
        self.assertIn("third answers", context["answer_text"])
        self.assertEqual(len(context["answer_paths"]), 3)

    def test_split_answer_text_filters_year_month_and_set(self) -> None:
        from backend.app.routers.imports import _answer_text_for_split

        answer_text = "\n\n".join(
            [
                "===== answer attachment: 2018.12英语六级解析第1套.pdf =====\nold",
                "===== answer attachment: 2019.06英语六级解析第1套.pdf =====\nwanted",
                "===== answer attachment: 2019.06英语六级解析第2套.pdf =====\nother-set",
                "===== answer attachment: 2020.06英语六级解析第1套.pdf =====\nother-year",
            ]
        )

        filtered = _answer_text_for_split(
            answer_text,
            {"year": 2019, "month": 6, "set_number": 1},
        )

        self.assertIn("wanted", filtered)
        self.assertNotIn("old", filtered)
        self.assertNotIn("other-set", filtered)
        self.assertNotIn("other-year", filtered)
        self.assertEqual(
            _answer_text_for_split(
                answer_text,
                {"year": 2021, "month": 6, "set_number": 3},
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
