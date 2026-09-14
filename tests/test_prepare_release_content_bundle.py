from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.test_create_release_content_bundle import _fixture
from tools.create_release_content_bundle import create_bundle
from tools.prepare_release_content_bundle import prepare_bundle


def test_prepare_bundle_verifies_and_installs_both_databases(tmp_path: Path) -> None:
    release = tmp_path / "source-release.db"
    offline = tmp_path / "source-offline.db"
    bundle = tmp_path / "content-bundle.zip"
    release_target = tmp_path / "installed" / "release.db"
    offline_target = tmp_path / "installed" / "offline.db"
    _fixture(release)
    _fixture(offline)
    create_bundle(release, offline, bundle)

    result = prepare_bundle(bundle, release_target, offline_target)

    assert result["content_version"]
    assert result["release"]["counts"]["papers"] == 1
    with sqlite3.connect(release_target) as connection:
        assert connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0] == 1
    with sqlite3.connect(offline_target) as connection:
        assert connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 1


def test_prepare_bundle_refuses_overwrite_without_force(tmp_path: Path) -> None:
    release = tmp_path / "source-release.db"
    offline = tmp_path / "source-offline.db"
    bundle = tmp_path / "content-bundle.zip"
    release_target = tmp_path / "installed" / "release.db"
    offline_target = tmp_path / "installed" / "offline.db"
    _fixture(release)
    _fixture(offline)
    create_bundle(release, offline, bundle)
    prepare_bundle(bundle, release_target, offline_target)

    with pytest.raises(FileExistsError):
        prepare_bundle(bundle, release_target, offline_target)
