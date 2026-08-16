"""Repair legacy ESQ exports whose locked labels lack content hashes."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.esq import load_esq_package


def repair(source: Path, destination: Path, content_version: str) -> None:
    package = load_esq_package(source)
    hashes = {
        question["questionKey"]: question["contentHash"]
        for paper in package["papers"]
        for unit in paper["units"]
        for question in unit["questions"]
    }
    with tempfile.TemporaryDirectory() as temp:
        extracted = Path(temp)
        with zipfile.ZipFile(source) as archive:
            archive.extractall(extracted)
        manifest_path = extracted / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["contentVersion"] = content_version
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        repaired = 0
        for reference in manifest["papers"]:
            label_path = reference.get("labelPath")
            if not label_path:
                continue
            path = extracted / label_path
            payload = json.loads(path.read_text(encoding="utf-8"))
            for question_key, label in payload.get("labels", {}).items():
                if label.get("reviewStatus") == "locked" and question_key in hashes:
                    label["questionContentHash"] = hashes[question_key]
                    repaired += 1
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(extracted.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(extracted).as_posix())
    print(f"repaired {repaired} locked labels -> {destination}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--content-version", required=True)
    args = parser.parse_args()
    repair(args.source, args.destination, args.content_version)


if __name__ == "__main__":
    main()
