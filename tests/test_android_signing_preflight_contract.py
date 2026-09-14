from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AndroidSigningPreflightContractTests(unittest.TestCase):
    def test_preflight_requires_secrets_without_printing_values(self) -> None:
        source = (ROOT / "scripts" / "check_android_release_signing.ps1").read_text(
            encoding="utf-8"
        )

        for name in (
            "ANDROID_KEYSTORE_PASSWORD",
            "ANDROID_KEY_ALIAS",
            "ANDROID_KEY_PASSWORD",
        ):
            self.assertIn(name, source)
        self.assertIn("keytool", source)
        self.assertNotIn("Write-Host $env:ANDROID_KEYSTORE_PASSWORD", source)

    def test_android_preflight_detects_common_windows_sdk_locations(self) -> None:
        source = (ROOT / "scripts" / "android_preflight.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("LOCALAPPDATA", source)
        self.assertIn("USERPROFILE", source)
        self.assertIn("Android\\Sdk", source)
        self.assertIn("android-sdk", source)


if __name__ == "__main__":
    unittest.main()
