from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

# v9.20.1: 打包路径自适应——Electron extraResources 把 backend 放在
# resources/backend，而 run_app.py 在 resources/app/。把 resources 根加入
# sys.path，否则 `uvicorn.run("backend.app.main:app")` import 失败 → 后端
# 起不来 → 桌面端白屏（复现于 2026-08-06 v1.0.1）
_HERE = os.path.dirname(os.path.abspath(__file__))
_RESOURCES = os.path.dirname(_HERE)
if os.path.isdir(os.path.join(_RESOURCES, "backend")):
    sys.path.insert(0, _RESOURCES)

URL = "http://127.0.0.1:8765"


def get_lan_ip() -> str:
    """获取局域网 IP，供手机端访问（优先私有网段，跳过 VPN 虚拟网卡）"""
    try:
        # 先枚举所有网卡，挑 192.168/10./172.16-31 私有网段
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith(("192.168.", "10.", "172.16.")) or ip.startswith("172.") and ip.split(".")[1].isdigit() and 16 <= int(ip.split(".")[1]) <= 31:
                return ip
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def open_when_ready(lan: bool = False) -> None:
    host = get_lan_ip() if lan else "127.0.0.1"
    target = f"http://{host}:8765"
    for _ in range(80):
        try:
            urllib.request.urlopen(f"{URL}/api/health", timeout=1)
            webbrowser.open(target)
            return
        except Exception:
            time.sleep(0.25)


if __name__ == "__main__":
    lan = "--lan" in sys.argv
    bind_host = "0.0.0.0" if lan else "127.0.0.1"
    print(f"[刷题机] {'局域网模式 (手机可访问 http://' + get_lan_ip() + ':8765)' if lan else '本机模式 (http://127.0.0.1:8765)'}")
    threading.Thread(target=open_when_ready, args=(lan,), daemon=True).start()
    uvicorn.run("backend.app.main:app", host=bind_host, port=8765)
