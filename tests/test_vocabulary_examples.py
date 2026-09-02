from __future__ import annotations

import sqlite3
import unittest

from tools.import_vocabulary_examples import import_examples


class VocabularyExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE vocabulary_entries (
                id INTEGER PRIMARY KEY,
                term TEXT NOT NULL,
                normalized_term TEXT NOT NULL
            );
            CREATE TABLE vocabulary_examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                english_sentence TEXT NOT NULL,
                chinese_translation TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                is_verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (entry_id, english_sentence)
            );
            INSERT INTO vocabulary_entries VALUES (1, 'abandon', 'abandon');
            """
        )

    def tearDown(self) -> None:
        self.connection.close()

    def test_import_is_idempotent_and_preserves_verified_translation(self) -> None:
        first = {
            "term": "abandon",
            "examples": [{
                "english": "They had to abandon the plan after the review.",
                "chinese": "审查之后，他们不得不放弃这个计划。",
                "verified": True,
                "source": "curated",
            }],
        }
        import_examples(self.connection, [first])
        second = {
            "term": "abandon",
            "examples": [{
                "english": "They had to abandon the plan after the review.",
                "chinese": "不可靠的机器翻译。",
                "verified": False,
            }],
        }
        import_examples(self.connection, [second])
        row = self.connection.execute(
            "SELECT chinese_translation, is_verified FROM vocabulary_examples"
        ).fetchone()
        self.assertEqual(row["chinese_translation"], "审查之后，他们不得不放弃这个计划。")
        self.assertEqual(row["is_verified"], 1)

    def test_rejects_missing_word(self) -> None:
        with self.assertRaises(ValueError):
            import_examples(
                self.connection,
                [{"term": "missing", "examples": []}],
                dry_run=True,
            )

    def test_rejects_unpaired_example(self) -> None:
        with self.assertRaises(ValueError):
            import_examples(
                self.connection,
                [{"term": "abandon", "examples": [{"english": "Only English text."}]}],
                dry_run=True,
            )


if __name__ == "__main__":
    unittest.main()
