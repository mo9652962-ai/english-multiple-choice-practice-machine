from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.config import DATA_DIR, UPLOAD_DIR

from .config import FRONTEND_DIST
from .database import connect, initialize_database
from .routers import (
    ai,
    auth,  # v9.24: 多用户认证
    dashboard,
    exam,
    feedback,
    imports,
    papers,
    practice,
    annotations,
    question_bank_profiles,
    question_banks,
    review,  # v9.28: 错题 SRS 复习
    version,
    vocabulary,
    vocab_plans,
    vocab_context,
    report,
    achievements,
    ai_recommend,
    vocab_cloze,
    vocab_quiz,
    leaderboard,
    calendar,
    diagnostic,
    explanations,
    library,
    wrong,
    essays,  # v9.26: P1 作文批改
    speaking,  # v9.26: P2 口语陪练
)
from .services.ai_client import ensure_ai_model_catalog
from .services.bundled_banks import install_bundled_question_banks
from .services.listening import repair_published_listening_assets
from .services.vocabulary import clean_machine_meanings, translate_queued_vocabulary
from .services.trash import purge_expired


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    _backup_database_on_startup()
    install_bundled_question_banks()
    with connect() as connection:
        ensure_ai_model_catalog(connection)
        clean_machine_meanings(connection)
        purge_expired(connection)
        repair_published_listening_assets(connection)
    # v9.23: 清理 24h 前的临时导出文件（exports/ 目录）
    try:
        from .config import DATA_DIR
        import time as _t
        for old in (DATA_DIR / "exports").glob("*"):
            try:
                if _t.time() - old.stat().st_mtime > 24 * 3600:
                    old.unlink()
            except OSError:
                pass
    except Exception:
        pass
    threading.Thread(
        target=translate_queued_vocabulary,
        name="vocabulary-translation-recovery",
        daemon=True,
    ).start()
    yield


def _backup_database_on_startup() -> None:
    """启动时自动备份数据库（v9.21: 用 SQLite 在线备份 API 替代 copy2——防 WAL 损坏）"""
    try:
        from .config import DATA_DIR, DATABASE_PATH
        if not DATABASE_PATH.exists():
            return
        backup_dir = DATA_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        import time as _t
        stamp = _t.strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"question_bank_{stamp}.db"
        with connect() as src, sqlite3.connect(dest) as dst:
            src.backup(dst)
        # 保留最近 5 份
        backups = sorted(backup_dir.glob("question_bank_*.db"))
        for old in backups[:-5]:
            try:
                old.unlink()
            except OSError:
                pass
    except Exception:
        # 备份失败不应阻塞启动
        pass


app = FastAPI(
    title="英语刷题机",
    version="0.1.0",
    contact={"name": "sora（mo9652962-ai）"},
    lifespan=lifespan,
)
# v9.20: 安全协议——API Key 鉴权 + 限流（云端部署/多人使用时启用 EPM_API_KEY）
from .security_middleware import SecurityMiddleware

app.add_middleware(SecurityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api")
app.include_router(auth.router, prefix="/api")  # v9.24: 多用户认证（register/login/me）
app.include_router(papers.router, prefix="/api")
app.include_router(practice.router, prefix="/api")
app.include_router(annotations.router, prefix="/api")
app.include_router(wrong.router, prefix="/api")
app.include_router(essays.router, prefix="/api")  # v9.26: P1 作文批改
app.include_router(speaking.router, prefix="/api")  # v9.26: P2 口语陪练
app.include_router(imports.router, prefix="/api")
app.include_router(question_banks.router, prefix="/api")
app.include_router(question_bank_profiles.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(vocab_plans.router, prefix="/api")
app.include_router(vocab_context.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(achievements.router, prefix="/api")
app.include_router(ai_recommend.router, prefix="/api")
app.include_router(vocab_cloze.router, prefix="/api")
app.include_router(vocab_quiz.router, prefix="/api")
app.include_router(review.router, prefix="/api")  # v9.28: 错题 SRS
app.include_router(leaderboard.router, prefix="/api")
app.include_router(calendar.router, prefix="/api")
app.include_router(explanations.router, prefix="/api")
app.include_router(library.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(diagnostic.router, prefix="/api")
app.include_router(vocabulary.router, prefix="/api")
app.include_router(exam.router, prefix="/api")
app.include_router(version.router, prefix="/api")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# v3.3: 我的墨题——版本号 + 开发时间 + 检查更新（GitHub releases 代理）
APP_VERSION = "2.0.0-beta.15"
APP_RELEASE_DATE = "2026-08-10"
_UPDATE_REPO = "mo9652962-ai/epm-releases"


@app.get("/api/version")
def get_version() -> dict:
    latest = None
    assets: list = []
    try:
        import json as _json
        import urllib.request as _urllib

        req = _urllib.Request(
            f"https://api.github.com/repos/{_UPDATE_REPO}/releases/latest",
            headers={"User-Agent": "epm-update-check", "Accept": "application/vnd.github+json"},
        )
        with _urllib.request.urlopen(req, timeout=8) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            latest = data.get("tag_name")
            assets = [
                {
                    "name": a.get("name"),
                    "url": a.get("browser_download_url"),
                    "size": a.get("size"),
                }
                for a in data.get("assets", [])
                if a.get("name") and a.get("name").endswith((".exe", ".apk", ".zip"))
            ]
    except Exception:
        latest = None
    return {
        "version": APP_VERSION,
        "release_date": APP_RELEASE_DATE,
        "latest_version": latest,
        "update_url": f"https://github.com/{_UPDATE_REPO}/releases/latest",
        # v3.3: 镜像回退（ghproxy——国内可访问）
        "mirrors": [
            f"https://ghproxy.net/https://github.com/{_UPDATE_REPO}/releases/latest",
            f"https://gh-proxy.com/https://github.com/{_UPDATE_REPO}/releases/latest",
        ],
        "assets": assets,
    }


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    # 听力音频静态服务（导入的 MP3/M4A/WAV/OGG → /audio/<filename>）
    if UPLOAD_DIR.exists():
        app.mount("/audio", StaticFiles(directory=UPLOAD_DIR), name="audio")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str):
        # v9.21: 路径沙箱——防止 ../ 逃逸读取后端源码/数据库
        if full_path:
            resolved = (FRONTEND_DIST / full_path).resolve()
            dist_root = FRONTEND_DIST.resolve()
            if resolved.is_file() and resolved.is_relative_to(dist_root):
                return FileResponse(resolved)
        html = (FRONTEND_DIST / "index.html").read_text(encoding="utf-8")
        with connect() as connection:
            startup_data = dashboard.dashboard(connection)
        serialized = json.dumps(startup_data, ensure_ascii=False).replace("<", "\\u003c")
        html = html.replace(
            "</head>",
            f'<script>window.__LINJIAN_STARTUP__={serialized};</script></head>',
        )
        return HTMLResponse(
            html,
            headers={"Cache-Control": "no-store, max-age=0"},
        )
