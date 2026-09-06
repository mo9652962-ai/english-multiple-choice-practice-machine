# -*- coding: utf-8 -*-
"""修复 fix_bank_data 第一/二轮的 5 处 stem 链位残留（q1446/1447/1449/1569/1570）。"""
import shutil
import sqlite3

DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
BACKUP_SUFFIX = ".bak_keyfix3_20260906"

STEM_FIXES = [
    (1446, "attitude toward the influence",
     "From the text we know that some of consumers' habits are developed due to ."),
    (1447, "biased",
     "The author's attitude toward the influence of advertisement on people's habits is ."),
    (1449, "Even in the 1960s",
     "The practice of selecting so-called elite jurors prior to 1968 showed ."),
    (1569, "The quotation in Paragraph 4",
     "According to Paragraph 3, to be a successful employee, one has to ."),
    (1570, "According to the author, to reduce unemployment",
     "The quotation in Paragraph 4 explains that ."),
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
conn.close()
print("stem fixes applied: %s" % [p[0] for p in plans])
print("backup: %s%s" % (DB, BACKUP_SUFFIX))
print("FIX3 DONE")
