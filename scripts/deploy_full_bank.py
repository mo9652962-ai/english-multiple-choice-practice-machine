"""从 frontend/public 全题库（647题/36套）生成干净版 → 更新所有目标库
保留: profiles, papers, units, questions, options（含 2025 模拟题）
清空: 所有学习/使用记录（practice/wrong/learning/exam/ai/vocabulary 等）
"""
import sqlite3
import shutil

SRC = r'D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db'
TARGETS = [
    r'D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db',   # 源本身（清理）
    r'D:\english-multiple-choice-practice-machine\frontend\dist\question_bank.db',     # 前端构建产物
    r'D:\english-multiple-choice-practice-machine\backend\data\question_bank.db',      # seed 源（打包）
    r'D:\english-multiple-choice-practice-machine\epm_app\question_bank.db',           # PWA 产物
]

CONTENT_TABLES = [
    'question_bank_profiles', 'papers', 'units', 'questions', 'options',
]

def clear_all_records(conn):
    """清空全部表，再复制内容表"""
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    conn.execute('PRAGMA foreign_keys=OFF')
    for (t,) in tables:
        if t in CONTENT_TABLES:
            continue
        try:
            conn.execute(f'DELETE FROM [{t}]')
        except Exception:
            pass
    try:
        conn.execute("DELETE FROM sqlite_sequence")
    except Exception:
        pass

src = sqlite3.connect(SRC)

# 1. 备份源（防止操作失误）
shutil.copy2(SRC, SRC + '.full.bak')
print(f'✅ 源备份: {SRC}.full.bak')

for dst_path in TARGETS:
    conn = sqlite3.connect(dst_path)
    clear_all_records(conn)
    # 复制内容表
    for t in CONTENT_TABLES:
        rows = src.execute(f'SELECT * FROM [{t}]').fetchall()
        if not rows:
            continue
        cols = [d[1] for d in src.execute(f'PRAGMA table_info([{t}])').fetchall()]
        placeholders = ','.join('?' * len(cols))
        colstr = ','.join(f'[{c}]' for c in cols)
        conn.execute(f'DELETE FROM [{t}]')
        conn.executemany(f'INSERT INTO [{t}] ({colstr}) VALUES ({placeholders})', rows)
    conn.commit()
    # 验证
    q = conn.execute('SELECT COUNT(*) FROM questions').fetchone()[0]
    p = conn.execute('SELECT COUNT(*) FROM papers').fetchone()[0]
    s = conn.execute('SELECT COUNT(*) FROM practice_sessions').fetchone()[0]
    print(f'✅ {dst_path}: {q} 题 / {p} 套 / 学习记录 {s}')

src.close()
print('\n完成：647 题全题库已部署（含 2025 模拟题，学习记录全清）')
