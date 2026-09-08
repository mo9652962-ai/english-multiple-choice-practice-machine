# -*- coding: utf-8 -*-
"""三库同步②：把 explain_collections 增量同步到种子库与在线库。

- 仅同步目标库 questions 表中已存在的 question_id（交集），避免孤儿行；
- 幂等：按 (question_id, fragment_type) 去重，已有的不覆盖（保护端上用户自藏数据）；
- 目标库缺表则建表（内联字面量 SQL）；user_id 列由应用运行时迁移幂等补齐，本脚本不依赖；
- 读后端库行 → Python 求交集 → executemany 参数化插入。
"""
import os
import sqlite3

BACKEND = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"


def load_backend_rows() -> list:
    conn = sqlite3.connect(BACKEND)
    rows = conn.execute(
        "SELECT question_id, fragment_type, content, source FROM explain_collections"
    ).fetchall()
    conn.close()
    return rows


def sync_one(tag: str, path: str, backend_rows: list) -> str:
    if not os.path.exists(path):
        return "%s: SKIP(文件不存在) %s" % (tag, path)
    conn = sqlite3.connect(path)
    has_table = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='explain_collections'"
    ).fetchone()[0]
    if not has_table:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS explain_collections ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " question_id INTEGER NOT NULL,"
            " fragment_type TEXT NOT NULL DEFAULT 'note',"
            " content TEXT NOT NULL,"
            " source TEXT DEFAULT 'deep-explain',"
            " created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')), "
            " FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE)"
        )
        conn.commit()
    qids = {r[0] for r in conn.execute("SELECT id FROM questions")}
    existing = {
        (r[0], r[1])
        for r in conn.execute("SELECT question_id, fragment_type FROM explain_collections")
    }
    todo = [
        (q, f, c, s)
        for (q, f, c, s) in backend_rows
        if q in qids and (q, f) not in existing
    ]
    conn.executemany(
        "INSERT INTO explain_collections (question_id, fragment_type, content, source) VALUES (?, ?, ?, ?)",
        todo,
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM explain_collections").fetchone()[0]
    qmax = conn.execute("SELECT MAX(id) FROM questions").fetchone()[0]
    covered = conn.execute(
        "SELECT COUNT(DISTINCT question_id) FROM explain_collections WHERE question_id<=?",
        (qmax,),
    ).fetchone()[0]
    conn.close()
    return "%s: 插入 %d 行 -> 共 %d 行；题面覆盖 %d 题（库内最大题号 %d）" % (
        tag, len(todo), after, covered, qmax)


def main() -> None:
    backend_rows = load_backend_rows()
    print("backend rows=%d" % len(backend_rows))
    print(sync_one("seed", r"D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db", backend_rows))
    print(sync_one("online", r"%USERPROFILE%\AppData\Roaming\ai-english-practice-desktop\data\question_bank.db", backend_rows))
    print("SYNC THREE DBS DONE")


if __name__ == "__main__":
    main()
