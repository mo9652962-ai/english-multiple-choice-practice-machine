from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from backend.app.database import SCHEMA
from tools.release_check import (
    _content_quality,
    _display_path,
    _read_content_metadata,
    main,
)


class ReleaseContentQualityTests(unittest.TestCase):
    def test_offline_only_applies_min_schema_to_offline_database(self) -> None:
        output = StringIO()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporary:
            offline_db = Path(temporary) / "offline.db"
            connection = sqlite3.connect(offline_db)
            try:
                connection.executescript(SCHEMA)
                connection.execute("ALTER TABLE papers ADD COLUMN source_metadata TEXT NOT NULL DEFAULT '{}' ")
                connection.commit()
            finally:
                connection.close()
            with patch(
                "sys.argv",
                [
                    "release_check.py",
                    "--offline-only",
                    "--offline-db",
                    str(offline_db),
                    "--min-schema-version",
                    "2",
                ],
            ), redirect_stdout(output):
                self.assertEqual(main(), 0, output.getvalue())

    def test_display_path_supports_external_build_output(self) -> None:
        external = Path("C:/build/question_bank.db")
        self.assertEqual(_display_path(external), str(external))

    def test_content_manifest_declares_scope_license_and_upgrade_policy(self) -> None:
        metadata = _read_content_metadata()
        self.assertRegex(metadata["content_version"], r"^content-\d{4}-\d{2}-\d{2}-r\d+$")
        self.assertRegex(metadata["offline_seed_version"], r"^offline-\d{4}-\d{2}-\d{2}-r\d+$")
        self.assertEqual(metadata["schema_version"], 2)
        self.assertEqual(
            metadata["policy"]["release"]["license_status"],
            "per_package_manifest_required",
        )
        self.assertEqual(
            metadata["policy"]["share_policy"]["package_format"],
            "ESQ",
        )
        self.assertTrue(metadata["policy"]["quality_policy"]["manual_review_required"])
        self.assertTrue(metadata["policy"]["quality_policy"]["ai_diff_required"])

    def test_quality_report_allows_contextual_cloze_stems_and_flags_real_gaps(self) -> None:
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(SCHEMA)
            connection.execute(
                "INSERT INTO question_bank_profiles (name, is_default) VALUES ('质量门禁测试级别', 1)"
            )
            profile_id = connection.execute(
                "SELECT id FROM question_bank_profiles ORDER BY id LIMIT 1"
            ).fetchone()[0]
            connection.execute(
                "INSERT INTO papers (profile_id, year, title, status) VALUES (?, 2099, '质量门禁测试', 'published')",
                (profile_id,),
            )
            paper_id = connection.execute("SELECT last_insert_rowid()").fetchone()[0]
            connection.executemany(
                """
                INSERT INTO units (paper_id, unit_type, subtype, title, sequence, passage)
                VALUES (?, ?, 'single_choice', ?, ?, ?)
                """,
                [
                    (paper_id, "cloze", "整篇完形", 1, "A complete cloze passage."),
                    (paper_id, "reading", "阅读理解", 2, "A reading passage."),
                ],
            )
            cloze_id, reading_id = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM units WHERE paper_id = ? ORDER BY sequence", (paper_id,)
                ).fetchall()
            ]
            connection.executemany(
                """
                INSERT INTO questions
                    (unit_id, number, stem, question_type, answer, score, sequence, content_hash)
                VALUES (?, 1, ?, 'single_choice', ?, 2, 1, ?)
                """,
                [
                    (cloze_id, "", "A", "same-hash"),
                    (reading_id, "", "Z", "same-hash"),
                ],
            )
            q1_id, q2_id = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM questions ORDER BY id"
                ).fetchall()
            ]
            connection.executemany(
                """
                INSERT INTO options (question_id, stable_key, original_label, content, sequence)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (q1_id, "A", "A", "first", 1),
                    (q1_id, "B", "B", "second", 2),
                    (q2_id, "A1", "A", "first", 1),
                    (q2_id, "A2", "A", "duplicate label", 2),
                ],
            )
            connection.commit()

            quality = _content_quality(connection)

            self.assertEqual(quality["papers_without_units"], 0)
            self.assertEqual(quality["units_without_questions"], 0)
            self.assertEqual(quality["questions_without_options"], 0)
            self.assertEqual(quality["units_with_unknown_type"], 0)
            self.assertEqual(quality["questions_with_unknown_type"], 0)
            self.assertEqual(quality["questions_with_insufficient_options"], 0)
            self.assertEqual(quality["questions_without_stem"], 1)
            self.assertEqual(quality["questions_with_invalid_answer"], 1)
            self.assertEqual(quality["questions_with_duplicate_option_labels"], 1)
            self.assertEqual(quality["duplicate_content_hash_groups"], 1)
            self.assertEqual(quality["explanations_invalid_json"], 0)
            self.assertEqual(quality["explanations_answer_mismatch"], 0)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
