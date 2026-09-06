# -*- coding: utf-8 -*-
"""导出待修复题的完整存储布局（题干/答案/选项全文 + 所在单元原文尾部），元组索引版。"""
import sqlite3

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
QIDS = [1523, 1524, 1528, 1529, 1530, 1531, 1533, 1534, 1535, 1568, 1569, 1570, 1571, 1573, 1574,
        2066, 2083, 2084, 2085, 2086]

conn = sqlite3.connect(DB)
seen_units = set()
for qid in QIDS:
    row = conn.execute(
        "SELECT q.id, q.number, q.stem, q.answer, u.id, u.title, u.unit_type, u.passage, p.title "
        "FROM questions q JOIN units u ON u.id=q.unit_id JOIN papers p ON p.id=u.paper_id WHERE q.id=?",
        (qid,),
    ).fetchone()
    if row is None:
        print("q%d NOT FOUND" % qid)
        continue
    qid_, number, stem, answer, uid, utitle, unit_type, passage, paper = row
    if uid not in seen_units:
        seen_units.add(uid)
        print("=" * 100)
        print("UNIT %d | %s | %s | type=%s" % (uid, paper, utitle, unit_type))
        print("PASSAGE TAIL: %r" % (passage or "")[-260:])
    print("-" * 90)
    print("q%d | number=%s | answer=%s" % (qid_, number, answer))
    print("  STEM: %r" % stem)
    for key, content in conn.execute(
        "SELECT stable_key, content FROM options WHERE question_id=? ORDER BY sequence", (qid_,)
    ):
        print("  %s: %r" % (key, content))
conn.close()
print("\nDUMP DONE")
