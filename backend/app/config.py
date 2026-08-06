from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
# v9.20.1: EPM_DATA_DIR 允许打包版指定可写数据目录（Electron 传 resources/backend/data）
DATA_DIR = Path(os.environ.get("EPM_DATA_DIR") or (ROOT_DIR / "backend" / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
QUESTION_BANK_DIR = DATA_DIR / "question_banks"
DATABASE_PATH = DATA_DIR / "question_bank.db"
FRONTEND_DIST = Path(os.environ.get("EPM_FRONTEND_DIST") or (ROOT_DIR / "frontend" / "dist"))


def ensure_directories() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    QUESTION_BANK_DIR.mkdir(parents=True, exist_ok=True)
