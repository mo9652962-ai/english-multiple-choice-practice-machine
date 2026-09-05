# -*- coding: utf-8 -*-
"""把 2132 题切成 25 题/chunk，以纯文本形式存入 chunks.db（供生成代理只读打印）。

全部数据通过 SQLite 落盘；chunk 正文为人类可读文本（UNIT/QUESTION 段），
长行自动折行到每行不超过 240 字符。
"""
import json
import os
import sqlite3
import textwrap

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
OUT = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen\data\chunks.db"
CHUNK_SIZE = 25
PASSAGE_LIMIT = 8000
DIRECTIONS_LIMIT = 500
CAND_LIMIT = 1500
TOTAL_CAND_LIMIT = 7000
WRAP_WIDTH = 240


def wrap(text: str) -> str:
    out_lines = []
    for raw in str(text).split("\n"):
        if len(raw) <= WRAP_WIDTH:
            out_lines.append(raw)
        else:
            out_lines.extend(
                textwrap.wrap(raw, width=WRAP_WIDTH, break_long_words=False, break_on_hyphens=False)
            )
    return "\n".join(out_lines)


if os.path.exists(OUT):
    os.remove(OUT)
os.makedirs(os.path.dirname(OUT), exist_ok=True)

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
out = sqlite3.connect(OUT)
out.execute("CREATE TABLE chunks (no INTEGER PRIMARY KEY, qids TEXT NOT NULL, body TEXT NOT NULL)")

papers = {r["id"]: r["title"] for r in conn.execute("SELECT id, title FROM papers")}

units = {}
for r in conn.execute(
    "SELECT id, paper_id, unit_type, title, subtype, passage, shared_data FROM units ORDER BY id"
):
    try:
        sd = json.loads(r["shared_data"] or "{}")
    except Exception:
        sd = {}
    candidates = sd.get("candidates") or {}
    cand_out = {}
    cand_total = 0
    if isinstance(candidates, dict):
        for k, v in candidates.items():
            if cand_total >= TOTAL_CAND_LIMIT:
                cand_out[str(k)] = "…（超出截断）"
                continue
            t = str(v)[:CAND_LIMIT]
            cand_out[str(k)] = t
            cand_total += len(t)
    passage = r["passage"] or ""
    units[r["id"]] = {
        "paper": papers.get(r["paper_id"], ""),
        "unit_type": r["unit_type"],
        "title": r["title"],
        "passage": passage[:PASSAGE_LIMIT] + ("…（截断）" if len(passage) > PASSAGE_LIMIT else ""),
        "directions": str(sd.get("directions") or "")[:DIRECTIONS_LIMIT],
        "candidates": cand_out,
    }

options_by_q = {}
for r in conn.execute(
    "SELECT question_id, stable_key, content FROM options ORDER BY question_id, sequence"
):
    options_by_q.setdefault(r["question_id"], []).append(
        {"key": r["stable_key"], "content": r["content"]}
    )

questions = []
for r in conn.execute(
    "SELECT id, unit_id, number, stem, question_type, answer FROM questions ORDER BY id"
):
    questions.append(
        {
            "id": r["id"],
            "unit_id": r["unit_id"],
            "number": r["number"],
            "type": r["question_type"],
            "stem": r["stem"],
            "answer": r["answer"],
            "options": options_by_q.get(r["id"], []),
        }
    )
conn.close()

total_chunks = 0
for i in range(0, len(questions), CHUNK_SIZE):
    chunk_qs = questions[i : i + CHUNK_SIZE]
    chunk_no = i // CHUNK_SIZE + 1
    lines = [
        "######## CHUNK %03d ########" % chunk_no,
        "question_ids: " + ",".join(str(q["id"]) for q in chunk_qs),
        "说明：ANSWER=正确答案。unit_type 含义：reading=仔细阅读；cloze=完形/选词填空（passage 中 {blank:N} 对应 number=N 的题）；"
        "paragraph_matching=长篇阅读（answer 为段落字母，passage 段落以 A) B) 开头）；part_b=七选五/新题型（选项为句子；"
        "考研排序题原文在 UNIT 的 CANDIDATES 里）。",
    ]
    cur_unit = None
    for q in chunk_qs:
        if q["unit_id"] != cur_unit:
            cur_unit = q["unit_id"]
            u = units[cur_unit]
            lines.append("")
            lines.append(
                "==== UNIT %d | paper=%s | type=%s | title=%s ====" % (cur_unit, u["paper"], u["unit_type"], u["title"])
            )
            if u["directions"]:
                lines.append("DIRECTIONS: " + u["directions"])
            if u["candidates"]:
                lines.append("CANDIDATES:")
                for k, v in u["candidates"].items():
                    lines.append("  [%s] %s" % (k, wrap(v)))
            if u["passage"]:
                lines.append("PASSAGE（原文，供定位与同义改写分析）:")
                lines.append(wrap(u["passage"]))
        lines.append("")
        lines.append(
            "==== QUESTION %d | unit=%d | number=%d | answer=%s ====" % (q["id"], q["unit_id"], q["number"], q["answer"])
        )
        lines.append("STEM: " + wrap(q["stem"] or "（无题干，见 passage 的 {blank:%d}）" % q["number"]))
        lines.append("OPTIONS:")
        for o in q["options"]:
            lines.append("  %s: %s" % (o["key"], o["content"]))
    body = "\n".join(lines)
    out.execute(
        "INSERT INTO chunks (no, qids, body) VALUES (?, ?, ?)",
        (chunk_no, ",".join(str(q["id"]) for q in chunk_qs), body),
    )
    total_chunks += 1
    print("chunk %03d: q%s-%s body=%d chars" % (chunk_no, chunk_qs[0]["id"], chunk_qs[-1]["id"], len(body)))

out.commit()
n, total_len = out.execute("SELECT COUNT(*), SUM(LENGTH(body)) FROM chunks").fetchone()
out.close()
print("\nchunks=%d total_chars=%d" % (n, total_len))
print("batch mapping: chunks 1-20 -> batch1 | 21-40 -> batch2 | 41-60 -> batch3 | 61-80 -> batch4 | 81-%d -> batch5" % total_chunks)
print("BUILD DONE")
