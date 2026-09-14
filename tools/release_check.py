#!/usr/bin/env python3
"""Validate release metadata and SQLite content contracts.

The repository intentionally keeps some licensed/development databases out of
Git. This checker therefore validates the databases that are present at build
time instead of assuming that a particular private content bundle is always
available. It reports a SHA-256, schema version, and the key content counts so
release logs can be tied to an exact database file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _display_path(path: Path) -> str:
    """Use repository-relative paths when possible, absolute paths otherwise."""
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
VERSION_FILE = ROOT / "VERSION"
RELEASE_DATE_FILE = ROOT / "RELEASE_DATE"
CONTENT_VERSION_FILE = ROOT / "CONTENT_VERSION"
OFFLINE_CONTENT_VERSION_FILE = ROOT / "OFFLINE_CONTENT_VERSION"
CONTENT_MANIFEST_FILE = ROOT / "content-manifest.json"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _read_metadata() -> tuple[str, str]:
    version = _read_text(VERSION_FILE)
    release_date = _read_text(RELEASE_DATE_FILE)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError(f"invalid VERSION: {version!r}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", release_date):
        raise ValueError(f"invalid RELEASE_DATE: {release_date!r}")
    return version, release_date


def _read_content_metadata() -> dict[str, Any]:
    content_version = _read_text(CONTENT_VERSION_FILE)
    offline_seed_version = _read_text(OFFLINE_CONTENT_VERSION_FILE)
    if not re.fullmatch(r"content-\d{4}-\d{2}-\d{2}-r\d+", content_version):
        raise ValueError(f"invalid CONTENT_VERSION: {content_version!r}")
    if not re.fullmatch(r"offline-\d{4}-\d{2}-\d{2}-r\d+", offline_seed_version):
        raise ValueError(f"invalid OFFLINE_CONTENT_VERSION: {offline_seed_version!r}")
    manifest = json.loads(CONTENT_MANIFEST_FILE.read_text(encoding="utf-8"))
    schema_version = manifest.get("schema_version")
    if not isinstance(schema_version, int) or schema_version < 1:
        raise ValueError("content-manifest.json schema_version must be a positive integer")
    if manifest.get("content_version") != content_version:
        raise ValueError("content-manifest.json content_version does not match CONTENT_VERSION")
    if manifest.get("offline_seed_version") != offline_seed_version:
        raise ValueError(
            "content-manifest.json offline_seed_version does not match OFFLINE_CONTENT_VERSION"
        )
    required_policy = {
        "release": {
            "scope",
            "source_policy",
            "license_status",
            "is_complete",
            "upgrade_policy",
            "allow_export",
            "allow_share",
        },
        "offline_seed": {
            "scope",
            "source_policy",
            "license_status",
            "is_complete",
            "upgrade_policy",
            "allow_export",
            "allow_share",
        },
        "share_policy": {"package_format", "include", "exclude"},
        "quality_policy": {
            "manual_review_required",
            "ai_diff_required",
            "release_sample_required",
            "publishable_provenance_requires_verified_license",
        },
    }
    for section, keys in required_policy.items():
        value = manifest.get(section)
        if not isinstance(value, dict) or not keys.issubset(value):
            missing = sorted(keys - set(value or {})) if isinstance(value, dict) else sorted(keys)
            raise ValueError(
                f"content-manifest.json {section} policy is incomplete: {', '.join(missing)}"
            )
    for section in ("release", "offline_seed"):
        policy = manifest[section]
        if policy["license_status"] != "per_package_manifest_required":
            raise ValueError(f"content-manifest.json {section}.license_status is not explicit")
        if not isinstance(policy["is_complete"], bool):
            raise ValueError(f"content-manifest.json {section}.is_complete must be boolean")
        if not isinstance(policy["allow_export"], bool) or not isinstance(
            policy["allow_share"], bool
        ):
            raise ValueError(f"content-manifest.json {section} export/share policy must be boolean")
        if not isinstance(policy["upgrade_policy"], str) or not policy["upgrade_policy"].strip():
            raise ValueError(f"content-manifest.json {section}.upgrade_policy is empty")
    return {
        "content_version": content_version,
        "offline_seed_version": offline_seed_version,
        "schema_version": schema_version,
        "policy": {
            key: value
            for key, value in manifest.items()
            if key not in {"content_version", "offline_seed_version"}
        },
    }


def _json_version(path: Path) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = payload.get("version")
    if not isinstance(version, str):
        raise ValueError(f"{path}: missing package version")
    return version


def check_metadata(
    version: str,
    release_date: str,
    *,
    require_android_metadata: bool = False,
) -> dict[str, Any]:
    mirrors = {
        "frontend/package.json": ROOT / "frontend" / "package.json",
        "frontend/package-lock.json": ROOT / "frontend" / "package-lock.json",
        "electron/package.json": ROOT / "electron" / "package.json",
        "electron/package-lock.json": ROOT / "electron" / "package-lock.json",
    }
    versions = {name: _json_version(path) for name, path in mirrors.items()}
    mismatches = {name: value for name, value in versions.items() if value != version}

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if f"v{version}" not in readme and version not in readme:
        mismatches["README.md"] = "version marker missing"

    shared_metadata_path = ROOT / "frontend" / "public" / "release-metadata.json"
    shared_metadata: dict[str, Any] = {"path": str(shared_metadata_path.relative_to(ROOT)), "status": "missing"}
    try:
        shared_payload = json.loads(shared_metadata_path.read_text(encoding="utf-8"))
        shared_values = shared_payload.get("metadata", {})
        expected_values = {
            "version": version,
            "release_date": release_date,
            "content_version": _read_text(CONTENT_VERSION_FILE),
            "offline_seed_version": _read_text(OFFLINE_CONTENT_VERSION_FILE),
        }
        mismatched_shared = {
            key: shared_values.get(key)
            for key, expected in expected_values.items()
            if shared_values.get(key) != expected
        }
        if mismatched_shared:
            mismatches["frontend/public/release-metadata.json"] = (
                f"shared metadata mismatch: {mismatched_shared}"
            )
        else:
            shared_metadata["status"] = "verified"
            shared_metadata["metadata"] = shared_values
    except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
        mismatches["frontend/public/release-metadata.json"] = "shared metadata missing or invalid"

    android_gradle_path = ROOT / "frontend" / "android" / "app" / "build.gradle"
    android_metadata = {
        "path": str(android_gradle_path.relative_to(ROOT)),
        "status": "not_generated",
    }
    if android_gradle_path.exists():
        android_gradle = android_gradle_path.read_text(encoding="utf-8")
        if "versionName epmVersion" not in android_gradle or "VERSION" not in android_gradle:
            mismatches[str(android_gradle_path.relative_to(ROOT))] = (
                "Android version is not derived from VERSION"
            )
        else:
            android_metadata["status"] = "verified"
    elif require_android_metadata:
        mismatches[str(android_gradle_path.relative_to(ROOT))] = (
            "generated Android project missing; run npx cap add android and sync_android_version.mjs"
        )

    return {
        "version": version,
        "release_date": release_date,
        "mirrors": versions,
        "mismatches": mismatches,
        "shared_metadata": shared_metadata,
        "android_metadata": android_metadata,
    }


def _table_count(connection: sqlite3.Connection, table: str) -> int:
    row = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
    return int(row[0] if row else 0)


def _package_provenance(connection: sqlite3.Connection, tables: set[str]) -> dict[str, Any]:
    """Summarize source/license metadata stored by the ESQ importer."""
    if "question_bank_packages" not in tables:
        return {
            "packages_total": 0,
            "packages_with_complete_provenance": 0,
            "packages_without_provenance": 0,
            "packages_publishable": 0,
            "packages_not_publishable": 0,
            "publishable_packages": [],
        }
    rows = connection.execute(
        "SELECT package_id, content_version, manifest_data FROM question_bank_packages"
    ).fetchall()
    complete = 0
    missing: list[dict[str, str]] = []
    not_publishable: list[dict[str, str]] = []
    publishable_packages: list[dict[str, str]] = []
    for row in rows:
        package_id = str(row["package_id"] or "")
        content_version = str(row["content_version"] or "")
        try:
            manifest = json.loads(row["manifest_data"] or "{}")
        except (TypeError, json.JSONDecodeError):
            manifest = {}
        license_data = manifest.get("license") if isinstance(manifest, dict) else None
        source_data = manifest.get("source") if isinstance(manifest, dict) else None
        has_license = isinstance(license_data, dict) and bool(
            str(license_data.get("notice") or "").strip()
        )
        has_source = isinstance(source_data, dict) and bool(
            str(source_data.get("description") or "").strip()
        )
        if has_license and has_source and content_version:
            complete += 1
        else:
            missing.append(
                {
                    "package_id": package_id,
                    "content_version": content_version,
                    "missing": ",".join(
                        name
                        for name, present in (
                            ("license.notice", has_license),
                            ("source.description", has_source),
                            ("content_version", bool(content_version)),
                        )
                        if not present
                    ),
                }
            )
        license_verified = bool(
            isinstance(license_data, dict)
            and license_data.get("verified") is True
            and str(license_data.get("spdx") or "").upper() not in {"", "NOASSERTION", "UNKNOWN"}
        )
        source_verified = bool(
            isinstance(source_data, dict) and source_data.get("verified") is True
        )
        review_data = manifest.get("review") if isinstance(manifest, dict) else None
        quality_data = manifest.get("quality") if isinstance(manifest, dict) else None
        human_reviewed = bool(
            isinstance(review_data, dict)
            and str(review_data.get("status") or "").lower() in {"reviewed", "locked"}
        )
        ai_diff_recorded = bool(
            isinstance(manifest.get("ai_assist") if isinstance(manifest, dict) else None, dict)
            and str((manifest.get("ai_assist") or {}).get("diff_status") or "").lower()
            in {"recorded", "reviewed", "not_applicable"}
        )
        sample_reviewed = bool(
            isinstance(quality_data, dict)
            and isinstance(quality_data.get("release_sample") , dict)
            and str(quality_data["release_sample"].get("status") or "").lower()
            in {"passed", "reviewed"}
        )
        publishable = all(
            (has_license, has_source, bool(content_version), license_verified,
             source_verified, human_reviewed, ai_diff_recorded, sample_reviewed)
        )
        if publishable:
            publishable_packages.append(
                {"package_id": package_id, "content_version": content_version}
            )
        if not publishable:
            not_publishable.append(
                {
                    "package_id": package_id,
                    "missing": ",".join(
                        name
                        for name, present in (
                            ("license.verified", license_verified),
                            ("source.verified", source_verified),
                            ("review.status", human_reviewed),
                            ("ai_assist.diff_status", ai_diff_recorded),
                            ("quality.release_sample", sample_reviewed),
                        )
                        if not present
                    ),
                }
            )
    return {
        "packages_total": len(rows),
        "packages_with_complete_provenance": complete,
        "packages_without_provenance": len(missing),
        "missing": missing,
        "packages_publishable": len(rows) - len(not_publishable),
        "packages_not_publishable": len(not_publishable),
        "not_publishable": not_publishable,
        "publishable_packages": publishable_packages,
    }


def _paper_provenance(
    connection: sqlite3.Connection,
    tables: set[str],
    package_provenance: dict[str, Any],
) -> dict[str, Any]:
    """Require every active public paper to resolve to a publishable package.

    Package-level provenance alone is insufficient: a database can contain a
    few verified packages alongside older papers that have no source trail.
    This report intentionally contains paper identity and missing fields, but
    never question text or answers.
    """
    empty = {
        "papers_total": 0,
        "papers_with_publishable_package": 0,
        "papers_without_package": 0,
        "papers_with_unregistered_package": 0,
        "papers_not_publishable": 0,
        "missing": [],
    }
    if "papers" not in tables:
        return empty

    columns = {
        str(row[1])
        for row in connection.execute('PRAGMA table_info("papers")').fetchall()
    }
    select_columns = ["id", "year", "title"]
    select_columns.append("status" if "status" in columns else "'' AS status")
    select_columns.append("deleted_at" if "deleted_at" in columns else "NULL AS deleted_at")
    select_columns.append("package_id" if "package_id" in columns else "NULL AS package_id")
    select_columns.append(
        "content_version" if "content_version" in columns else "NULL AS content_version"
    )
    where = []
    if "deleted_at" in columns:
        where.append("deleted_at IS NULL")
    if "status" in columns:
        where.append("status = 'published'")
    rows = connection.execute(
        f"SELECT {', '.join(select_columns)} FROM papers"
        + (f" WHERE {' AND '.join(where)}" if where else "")
    ).fetchall()
    package_keys = {
        (str(item.get("package_id") or ""), str(item.get("content_version") or ""))
        for item in package_provenance.get("publishable_packages", [])
        if isinstance(item, dict)
    }
    result = dict(empty)
    result["papers_total"] = len(rows)
    missing: list[dict[str, Any]] = []
    for row in rows:
        package_id = str(row["package_id"] or "")
        content_version = str(row["content_version"] or "")
        missing_fields: list[str] = []
        if "package_id" not in columns or not package_id:
            missing_fields.append("package_id")
        if "content_version" not in columns or not content_version:
            missing_fields.append("content_version")
        if not missing_fields and (package_id, content_version) not in package_keys:
            missing_fields.append("package.not_registered_or_not_publishable")
        if missing_fields:
            if "package_id" in missing_fields or "content_version" in missing_fields:
                result["papers_without_package"] += 1
            else:
                result["papers_with_unregistered_package"] += 1
            missing.append(
                {
                    "paper_id": int(row["id"]),
                    "year": int(row["year"]),
                    "title": str(row["title"] or ""),
                    "package_id": package_id,
                    "content_version": content_version,
                    "missing": ",".join(missing_fields),
                }
            )
    result["missing"] = missing
    result["papers_not_publishable"] = len(missing)
    result["papers_with_publishable_package"] = len(rows) - len(missing)
    return result


def _content_quality(connection: sqlite3.Connection) -> dict[str, Any]:
    """Run deterministic content checks that are safe for every release DB.

    These checks intentionally report counts rather than sample question text.
    A release manifest should expose whether a package is structurally sound
    without leaking licensed content into CI logs.
    """

    def count(sql: str) -> int:
        row = connection.execute(sql).fetchone()
        return int(row[0] if row else 0)

    duplicate_hash_groups = count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT content_hash
            FROM questions
            WHERE TRIM(COALESCE(content_hash, '')) <> ''
            GROUP BY content_hash
            HAVING COUNT(*) > 1
        )
        """
    )
    duplicate_labels = count(
        """
        SELECT COUNT(*)
        FROM (
            SELECT question_id, LOWER(TRIM(original_label)) AS label
            FROM options
            WHERE TRIM(COALESCE(original_label, '')) <> ''
            GROUP BY question_id, LOWER(TRIM(original_label))
            HAVING COUNT(*) > 1
        )
        """
    )
    # Keep this gate deliberately conservative.  The importer supports several
    # exam families and their subtypes, so we validate the stable unit enum and
    # the question contract without pretending that every paper has one fixed
    # number of options.
    allowed_unit_types = (
        "'cloze', 'reading', 'part_b', 'listening', 'word_bank', 'paragraph_matching'"
    )
    allowed_question_types = "'single_choice'"
    template_quality = {
        "units_with_unknown_type": count(
            f"""
            SELECT COUNT(*) FROM units
            WHERE LOWER(TRIM(COALESCE(unit_type, ''))) NOT IN ({allowed_unit_types})
            """
        ),
        "questions_with_unknown_type": count(
            f"""
            SELECT COUNT(*) FROM questions
            WHERE LOWER(TRIM(COALESCE(question_type, ''))) NOT IN ({allowed_question_types})
            """
        ),
        "questions_with_insufficient_options": count(
            """
            SELECT COUNT(*) FROM questions q
            WHERE (
                SELECT COUNT(*) FROM options o WHERE o.question_id = q.id
            ) < 2
            """
        ),
    }
    explanation_quality = {
        "explanations_invalid_json": 0,
        "explanations_without_correct_analysis": 0,
        "explanations_answer_mismatch": 0,
    }
    table_exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'question_explanations'"
    ).fetchone()
    if table_exists:
        rows = connection.execute(
            """
            SELECT e.content, q.answer
            FROM question_explanations e
            JOIN questions q ON q.id = e.question_id
            """
        ).fetchall()
        for row in rows:
            try:
                explanation = json.loads(row["content"] or "")
            except (TypeError, json.JSONDecodeError):
                explanation_quality["explanations_invalid_json"] += 1
                continue
            if not isinstance(explanation, dict):
                explanation_quality["explanations_invalid_json"] += 1
                continue
            if not str(
                explanation.get("correct_analysis")
                or explanation.get("locator_sentence")
                or ""
            ).strip() and not isinstance(explanation.get("options_analysis"), dict):
                explanation_quality["explanations_without_correct_analysis"] += 1
            options_analysis = explanation.get("options_analysis")
            if isinstance(options_analysis, dict) and options_analysis:
                correct_keys = [
                    str(key).strip().upper()
                    for key, value in options_analysis.items()
                    if isinstance(value, dict) and value.get("status") == "correct"
                ]
                if len(correct_keys) != 1 or correct_keys[0] != str(row["answer"]).strip().upper():
                    explanation_quality["explanations_answer_mismatch"] += 1
    return {
        "papers_without_units": count(
            """
            SELECT COUNT(*) FROM papers p
            WHERE p.deleted_at IS NULL
              AND NOT EXISTS (SELECT 1 FROM units u WHERE u.paper_id = p.id)
            """
        ),
        "units_without_questions": count(
            """
            SELECT COUNT(*) FROM units u
            WHERE NOT EXISTS (SELECT 1 FROM questions q WHERE q.unit_id = u.id)
            """
        ),
        "questions_without_options": count(
            """
            SELECT COUNT(*) FROM questions q
            WHERE NOT EXISTS (SELECT 1 FROM options o WHERE o.question_id = q.id)
            """
        ),
        "questions_without_stem": count(
            """
            SELECT COUNT(*)
            FROM questions q
            JOIN units u ON u.id = q.unit_id
            WHERE TRIM(COALESCE(q.stem, '')) = ''
              AND NOT (
                  u.unit_type = 'cloze'
                  AND TRIM(COALESCE(u.passage, '')) <> ''
              )
            """
        ),
        "questions_without_answer": count(
            """
            SELECT COUNT(*) FROM questions
            WHERE TRIM(COALESCE(answer, '')) = ''
            """
        ),
        "questions_with_invalid_answer": count(
            """
            SELECT COUNT(*) FROM questions q
            WHERE TRIM(COALESCE(q.answer, '')) <> ''
              AND NOT EXISTS (
                  SELECT 1 FROM options o
                  WHERE o.question_id = q.id
                    AND (o.stable_key = q.answer OR o.original_label = q.answer)
              )
            """
        ),
        "questions_with_duplicate_option_labels": duplicate_labels,
        "duplicate_content_hash_groups": duplicate_hash_groups,
        "questions_without_content_hash": count(
            """
            SELECT COUNT(*) FROM questions
            WHERE TRIM(COALESCE(content_hash, '')) = ''
            """
        ),
        **template_quality,
        **explanation_quality,
    }


