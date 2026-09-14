"""Validate that an Android APK embeds the current Web offline assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from typing import Any


REQUIRED_ASSETS = (
    "question_bank.db",
    "offline_migrations.json",
    "release-metadata.json",
)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def inspect_android_artifact(apk_path: Path, dist_dir: Path) -> dict[str, Any]:
    """Return a JSON-serializable comparison report for an APK and Web dist."""

    apk_path = Path(apk_path)
    dist_dir = Path(dist_dir)
    if not apk_path.is_file():
        raise FileNotFoundError(apk_path)
    if not dist_dir.is_dir():
        raise FileNotFoundError(dist_dir)

    apk_bytes = apk_path.read_bytes()
    report: dict[str, Any] = {
        "ok": True,
        "apk": {
            "path": str(apk_path),
            "size_bytes": len(apk_bytes),
            "sha256": _sha256(apk_bytes),
        },
        "assets": {},
        "errors": [],
    }

    try:
        archive = zipfile.ZipFile(apk_path)
    except zipfile.BadZipFile as error:
        report["ok"] = False
        report["errors"].append(f"invalid APK zip: {error}")
        return report

    with archive:
        names = set(archive.namelist())
        for asset_name in REQUIRED_ASSETS:
            archive_name = f"assets/public/{asset_name}"
            dist_path = dist_dir / asset_name
            item: dict[str, Any] = {"matches_dist": False}
            if archive_name not in names:
                item["missing_in_apk"] = True
                report["errors"].append(f"missing APK asset: {archive_name}")
            elif not dist_path.is_file():
                item["missing_in_dist"] = True
                report["errors"].append(f"missing Web dist asset: {dist_path}")
            else:
                apk_asset = archive.read(archive_name)
                dist_asset = dist_path.read_bytes()
                item.update(
                    {
                        "apk_size_bytes": len(apk_asset),
                        "apk_sha256": _sha256(apk_asset),
                        "dist_size_bytes": len(dist_asset),
                        "dist_sha256": _sha256(dist_asset),
                        "matches_dist": apk_asset == dist_asset,
                    }
                )
                if not item["matches_dist"]:
                    report["errors"].append(
                        f"APK asset differs from Web dist: {asset_name}"
                    )
            report["assets"][asset_name] = item

    report["ok"] = not report["errors"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check Android APK offline assets against the current Web dist"
    )
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--write-report", type=Path)
    args = parser.parse_args()

    try:
        report = inspect_android_artifact(args.apk, args.dist)
    except (OSError, ValueError) as error:
        report = {"ok": False, "errors": [str(error)]}

    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(payload, end="")
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(payload, encoding="utf-8")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
