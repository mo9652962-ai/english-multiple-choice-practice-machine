# -*- coding: utf-8 -*-
"""修复核验二：导出关键单元原文（判断正确项文本）+ 相关题的已写 option/note 片段。"""
import json
import os
import sqlite3

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
BASE = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen"

conn = sqlite3.connect(DB)
for uid in (214, 215, 285, 289):
    row = conn.execute("SELECT passage, shared_data FROM units WHERE id=?", (uid,)).fetchone()
    passage, shared = row[0] or "", row[1] or ""
    print("=" * 100)
    print("UNIT %d PASSAGE (full):" % uid)
    print(passage[:4200])
    if uid == 289:
        try:
            sd = json.loads(shared)
            cands = sd.get("candidates") or {}
            print("CANDIDATES keys:", list(cands.keys())[:10])
        except Exception as e:
            print("shared parse err:", e)
conn.close()

print("\n" + "=" * 100)
print("已写内容（option/note 片段）:")
QIDS = [1528, 1529, 1530, 1531, 1534, 1535, 1568, 1569, 1570, 1571, 1573, 1574, 2066, 2083, 2084, 2085, 2086]
for qid in QIDS:
    chunk_no = qid // 25 + 1
    batch_no = (chunk_no - 1) // 20 + 1
    path = os.path.join(BASE, "content", "batch%d" % batch_no, "chunk_%03d.json" % chunk_no)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for it in data["items"]:
        if it["question_id"] == qid:
            print("-" * 90)
            print("q%d [option] %s" % (qid, it.get("option", "")))
            print("q%d [note] %s" % (qid, it.get("note", "")))
            break
print("\nVERIFY DUMP DONE")
