"""对比两库表结构"""
import sqlite3

for name, path in [('内置', r'D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db'),
                   ('后端', r'D:\english-multiple-choice-practice-machine\backend\data\question_bank.db')]:
    conn = sqlite3.connect(path)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f'=== {name} 库表: {len(tables)} 个 ===')
    for t in tables:
        n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        print(f'  {t}: {n} 行')
    conn.close()
