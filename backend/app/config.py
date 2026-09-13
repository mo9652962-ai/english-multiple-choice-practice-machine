from __future__ import annotations

import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    # PyInstaller 打包：资源(含 examples/bundled-banks)解压到 sys._MEIPASS
    ROOT_DIR = Path(sys._MEIPASS)
else:
    ROOT_DIR = Path(__file__).resolve().parents[2]
# v9.20.1: EPM_DATA_DIR 允许打包版指定可写数据目录（Electron 传 resources/backend/data）
DATA_DIR = Path(os.environ.get("EPM_DATA_DIR") or (ROOT_DIR / "backend" / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
QUESTION_BANK_DIR = DATA_DIR / "question_banks"
DATABASE_PATH = DATA_DIR / "question_bank.db"
FRONTEND_DIST = Path(os.environ.get("EPM_FRONTEND_DIST") or (ROOT_DIR / "frontend" / "dist"))


def _read_project_metadata(name: str, fallback: str) -> str:
    """Read release metadata bundled with source and PyInstaller builds."""
    path = ROOT_DIR / name
    try:
        value = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        value = fallback
    return value or fallback


APP_VERSION = _read_project_metadata("VERSION", "2.1.3")
APP_RELEASE_DATE = _read_project_metadata("RELEASE_DATE", "2026-09-13")
CONTENT_VERSION = _read_project_metadata("CONTENT_VERSION", "content-2026-09-13-r1")
OFFLINE_CONTENT_VERSION = _read_project_metadata(
    "OFFLINE_CONTENT_VERSION", "offline-2026-09-13-r1"
)


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    QUESTION_BANK_DIR.mkdir(parents=True, exist_ok=True)
