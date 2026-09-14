"""Install a verified release-content bundle into the two ignored seed paths.

The bundle is treated as an input artifact, never as executable content.  Its
manifest, version pair, database hashes, sizes, and public-content counts are
checked before either destination is replaced.  Without ``--force`` existing
database files are left untouched, which makes local use fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import zipfile
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
CONTENT_VERSION_FILE = ROOT / "CONTENT_VERSION"
OFFLINE_CONTENT_VERSION_FILE = ROOT / "OFFLINE_CONTENT_VERSION"
REQUIRED_MEMBERS = {
    "manifest.json",
    "release/question_bank.db",
    "offline/question_bank.db",
}
CONTENT_COUNT_KEYS = ("papers", "questions", "vocabulary_entries")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _safe_member(name: str) -> bool:
    path = Path(name)
    return not path.is_absolute() and ".." not in path.parts and "\\" not in name


def _public_counts(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(path)) as connection:
        vocabulary_columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(\"vocabulary_entries\")")
        }
        papers = int(
            connection.execute(
                "SELECT COUNT(*) FROM papers "
                "WHERE deleted_at IS NULL AND status = 'published'"
            ).fetchone()[0]
        )
        units = int(
            connection.execute(
                "SELECT COUNT(*) FROM units "
                "WHERE paper_id IN ("
                "SELECT id FROM papers WHERE deleted_at IS NULL AND status = 'published'"
                ")"
            ).fetchone()[0]
        )
        questions = int(
            connection.execute(
                "SELECT COUNT(*) FROM questions WHERE unit_id IN ("
                "SELECT id FROM units WHERE paper_id IN ("
                "SELECT id FROM papers WHERE deleted_at IS NULL AND status = 'published'"
                ")"
                ")"
            ).fetchone()[0]
        )
        vocabulary_sql = "SELECT COUNT(*) FROM vocabulary_entries"
        if "user_id" in vocabulary_columns:
            vocabulary_sql += " WHERE user_id IS NULL"
        vocabulary = int(connection.execute(vocabulary_sql).fetchone()[0])
    return {
        "papers": papers,
        "units": units,
        "questions": questions,
        "vocabulary_entries": vocabulary,
    }


def _verify_database(path: Path, entry: dict[str, object], label: str) -> dict[str, int]:
    expected_hash = str(entry.get("sha256") or "").upper()
    actual_hash = _sha256(path)
    if not expected_hash or actual_hash != expected_hash:
        raise ValueError(
            f"{label} database hash mismatch: expected={expected_hash}, actual={actual_hash}"
        )
    expected_size = int(entry.get("size_bytes") or 0)
    if path.stat().st_size != expected_size:
        raise ValueError(
            f"{label} database size mismatch: expected={expected_size}, "
            f"actual={path.stat().st_size}"
        )
    actual_counts = _public_counts(path)
    expected_counts = entry.get("counts")
    if not isinstance(expected_counts, dict):
        raise ValueError(f"{label} manifest counts are missing")
    for key in CONTENT_COUNT_KEYS:
        expected = int(expected_counts.get(key) or 0)
        if actual_counts[key] != expected:
            raise ValueError(
                f"{label} {key} mismatch: expected={expected}, actual={actual_counts[key]}"
            )
    return actual_counts


def _install(source: Path, target: Path, force: bool) -> None:
    if target.exists() and not force:
        raise FileExistsError(
            f"refusing to overwrite existing release content input without --force: {target}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.prepare.tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_bundle(
    bundle_path: Path,
    release_db: Path,
    offline_db: Path,
    *,
    force: bool = False,
) -> dict[str, object]:
    if not bundle_path.is_file():
        raise FileNotFoundError(f"release content bundle is missing: {bundle_path}")
    expected_content_version = CONTENT_VERSION_FILE.read_text(encoding="utf-8").strip()
    expected_offline_version = OFFLINE_CONTENT_VERSION_FILE.read_text(encoding="utf-8").strip()

    with TemporaryDirectory(prefix="epm-prepare-content-") as temporary_root:
        extracted = Path(temporary_root)
        with zipfile.ZipFile(bundle_path) as archive:
            members = archive.infolist()
            names = [item.filename for item in members]
            unsafe = [name for name in names if not _safe_member(name)]
            if unsafe:
                raise ValueError(f"bundle contains unsafe paths: {unsafe[:3]}")
            if len(names) != len(set(names)):
                raise ValueError("bundle contains duplicate member names")
            if set(names) != REQUIRED_MEMBERS:
                raise ValueError(
                    f"bundle members differ from required set: actual={sorted(names)}"
                )
            archive.extractall(extracted)

        manifest_path = extracted / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("manifest_version") != 1:
            raise ValueError("unsupported release content bundle manifest version")
        if manifest.get("content_version") != expected_content_version:
            raise ValueError(
                "bundle content_version does not match CONTENT_VERSION: "
                f"{manifest.get('content_version')} != {expected_content_version}"
            )
        if manifest.get("offline_seed_version") != expected_offline_version:
            raise ValueError(
                "bundle offline_seed_version does not match OFFLINE_CONTENT_VERSION: "
                f"{manifest.get('offline_seed_version')} != {expected_offline_version}"
            )

        release_entry = manifest.get("release")
        offline_entry = manifest.get("offline")
        if not isinstance(release_entry, dict) or not isinstance(offline_entry, dict):
            raise ValueError("bundle release/offline manifest entries are missing")
        release_source = extracted / "release" / "question_bank.db"
        offline_source = extracted / "offline" / "question_bank.db"
        release_counts = _verify_database(release_source, release_entry, "release")
        offline_counts = _verify_database(offline_source, offline_entry, "offline")
        if {
            key: release_counts[key] for key in CONTENT_COUNT_KEYS
        } != {
            key: offline_counts[key] for key in CONTENT_COUNT_KEYS
        }:
            raise ValueError(
                "bundle release/offline public content counts differ: "
                f"release={release_counts}, offline={offline_counts}"
            )

        if not force and (release_db.exists() or offline_db.exists()):
            raise FileExistsError(
                "refusing to overwrite existing release content inputs without --force"
            )
        _install(release_source, release_db, force=force)
        _install(offline_source, offline_db, force=force)

    return {
        "bundle": str(bundle_path),
        "content_version": expected_content_version,
        "offline_seed_version": expected_offline_version,
        "release": {"path": str(release_db), "sha256": _sha256(release_db), "counts": release_counts},
        "offline": {"path": str(offline_db), "sha256": _sha256(offline_db), "counts": offline_counts},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="安装并验证发布内容 bundle")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--release-db", type=Path, default=ROOT / "backend/data/question_bank.db")
    parser.add_argument("--offline-db", type=Path, default=ROOT / "frontend/public/question_bank.db")
    parser.add_argument("--force", action="store_true", help="允许覆盖已有数据库输入")
    args = parser.parse_args()
    result = prepare_bundle(
        args.bundle,
        args.release_db,
        args.offline_db,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
