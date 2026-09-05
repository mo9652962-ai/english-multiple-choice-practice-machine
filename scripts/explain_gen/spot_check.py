# -*- coding: utf-8 -*-
"""随机抽查 N 题的精讲质量（打印题干+选项+4 条 fragment）。用法：python spot_check.py [N] [seed]"""
import random
import sqlite3
import sys

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42
qids = [r[0] for r in conn.execute("SELECT DISTINCT question_id FROM explain_collections ORDER BY question_id")]
random.Random(seed).shuffle(qids)
picks = sorted(qids[:n])

print("抽查 %d 题（seed=%d）: %s\n" % (len(picks), seed, picks))
for qid in picks:
    q = conn.execute(
        "SELECT q.id, q.number, q.stem, q.answer, u.unit_type, u.title FROM questions q "
        "JOIN units u ON u.id=q.unit_id WHERE q.id=?",
        (qid,),
    ).fetchone()
    print("=" * 80)
    print("q%d | %s | %s | number=%s | answer=%s" % (q["id"], q["unit_type"], q["title"], q["number"], q["answer"]))
    print("STEM:", (q["stem"] or "")[:200])
    opts = conn.execute(
        "SELECT stable_key, content FROM options WHERE question_id=? ORDER BY sequence", (qid,)
    ).fetchall()
    print("OPTIONS:", "; ".join("%s=%s" % (o["stable_key"], o["content"][:50]) for o in opts))
    for r in conn.execute(
        "SELECT fragment_type, content, LENGTH(content) ln FROM explain_collections "
        "WHERE question_id=? ORDER BY CASE fragment_type WHEN 'long_sentence' THEN 1 WHEN 'option' THEN 2 "
        "WHEN 'keyword' THEN 3 ELSE 4 END",
        (qid,),
    ):
        print("  [%s|%d字] %s" % (r["fragment_type"], r["ln"], r["content"]))
conn.close()
print("\nSPOT CHECK DONE")
