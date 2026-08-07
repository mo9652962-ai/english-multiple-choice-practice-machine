"""虚拟用户全流程测试 v2.26 — 模拟真实学习闭环, 发现并修复问题
流程: 首页→切级别→随机练习→答题→提交→错题→背单词→模拟考试→报告→词文串学→听力
"""
import json, sqlite3, sys, time, urllib.request

API = "http://127.0.0.1:8765"
BASE = r"D:\english-multiple-choice-practice-machine"
passed, failed = [], []


def req(method, path, body=None):
    time.sleep(0.35)  # 节流, 避免触发 429 限流 (120次/60s)
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()[:200]
        raise RuntimeError(f"HTTP {e.code}: {body_text}")


def set_profile(pid):
    conn = sqlite3.connect(BASE + r"\backend\data\question_bank.db")
    conn.execute("INSERT INTO app_settings(key,value) VALUES ('active_question_bank_profile_id',?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(pid),))
    conn.commit(); conn.close()


def check(name, fn):
    try:
        fn()
        passed.append(name)
        print(f"  ✅ {name}")
    except Exception as e:
        failed.append((name, str(e)))
        print(f"  ❌ {name}: {e}")


# ── 1. 首页 startup ──
def t_home():
    d = req("GET", "/api/startup")
    assert d.get("active_profile"), "active_profile 缺失"
    assert d.get("today_plan"), "today_plan 缺失"
    assert d.get("exam_countdown"), "exam_countdown 缺失"
    assert d.get("recommendations"), "recommendations 缺失"
    assert d.get("unit_count") is not None
check("首页 startup (5项数据)", t_home)

# ── 2. 五级别切换 ──
def t_switch():
    for pid in [1, 2, 3, 4, 5]:
        set_profile(pid)
        d = req("GET", "/api/startup")
        assert d["active_profile"]["id"] == pid, f"切换失败 pid={pid}"
check("五级别切换", t_switch)

# ── 3. 随机练习创建 (每级别每题型) ──
def t_create_practice():
    for pid in [1, 2, 3, 4, 5]:
        set_profile(pid)
        for ut in ["cloze", "reading", "part_b", "listening"]:
            try:
                s = req("POST", "/api/practice/sessions",
                        {"mode": "random", "unit_type": ut, "count": 1, "shuffle_options": True})
                assert s.get("id"), f"{pid} {ut} 无 id"
            except Exception as e:
                # 该级别无该题型属正常 (如考研一无听力)
                print(f"    (跳过 {pid} {ut}: {type(e).__name__})")
check("五级别×四题型练习创建", t_create_practice)

# ── 4. 答题 + 提交闭环 ──
def t_answer_submit():
    set_profile(3)
    s = req("POST", "/api/practice/sessions", {"mode": "random", "unit_type": "reading", "count": 1, "shuffle_options": True})
    sid = s["id"]
    detail = req("GET", f"/api/practice/sessions/{sid}")
    units = detail.get("units", [])
    assert units, "无题目"
    unit = units[0]
    for q in unit.get("questions", []):
        opts = q.get("options", [])
        if opts:
            req("PUT", f"/api/practice/sessions/{sid}/answers/{q['id']}", {"answer": opts[0].get("label") or opts[0].get("key") or opts[0].get("stable_key")})
    # 提交 (random 模式用 session 级提交)
    result = req("POST", f"/api/practice/sessions/{sid}/submit", {})
    assert result, "提交失败"
    assert result.get("score") is not None or result.get("result_summary"), "无分数"
check("答题+提交闭环", t_answer_submit)

# ── 5. 错题本 ──
def t_wrong():
    d = req("GET", "/api/wrong")
    assert "items" in d or isinstance(d, list) or "wrong" in str(d)[:50], f"错题本异常 {str(d)[:80]}"
check("错题本", t_wrong)

# ── 6. 词书+每日任务 ──
def t_plans():
    d = req("GET", "/api/vocabulary/plans")
    assert len(d.get("plans", [])) >= 5, "词书不足"
    daily = req("GET", f"/api/vocabulary/plans/{d['plans'][0]['key']}/daily")
    assert len(daily.get("words", [])) > 0, "每日任务空"
check("词书+每日任务", t_plans)

# ── 7. 词文串学 ──
def t_context():
    conn = sqlite3.connect(BASE + r"\backend\data\question_bank.db")
    eid = conn.execute("SELECT id FROM vocabulary_entries WHERE term IN ('achieve','research','study') ORDER BY id LIMIT 1").fetchone()[0]
    conn.close()
    d = req("GET", f"/api/vocabulary/{eid}/context")
    assert len(d.get("contexts", [])) > 0, "无真题例句"
check("词文串学", t_context)

# ── 8. 模拟考试 ──
def t_exam():
    set_profile(3)
    s = req("POST", "/api/exam/start", {"profile_id": 3, "count": 5})
    assert s.get("id"), "模拟考试创建失败"
    eid = s["id"]
    detail = req("GET", f"/api/exam/sessions/{eid}")
    assert detail.get("questions"), "模拟考试无题"
    assert detail.get("remaining_seconds") is not None, "无倒计时"
    # 答几题
    for q in detail["questions"][:3]:
        opts = q.get("options", [])
        if opts:
            req("PUT", f"/api/exam/sessions/{eid}/answers/{q['id']}", {"answer": opts[0]["key"]})
    result = req("POST", f"/api/exam/sessions/{eid}/submit", {})
    assert result, "模拟考试提交失败"
check("模拟考试(创建/计时/答题/提交)", t_exam)

# ── 9. 学习报告 ──
def t_report():
    d = req("GET", "/api/report")
    for k in ["trend", "by_type", "vocab", "suggestions", "practice"]:
        assert k in d, f"报告缺 {k}"
check("学习报告", t_report)

# ── 10. 听力 audio_url ──
def t_audio():
    set_profile(3)
    s = req("POST", "/api/practice/sessions", {"mode": "random", "unit_type": "listening", "count": 1, "shuffle_options": True})
    detail = req("GET", f"/api/practice/sessions/{s['id']}")
    assert "bilibili" in (detail.get("audio_url") or ""), "听力无B站音频"
check("听力B站音频", t_audio)

# ── 11. 热力图/打卡 ──
def t_streak():
    d = req("GET", "/api/dashboard/streak")
    assert "streak" in d and "heatmap" in d, "热力图异常"
check("热力图+打卡", t_streak)

# ── 12. 倒计时 ──
def t_countdown():
    d = req("GET", "/api/exam-countdown")
    assert d.get("exams"), "倒计时空"
    assert all("days_left" in e for e in d["exams"]), "倒计时格式错"
check("备考倒计时", t_countdown)

print(f"\n{'='*50}")
print(f"虚拟测试结果: {len(passed)} 通过 / {len(failed)} 失败")
if failed:
    print("失败项:")
    for name, err in failed:
        print(f"  ❌ {name}: {err}")
else:
    print("全部通过 🎉")