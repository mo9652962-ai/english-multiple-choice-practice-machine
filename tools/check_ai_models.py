"""检查 ai_profile_models 表结构"""
import sqlite3

conn = sqlite3.connect(r'D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db')
cols = [r[1] for r in conn.execute('PRAGMA table_info(ai_profile_models)').fetchall()]
print('ai_profile_models 字段:', cols)
rows = conn.execute('SELECT * FROM ai_profile_models').fetchall()
print(f'行数: {len(rows)}')
for r in rows[:6]:
    print(' ', r)
conn.close()
