from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.app.schemas import ModelAssistRequest
from tools.batch_import import discover_batch


class BatchImportDiscoveryTests(unittest.TestCase):
    def test_pairs_answer_and_audio_by_year_and_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "2023-06-第一套"
            folder.mkdir()
            question = folder / "2023年6月四级第一套.docx"
            answer = folder / "2023年6月四级第一套答案.pdf"
            audio = folder / "2023年6月四级第一套听力.mp3"
            question.write_bytes(b"question")
            answer.write_bytes(b"answer")
            audio.write_bytes(b"audio")

            items = discover_batch(root)

            self.assertEqual(len(items), 1)
            self.assertEqual(Path(items[0].question_path), question)
            self.assertEqual(tuple(Path(path) for path in items[0].answer_paths), (answer,))
            self.assertEqual(tuple(Path(path) for path in items[0].audio_paths), (audio,))

    def test_does_not_guess_unmarked_answer_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            question = root / "2010年考研英语二真题.doc"
            unrelated = root / "2010年考研英语二参考资料.pdf"
            question.write_bytes(b"question")
            unrelated.write_bytes(b"reference")

            items = discover_batch(root)

            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].answer_paths, ())

    def test_all_sets_word_pairs_multiple_answer_attachments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            question_folder = root / "2017年06月四级" / "2017.06四级真题word"
            answer_folder = root / "2017年06月四级" / "2017.06四级解析PDF"
            question_folder.mkdir(parents=True)
            answer_folder.mkdir(parents=True)
            question = question_folder / "2017年06月四级真题全3套.docx"
            question.write_bytes(b"question")
            answers = []
            for set_number in (1, 2, 3):
                answer = answer_folder / f"2017.06英语四级解析第{set_number}套.pdf"
                answer.write_bytes(f"answer-{set_number}".encode())
                answers.append(answer)

            items = discover_batch(root)

            self.assertEqual(len(items), 1)
            self.assertEqual(
                {Path(path) for path in items[0].answer_paths},
                set(answers),
            )

    def test_model_assist_output_budget_is_provider_managed(self) -> None:
        request = ModelAssistRequest(max_tokens=12000)
        self.assertEqual(request.max_tokens, 12000)
        self.assertEqual(ModelAssistRequest(max_tokens=100000).max_tokens, 100000)

    def test_prefers_individual_pdfs_over_combined_three_set_word(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / "2018年12月四级"
            folder.mkdir()
            (folder / "2018年12月四级真题全3套.docx").write_bytes(b"combined")
            for set_number in (1, 2, 3):
                (folder / f"2018.12四级真题第{set_number}套.pdf").write_bytes(
                    f"pdf-{set_number}".encode()
                )
                (folder / f"2018.12英语四级解析第{set_number}套.pdf").write_bytes(
                    f"answer-{set_number}".encode()
                )

            items = discover_batch(root)

            self.assertEqual(len(items), 3)
            self.assertEqual(
                {Path(item.question_path).stem for item in items},
                {
                    "2018.12四级真题第1套",
                    "2018.12四级真题第2套",
                    "2018.12四级真题第3套",
                },
            )
            self.assertTrue(all(len(item.answer_paths) == 1 for item in items))


if __name__ == "__main__":
    unittest.main()
