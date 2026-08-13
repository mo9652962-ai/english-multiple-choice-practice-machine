"""检查词汇表标签字段分布"""
import sqlite3

conn = sqlite3.connect(r'D:\english-multiple-choice-practice-machine\backend\data\question_bank.db')
print('=== manually_frequent 分布 ===')
for r in conn.execute('SELECT manually_frequent, COUNT(*) FROM vocabulary_entries GROUP BY manually_frequent').fetchall():
    print(f'  {r[0]!r}: {r[1]}')
print('=== study_status 分布 ===')
for r in conn.execute('SELECT study_status, COUNT(*) FROM vocabulary_entries GROUP BY study_status').fetchall():
    print(f'  {r[0]!r}: {r[1]}')
print('=== category 分布 ===')
for r in conn.execute('SELECT category, COUNT(*) FROM vocabulary_entries GROUP BY category').fetchall():
    print(f'  {r[0]!r}: {r[1]}')
print('=== encounter_count 分布 ===')
for r in conn.execute('SELECT encounter_count, COUNT(*) FROM vocabulary_entries GROUP BY encounter_count').fetchall()[:12]:
    print(f'  {r[0]!r}: {r[1]}')
conn.close()