def inspect_database(
    path: Path,
    *,
    declared_schema_version: int | None = None,
) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required = {
            "papers",
            "units",
            "questions",
            "options",
            "vocabulary_entries",
        }
        missing = sorted(required - tables)
        if missing:
            raise ValueError(f"{path}: missing tables: {', '.join(missing)}")
        migration = 0
        if "schema_migrations" in tables:
            row = connection.execute(
                "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
            ).fetchone()
            migration = int(row[0] if row else 0)
        counts = {
            table: _table_count(connection, table)
            for table in (
                "papers",
                "units",
                "questions",
                "options",
                "vocabulary_entries",
            )
        }
        if "vocabulary_examples" in tables:
            counts["vocabulary_examples"] = _table_count(connection, "vocabulary_examples")
        quality = _content_quality(connection)
        quality["papers_with_source_metadata"] = int(connection.execute(
            """
            SELECT COUNT(*) FROM papers p
            WHERE p.deleted_at IS NULL
              AND (TRIM(COALESCE(p.source_file, '')) <> ''
                   OR TRIM(COALESCE(p.source_metadata, '')) NOT IN ('', '{}'))
            """
        ).fetchone()[0])
        quality["package_provenance"] = _package_provenance(connection, tables)
        quality["paper_provenance"] = _paper_provenance(
            connection, tables, quality["package_provenance"]
        )
        return {
            "path": _display_path(path),
            "sha256": digest,
            "schema_version": declared_schema_version if declared_schema_version is not None else migration,
            "physical_schema_version": migration,
            "schema_version_source": (
                "content-manifest"
                if declared_schema_version is not None
                else "schema_migrations"
            ),
            "counts": counts,
            "quality": quality,
        }
    finally:
        connection.close()


