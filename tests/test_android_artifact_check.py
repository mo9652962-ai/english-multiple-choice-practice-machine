from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.check_android_artifact import inspect_android_artifact


class AndroidArtifactCheckTests(unittest.TestCase):
    def test_matching_apk_assets_are_reported_with_artifact_hash(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            dist = root / "dist"
            dist.mkdir()
            assets = {
                "question_bank.db": b"seed-r3",
                "offline_migrations.json": b"migrations-r3",
                "release-metadata.json": b'{"content_version":"content-r3"}',
            }
            for name, content in assets.items():
                (dist / name).write_bytes(content)

            apk = root / "app-debug.apk"
            with zipfile.ZipFile(apk, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, content in assets.items():
                    archive.writestr(f"assets/public/{name}", content)

            report = inspect_android_artifact(apk, dist)

            self.assertTrue(report["ok"])
            self.assertEqual(
                report["apk"]["sha256"],
                hashlib.sha256(apk.read_bytes()).hexdigest(),
            )
            self.assertTrue(
                all(item["matches_dist"] for item in report["assets"].values())
            )


if __name__ == "__main__":
    unittest.main()
