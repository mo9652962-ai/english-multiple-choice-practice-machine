#!/usr/bin/env python3
"""词库脏词清洗（Gemini batch5 任务1 落地）— 2026-08-20
策略:
  - 拼错/变形 → 合并到已存在的正确词条（迁移 review/occurrences 引用，再删旧行）
  - 垃圾词（a./hur/gy）→ 删除（无任何引用）
  - 英式拼写 organiser / 专名（Tibet 等）→ 保留（非脏词）
事务执行 + 每步打印统计。
"""
import argparse
import sqlite3
import sys

DEFAULT_DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"

# 合并映射: 旧词 → 新词（先查新词 id）
MERGE = {
    "offers": "offer",
    "behavious": "behaviour",
    "proximately": "approximately",
    "chain stores": "chain store",
}
# 垃圾词（直接删除）
DELETE = ["a.", "hur", "gy"]

def main() -> int:
    parser = argparse.ArgumentParser(description="词库脏词清洗")
    parser.add_argument("--db", default=DEFAULT_DB, help="目标 SQLite 库")
    args = parser.parse_args()
    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    merged = 0
    for old, new in MERGE.items():
        old_rows = cur.execute(
            "SELECT id FROM vocabulary_entries WHERE term = ?", (old,)
        ).fetchall()
        new_rows = cur.execute(
            "SELECT id FROM vocabulary_entries WHERE term = ?", (new,)
        ).fetchall()
        if not old_rows or not new_rows:
            print(f"  SKIP {old!r}→{new!r}: 缺少源或目标 ({len(old_rows)}/{len(new_rows)})")
            continue
        old_id, new_id = old_rows[0][0], new_rows[0][0]
        if old_id == new_id:
            continue
        # 迁移引用（vocabulary_occurrences / vocabulary_reviews 按 entry_id 关联）
        for table in ("vocabulary_occurrences", "vocabulary_reviews"):
            moved = cur.execute(
                f"UPDATE OR IGNORE {table} SET entry_id = ? WHERE entry_id = ?",
                (new_id, old_id),
            ).rowcount
            print(f"  {old!r}→{new!r}: {table} 迁移 {moved} 行")
        cur.execute("DELETE FROM vocabulary_entries WHERE id = ?", (old_id,))
        merged += 1
        print(f"  {old!r} 已合并到 {new!r} (旧 id={old_id} 删除)")

    deleted = 0
    for word in DELETE:
        rows = cur.execute(
            "SELECT id FROM vocabulary_entries WHERE term = ?", (word,)
        ).fetchall()
        for rid in rows:
            # 有引用则不删（防悬空）
            refs = cur.execute(
                "SELECT COUNT(*) FROM vocabulary_occurrences WHERE entry_id = ?", (rid[0],)
            ).fetchone()[0]
            if refs:
                print(f"  {word!r} 有 {refs} 处引用——跳过删除")
                continue
            cur.execute("DELETE FROM vocabulary_entries WHERE id = ?", (rid[0],))
            deleted += 1
    print(f"  删除垃圾词 {deleted} 个")

    conn.commit()
    # 验证
    remaining = cur.execute(
        """SELECT term FROM vocabulary_entries
           WHERE term IN ('offers','behavious','proximately','chain stores','a.','hur','gy')"""
    ).fetchall()
    print(f"\n验证: 残留脏词 {len(remaining)}")
    for r in remaining:
        print(f"  {r[0]!r} 仍在")
    conn.close()
    print(f"完成: 合并 {merged} / 删除 {deleted}")
    return 1 if remaining else 0

if __name__ == "__main__":
    sys.exit(main())
