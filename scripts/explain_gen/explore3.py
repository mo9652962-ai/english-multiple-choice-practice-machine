# -*- coding: utf-8 -*-
"""探查第三轮：cloze/part_b 的 stem 形态、part_b 数据位置、question_explanations 存量"""
import sqlite3
import json

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("== question_explanations count + schema ==")
row = cur.execute("SELECT sql FROM sqlite_master WHERE name='question_explanations'").fetchone()
print(row[0] if row else "MISSING")
print("count:", cur.execute("SELECT COUNT(*) FROM question_explanations").fetchone()[0])

print("\n== cloze sample (考研完形) ==")
r = cur.execute(
    "SELECT q.id, q.number, q.stem, q.answer, u.id uid, u.title FROM questions q "
    "JOIN units u ON u.id=q.unit_id WHERE u.unit_type='cloze' AND u.paper_id=37 ORDER BY q.number LIMIT 3"
).fetchone()
rows = cur.execute(
    "SELECT q.id, q.number, q.stem, q.answer FROM questions q "
    "JOIN units u ON u.id=q.unit_id WHERE u.unit_type='cloze' ORDER BY q.id LIMIT 2"
).fetchall()
for r in rows:
    print(f"q{r['id']} number={r['number']} answer={r['answer']} stem={r['stem'][:250]!r}")
    opts = cur.execute("SELECT stable_key, content FROM options WHERE question_id=? ORDER BY sequence", (r["id"],)).fetchall()
    print("  options:", [(o["stable_key"], o["content"][:40]) for o in opts])

print("\n== cloze unit passage blank marker sample ==")
r = cur.execute("SELECT id, passage FROM units WHERE unit_type='cloze' ORDER BY id LIMIT 1").fetchone()
print(f"unit {r['id']} passage head 600:", r["passage"][:600])
print("shared_data head 400:", cur.execute("SELECT shared_data FROM units WHERE id=?", (r["id"],)).fetchone()[0][:400])

print("\n== part_b sample (七选五/新题型) ==")
r = cur.execute("SELECT id, paper_id, title, passage, shared_data FROM units WHERE unit_type='part_b' ORDER BY id LIMIT 1").fetchone()
print(f"unit {r['id']} paper={r['paper_id']} title={r['title']}")
print("passage head 700:", (r["passage"] or "EMPTY")[:700])
print("shared_data head 700:", (r["shared_data"] or "EMPTY")[:700])
qs = cur.execute("SELECT id, number, stem, answer FROM questions WHERE unit_id=? ORDER BY number LIMIT 2", (r["id"],)).fetchall()
for q in qs:
    print(f"  q{q['id']} number={q['number']} answer={q['answer']} stem={q['stem'][:200]!r}")
    opts = cur.execute("SELECT stable_key, content FROM options WHERE question_id=? ORDER BY sequence", (q["id"],)).fetchall()
    print("    options:", [(o["stable_key"], o["content"][:60]) for o in opts])

print("\n== part_b units with empty passage count ==")
n = cur.execute("SELECT COUNT(*) FROM units WHERE unit_type='part_b' AND TRIM(passage)=''").fetchone()[0]
print("empty passage part_b units:", n)
r = cur.execute("SELECT id, paper_id, title, shared_data FROM units WHERE unit_type='part_b' AND TRIM(passage)='' ORDER BY id LIMIT 1").fetchone()
if r:
    print(f"  example empty unit {r['id']} paper={r['paper_id']} title={r['title']}")
    print("  shared_data head 800:", (r["shared_data"] or "EMPTY")[:800])

print("\n== paragraph_matching unit passage paragraph markers ==")
r = cur.execute("SELECT id, passage FROM units WHERE unit_type='paragraph_matching' ORDER BY id LIMIT 1").fetchone()
print(f"unit {r['id']}: head 400", r["passage"][:400])

conn.close()
print("\nDONE")
