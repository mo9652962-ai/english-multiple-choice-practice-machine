from __future__ import annotations

import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = PROJECT_ROOT / "frontend" / "src" / "services" / "api-adapter.ts"
API = PROJECT_ROOT / "frontend" / "src" / "api.ts"


class OfflineAdapterContractTests(unittest.TestCase):
    """Keep the offline learning routes aligned with the sql.js schema.

    These are intentionally source-level contracts: the adapter is TypeScript
    bundled for the browser, while the backend pytest suite cannot execute its
    sql.js/IndexedDB runtime. They protect the two regressions that previously
    bypassed the real offline state update or addressed a non-existent column.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = ADAPTER.read_text(encoding="utf-8")
        cls.api_source = API.read_text(encoding="utf-8")

    def test_health_checks_reject_spa_html_fallbacks(self) -> None:
        self.assertIn("data?.status === 'ok'", self.source)
        self.assertIn("data?.status === 'ok'", self.api_source)
        self.assertNotIn("backendAvailable = resp.ok\n", self.source)

    def test_wrong_delete_uses_question_id_primary_key(self) -> None:
        self.assertIn(
            "DELETE FROM wrong_stats WHERE question_id = ?",
            self.source,
        )
        self.assertNotIn(
            "DELETE FROM wrong_stats WHERE id = ?",
            self.source,
        )

    def test_vocabulary_review_reaches_state_update_branch(self) -> None:
        self.assertNotIn(
            "if (path.match(/\\/vocabulary\\/\\d+\\/review/))",
            self.source,
        )
        self.assertIn(
            "const vr = path.match(/^\\/vocabulary\\/(\\d+)\\/review$/)",
            self.source,
        )
        self.assertIn(
            "UPDATE vocabulary_entries SET study_status = ?",
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
