# -*- coding: utf-8 -*-
"""按题号检查：chunks.db 材料块 + 已写内容文件中的 4 条 fragment。用法：python inspect_qa.py 1443 1487 ..."""
import json
import os
import re
import sqlite3
import sys

BASE = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen"
CHUNKS_DB = os.path.join(BASE, "data", "chunks.db")
CONTENT_DIR = os.path.join(BASE, "content")
QIDS = [int(a) for a in sys.argv[1:]] or [1487]

conn = sqlite3.connect(CHUNKS_DB)
bodies = dict(conn.execute("SELECT no, body FROM chunks").fetchall())
conn.close()

def extract_block(body: str, qid: int) -> str:
    m = re.search(r"==== QUESTION %d \|.*?(?=\n==== |\n#### CHUNK)" % qid, body, re.S)
    return m.group(0) if m else "(材料中未找到 q%d)" % qid

written = {}
for b in sorted(os.listdir(CONTENT_DIR)):
    bdir = os.path.join(CONTENT_DIR, b)
    if not os.path.isdir(bdir):
        continue
    for fn in sorted(os.listdir(bdir)):
        if not re.fullmatch(r"chunk_[0-9]{3}\.json", fn):
            continue
        with open(os.path.join(bdir, fn), encoding="utf-8") as f:
            data = json.load(f)
        for it in data.get("items", []):
            if it.get("question_id") in QIDS:
                written[it["question_id"]] = (os.path.join(b, fn), it)

for qid in QIDS:
    print("=" * 90)
    found = False
    for no, body in bodies.items():
        if ("==== QUESTION %d |" % qid) in body:
            print(extract_block(body, qid))
            found = True
            break
    if not found:
        print("(chunks.db 无 q%d)" % qid)
    if qid in written:
        src, it = written[qid]
        print("--- 已写内容（%s）---" % src)
        for k in ("long_sentence", "option", "keyword", "note"):
            print("  [%s] %s" % (k, it.get(k, "(缺失)")))
    else:
        print("--- 尚无已写内容 ---")
