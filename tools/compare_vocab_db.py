"""对比内置离线库 vs 后端数据库"""
import sqlite3, os

db_internal = r'D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db'
db_backend = r'D:\english-multiple-choice-practice-machine\backend\data\question_bank.db'

for name, path in [('内置(手机)', db_internal), ('后端(桌面)', db_backend)]:
    if not os.path.exists(path):
        print(f'{name}: ❌ 不存在')
        continue
    conn = sqlite3.connect(path)
    try:
        total = conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0]
        freq = conn.execute('SELECT COUNT(*) FROM vocabulary_entries WHERE manually_frequent=1').fetchone()[0]
        enc2 = conn.execute('SELECT COUNT(*) FROM vocabulary_entries WHERE encounter_count>=2').fetchone()[0]
        hot = conn.execute("SELECT COUNT(*) FROM vocabulary_entries WHERE category LIKE '%热点%'").fetchone()[0]
        print(f'{name}: 总词={total} | 高频标记={freq} | encounter>=2={enc2} | 热点={hot}')
    except Exception as e:
        print(f'{name}: 错误 {e}')
    conn.close()

# 内置库文件信息
print(f'\n内置库大小: {os.path.getsize(db_internal)//1024}KB | 修改时间: {os.path.getmtime(db_internal)}')
print(f'后端库大小: {os.path.getsize(db_backend)//1024}KB | 修改时间: {os.path.getmtime(db_backend)}')
