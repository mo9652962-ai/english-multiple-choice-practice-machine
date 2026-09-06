# -*- coding: utf-8 -*-
"""修复 fix_bank_data 第一轮的 5 处 stem 残留问题（链式引用错位 + 人名多余句号）。"""
import shutil
import sqlite3

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
BACKUP_SUFFIX = ".bak_keyfix2_20260906"

# (qid, 当前 stem 必含子串, 新 stem)
STEM_FIXES = [
    (1444, "Which of the following",
     "Bottled water, chewing gum and skin moisturizers are mentioned in Paragraph 5 so as to ."),
    (1445, "From the text we know",
     "Which of the following does NOT belong to products that help create people's habits?"),
    (1450, "they tended to evade",
     "Even in the 1960s, women were seldom on the jury list in some states because ."),
    (2085, "Kelley .", "Katie Kelley"),
    (2086, "Levine .", "Mayghin Levine"),
]

conn = sqlite3.connect(DB)
problems = []
plans = []
for qid, needle, new_stem in STEM_FIXES:
    row = conn.execute("SELECT stem FROM questions WHERE id=?", (qid,)).fetchone()
    if row is None:
        problems.append("q%d 不存在" % qid)
    elif needle not in row[0]:
        problems.append("q%d 锚点失配: %r 不含 %r" % (qid, row[0][:60], needle))
    else:
        plans.append((qid, new_stem))
if problems:
    conn.close()
    print("ABORT: %s" % "; ".join(problems))
    raise SystemExit(1)
shutil.copyfile(DB, DB + BACKUP_SUFFIX)
for qid, new_stem in plans:
    conn.execute("UPDATE questions SET stem=? WHERE id=?", (new_stem, qid))
conn.commit()
tail = conn.execute("SELECT passage FROM units WHERE id=203").fetchone()[0]
conn.close()
print("stem fixes applied: %s" % [p[0] for p in plans])
print("backup: %s" % DB + BACKUP_SUFFIX)
print("UNIT 203 PASSAGE TAIL: %r" % tail[-200:])
print("FIX2 DONE")
