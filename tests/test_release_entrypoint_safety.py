from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseEntrypointSafetyTests(unittest.TestCase):
    def test_legacy_entrypoint_is_disabled_and_points_to_gated_workflows(self) -> None:
        source = (ROOT / "scripts" / "release_all.py").read_text(encoding="utf-8")

        self.assertIn("is disabled", source)
        self.assertIn(".github/workflows/release.yml", source)
        self.assertIn(".github/workflows/android.yml", source)
        self.assertNotIn("gh release create", source)
        self.assertNotIn("assembleDebug", source)
        self.assertNotIn("Set-AuthenticodeSignature", source)
        self.assertNotIn("D:\\english-multiple-choice-practice-machine", source)

    def test_legacy_entrypoint_returns_nonzero_without_side_effects(self) -> None:
        namespace: dict[str, object] = {}
        source = (ROOT / "scripts" / "release_all.py").read_text(encoding="utf-8")
        exec(compile(source, str(ROOT / "scripts" / "release_all.py"), "exec"), namespace)

        self.assertEqual(namespace["main"](), 2)


if __name__ == "__main__":
    unittest.main()
