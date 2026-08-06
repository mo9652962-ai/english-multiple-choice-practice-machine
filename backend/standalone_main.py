"""backend_app 独立启动入口（PyInstaller 打包，Electron 免 Python 依赖）

v9.20.1: 别人电脑没有 Python——把后端打成独立 exe。
Electron spawn 本 exe 并传 EPM_DATA_DIR/EPM_FRONTEND_DIST 环境变量。
"""
from __future__ import annotations

import os
import sys


def _bootstrap_paths() -> None:
    """确保 backend 包在 sys.path（PyInstaller onedir 模式下 _internal 已含，
    但以源码方式运行脚本时把 backend/ 加入）"""
    here = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.dirname(here)  # backend/
    if os.path.isdir(os.path.join(backend_root, "app")) and backend_root not in sys.path:
        sys.path.insert(0, backend_root)


def main() -> None:
    _bootstrap_paths()
    import uvicorn

    host = os.environ.get("EPM_HOST", "127.0.0.1")
    port = int(os.environ.get("EPM_PORT", "8765"))
    uvicorn.run("app.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
