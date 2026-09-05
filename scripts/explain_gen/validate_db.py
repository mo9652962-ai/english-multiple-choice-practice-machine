# -*- coding: utf-8 -*-
"""explain_collections 全量验证（任务包第 4 节的三条 SQL + 扩展检查）。用法：python validate_db.py [期望题数]"""
import sqlite3
import sys

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
conn = sqlite3.connect(DB)

n, distinct = conn.execute("SELECT COUNT(*), COUNT(DISTINCT question_id) FROM explain_collections").fetchone()
print("[1] COUNT(*)=%d, COUNT(DISTINCT question_id)=%d" % (n, distinct))
if len(sys.argv) > 1:
    expect_q = int(sys.argv[1])
    print("    期望覆盖题数=%d -> %s" % (expect_q, "OK" if distinct == expect_q else "MISMATCH"))

print("\n[2] 每题 fragment 数分布（期望全部=4，任务底线>=3）:")
bad = 0
for cnt, qs in conn.execute(
    "SELECT c, COUNT(*) FROM (SELECT question_id AS qid, COUNT(*) AS c FROM explain_collections GROUP BY question_id) GROUP BY c ORDER BY c"
):
    print("    %d 条/题: %d 题" % (cnt, qs))
    if cnt < 3:
        bad += qs
rows = conn.execute(
    "SELECT question_id, COUNT(*) FROM explain_collections GROUP BY question_id HAVING COUNT(*) < 3"
).fetchall()
print("    HAVING COUNT(*)<3 行数=%d（期望 0）%s" % (len(rows), rows[:10] if rows else ""))

n_short = conn.execute("SELECT COUNT(*) FROM explain_collections WHERE LENGTH(TRIM(content)) < 10").fetchone()[0]
print("\n[3] LENGTH(TRIM(content))<10 行数=%d（期望 0）" % n_short)

n_long = conn.execute("SELECT COUNT(*) FROM explain_collections WHERE LENGTH(content) > 320").fetchone()[0]
print("[4] content>320 字符行数=%d（参考，任务要求 50~200 字）" % n_long)
if n_long:
    for qid, ft, ln in conn.execute("SELECT question_id, fragment_type, LENGTH(content) FROM explain_collections WHERE LENGTH(content) > 320 LIMIT 10"):
        print("    q%d %s %d字" % (qid, ft, ln))

print("\n[5] fragment_type 取值:")
for ft, c in conn.execute("SELECT fragment_type, COUNT(*) FROM explain_collections GROUP BY fragment_type"):
    print("    %s: %d" % (ft, c))

n_orphan = conn.execute(
    "SELECT COUNT(*) FROM explain_collections c WHERE NOT EXISTS (SELECT 1 FROM questions q WHERE q.id=c.question_id)"
).fetchone()[0]
print("\n[6] 孤儿 question_id（题库中不存在）=%d（期望 0）" % n_orphan)

print("\n[7] source 取值:")
for s, c in conn.execute("SELECT source, COUNT(*) FROM explain_collections GROUP BY source"):
    print("    %s: %d" % (s, c))

n_pairs = conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT question_id, fragment_type FROM explain_collections)").fetchone()[0]
print("\n[8] (question_id, fragment_type) 去重后=%d，总行=%d -> %s" % (n_pairs, n, "无重复" if n_pairs == n else "有重复!"))

total_q = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
print("\n[9] 题库总题数=%d，已覆盖=%d，未覆盖=%d" % (total_q, distinct, total_q - distinct))
conn.close()
print("\nVALIDATE DONE")
