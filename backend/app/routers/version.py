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
import os
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db

router = APIRouter()

CONTENT_VERSION = "2026-08-06.1"  # 内容版本号（我每次更新题库时递增）


def _db_sha256(connection: sqlite3.Connection) -> str:
    """计算题库内容哈希（questions+options+vocabulary 三表）——客户端比对用"""
    h = hashlib.sha256()
    for table in ("questions", "options", "vocabulary_entries"):
        try:
            rows = connection.execute(
                f"SELECT COUNT(*), COALESCE(SUM(LENGTH(rowid)), 0) FROM {table}"
            ).fetchone()
            h.update(f"{table}:{rows[0]}:{rows[1]}".encode())
        except Exception:
            h.update(f"{table}:0:0".encode())
    return h.hexdigest()[:16]


@router.get("/content/version")
def content_version(
    connection: sqlite3.Connection = Depends(get_db),
) -> dict:
    """内容版本接口——客户端启动时调用，对比本地题库是否最新"""
    return {
        "content_version": CONTENT_VERSION,
        "content_hash": _db_sha256(connection),
        "questions": connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
        "vocabulary": connection.execute(
            "SELECT COUNT(*) FROM vocabulary_entries"
        ).fetchone()[0],
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@router.get("/app/version")
def app_version() -> dict:
    """App 版本接口——桌面/安卓客户端检查更新

    返回最新版本号 + 下载地址（由环境变量配置，未配置返回当前为最新）
    """
    latest = os.environ.get("EPM_APP_VERSION", "1.0.0")
    download = os.environ.get("EPM_APP_DOWNLOAD_URL", "")
    return {
        "latest_version": latest,
        "download_url": download,
        "changelog": os.environ.get("EPM_APP_CHANGELOG", ""),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
