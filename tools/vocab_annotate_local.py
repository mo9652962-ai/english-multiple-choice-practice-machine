"""用本地 Qwen3-8B 批量标注 195 个卡住的词汇（translating 状态）
- 从 vocabulary_entries 取 translating 词 + 真题上下文
- 调本地 llama-server (:8080) 批量翻译
- 更新数据库字段 + status=ready
"""
import json
import os
import re
import shutil
import sqlite3
import time
import urllib.request

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
# 云端基元律动（tokenrhythm.studio, deepseek-v4-flash —— 实测真实便宜）
import yaml as _yaml
_CFG = _yaml.safe_load(open(r"C:\Users\31954\AppData\Local\hermes\config.yaml", encoding="utf-8"))
_JYL = next(p for p in _CFG["custom_providers"] if p.get("name") == "jiyuanlvdong")
API = _JYL["base_url"].rstrip("/") + "/chat/completions"
API_KEY = _JYL.get("api_key", "")
MODEL = "deepseek-v4-flash"
BATCH = 3          # 每批词数（减小提高JSON成功率）
MAX_TOKENS = 4000  # 思考+输出

SYSTEM_PROMPT = """你是考研英语语境词汇助手。请批量分析用户标记的单词或短语，并结合各自真题原句判断含义。
只返回 JSON，不要使用 Markdown。格式必须为：
{
  "translations": [
    {
      "entryId": 123,
      "lemma": "词形还原；短语保持原形",
      "phonetic": "常见英式或美式音标；不确定则留空",
      "partOfSpeech": "简短词性",
      "contextualMeaning": "该原句中的准确中文释义",
      "commonMeaning": "一到三个常见中文释义",
      "memoryHint": "一句简短记忆提示，不编造词源",
      "synonyms": [{"word": "同义词", "note": "一句极简辨析"}],
      "antonyms": [{"word": "反义词", "note": "一句极简辨析"}],
      "similarForms": [{"word": "形近词", "note": "一句极简辨析"}]
    }
  ]
}
必须原样返回每个 entryId，不能增加不存在的 ID。释义只填写可直接背诵的简洁中文词义。
同义词/反义词/形近词每组 0-3 条，辨析各用一句话（30 字以内）；没有就返回空数组 []。"""


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
    """容错解析：去掉 markdown 代码块，提取 JSON；数组自动包成 translations"""
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
        return {"translations": data}
    if isinstance(data, dict):
        if "translations" not in data and any(k in data for k in ("entryId", "term")):
            return {"translations": [data]}
        return data
    return None


def clean_meaning(v, limit=1000):
    if isinstance(v, list):
        v = " ".join(str(x) for x in v if x is not None)
    return str(v or "").strip()[:limit]


def model_text(v, limit=120):
    if isinstance(v, list):
        v = " ".join(str(x) for x in v if x is not None)
    return str(v or "").strip()[:limit]


def disc_list(v):
    out = []
    if isinstance(v, list):
        for it in v:
            if isinstance(it, dict) and it.get("word"):
                out.append({"word": str(it["word"])[:80], "note": str(it.get("note", ""))[:200]})
    return out


def main():
    # 备份
    bak = DB + ".bak-vocab-annotate"
    if not os.path.exists(bak):
        shutil.copy2(DB, bak)
        print(f"备份: {bak}")

    conn = sqlite3.connect(DB)
    rows = conn.execute("""
        SELECT v.id, v.term,
               (SELECT context_sentence FROM vocabulary_occurrences WHERE entry_id = v.id ORDER BY id DESC LIMIT 1),
               (SELECT context_before FROM vocabulary_occurrences WHERE entry_id = v.id ORDER BY id DESC LIMIT 1),
               (SELECT context_after FROM vocabulary_occurrences WHERE entry_id = v.id ORDER BY id DESC LIMIT 1)
        FROM vocabulary_entries v
        WHERE v.user_edited = 0 AND v.translation_status = 'translating'
        ORDER BY v.id
    """).fetchall()
    print(f"待标注: {len(rows)} 词，分 {max(1, (len(rows) + BATCH - 1) // BATCH)} 批")

    done = failed = 0
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        items = [
            {"entryId": r[0], "term": r[1], "sentence": r[2] or "", "before": r[3] or "", "after": r[4] or ""}
            for r in batch
        ]
        try:
            resp = call_local(json.dumps({"items": items}, ensure_ascii=False))
            msg = resp["choices"][0]["message"]
            content = msg.get("content") or ""
            parsed = parse_json_reply(content)
            if not parsed or not isinstance(parsed.get("translations"), list):
                print(f"  ⚠️ 批 {start // BATCH + 1}: JSON 解析失败，重试下一批")
                failed += len(batch)
                continue
            for item in parsed["translations"]:
                if not isinstance(item, dict):
                    continue
                eid = item.get("entryId")
                if not isinstance(eid, int):
                    continue
                contextual = clean_meaning(item.get("contextualMeaning", ""))
                if not contextual:
                    continue
                conn.execute("""
                    UPDATE vocabulary_entries
                    SET lemma=?, phonetic=?, part_of_speech=?, contextual_meaning=?,
                        common_meaning=?, memory_hint=?, synonyms=?, antonyms=?, similar_forms=?,
                        translation_status='ready', translation_error='', updated_at=CURRENT_TIMESTAMP
                    WHERE id=? AND user_edited=0 AND translation_status='translating'
                """, (
                    model_text(item.get("lemma", "")), model_text(item.get("phonetic", "")),
                    model_text(item.get("partOfSpeech", "")), contextual,
                    clean_meaning(item.get("commonMeaning", "")),
                    model_text(item.get("memoryHint", ""), 1000),
                    json.dumps(disc_list(item.get("synonyms")), ensure_ascii=False),
                    json.dumps(disc_list(item.get("antonyms")), ensure_ascii=False),
                    json.dumps(disc_list(item.get("similarForms")), ensure_ascii=False),
                    eid,
                ))
                done += 1
            conn.commit()
            print(f"  ✅ 批 {start // BATCH + 1}: {len(batch)} 词 (累计 {done})")
        except Exception as e:
            print(f"  ❌ 批 {start // BATCH + 1}: {str(e)[:80]}")
            failed += len(batch)
        time.sleep(1)

    conn.close()
    print(f"\n完成: 成功 {done} / 失败 {failed}")
    print(f"剩余 translating: ")


if __name__ == "__main__":
    main()
