"""功能 API 虚拟压力测试 (v2.35) — 短文填词/词汇自测/热力图/报告 循环验证
每类 100 次, 验证新功能在高频调用下稳定
"""
import json, sys, time, urllib.request

API = "http://127.0.0.1:8765"
ok = 0
fail = 0
errors: dict[str, int] = {}


def req(method, path, body=None, timeout=30, retries=3):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    r = urllib.request.Request(API + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(20)
                continue
            raise
        except Exception as e:
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise


t0 = time.time()
# 1. 短文填词 ×100
for i in range(100):
    try:
        d = req("GET", "/api/vocab/cloze?count=5")
        assert d.get("total", 0) >= 3 and d["items"][0]["answer"] in d["items"][0]["options"]
        ok += 1
    except Exception as e:
        fail += 1; errors.setdefault(f"cloze:{str(e)[:40]}", 0); errors[f"cloze:{str(e)[:40]}"] += 1
    if (i + 1) % 50 == 0: print(f"  填词 {i+1}/100", flush=True)
print(f"短文填词: {ok} 成功 {fail} 失败", flush=True)

# 2. 词汇量自测 ×100 (抽取+估算)
for i in range(100):
    try:
        q = req("GET", "/api/vocab/quiz?count=10")
        assert q.get("total", 0) >= 8
        est = req("POST", "/api/vocab/quiz/estimate",
                  {"results": [{"word": w["word"], "known": (i + idx) % 3} for idx, w in enumerate(q["items"])]})
        assert est.get("estimated", 0) > 0 and est.get("level")
        ok += 1
    except Exception as e:
        fail += 1; errors.setdefault(f"quiz:{str(e)[:40]}", 0); errors[f"quiz:{str(e)[:40]}"] += 1
    if (i + 1) % 50 == 0: print(f"  自测 {i+1}/100", flush=True)
print(f"词汇自测: {ok} 成功 {fail} 失败 (累计)", flush=True)

# 3. 热力图 ×100
for i in range(100):
    try:
        d = req("GET", "/api/report/heatmap")
        assert len(d.get("cells", [])) == 16 * 7
        ok += 1
    except Exception as e:
        fail += 1; errors.setdefault(f"heatmap:{str(e)[:40]}", 0); errors[f"heatmap:{str(e)[:40]}"] += 1
print(f"热力图: 完成", flush=True)

elapsed = time.time() - t0
print(f"\n=== 功能 API 300 次: 成功 {ok} / 失败 {fail} ({elapsed:.0f}s) ===", flush=True)
if errors:
    print("错误分布:", errors, flush=True)
print(f"\nAD-HOC V2.35 FEATURES (real) — 成功 {ok} 失败 {fail}", flush=True)
sys.exit(0 if fail == 0 else 1)
