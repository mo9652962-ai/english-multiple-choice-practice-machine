"""全量补 contextual_meaning（语境释义）——云端基元律动 deepseek-v4-flash
查询：有 common_meaning 但 contextual_meaning 为空的词（7847 个）
批量 5 + 自动多轮重试（失败词下一轮再跑，最多 4 轮）
"""
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.request

import yaml as _yaml

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
_CFG = _yaml.safe_load(open(r"C:\Users\31954\AppData\Local\hermes\config.yaml", encoding="utf-8"))
_JYL = next(p for p in _CFG["custom_providers"] if p.get("name") == "jiyuanlvdong")
API = _JYL["base_url"].rstrip("/") + "/chat/completions"
API_KEY = _JYL.get("api_key", "")
MODEL = "deepseek-v4-flash"
BATCH = 12
MAX_TOKENS = 8000
MAX_ROUNDS = 6

SYSTEM_PROMPT = """你是考研英语语境词汇助手。用户会给出单词及其常用释义，以及该词在真题原句中的上下文。
请结合原句判断该词在**这句真题里**的准确中文释义（语境释义）。
只返回 JSON，不要使用 Markdown。格式：
{
  "results": [
    {"entryId": 123, "contextualMeaning": "该原句中的准确中文释义（简洁，可直接背诵）"}
  ]
}
必须原样返回每个 entryId。语境释义要贴合原句含义，不要照抄常用释义，不要加括号说明。"""


def call_local(items_json, timeout=120):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": items_json},
        ],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.2,
    }
    req = urllib.request.Request(API, data=json.dumps(payload).encode("utf-8"),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {API_KEY}"},
                                 method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if attempt < 3:
                time.sleep(2)
                continue
            raise


def parse_json_reply(content):
    if not content:
        return None
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]|\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if isinstance(data, list):
        return {"results": data}
    if isinstance(data, dict):
        if "results" not in data and "entryId" in data:
            return {"results": [data]}
        return data
    return None


def get_pending(conn):
    return conn.execute("""
        SELECT v.id, v.term, v.common_meaning,
               (SELECT context_sentence FROM vocabulary_occurrences WHERE entry_id = v.id ORDER BY id DESC LIMIT 1),
               (SELECT context_before FROM vocabulary_occurrences WHERE entry_id = v.id ORDER BY id DESC LIMIT 1),
               (SELECT context_after FROM vocabulary_occurrences WHERE entry_id = v.id ORDER BY id DESC LIMIT 1)
        FROM vocabulary_entries v
        WHERE (v.contextual_meaning IS NULL OR v.contextual_meaning = '')
          AND v.common_meaning IS NOT NULL AND v.common_meaning != ''
        ORDER BY v.id
    """).fetchall()


def main():
    if not os.path.exists(DB + ".bak-contextual"):
        shutil.copy2(DB, DB + ".bak-contextual")
        print(f"备份: {DB}.bak-contextual")

    for round_no in range(1, MAX_ROUNDS + 1):
        conn = sqlite3.connect(DB)
        rows = get_pending(conn)
        total = len(rows)
        if total == 0:
            print(f"✅ 第 {round_no} 轮: 已全部完成")
            conn.close()
            break
        print(f"\n第 {round_no} 轮: 待补 {total} 词，分 {(total + BATCH - 1) // BATCH} 批")
        done = 0
        for start in range(0, total, BATCH):
            batch = rows[start:start + BATCH]
            items = [
                {"entryId": r[0], "term": r[1], "commonMeaning": r[2] or "",
                 "sentence": r[3] or "", "before": r[4] or "", "after": r[5] or ""}
                for r in batch
            ]
            try:
                resp = call_local(json.dumps({"items": items}, ensure_ascii=False))
                content = resp["choices"][0]["message"].get("content") or ""
                parsed = parse_json_reply(content)
                if not parsed or not isinstance(parsed.get("results"), list):
                    print(f"  ⚠️ 批 {start // BATCH + 1}: JSON 失败")
                    continue
                for item in parsed["results"]:
                    if not isinstance(item, dict):
                        continue
                    eid = item.get("entryId")
                    if not isinstance(eid, int):
                        continue
                    ctx = str(item.get("contextualMeaning") or "").strip()[:1000]
                    if not ctx:
                        continue
                    cur = conn.execute("UPDATE vocabulary_entries SET contextual_meaning=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (ctx, eid))
                    if cur.rowcount:
                        done += 1
                conn.commit()
                print(f"  ✅ 批 {start // BATCH + 1}: +{done} (累计 {done})")
            except Exception as e:
                print(f"  ❌ 批 {start // BATCH + 1}: {str(e)[:80]}")
            time.sleep(1)
        conn.close()
        print(f"第 {round_no} 轮完成: +{done}")

    # 最终验证
    conn = sqlite3.connect(DB)
    remaining = conn.execute("""
        SELECT COUNT(*) FROM vocabulary_entries
        WHERE (contextual_meaning IS NULL OR contextual_meaning = '')
          AND common_meaning IS NOT NULL AND common_meaning != ''
    """).fetchone()[0]
    conn.close()
    print(f"\n最终剩余缺语境释义: {remaining}")


if __name__ == "__main__":
    main()
