"""从测试备份提取正式真题 → 目标库（清空学习记录）
内容表（真题）: profiles, papers, units, questions, options
清空表（使用记录）: practice_*/wrong_*/learning_*/ai_*/exam_*/trash/revision
"""
import sqlite3

SRC = r'D:\english-multiple-choice-practice-machine\epm_app\question_bank.testdata.bak'
TARGETS = [
    r'D:\english-multiple-choice-practice-machine\epm_app\question_bank.db',
    r'D:\english-multiple-choice-practice-machine\backend\data\question_bank.db',
]

# 内容表（保留正式数据）
CONTENT_TABLES = [
    'question_bank_profiles', 'papers', 'units', 'questions', 'options',
]
# 记录表（清空——测试使用痕迹）
CLEAR_TABLES = [
    'practice_sessions', 'practice_answers', 'practice_answer_events',
    'practice_unit_submissions', 'wrong_stats', 'vocabulary_entries',
    'vocabulary_occurrences', 'vocabulary_reviews', 'ai_settings',
    'ai_profiles', 'ai_profile_models', 'ai_conversations', 'ai_messages',
    'learning_days', 'question_ai_labels', 'question_label_run_items',
    'wrong_analysis_reports', 'wrong_analysis_states',
    'import_jobs', 'trash_entries', 'revision_log', 'app_settings',
    'exam_sessions', 'exam_answers',
]

src = sqlite3.connect(SRC)

for dst_path in TARGETS:
    dst = sqlite3.connect(dst_path)
    dst.execute('PRAGMA foreign_keys=OFF')

    # 1. 清空目标库所有表
    tables = dst.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    for (t,) in tables:
        dst.execute(f'DELETE FROM [{t}]')

    # 2. 复制内容表（正式真题）
    copied = {}
    for t in CONTENT_TABLES:
        rows = src.execute(f'SELECT * FROM [{t}]').fetchall()
        if rows:
            cols = [d[1] for d in src.execute(f'PRAGMA table_info([{t}])').fetchall()]
            placeholders = ','.join('?' * len(cols))
            colstr = ','.join(f'[{c}]' for c in cols)
            dst.executemany(
                f'INSERT INTO [{t}] ({colstr}) VALUES ({placeholders})', rows
            )
        copied[t] = len(rows)

    # 3. 重置自增
    try:
        dst.execute("DELETE FROM sqlite_sequence")
    except Exception:
        pass
    dst.commit()

    # 4. 验证
    q = dst.execute('SELECT COUNT(*) FROM questions').fetchone()[0]
    print(f'=== {dst_path} ===')
    print(f'  真题: {q} 题, 试卷: {copied["papers"]}, 单元: {copied["units"]}, profile: {copied["question_bank_profiles"]}')
    dst.close()

src.close()
print('\n✅ 全部目标库已重建（正式真题 + 学习记录全清）')
