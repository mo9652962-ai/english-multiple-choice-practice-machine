"""同步 phonetic 字段到其他词库副本（源库 → 用户库 + 构建库）。

用法: python tools/sync_phonetics.py
"""
import os
import sqlite3
import sys

SRC = r"D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db"
TARGETS = [
    os.path.join(os.environ.get("APPDATA", ""), "ai-english-practice-desktop", "data", "question_bank.db"),
    r"D:\english-multiple-choice-practice-machine\frontend\dist\question_bank.db",
]


def main() -> int:
    if not os.path.exists(SRC):
        print(f"源库不存在: {SRC}")
        return 1

    src = sqlite3.connect(SRC, timeout=60)
    src.execute("PRAGMA busy_timeout=30000")
    # 读映射 term -> phonetic
    mapping = {}
    for term, ph in src.execute(
        "SELECT term, phonetic FROM vocabulary_entries WHERE phonetic IS NOT NULL AND phonetic != ''"
    ):
        mapping[term] = ph
    src.close()
    print(f"源库映射: {len(mapping)} 个词条")

    for target in TARGETS:
        if not os.path.exists(target):
            print(f"  SKIP (不存在): {target}")
            continue
        conn = sqlite3.connect(target, timeout=60)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        cur = conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM vocabulary_entries")
        except sqlite3.OperationalError:
            print(f"  SKIP (无 vocabulary_entries): {target}")
            conn.close()
            continue

        updated = 0
        for term, ph in mapping.items():
            for _ in range(3):
                try:
                    cur.execute(
                        "UPDATE vocabulary_entries SET phonetic=? WHERE term=? AND (phonetic IS NULL OR phonetic='')",
                        (ph, term),
                    )
                    updated += cur.rowcount
                    break
                except sqlite3.OperationalError:
                    import time
                    time.sleep(1)
        conn.commit()
        conn.close()
        print(f"  ✅ {target}: 更新 {updated} 词")

    return 0


if __name__ == "__main__":
    sys.exit(main())
