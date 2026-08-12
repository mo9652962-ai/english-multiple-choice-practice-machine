#!/usr/bin/env python
"""keylinkclub.com 注水测试（增强版）
检测: ①模型真实性(身份自认) ②独特标记复述(掺水) ③多分组/前缀探测 ④延迟 ⑤usage 倍率核对
用法: 填 API_KEY → python keylinkclub_check.py
"""
import json
import os
import random
import string
import time
import urllib.error
import urllib.request

BASE = "https://www.keylinkclub.com/v1"
API_KEY = "sk-KZMxRmVrCHhuwfYVPdUXIV0pF0tO6yhNTMx4X7DKmDE6L9wi"  # ← 在这里填 key

# keylinkclub 真实模型清单（/v1/models 探测 2026-08-11：34 模型，new-api 直接调用）
# 按可疑度排序：低价渠道（tj_* 分组）重点测
CANDIDATES = [
    # (描述, 模型名)
    ("deepseek-v4-flash（用户主力，对照官方）", "deepseek-v4-flash"),
    ("deepseek-v4-pro", "deepseek-v4-pro"),
    ("claude-sonnet-5（tj_claude 0.2x 渠道？）", "claude-sonnet-5"),
    ("claude-opus-5（高价模型）", "claude-opus-5"),
    ("gpt-5.6-sol（tj_openai 0.06x？）", "gpt-5.6-sol"),
    ("gpt-5.4", "gpt-5.4"),
    ("glm-5.2（国产）", "glm-5.2"),
    ("kimi-k2.7-code（国产）", "kimi-k2.7-code"),
    ("grok-4.5", "grok-4.5"),
    ("gemini-3.5-flash", "gemini-3.5-flash"),
]

ROUNDS = 3  # 每个模型测几轮（key 余额宝贵，先 3 轮）


def call(model: str, prompt: str, timeout: int = 60):
    url = BASE + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}",
                 "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 无代理直连（www 域名可通）
    t0 = time.time()
    for attempt in range(3):  # SSL 间歇错误重试
        try:
            with opener.open(req, timeout=timeout) as r:
                data = json.loads(r.read().decode())
            lat = time.time() - t0
            msg = data["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content") or ""
            return True, lat, data.get("model", ""), content, data.get("usage", {}), None
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()[:200]
            except Exception:
                body = str(e)
            return False, time.time() - t0, "", "", {}, f"HTTP {e.code}: {body}"
        except Exception as e:
            if attempt < 2 and "SSL" in str(e):
                time.sleep(1.5)
                continue
            return False, time.time() - t0, "", "", {}, str(e)[:120]
    return False, time.time() - t0, "", "", {}, "重试耗尽"


def marker() -> str:
    return "RELAY_CHECK_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def main():
    if "PASTE_YOUR" in API_KEY:
        print("⚠️  先在脚本顶部 API_KEY 填入你的 keylinkclub Key")
        return
    print("=" * 72)
    print("keylinkclub.com 注水测试（分组 × 3轮：身份 / 标记复述 / 延迟 / usage）")
    print("=" * 72)

    for desc, used_model in CANDIDATES:
        print(f"\n{'─' * 72}\n🔍 {desc}  [{used_model}]")
        # 先探测可用性
        ok, lat, resp_m, content, usage, err = call(used_model, "hi", timeout=30)
        if not ok:
            print(f"   ✗ 不可用: {err}")
            continue
        print(f"   ✓ 可用 → 响应 model={resp_m or '?'} ({lat:.1f}s)")

        hits = 0
        lat_sum = 0.0
        ok_calls = 0
        models_seen = set()
        usage_list = []
        for i in range(ROUNDS):
            mk = marker()
            prompt = f"请回答：你具体是什么模型？只回复模型名称。然后原样复述这个标记：{mk}"
            ok, lat, resp_m, content, usage, err = call(used_model, prompt)
            if not ok:
                print(f"   [{i + 1}] ❌ {err}")
                continue
            ok_calls += 1
            lat_sum += lat
            models_seen.add(resp_m or "?")
            if mk.lower() in content.lower():
                hits += 1
            usage_list.append(usage)
            print(f"   [{i + 1}] model={resp_m or '?'} | 延迟 {lat:.1f}s | 标记{'✓' if mk.lower() in content.lower() else '✗'} | usage={usage}")

        if ok_calls:
            print(f"   ├─ 成功率 {ok_calls}/{ROUNDS} | 平均延迟 {lat_sum / ok_calls:.1f}s")
            print(f"   ├─ 标记复述 {hits}/{ok_calls}  {'✅' if hits == ok_calls else '⚠️ 掺水/降级嫌疑'}")
            print(f"   ├─ 响应model字段: {sorted(models_seen)}")
            # usage 一致性检查（同一模型多次调用的 token 应接近）
            if len(usage_list) >= 2:
                uts = [u.get("total_tokens", 0) for u in usage_list if u]
                if uts:
                    spread = max(uts) - min(uts)
                    print(f"   ├─ usage total_tokens 波动: {uts} (spread={spread})")
            rate = hits / ok_calls
            if rate == 1.0:
                print(f"   └─ 结论: ✅ 基本可信（标记全部复述）")
            elif rate >= 0.6:
                print(f"   └─ 结论: ⚠️ 疑似掺水/降级")
            else:
                print(f"   └─ 结论: ❌ 高度可疑")

    print("\n" + "=" * 72)
    print("⚠️  说明：标记复述失败≠100%注水（可能 max_tokens 截断）。")
    print("  建议：对照官方定价页算实际倍率（usage total_tokens × 单价 vs 扣费）。")
    print("  安全：小额充值、不传敏感数据、用多少充多少。")
    print("=" * 72)


if __name__ == "__main__":
    main()
