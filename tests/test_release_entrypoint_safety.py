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

    def test_build_scripts_do_not_reintroduce_direct_release_side_effects(self) -> None:
        forbidden_fragments = (
            "gh release create",
            "gh release upload",
            "Set-AuthenticodeSignature",
        )
        candidates = [
            path
            for directory in (ROOT / "scripts", ROOT / "tools")
            for path in directory.rglob("*")
            if path.is_file() and path.suffix.lower() in {".py", ".ps1", ".mjs"}
        ]

        for path in candidates:
            source = path.read_text(encoding="utf-8")
            for fragment in forbidden_fragments:
                self.assertNotIn(fragment, source, f"unsafe release command in {path}")


if __name__ == "__main__":
    unittest.main()
