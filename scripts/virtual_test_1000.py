"""千轮虚拟压力测试 (v2.32b) — 符合后端限流 (120次/60s ≈ 2次/秒)
每轮 3 请求(创建/详情/答1题+提交) × 2.5s 节流 → ~45 分钟后台跑
429 时等待 65s 重置窗口
"""
import json, sqlite3, sys, time, urllib.request

API = "http://127.0.0.1:8765"
BASE = r"D:\english-multiple-choice-practice-machine"
CLOZE_TOTAL = 1000
ok_count = 0
fail_count = 0
errors: dict[str, int] = {}


def req(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    while True:
        try:
            with urllib.request.urlopen(r, timeout=45) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"    ⏳ 429 限流, 等待 65s 重置窗口...", flush=True)
                time.sleep(65)
                continue
            raise


def set_profile(pid):
    conn = sqlite3.connect(BASE + r"\backend\data\question_bank.db")
    conn.execute("INSERT INTO app_settings(key,value) VALUES ('active_question_bank_profile_id',?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(pid),))
    conn.commit(); conn.close()


PROFILES = [1, 2, 3, 4, 5]
TYPES = ["cloze", "reading", "part_b", "listening"]

print(f"🚀 千轮虚拟压力测试开始 — {CLOZE_TOTAL} 轮 × 五级别×四题型 (高限流模式 0.2s/轮)", flush=True)
t0 = time.time()
for i in range(CLOZE_TOTAL):
    pid = PROFILES[i % len(PROFILES)]
    ut = TYPES[i % len(TYPES)]
    set_profile(pid)
    try:
        s = req("POST", "/api/practice/sessions",
                {"mode": "random", "unit_type": ut, "count": 1, "shuffle_options": True})
        sid = s["id"]
        detail = req("GET", f"/api/practice/sessions/{sid}")
        answered = False
        for unit in detail.get("units", []):
            # v2.32b: 必须答全部题 (submit_session 有防漏答完整性检查, 部分作答→409)
            for q in unit.get("questions", []):
                opts = q.get("options", [])
                if opts:
                    req("PUT", f"/api/practice/sessions/{sid}/answers/{q['id']}",
                        {"answer": opts[0].get("label") or opts[0].get("key") or opts[0].get("stable_key")})
                    answered = True
            # 无选项题(如听力音频题)跳过, 提交时若仍缺会 409 → 统计为失败
        req("POST", f"/api/practice/sessions/{sid}/submit", {})
        ok_count += 1
    except urllib.error.HTTPError as e:
        fail_count += 1
        errors[f"HTTP{e.code}"] = errors.get(f"HTTP{e.code}", 0) + 1
    except Exception as e:
        fail_count += 1
        key = str(e)[:60]
        errors[key] = errors.get(key, 0) + 1
    if (i + 1) % 50 == 0:
        el = time.time() - t0
        print(f"  {i+1}/1000 轮 | 成功 {ok_count} 失败 {fail_count} | {el:.0f}s", flush=True)
    time.sleep(0.2)

elapsed = time.time() - t0
print(f"\n=== 千轮结果: 成功 {ok_count} / 失败 {fail_count} ({elapsed:.0f}s ===", flush=True)
if errors:
    print("错误分布:", errors, flush=True)

# 新功能验证: 短文填词
try:
    r = req("GET", "/api/vocab/cloze?count=5")
    total = r.get("total", 0)
    assert total >= 3, f"短文填词生成不足: {total}"
    print(f"✅ 短文填词 API: {total} 道题生成", flush=True)
    ok_count += 1
except Exception as e:
    print(f"❌ 短文填词 API 失败: {e}", flush=True)
    fail_count += 1

# 报告页
try:
    r = req("GET", "/api/report")
    assert r.get("by_profile"), "报告缺 by_profile"
    print(f"✅ 报告 API: {len(r['by_profile'])} 级别汇总", flush=True)
    ok_count += 1
except Exception as e:
    print(f"❌ 报告 API 失败: {e}", flush=True)
    fail_count += 1

print(f"\nAD-HOC V2.32 THOUSAND-ROUND (real) — 成功 {ok_count} 失败 {fail_count}", flush=True)
sys.exit(0 if fail_count == 0 else 1)
