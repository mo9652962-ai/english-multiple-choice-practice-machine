#!/usr/bin/env python3
"""修复 v9.24 schema 迁移遗留：vocabulary_occurrences / vocabulary_reviews 外键
仍引用已 DROP 的 vocabulary_entries_old → 重建表（正确 FK → vocabulary_entries）
三库执行：backend/data + frontend/public + frontend/dist
"""
import sqlite3
import sys

DBS = [
    r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db",
    r"D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db",
    r"D:\english-multiple-choice-practice-machine\frontend\dist\question_bank.db",
]

FIX_SQL = """
-- 1. 重建 vocabulary_occurrences（正确 FK）
CREATE TABLE vocabulary_occurrences_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    surface_form TEXT NOT NULL,
    context_sentence TEXT NOT NULL DEFAULT '',
    context_before TEXT NOT NULL DEFAULT '',
    context_after TEXT NOT NULL DEFAULT '',
    unit_id INTEGER,
    question_id INTEGER,
    year INTEGER,
    unit_title TEXT NOT NULL DEFAULT '',
    unit_type TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entry_id) REFERENCES vocabulary_entries(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE SET NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE SET NULL
);
INSERT INTO vocabulary_occurrences_new
    (id, entry_id, surface_form, context_sentence, context_before, context_after,
     unit_id, question_id, year, unit_title, unit_type, created_at)
    SELECT id, entry_id, surface_form, context_sentence, context_before, context_after,
           unit_id, question_id, year, unit_title, unit_type, created_at
    FROM vocabulary_occurrences;
DROP TABLE vocabulary_occurrences;
ALTER TABLE vocabulary_occurrences_new RENAME TO vocabulary_occurrences;

-- 2. 重建 vocabulary_reviews（正确 FK）
CREATE TABLE vocabulary_reviews_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    rating INTEGER DEFAULT 0,
    reviewed_at TEXT,
    next_review_at TEXT,
    FOREIGN KEY (entry_id) REFERENCES vocabulary_entries(id) ON DELETE CASCADE
);
INSERT INTO vocabulary_reviews_new (id, entry_id, rating, reviewed_at, next_review_at)
    SELECT id, entry_id, rating, reviewed_at, next_review_at FROM vocabulary_reviews;
DROP TABLE vocabulary_reviews;
ALTER TABLE vocabulary_reviews_new RENAME TO vocabulary_reviews;
"""


def fix(db_path: str) -> int:
    conn = sqlite3.connect(db_path, timeout=60)
    try:
        # 检查是否真的有问题（外键引用 _old）
        bad = conn.execute(
            """SELECT COUNT(*) FROM sqlite_master
               WHERE type='table' AND name IN ('vocabulary_occurrences','vocabulary_reviews')
               AND sql LIKE '%vocabulary_entries_old%'"""
        ).fetchone()[0]
        if not bad:
            print(f"  {db_path}: FK 正常，跳过")
            return 0
        print(f"  {db_path}: 发现旧 FK 引用 → 修复中…")
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.executescript(FIX_SQL)
        conn.commit()
        # 验证
        bad_after = conn.execute(
            """SELECT COUNT(*) FROM sqlite_master
               WHERE type='table' AND name IN ('vocabulary_occurrences','vocabulary_reviews')
               AND sql LIKE '%vocabulary_entries_old%'"""
        ).fetchone()[0]
        print(f"  {db_path}: 修复完成，残留旧引用 {bad_after}")
        return bad_after
    except sqlite3.Error as e:
        print(f"  {db_path}: 修复失败 {e}")
        conn.rollback()
        return 1
    finally:
        conn.close()


def main() -> int:
    total = 0
    for db in DBS:
        total += fix(db)
    print(f"\n完成（残留问题 {total}）")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
