# -*- coding: utf-8 -*-
"""把 content/batchN/chunk_NNN.json 的生成内容幂等写入 explain_collections。

- 幂等：INSERT 前比对 (question_id, fragment_type) 是否已存在，已存在跳过。
- source 固定 'deep-explain'；content 长度限制 10~2000（与 API 上限一致）。
用法：python apply_content.py 1        # 只应用批次1
     python apply_content.py         # 应用全部批次
"""
import json
import os
import re
import sqlite3
import sys

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
CONTENT_DIR = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen\content"
FRAG_KEYS = ("long_sentence", "option", "keyword", "note")
NAME_RE = re.compile(r"chunk_[0-9]{3}\.json")


def main() -> None:
    batches = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4, 5]
    conn = sqlite3.connect(DB)
    existing = {
        (qid, ft)
        for qid, ft in conn.execute("SELECT question_id, fragment_type FROM explain_collections")
    }
    print("existing explain_collections rows: %d (pairs %d)" % (
        conn.execute("SELECT COUNT(*) FROM explain_collections").fetchone()[0], len(existing))
    )
    total_ins = 0
    total_skip = 0
    failed = False
    for b in batches:
        bdir = os.path.join(CONTENT_DIR, "batch%d" % b)
        if not os.path.isdir(bdir):
            print("batch%d: 目录不存在，跳过" % b)
            continue
        for fn in sorted(os.listdir(bdir)):
            if not NAME_RE.fullmatch(fn):
                continue
            path = os.path.join(bdir, fn)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            items = data.get("items") or []
            rows = []
            skipped = 0
            problems = []
            for it in items:
                try:
                    qid = int(it["question_id"])
                except (KeyError, TypeError, ValueError):
                    problems.append("%s: 非法 question_id %r" % (fn, it.get("question_id")))
                    continue
                for ft in FRAG_KEYS:
                    c = str(it.get(ft) or "").strip()
                    if not c:
                        problems.append("%s q%d: %s 为空" % (fn, qid, ft))
                    elif len(c) < 10:
                        problems.append("%s q%d: %s 过短(%d)" % (fn, qid, ft, len(c)))
                    elif len(c) > 2000:
                        problems.append("%s q%d: %s 超长(%d)" % (fn, qid, ft, len(c)))
                    elif (qid, ft) in existing:
                        skipped += 1
                    else:
                        rows.append((qid, ft, c, "deep-explain"))
            if problems:
                failed = True
                print("batch%d %s: 发现 %d 个问题，拒绝入库" % (b, fn, len(problems)))
                for p in problems[:10]:
                    print("   -", p)
                continue
            if rows:
                conn.executemany(
                    "INSERT INTO explain_collections (question_id, fragment_type, content, source) VALUES (?, ?, ?, ?)",
                    rows,
                )
                conn.commit()
                existing.update((r[0], r[1]) for r in rows)
            total_ins += len(rows)
            total_skip += skipped
            print("batch%d %s: items=%d inserted=%d skipped=%d" % (b, fn, len(items), len(rows), skipped))
    n, distinct = conn.execute(
        "SELECT COUNT(*), COUNT(DISTINCT question_id) FROM explain_collections"
    ).fetchone()
    conn.close()
    print("\ninserted=%d skipped=%d -> explain_collections now %d rows / %d questions" % (total_ins, total_skip, n, distinct))
    if failed:
        print("RESULT: FAILED（存在被拒绝的文件，未入库）")
        sys.exit(1)
    print("APPLY DONE")


if __name__ == "__main__":
    main()
