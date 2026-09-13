# -*- coding: utf-8 -*-
"""AI 英语刷题机 — 在线版本与内容同步接口（v9.20, 多人使用）

核心设计（让"我更新 → 别人自动同步"成立）:
  1. 内容版本: 题库/单词数据内容哈希 + 版本号。
     客户端启动时对比本地与云端版本，有新版则拉取最新题库（在线模式）。
  2. App 版本: 桌面(Electron)/安卓(APK) 检查最新安装包版本 + 下载地址。
     微信小程序天然在线（微信平台发布即生效），无需此接口。

部署:
  - 本机/局域网: 不启用（内容即本地, 版本恒一致）
  - 云端: 题库在云端 DB, 客户端从云端 API 拉取
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .. import database as database_module
from ..database import get_db
from ..config import (
    APP_RELEASE_DATE,
    APP_VERSION,
    CONTENT_VERSION,
    OFFLINE_CONTENT_VERSION,
    ROOT_DIR,
)

router = APIRouter()

def _db_sha256(connection: sqlite3.Connection) -> str:
    """Return the exact release database hash, with a structural fallback for tests."""
    try:
        database_path = database_module.DATABASE_PATH
        if database_path.exists():
            return hashlib.sha256(database_path.read_bytes()).hexdigest()
    except OSError:
        pass
    # Test/in-memory databases have no file path. Keep a deterministic fallback
    # instead of claiming that an unavailable file hash is authoritative.
    h = hashlib.sha256()
    for table in ("questions", "options", "vocabulary_entries"):
        try:
            rows = connection.execute(
                f"SELECT COUNT(*), COALESCE(SUM(LENGTH(rowid)), 0) FROM {table}"
            ).fetchone()
            h.update(f"{table}:{rows[0]}:{rows[1]}".encode())
        except Exception:
            h.update(f"{table}:0:0".encode())
    return f"structural:{h.hexdigest()}"


def _schema_version(connection: sqlite3.Connection) -> int:
    try:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
        return int(row[0] if row else 0)
    except sqlite3.Error:
        return 0


def _content_policy() -> dict:
    path = Path(ROOT_DIR) / "content-manifest.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            "release": payload.get("release", {}),
            "offline_seed": payload.get("offline_seed", {}),
            "share_policy": payload.get("share_policy", {}),
            "quality_policy": payload.get("quality_policy", {}),
        }
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _database_counts(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("papers", "units", "questions", "options", "vocabulary_entries"):
        try:
            counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.Error:
            counts[table] = 0
    return counts


@router.get("/content/version")
def content_version(
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """内容版本接口——客户端启动时调用，对比本地题库是否最新"""
    return {
        "version": APP_VERSION,
        "release_date": APP_RELEASE_DATE,
        "content_version": CONTENT_VERSION,
        "offline_seed_version": OFFLINE_CONTENT_VERSION,
        "schema_version": _schema_version(connection),
        "database_sha256": _db_sha256(connection),
        "counts": _database_counts(connection),
        "content_policy": _content_policy(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/app/version")
def app_version() -> dict:
    """App 版本接口——桌面/安卓客户端检查更新

    返回最新版本号 + 下载地址（由环境变量配置，未配置返回当前为最新）
    """
    latest = os.environ.get("EPM_APP_VERSION", APP_VERSION)
    download = os.environ.get("EPM_APP_DOWNLOAD_URL", "")
    return {
        "version": APP_VERSION,
        "latest_version": latest,
        "content_version": CONTENT_VERSION,
        "offline_seed_version": OFFLINE_CONTENT_VERSION,
        "release_date": APP_RELEASE_DATE,
        "download_url": download,
        "changelog": os.environ.get("EPM_APP_CHANGELOG", ""),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