def inspect_artifact(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "missing": True}
    return {
        "path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": path.stat().st_size,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate EPM release metadata and data")
    parser.add_argument("--release-db", type=Path, default=None)
    parser.add_argument("--offline-db", type=Path, default=None)
    parser.add_argument("--metadata-only", action="store_true")
    parser.add_argument(
        "--offline-only",
        action="store_true",
        help="只检查离线数据库并把其 hash/Schema/计数写入发布清单",
    )
    parser.add_argument(
        "--require-android-metadata",
        action="store_true",
        help="要求已生成的 Android 项目把版本绑定到 VERSION",
    )
    parser.add_argument("--require-matching-content", action="store_true")
    parser.add_argument(
        "--strict-quality",
        action="store_true",
        help="将题库结构、答案和重复内容质量问题作为发布失败",
    )
    parser.add_argument(
        "--require-package-provenance",
        action="store_true",
        help="要求发布库中每个已登记 ESQ 包都有来源、许可证和内容版本",
    )
    parser.add_argument(
        "--require-publishable-provenance",
        action="store_true",
        help="除元数据完整外，还要求许可证/来源已核验、人工复核、AI diff 和发布抽样均有记录",
    )
    parser.add_argument(
        "--require-paper-provenance",
        action="store_true",
        help="要求 release 数据库中每条未删除公开试卷都绑定可发布的题包",
    )
    parser.add_argument("--min-vocabulary", type=int, default=0)
    parser.add_argument("--min-schema-version", type=int, default=0)
    parser.add_argument("--check-templates", action="store_true")
    parser.add_argument(
        "--artifact",
        type=Path,
        action="append",
        default=[],
        help="记录并校验构建产物的 SHA-256；可重复传入",
    )
    parser.add_argument("--write-report", type=Path, default=None)
    args = parser.parse_args()

    version, release_date = _read_metadata()
    content = _read_content_metadata()
    report: dict[str, Any] = {
        "metadata": {
            **check_metadata(
                version,
                release_date,
                require_android_metadata=args.require_android_metadata,
            ),
            **content,
            "source_revision": os.environ.get("GITHUB_SHA", ""),
        },
        "databases": {},
        "artifacts": {},
    }
    errors: list[str] = []
    if report["metadata"]["mismatches"]:
        errors.append("version mirrors are inconsistent")

    if not args.metadata_only:
        db_paths = {
            "offline": args.offline_db or ROOT / "frontend" / "public" / "question_bank.db",
        } if args.offline_only else {
            "release": args.release_db or ROOT / "backend" / "data" / "question_bank.db",
            "offline": args.offline_db or ROOT / "frontend" / "public" / "question_bank.db",
        }
        for name, raw_path in db_paths.items():
            path = raw_path if raw_path.is_absolute() else ROOT / raw_path
            if not path.exists():
                report["databases"][name] = {"path": _display_path(path), "missing": True}
                errors.append(f"{name}: database missing: {path}")
                continue
            try:
                report["databases"][name] = inspect_database(
                    path,
                    declared_schema_version=(
                        content["schema_version"] if name == "offline" else None
                    ),
                )
            except (OSError, sqlite3.Error, ValueError) as error:
                errors.append(str(error))

        for name, data in report["databases"].items():
            if not data.get("missing") and data.get("counts", {}).get("vocabulary_entries", 0) < args.min_vocabulary:
                errors.append(f"{name}: vocabulary_entries below minimum {args.min_vocabulary}")
            if not data.get("missing"):
                for key in (
                    "papers_without_units",
                    "units_without_questions",
                    "questions_without_options",
                ):
                    if data.get("quality", {}).get(key, 0):
                        errors.append(f"{name}: quality gate failed: {key}")
                if args.strict_quality:
                    for key in (
                        "questions_without_stem",
                        "questions_without_answer",
                        "questions_with_invalid_answer",
                        "questions_with_duplicate_option_labels",
                        "duplicate_content_hash_groups",
                        "questions_without_content_hash",
                        "units_with_unknown_type",
                        "questions_with_unknown_type",
                        "questions_with_insufficient_options",
                        "explanations_invalid_json",
                        "explanations_without_correct_analysis",
                        "explanations_answer_mismatch",
                    ):
                        if data.get("quality", {}).get(key, 0):
                            errors.append(f"{name}: strict quality gate failed: {key}")
                if (
                    args.require_package_provenance
                    and name == "release"
                    and data.get("quality", {}).get("package_provenance", {}).get(
                        "packages_without_provenance", 0
                    )
                ):
                    errors.append("release: quality gate failed: package provenance")
                if (
                    args.require_publishable_provenance
                    and name == "release"
                    and data.get("quality", {}).get("package_provenance", {}).get(
                        "packages_not_publishable", 0
                    )
                ):
                    errors.append("release: quality gate failed: publishable provenance")
                if (
                    args.require_paper_provenance
                    and name == "release"
                    and data.get("quality", {}).get("paper_provenance", {}).get(
                        "papers_not_publishable", 0
                    )
                ):
                    count = data["quality"]["paper_provenance"]["papers_not_publishable"]
                    errors.append(
                        f"release: quality gate failed: paper provenance ({count} papers)"
                    )

        schema_name = "offline" if args.offline_only else "release"
        schema_database = report["databases"].get(schema_name, {})
        if (
            not schema_database.get("missing")
            and schema_database.get("schema_version", 0) < args.min_schema_version
        ):
            errors.append(
                f"{schema_name}: schema_version below minimum {args.min_schema_version}"
            )

        release = report["databases"].get("release", {})

        offline = report["databases"].get("offline", {})
        if args.require_matching_content and release and offline and not release.get("missing") and not offline.get("missing"):
            if release.get("sha256") != offline.get("sha256"):
                errors.append("release and offline databases have different SHA-256 hashes")

    if args.check_templates:
        # Keep this check importable from a clean checkout without importing the app.
        sys.path.insert(0, str(ROOT))
        from backend.app.services.exam_templates import supported_exam_types

        if not {"gaokao", "tem4", "tem8"}.issubset(supported_exam_types()):
            errors.append("required exam templates are not registered")

    for raw_path in args.artifact:
        path = raw_path if raw_path.is_absolute() else ROOT / raw_path
        artifact = inspect_artifact(path)
        report["artifacts"][str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)] = artifact
        if artifact.get("missing"):
            errors.append(f"missing release artifact: {path}")

    if args.write_report:
        output = args.write_report if args.write_report.is_absolute() else ROOT / args.write_report
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if errors:
        for error in errors:
            print(f"release_check: ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
