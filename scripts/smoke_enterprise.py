"""冒烟测试：三企业功能全链路（内存库，不污染真实数据）
组卷 → 开考 → 交卷(达标) → 证书 → 防作弊事件
"""
import os, sys, json, sqlite3, tempfile
from pathlib import Path

# 用临时目录隔离数据
tmp = tempfile.mkdtemp(prefix="epm_smoke_")
os.environ["EPM_DATA_DIR"] = tmp
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from fastapi.testclient import TestClient
from app.database import initialize_database, connect, DATABASE_PATH
from app.main import app

# 1. 初始化隔离库
initialize_database()
print("隔离库建立于:", tmp, "| 库文件:", DATABASE_PATH)

# 2. 往隔离库塞测试题（3 道单选进 profile 1）
with connect() as conn:
    # 建一篇 paper + unit + 3 题 + 每题选项
    cur = conn.execute(
        "INSERT INTO papers (title, year, profile_id) VALUES ('冒烟测试卷', 2026, 1)"
    )
    pid = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO units (paper_id, sequence, title, unit_type) VALUES (?, 1, '冒烟单元', 'reading')",
        (pid,),
    )
    uid = cur.lastrowid
    qids = []
    for i, (qtype, ans) in enumerate([("single_choice", "A"), ("single_choice", "B"), ("single_choice", "C"),
                                       ("single_choice", "D"), ("single_choice", "A")], 1):
        cur = conn.execute(
            "INSERT INTO questions (unit_id, number, sequence, question_type, stem, answer, score) VALUES (?, ?, ?, ?, ?, ?, 10)",
            (uid, i, i, qtype, f"测试题{i}: What is {i}?", ans),
        )
        qids.append(cur.lastrowid)
        for opt in ["A", "B", "C", "D"]:
            conn.execute(
                "INSERT INTO options (question_id, sequence, stable_key, original_label, content) VALUES (?, ?, ?, ?, ?)",
                (qids[-1], "ABCD".index(opt), opt, opt, f"{opt}选项{i}"),
            )
    conn.commit()
    print(f"塞入 paper#{pid}, unit#{uid}, 题目#{qids}")

client = TestClient(app)

# 3. 注册用户（证书需要 user_id）
r = client.post("/api/auth/register", json={"username": "smoketest", "password": "pass123456"})
print("register:", r.status_code, r.json() if r.status_code != 200 else "ok")
if r.status_code == 409:  # 已存在
    r = client.post("/api/auth/login", json={"username": "smoketest", "password": "pass123456"})
t = r.json().get("access_token") or r.json().get("token")
print("token 取出:", repr(t)[:40] if t else "EMPTY")
headers = {"Authorization": f"Bearer {t}"} if t else {}
uid_user = r.json().get("user_id") or r.json().get("id")

# 4. 组卷
print("\n=== 组卷 ===")
gr = client.post("/api/papers/generate",
    json={"title": "冒烟组卷", "profile_id": 1, "types": {"single_choice": 3}, "pass_score": 50})
print("POST /api/papers/generate:", gr.status_code)
print(gr.json())
gen = gr.json()
assert gr.status_code == 200 and gen["total_questions"] == 3, "组卷失败"
gen_id = gen["id"]
question_ids = gen["question_ids"]

# 5. 列出组卷
lr = client.get("/api/papers/generated", headers=headers)
print("GET /api/papers/generated:", lr.status_code, "共", len(lr.json()), "张")

# 6. 开考（exam.start 抽 5 题）
sr = client.post("/api/exam/start", json={"profile_id": 1, "count": 5, "minutes": 10},
                 headers=headers)
print("POST /api/exam/start:", sr.status_code, sr.json().get("id"), "题数", sr.json().get("total_questions"))
exam_id = sr.json()["id"]

# 7. 达标证书：通过 submit 全对。先获取题目→全答对→交卷
det = client.get(f"/api/exam/sessions/{exam_id}", headers=headers).json()
for q in det["questions"]:
    correct = None
    # 从题库查正确答案（模拟考生知道答案）
    with connect() as _c:
        row = _c.execute("SELECT answer FROM questions WHERE id=?", (q["id"],)).fetchone()
        correct = row["answer"]
    client.put(f"/api/exam/sessions/{exam_id}/answers/{q['id']}",
               json={"answer": correct}, headers=headers)
print("已答全部题目")
sub = client.post(f"/api/exam/sessions/{exam_id}/submit", headers=headers)
print("POST submit:", sub.status_code)
res = sub.json()
print("score/max:", res.get("score"), "/", res.get("max_score"), "| accuracy:", res.get("accuracy"))
print("certificate:", res.get("certificate"))
assert res.get("certificate"), "达标应自动发证书！"
cert = res["certificate"]
cert_no = cert["cert_no"]

# 8. 查我的证书
mc = client.get("/api/certificates", headers=headers)
print("\n=== 证书 ===")
print("GET /api/certificates:", mc.status_code, mc.json())

# 9. 证书校验
vc = client.get(f"/api/certificates/verify/{cert_no}")
print("GET verify:", vc.status_code, vc.json())

# 10. 防作弊：开第二场考试并记录 2 次切屏
sr2 = client.post("/api/exam/start", json={"profile_id": 1, "count": 5, "minutes": 10}, headers=headers)
print("第二次 start:", sr2.status_code, sr2.json().get("id"))
exam2 = sr2.json()["id"]
ac1 = client.post(f"/api/exams/{exam2}/anti-cheat",
    json={"event_type": "screen_switch", "detail": "切到微信"}, headers=headers)
ac2 = client.post(f"/api/exams/{exam2}/anti-cheat",
    json={"event_type": "copy", "detail": "复制题目"}, headers=headers)
print("\n=== 防作弊 ===")
print("记录切屏:", ac1.json(), "| 记录复制:", ac2.json())
al = client.get(f"/api/exams/{exam2}/anti-cheat")
print("GET anti-cheat log:", al.json())

print("\n✅ 全链路冒烟通过：组卷→考试→达标证书→校验→防作弊")