# -*- coding: utf-8 -*-
"""备份 question_bank.db（SQLite backup API，WAL 安全）→ question_bank.db.bak_explain_<日期>"""
import sqlite3
import os

SRC = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
DST = SRC + ".bak_explain_20260905"

src = sqlite3.connect(SRC)
dst = sqlite3.connect(DST)
src.backup(dst)
dst.close()

qc = dst = sqlite3.connect(DST)
n_q = qc.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
n_e = qc.execute("SELECT COUNT(*) FROM explain_collections").fetchone()[0]
qc.close()
src.close()

print(f"backup -> {DST}")
print(f"size = {os.path.getsize(DST)} bytes")
print(f"questions = {n_q}, explain_collections = {n_e}")
assert n_q == 2132 and n_e == 0, "backup content mismatch!"
print("BACKUP OK")
