from __future__ import annotations

import json
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import FRONTEND_DIST
from .database import connect, initialize_database
from .routers import (
    ai,
    dashboard,
    exam,
    feedback,
    imports,
    papers,
    practice,
    question_bank_profiles,
    question_banks,
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
    library,
    wrong,
)
from .services.ai_client import ensure_ai_model_catalog
from .services.vocabulary import clean_machine_meanings, translate_queued_vocabulary
from .services.trash import purge_expired


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    _backup_database_on_startup()
    with connect() as connection:
        ensure_ai_model_catalog(connection)
        clean_machine_meanings(connection)
        purge_expired(connection)
    threading.Thread(
        target=translate_queued_vocabulary,
        name="vocabulary-translation-recovery",
        daemon=True,
    ).start()
    yield


def _backup_database_on_startup() -> None:
    """启动时自动备份数据库（Anki 式数据安全：保留最近 5 份）"""
    import shutil
    try:
        from .config import DATA_DIR, DATABASE_PATH
        if not DATABASE_PATH.exists():
            return
        backup_dir = DATA_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        import time as _t
        stamp = _t.strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"question_bank_{stamp}.db"
        shutil.copy2(DATABASE_PATH, dest)
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
    contact={"name": "往事随风k"},
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
app.include_router(papers.router, prefix="/api")
app.include_router(practice.router, prefix="/api")
app.include_router(wrong.router, prefix="/api")
app.include_router(imports.router, prefix="/api")
app.include_router(question_banks.router, prefix="/api")
app.include_router(question_bank_profiles.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(vocab_plans.router, prefix="")
app.include_router(vocab_context.router, prefix="")
app.include_router(report.router, prefix="")
app.include_router(achievements.router, prefix="")
app.include_router(ai_recommend.router, prefix="")
app.include_router(vocab_cloze.router, prefix="")
app.include_router(vocab_quiz.router, prefix="")
app.include_router(leaderboard.router, prefix="")
app.include_router(calendar.router, prefix="")
app.include_router(library.router, prefix="")
app.include_router(vocabulary.router, prefix="/api")
app.include_router(exam.router, prefix="/api")
app.include_router(version.router, prefix="/api")
app.include_router(feedback.router, prefix="")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str):
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
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
