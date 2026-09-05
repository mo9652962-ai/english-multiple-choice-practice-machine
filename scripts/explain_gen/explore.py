# -*- coding: utf-8 -*-
"""探查 question_bank.db：表结构、题型分布、选项存储位置、explain_collections 现状（全部内联字面量 SQL）"""
import sqlite3
import json

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("== all tables ==")
tables = [r["name"] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(tables)

print("\n== questions schema ==")
row = cur.execute("SELECT sql FROM sqlite_master WHERE name='questions'").fetchone()
print(row[0] if row else "MISSING")

print("\n== explain_collections schema ==")
row = cur.execute("SELECT sql FROM sqlite_master WHERE name='explain_collections'").fetchone()
print(row[0] if row else "MISSING")

print("\n== counts ==")
print("questions:", cur.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
if "explain_collections" in tables:
    print("explain_collections:", cur.execute("SELECT COUNT(*) FROM explain_collections").fetchone()[0])
print("id range:", tuple(cur.execute("SELECT MIN(id), MAX(id) FROM questions").fetchone()))
print("journal_mode:", cur.execute("PRAGMA journal_mode").fetchone()[0])

print("\n== question_type distribution ==")
for r in cur.execute("SELECT question_type, COUNT(*) c FROM questions GROUP BY question_type ORDER BY c DESC"):
    print(f"  {r['question_type']}: {r['c']}")

print("\n== papers (top 10) ==")
if "papers" in tables:
    for r in cur.execute("SELECT id, title, subject FROM papers ORDER BY id LIMIT 10"):
        print(" ", dict(r))

print("\n== metadata analysis ==")
print("non-empty metadata:", cur.execute(
    "SELECT COUNT(*) FROM questions WHERE metadata IS NOT NULL AND TRIM(metadata) NOT IN ('', '{}')"
).fetchone()[0])
seen = {}
for (m,) in cur.execute(
    "SELECT metadata FROM questions WHERE metadata IS NOT NULL AND TRIM(metadata) NOT IN ('', '{}') LIMIT 400"
):
    try:
        d = json.loads(m)
        if isinstance(d, dict):
            for k in d:
                seen[k] = seen.get(k, 0) + 1
    except Exception:
        pass
print("metadata keys seen:", seen)

print("\n== option-like tables ==")
if "question_options" in tables:
    print(cur.execute("SELECT sql FROM sqlite_master WHERE name='question_options'").fetchone()[0])
    for r in cur.execute("SELECT * FROM question_options LIMIT 3"):
        print("  row:", str(dict(r))[:400])
if "options" in tables:
    print(cur.execute("SELECT sql FROM sqlite_master WHERE name='options'").fetchone()[0])
    for r in cur.execute("SELECT * FROM options LIMIT 3"):
        print("  row:", str(dict(r))[:400])
if "candidates" in tables:
    print(cur.execute("SELECT sql FROM sqlite_master WHERE name='candidates'").fetchone()[0])
    for r in cur.execute("SELECT * FROM candidates LIMIT 3"):
        print("  row:", str(dict(r))[:400])

print("\n== answer distribution (top 12) ==")
for r in cur.execute("SELECT answer, COUNT(*) c FROM questions GROUP BY answer ORDER BY c DESC LIMIT 12"):
    print(f"  {r['answer']!r}: {r['c']}")

print("\n== full sample: one question per type ==")
types = [r["question_type"] for r in cur.execute("SELECT DISTINCT question_type FROM questions")]
for t in types:
    r = cur.execute("SELECT * FROM questions WHERE question_type=? ORDER BY id LIMIT 1", (t,)).fetchone()
    if r:
        d = dict(r)
        print(f"--- type={t} (id={d['id']}) ---")
        for k, v in d.items():
            print(f"  {k} = {str(v)[:500]}")

print("\n== units schema + sample ==")
if "units" in tables:
    print(cur.execute("SELECT sql FROM sqlite_master WHERE name='units'").fetchone()[0])
    for r in cur.execute("SELECT id, title, unit_type, substr(passage,1,120) p FROM units ORDER BY id LIMIT 6"):
        print(" ", dict(r))

conn.close()
print("\nDONE")
