from __future__ import annotations

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from backend.app.services.option_cleanup import (
    normalize_option_rows,
    split_embedded_option_content,
)
from tools.repair_dirty_options import repair_database


class OptionCleanupTests(unittest.TestCase):
    def test_split_only_treats_labelled_tab_or_newline_as_embedded_option(self) -> None:
        self.assertEqual(
            split_embedded_option_content("A", "first\tB. second"),
            [("A", "first"), ("B", "second")],
        )
        self.assertEqual(
            split_embedded_option_content("C", "third\nD) fourth"),
            [("C", "third"), ("D", "fourth")],
        )
        self.assertEqual(
            split_embedded_option_content("A", "a plain\tvalue"),
            [("A", "a plain\tvalue")],
        )
        self.assertEqual(
            split_embedded_option_content("A", "A. a legitimate single option"),
            [("A", "A. a legitimate single option")],
        )

    def test_normalize_preserves_metadata_and_expands_keys(self) -> None:
        rows = normalize_option_rows(
            [
                {
                    "key": "A",
                    "content": "first\tB. second",
                    "metadata": {"source": "word"},
                },
                {"key": "C", "content": "third\tD. fourth"},
            ]
        )
        self.assertEqual([row["key"] for row in rows], ["A", "B", "C", "D"])
        self.assertEqual(rows[1]["metadata"], {"source": "word"})
        self.assertEqual([row["content"] for row in rows], ["first", "second", "third", "fourth"])

    def test_esq_validation_expands_legacy_merged_content_before_import(self) -> None:
        from backend.app.services.esq import _validate_paper

        details: list[dict[str, str]] = []
        result = _validate_paper(
            {
                "paperKey": "org.example.2030",
                "year": 2030,
                "units": [
                    {
                        "unitKey": "org.example.2030.reading.1",
                        "type": "reading",
                        "passage": {
                            "blocks": [
                                {"blockKey": "paragraph.1", "type": "paragraph", "text": "Passage"}
                            ]
                        },
                        "questions": [
                            {
                                "questionKey": "org.example.2030.q1",
                                "number": 1,
                                "type": "single_choice",
                                "stem": "Question",
                                "options": [
                                    {"key": "A", "content": "first\tB. second"},
                                    {"key": "C", "content": "third\nD. fourth"},
                                ],
                                "score": 1,
                            }
                        ],
                    }
                ],
            },
            {"paperKey": "org.example.2030"},
            {
                "answers": {
                    "org.example.2030.q1": {"correctOption": "D", "score": 1}
                }
            },
            None,
            {},
            details,
        )
        self.assertEqual(details, [])
        self.assertEqual(
            [option["key"] for option in result["units"][0]["questions"][0]["options"]],
            ["A", "B", "C", "D"],
        )

    def test_repair_is_backed_up_idempotent_and_keeps_answer_key(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            db_path = root / "question_bank.db"
            backup_dir = root / "backups"
            connection = sqlite3.connect(db_path)
            connection.executescript(
                """
                CREATE TABLE questions (id INTEGER PRIMARY KEY, answer TEXT NOT NULL);
                CREATE TABLE options (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    stable_key TEXT NOT NULL,
                    original_label TEXT NOT NULL,
                    content TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    UNIQUE (question_id, stable_key)
                );
                INSERT INTO questions VALUES (1, '2');
                INSERT INTO options(question_id, stable_key, original_label, content, sequence)
                VALUES (1, 'A', 'A', 'first\tB. second', 1);
                INSERT INTO options(question_id, stable_key, original_label, content, sequence)
                VALUES (1, 'C', 'C', 'third\tD. fourth', 2);
                """
            )
            connection.commit()
            connection.close()

            result = repair_database(db_path, backup_dir=backup_dir)
            self.assertEqual(result["questions_changed"], 1)
            self.assertEqual(result["options_before"], 2)
            self.assertEqual(result["options_after"], 4)
            self.assertTrue(Path(result["backup"]).exists())

            connection = sqlite3.connect(db_path)
            rows = connection.execute(
                "SELECT stable_key, content FROM options ORDER BY sequence"
            ).fetchall()
            answer = connection.execute("SELECT answer FROM questions WHERE id = 1").fetchone()[0]
            connection.close()
            self.assertEqual(rows, [("A", "first"), ("B", "second"), ("C", "third"), ("D", "fourth")])
            self.assertEqual(answer, "B")

            second = repair_database(db_path, backup_dir=backup_dir)
            self.assertEqual(second["questions_changed"], 0)
            self.assertNotIn("backup", second)


if __name__ == "__main__":
    unittest.main()
