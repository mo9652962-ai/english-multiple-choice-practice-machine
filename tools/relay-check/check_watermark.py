#!/usr/bin/env python
"""AI 中转站注水测试脚本
检测: ①模型真实性(回显model vs 声称) ②独特标记复述(掺水检测) ③延迟 ④多轮一致性
用法: 1) 编辑 stations.json 填入 base_url/api_key  2) python check_watermark.py
参考: 36氪《API中转站的三个世界》注水率10-20% + zzsting88/relayAPI 评测
"""
import json
import os
import random
import string
import time
import urllib.error
import urllib.request

CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stations.json")
ROUNDS = 5  # 每站测试轮数


def call(base_url: str, api_key: str, model: str, prompt: str, timeout: int = 60):
    """调用 chat completions，返回 (ok, latency, response_model, content, raw_error)"""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 300,
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode())
        latency = time.time() - t0
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        # 有些中转站返回 reasoning_content
        if not content and msg.get("reasoning_content"):
            content = msg["reasoning_content"]
        return True, latency, data.get("model", ""), content, None
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()[:300]
        except Exception:
            body = str(e)
        return False, time.time() - t0, "", "", f"HTTP {e.code}: {body}"
    except Exception as e:
        return False, time.time() - t0, "", "", str(e)


def random_token() -> str:
    return "RELAY_CHECK_" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


def main():
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)

    print("=" * 70)
    print("AI 中转站注水测试 — 5 轮检测 (模型身份 / 独特标记 / 延迟 / 一致性)")
    print("=" * 70)

    for station in cfg["stations"]:
        name = station["name"]
        base = station["base_url"]
        key = station["api_key"]
        model = station["target_model"]
        print(f"\n{'─' * 70}")
        print(f"🔍 {name}  | 声称: {model}  ({station.get('claimed_price', '')})")
        print(f"   {station['desc']}")
        if "REPLACE_ME" in key or not key:
            print("   ⚠️ 未填 api_key，跳过")
            continue

        identity_hits = 0      # 模型能说出与声称一致的型号
        token_echo_hits = 0    # 独特标记复述成功
        latency_sum = 0.0
        ok_calls = 0
        model_reports = []

        for i in range(ROUNDS):
            marker = random_token()
            prompts = [
                f"请回答：你具体是什么模型？只回答模型名称，不要解释。另外请复述这个标记：{marker}",
                f"输出你的模型ID。然后复述标记：{marker}",
                f"你是谁？只回复型号名。复述标记：{marker}",
                f"请确认模型名称（如 gpt-4o、claude-sonnet-4.5 等），并复述：{marker}",
                f"模型型号是什么？复述标记：{marker}",
            ]
            ok, lat, resp_model, content, err = call(base, key, model, prompts[i % len(prompts)])
            if not ok:
                print(f"   [{i + 1}] ❌ 调用失败: {err}")
                continue
            ok_calls += 1
            latency_sum += lat
            model_reports.append(resp_model)
            lower = content.lower()
            if marker.lower() in lower:
                token_echo_hits += 1
            claimed_key = model.split("/")[-1].lower().replace(" ", "")
            resp_key = (resp_model or "").lower()
            if claimed_key in resp_key or claimed_key.replace("-", "") in resp_key.replace("-", ""):
                identity_hits += 1

        print(f"   ├─ 调用成功率: {ok_calls}/{ROUNDS}")
        if ok_calls:
            print(f"   ├─ 平均延迟:   {latency_sum / ok_calls:.2f}s")
            print(f"   ├─ 独特标记复述: {token_echo_hits}/{ok_calls}  {' ✅' if token_echo_hits == ok_calls else ' ⚠️ 存在掺水/降级嫌疑'}")
            print(f"   ├─ 身份自认匹配: {identity_hits}/{ok_calls}")
            print(f"   ├─ 响应 model 字段: {sorted(set(model_reports))[:3]}")
            echo_rate = token_echo_hits / ok_calls
            if echo_rate == 1.0:
                verdict = "✅ 基本可信（标记全部复述）"
            elif echo_rate >= 0.6:
                verdict = "⚠️ 疑似掺水/降级（部分请求被替换）"
            else:
                verdict = "❌ 高度可疑（多数请求未复述标记）"
            print(f"   └─ 结论: {verdict}")

    print("\n" + "=" * 70)
    print("⚠️  提示: 标记复述失败 ≠ 100% 注水，可能是 max_tokens 截断或模型指令遵循差。")
    print("   建议每站多跑几轮、换不同 prompt，并小额充值观察账单与 usage 字段一致性。")
    print("   中转站行业不稳定，用多少充多少。")
    print("=" * 70)


if __name__ == "__main__":
    main()
