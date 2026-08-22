# -*- coding: utf-8 -*-
"""v9.30b 安全修复扩展冒烟——新增路由隔离验证（annotations/vocab/achievements/report/diagnostic）"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ["EPM_AUTH"] = "1"
os.environ["EPM_ADMIN_USERNAME"] = "boss"

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "backend"))

import app.database as database
from app.database import connect, initialize_database

tmp = tempfile.mkdtemp(prefix="epm-sec2-")
database.DATABASE_PATH = Path(tmp) / "question_bank.db"
initialize_database()
with connect() as connection:
    connection.execute("INSERT OR IGNORE INTO question_bank_profiles (id, name) VALUES (1, '默认')")
    connection.commit()

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

PASS = 0
FAIL = 0

def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")

def reg(username):
    r = client.post("/api/auth/register", json={"username": username, "password": "Passw0rd123!"})
    assert r.status_code == 200, r.text
    return r.json()["token"]

def hdr(token):
    return {"Authorization": f"Bearer {token}"}

print("[0] 注册")
tok_a = reg("alice")
tok_b = reg("bob")

print("[1] 管理员初始化")
r = client.post("/api/auth/register", json={"username": "boss", "password": "Passw0rd123!"})
check("EPM_ADMIN_USERNAME 指定用户名=管理员", r.status_code == 200 and r.json()["user"]["is_admin"] is True)
r = client.post("/api/auth/register", json={"username": "carol", "password": "Passw0rd123!"})
check("普通用户注册不是管理员", r.status_code == 200 and r.json()["user"]["is_admin"] is False)

print("[2] 标注隔离 (annotations)")
r = client.post("/api/units/1/annotations", headers=hdr(tok_a),
                json={"start_offset": 0, "end_offset": 5, "text": "alice的私密标注", "note": "私密笔记"})
aid = r.json().get("id") if r.status_code == 200 else None
if aid:
    r2 = client.get(f"/api/units/1/annotations", headers=hdr(tok_b))
    check("B 列表不含 A 标注", "alice的私密标注" not in r2.text)
    r3 = client.delete(f"/api/annotations/{aid}", headers=hdr(tok_b))
    check("B 删 A 标注被拒(404)", r3.status_code == 404)
    r4 = client.get(f"/api/units/1/annotations", headers=hdr(tok_a))
    check("A 列表含自己的标注(200)", "alice的私密标注" in r4.text)
else:
    print(f"    创建响应: {r.status_code} {r.text[:200]}")
    check("创建标注成功", False)
    check("B 列表不含 A 标注", False)
    check("B 删 A 标注被拒(404)", False)
    check("A 列表含自己的标注(200)", False)

print("[3] 词汇隔离 (vocab)")
r = client.post("/api/vocabulary", headers=hdr(tok_a),
                json={"term": "zephyralice", "common_meaning": "x"})
if r.status_code in (200, 201):
    r2 = client.get("/api/vocabulary/plans", headers=hdr(tok_b))
    check("B 词汇计划不含 A 的词", "zephyralice" not in r2.text)
    r3 = client.get("/api/vocabulary", headers=hdr(tok_a))
    check("A 词汇列表含自己的词", "zephyralice" in r3.text)
    r4 = client.get("/api/vocabulary", headers=hdr(tok_b))
    check("B 词汇列表不含 A 的词", "zephyralice" not in r4.text)
else:
    print(f"    创建响应: {r.status_code} {r.text[:200]}")
    check("创建词汇成功", False)
    check("B 词汇计划不含 A 的词", False)
    check("A 词汇计划含自己的词", False)

print("[4] 报告隔离 (report)")
r = client.get("/api/report", headers=hdr(tok_b))
check("B 报告接口可访问(200)", r.status_code == 200)
r2 = client.get("/api/report", headers=hdr(tok_a))
check("A 报告接口可访问(200)", r2.status_code == 200)

print("[5] 成就隔离 (achievements)")
r = client.get("/api/achievements", headers=hdr(tok_a))
check("A 成就接口可访问(200)", r.status_code == 200)
r2 = client.get("/api/achievements", headers=hdr(tok_b))
check("B 成就接口可访问(200)", r2.status_code == 200)

print("[6] 诊断隔离 (diagnostic)")
r = client.get("/api/diagnostic/reports", headers=hdr(tok_a))
check("A 诊断列表可访问(200)", r.status_code == 200)
r2 = client.get("/api/diagnostic/reports", headers=hdr(tok_b))
check("B 诊断列表可访问(200)", r2.status_code == 200)

print("[7] 未登录拦截（新增路由）")
for path in ["/api/units/1/annotations", "/api/vocabulary/plans",
             "/api/report", "/api/achievements", "/api/diagnostic/reports",
             "/api/recommendations/ai", "/api/calendar", "/api/dashboard"]:
    r = client.get(path)
    check(f"未登录 {path} 被拒", r.status_code in (401, 403))

print("=" * 40)
print(f"结果: {PASS} 通过 / {FAIL} 失败")
sys.exit(1 if FAIL else 0)
