"""同步后端词汇库到前端内置离线库"""
import shutil, sqlite3, os

src = r'D:\english-multiple-choice-practice-machine\backend\data\question_bank.db'
dst = r'D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db'

# 备份
bak = dst + '.bak-20260813'
if not os.path.exists(bak):
    shutil.copy2(dst, bak)
    print(f'备份: {bak}')

# 同步
shutil.copy2(src, dst)
print(f'已同步: {src} -> {dst}')

# 验证
conn = sqlite3.connect(dst)
total = conn.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0]
freq = conn.execute('SELECT COUNT(*) FROM vocabulary_entries WHERE manually_frequent=1').fetchone()[0]
hot = conn.execute("SELECT COUNT(*) FROM vocabulary_entries WHERE category LIKE '%热点%'").fetchone()[0]
size = os.path.getsize(dst) // 1024
print(f'新内置库: 总词={total} | 高频={freq} | 热点={hot} | 大小={size}KB')
conn.close()
