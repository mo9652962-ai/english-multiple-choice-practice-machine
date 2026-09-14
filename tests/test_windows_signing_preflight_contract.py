from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WindowsSigningPreflightContractTests(unittest.TestCase):
    def test_preflight_checks_authenticode_and_public_code_signing_certificate(self) -> None:
        source = (ROOT / "scripts" / "check_windows_release_signing.ps1").read_text(
            encoding="utf-8"
        )

        self.assertIn("Get-AuthenticodeSignature", source)
        self.assertIn("1.3.6.1.5.5.7.3.3", source)
        self.assertIn("$certificate.Subject -eq $certificate.Issuer", source)
        self.assertIn("WINDOWS_CSC_LINK", source)
        self.assertIn("WINDOWS_CSC_KEY_PASSWORD", source)
        self.assertNotIn("Write-Host $env:WINDOWS_CSC_KEY_PASSWORD", source)


if __name__ == "__main__":
    unittest.main()
