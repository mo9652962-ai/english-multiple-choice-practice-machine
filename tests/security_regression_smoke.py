# -*- coding: utf-8 -*-
"""v9.30 安全修复回归冒烟——验证多用户隔离 + 登录限流 + 管理员初始化"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# 必须在 import 后端前设置（模块级读取）
os.environ["EPM_AUTH"] = "1"
os.environ["EPM_ADMIN_USERNAME"] = "rootadmin"
os.environ["EPM_API_KEY"] = ""  # 不启用 API key，专注用户隔离

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # 项目根
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))  # backend

from fastapi.testclient import TestClient  # noqa: E402

# 临时数据库
_tmp = tempfile.mkdtemp()
from backend.app import database as db_module

db_module.DATABASE_PATH = Path(_tmp) / "test_security.db"

from backend.app.main import app  # noqa: E402
from backend.app.database import initialize_database  # noqa: E402

initialize_database()
client = TestClient(app)

passed = 0
failed = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} {detail}")


# ── 1. 管理员初始化（MEDIUM-3）──
print("\n[1] 管理员初始化")
r = client.post("/api/auth/register", json={"username": "rootadmin", "password": "admin123456"})
check("EPM_ADMIN_USERNAME 指定用户名注册=管理员", r.status_code == 200 and r.json()["user"]["is_admin"] is True, f"got {r.status_code} {r.text[:100]}")

r = client.post("/api/auth/register", json={"username": "userB", "password": "userb123456"})
check("普通用户注册≠管理员", r.status_code == 200 and r.json()["user"]["is_admin"] is False, f"got {r.status_code} {r.text[:100]}")
token_admin = client.post("/api/auth/login", json={"username": "rootadmin", "password": "admin123456"}).json()["token"]
token_b = client.post("/api/auth/login", json={"username": "userB", "password": "userb123456"}).json()["token"]
h_admin = {"Authorization": f"Bearer {token_admin}"}
h_b = {"Authorization": f"Bearer {token_b}"}

# ── 2. HIGH-1: AI 对话隔离 ──
print("\n[2] AI 对话跨用户隔离")
r = client.post("/api/ai/conversations", headers=h_admin)
conversation_id = r.json()["id"]
check("管理员创建对话", r.status_code == 200, f"got {r.status_code}")

r = client.get(f"/api/ai/conversations/{conversation_id}", headers=h_b)
check("B 读 A 的对话被拒(404)", r.status_code == 404, f"got {r.status_code}")

r = client.delete(f"/api/ai/conversations/{conversation_id}", headers=h_b)
check("B 删 A 的对话被拒(404)", r.status_code == 404, f"got {r.status_code}")

r = client.get(f"/api/ai/conversations/{conversation_id}", headers=h_admin)
check("A 读自己的对话正常", r.status_code == 200, f"got {r.status_code}")

r = client.get("/api/ai/conversations", headers=h_b)
check("B 列表看不到 A 的对话", all(c["id"] != conversation_id for c in r.json()), f"got {r.json()}")

# ── 3. HIGH-2: 作文隔离 ──
print("\n[3] 作文批改隔离")
r = client.get("/api/essays", headers=h_admin)
admin_essay_count = r.json()["count"]
r = client.get("/api/essays", headers=h_b)
check("B 列表看不到 A 的作文", r.json()["count"] == admin_essay_count - 0 and admin_essay_count == 0, f"A={admin_essay_count} B={r.json()['count']}")

# ── 4. MEDIUM-4: 登录限流 ──
print("\n[4] 登录失败限流")
statuses = []
for _ in range(6):
    r = client.post("/api/auth/login", json={"username": "userB", "password": "wrongpass"})
    statuses.append(r.status_code)
check("第5次失败后锁定(429)", 429 in statuses, f"statuses={statuses}")

# ── 5. 未登录访问（EPM_AUTH=1 时 maybe_require_user 强制 401）──
print("\n[5] 未登录访问业务接口")
r = client.get("/api/ai/conversations")
check("未登录访问 AI 对话被拒(401)", r.status_code == 401, f"got {r.status_code}")
r = client.get("/api/wrong")
check("未登录访问错题被拒(401)", r.status_code == 401, f"got {r.status_code}")

print(f"\n{'='*40}\n结果: {passed} 通过 / {failed} 失败")
client.close()
sys.exit(1 if failed else 0)
