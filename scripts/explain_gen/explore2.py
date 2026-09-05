# -*- coding: utf-8 -*-
"""探查第二轮：unit_type 分布、选词填空词库、听力单元、阅读题选项实样、papers 全览"""
import sqlite3
import json

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("== unit_type distribution (units + question counts) ==")
for r in cur.execute(
    "SELECT u.unit_type, COUNT(DISTINCT u.id) units, COUNT(q.id) qs "
    "FROM units u LEFT JOIN questions q ON q.unit_id = u.id GROUP BY u.unit_type ORDER BY qs DESC"
):
    print(f"  {r['unit_type']}: {r['units']} units, {r['qs']} questions")

print("\n== papers all (id/title/question count) ==")
for r in cur.execute(
    "SELECT p.id, p.title, COUNT(q.id) qs FROM papers p "
    "LEFT JOIN units u ON u.paper_id = p.id LEFT JOIN questions q ON q.unit_id = u.id "
    "GROUP BY p.id ORDER BY p.id"
):
    print(f"  #{r['id']} {r['title']}: {r['qs']}q")

print("\n== one banked_cloze unit: shared_data + passage head ==")
r = cur.execute("SELECT id, paper_id, title, passage, shared_data FROM units WHERE unit_type='banked_cloze' ORDER BY id LIMIT 1").fetchone()
if r:
    print(f"unit {r['id']} paper {r['paper_id']} title={r['title']}")
    print("shared_data:", r["shared_data"][:800])
    print("passage head:", r["passage"][:300])
    qs = cur.execute("SELECT id, number, stem, answer FROM questions WHERE unit_id=? ORDER BY number LIMIT 2", (r["id"],)).fetchall()
    for q in qs:
        print("  q:", dict(q))
    if qs:
        opts = cur.execute("SELECT stable_key, original_label, content FROM options WHERE question_id=? ORDER BY sequence", (qs[0]["id"],)).fetchall()
        print("  options:", [(o["stable_key"], o["content"][:30]) for o in opts])
else:
    print("no banked_cloze")

print("\n== one listening unit: shared_data + passage head ==")
r = cur.execute("SELECT id, paper_id, title, passage, shared_data FROM units WHERE unit_type='listening' ORDER BY id LIMIT 1").fetchone()
if r:
    print(f"unit {r['id']} paper {r['paper_id']} title={r['title']}")
    print("shared_data head:", r["shared_data"][:500])
    print("passage head:", (r["passage"] or "EMPTY")[:300])
    q = cur.execute("SELECT id, number, stem, answer FROM questions WHERE unit_id=? ORDER BY number LIMIT 1", (r["id"],)).fetchone()
    if q:
        print("  q:", dict(q))
        opts = cur.execute("SELECT stable_key, content FROM options WHERE question_id=? ORDER BY sequence", (q["id"],)).fetchall()
        print("  options:", [(o["stable_key"], o["content"][:60]) for o in opts])
else:
    print("no listening")

print("\n== one reading question with real options ==")
r = cur.execute(
    "SELECT q.id, q.number, q.stem, q.answer, u.title FROM questions q JOIN units u ON u.id=q.unit_id "
    "WHERE u.unit_type='reading' ORDER BY q.id LIMIT 1"
).fetchone()
if r:
    print(f"q{r['id']} number={r['number']} unit={r['title']} answer={r['answer']}")
    print("stem:", r["stem"][:300])
    opts = cur.execute("SELECT stable_key, content FROM options WHERE question_id=? ORDER BY sequence", (r["id"],)).fetchall()
    for o in opts:
        print(f"  {o['stable_key']}: {o['content'][:100]}")

print("\n== paragraph_matching options sample ==")
r = cur.execute(
    "SELECT q.id, q.stem, q.answer FROM questions q JOIN units u ON u.id=q.unit_id "
    "WHERE u.unit_type='paragraph_matching' ORDER BY q.id LIMIT 1"
).fetchone()
if r:
    print(f"q{r['id']} answer={r['answer']} stem: {r['stem'][:200]}")
    opts = cur.execute("SELECT stable_key, content FROM options WHERE question_id=? ORDER BY sequence LIMIT 4", (r["id"],)).fetchall()
    print("  options:", [(o["stable_key"], o["content"][:30]) for o in opts])

print("\n== options coverage: questions without any options row ==")
n = cur.execute("SELECT COUNT(*) FROM questions q WHERE NOT EXISTS (SELECT 1 FROM options o WHERE o.question_id=q.id)").fetchone()[0]
print("questions without options:", n)

print("\n== metadata-bearing question sample (49 with analysis) ==")
r = cur.execute("SELECT id, stem, answer, metadata FROM questions WHERE TRIM(metadata) NOT IN ('', '{}') ORDER BY id LIMIT 1").fetchone()
if r:
    print(f"q{r['id']} answer={r['answer']}")
    print("stem:", r["stem"][:200])
    print("metadata:", r["metadata"][:600])

print("\n== passage length stats per unit_type ==")
for r in cur.execute(
    "SELECT unit_type, MIN(LENGTH(passage)) mn, AVG(LENGTH(passage)) av, MAX(LENGTH(passage)) mx, "
    "AVG(LENGTH(shared_data)) sd FROM units GROUP BY unit_type"
):
    print(f"  {r['unit_type']}: min={r['mn']} avg={int(r['av'])} max={r['mx']} shared_avg={int(r['sd'])}")

conn.close()
print("\nDONE")
