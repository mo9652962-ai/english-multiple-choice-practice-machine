# -*- coding: utf-8 -*-
"""AI 英语刷题机 — 安全协议中间件（v9.20, 多人使用场景）

威胁模型（应用部署给别人用时）:
  1. 未授权访问 API → 抓包直接调接口/爬题库
  2. 接口被刷 → 限流缺失导致资源耗尽
  3. 跨用户数据访问 → 学习记录无隔离
  4. 题库被批量抓取 → 无防爬措施

安全协议:
  - 传输层: 云端部署必须 HTTPS（反向代理层保证，本中间件不处理）
  - 鉴权层: X-API-Key header 校验（环境变量 EPM_API_KEY 设置时启用）
    本地/局域网模式（未设置 EPM_API_KEY）→ 放行，兼容现有使用
  - 限流层: 每 IP 滑动窗口限流（默认 120 次/分钟，环境变量可调）
  - 数据隔离: 多用户场景由业务层按 user_id 过滤（本中间件不做）

用法:
  EPM_API_KEY=xxx python run_app.py      # 启用 API Key 校验（云端）
  EPM_RATE_LIMIT=300 python run_app.py   # 调限流阈值（默认 120/分钟）
"""
from __future__ import annotations

import os
import time
import hmac

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# 安全配置（环境变量）
API_KEY = os.environ.get("EPM_API_KEY", "").strip()
RATE_LIMIT = int(os.environ.get("EPM_RATE_LIMIT", "120"))
RATE_WINDOW = 60  # 秒

# 放行路径（无需鉴权/不限流——健康检查、静态资源）
PUBLIC_PATHS = (
    "/api/health",
    "/api/auth/login",     # v9.24: 多用户登录/注册必须在 API Key 白名单外
    "/api/auth/register",
    "/assets/",
    "/manifest.json",
    "/sw.js",
    "/icons/",
)

_requests: dict[str, list[float]] = {}  # ip → 时间戳列表


def _client_ip(request: Request) -> str:
    """取客户端 IP（v9.21: 仅当配置了可信代理时信任 X-Forwarded-For，否则回退直连 IP）
    防伪造 XFF 绕过限流：未显式配置 EPM_TRUST_PROXY 时不读 XFF"""
    if os.environ.get("EPM_TRUST_PROXY", "").strip():
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _is_public(path: str) -> bool:
    return any(path.startswith(p) for p in PUBLIC_PATHS)


class SecurityMiddleware(BaseHTTPMiddleware):
    """API Key 校验 + 限流（只对 /api 路径生效）"""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api") or _is_public(path):
            return await call_next(request)

        ip = _client_ip(request)

        # 1. 鉴权：EPM_API_KEY 启用时必须带 X-API-Key（v9.21: 常量时间比对）
        if API_KEY:
            key = request.headers.get("x-api-key", "")
            if not hmac.compare_digest(key, API_KEY):
                return JSONResponse(
                    {"detail": "未授权访问（无效 API Key）"},
                    status_code=401,
                )

        # 2. 限流：滑动窗口
        now = time.time()
        with _requests_lock:
            window = [t for t in _requests.get(ip, []) if now - t < RATE_WINDOW]
            if len(window) >= RATE_LIMIT:
                return JSONResponse(
                    {"detail": f"请求过于频繁（限 {RATE_LIMIT} 次/{RATE_WINDOW}秒）"},
                    status_code=429,
                )
            window.append(now)
            _requests[ip] = window

        return await call_next(request)


# 限流状态锁（模块级，简单线程安全）
import threading
_requests_lock = threading.Lock()
