# -*- coding: utf-8 -*-
"""为批次4 发现的数据层问题题追加警示 note（经 patches.db 覆盖，幂等同步已入库行）。

- KEY_WARN：题库答案键与原文证据不符的题，追加「答案键疑点」警示。
- MISALIGN：题库题干/选项数组错位或题干残缺的题，追加「数据错位」说明。
note 追加后若超过 320 字上限则跳过并提示（人工处理）。
"""
import json
import os
import sqlite3

BASE = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen"
CONTENT_DIR = os.path.join(BASE, "content")
PATCHES_DB = os.path.join(BASE, "data", "patches.db")
MAIN_DB = r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db"
MAX_LEN = 320

# 答案键疑点：qid -> (库标字母, 解析认定的正确字母)
KEY_WARN = {
    1527: ("B", "A"),
    1532: ("B", "C"),
    1577: ("A", "D"),
    1582: ("C", "B"),
    1667: ("A", "D"),
    2083: ("C", "E"),
    2084: ("E", "C"),
}
KEY_WARN_SUFFIX = "注：题库答案键标为 %s，与原文证据不符，本题正确项应为 %s，解析按原文正确项撰写，建议核对题库答案键。"

# 题干/选项错位或残缺题
MISALIGN = [1523, 1524, 1528, 1529, 1530, 1531, 1533, 1534, 1535, 1568, 1569, 1570, 1571, 1573, 1574, 2066, 2085, 2086]
MISALIGN_SUFFIX = "注：本题题库题干与选项数据存在错位，解析按真题选项文本作答，字母请以题库核对为准。"


def chunk_file(qid: int) -> str:
    chunk_no = qid // 25 + 1
    batch_no = (chunk_no - 1) // 20 + 1
    return os.path.join(CONTENT_DIR, "batch%d" % batch_no, "chunk_%03d.json" % chunk_no)


def main() -> None:
    targets = {}
    for qid, (db_letter, real_letter) in KEY_WARN.items():
        targets[qid] = KEY_WARN_SUFFIX % (db_letter, real_letter)
    for qid in MISALIGN:
        targets[qid] = MISALIGN_SUFFIX

    conn = sqlite3.connect(PATCHES_DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS patches ("
        "question_id INTEGER NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL, "
        "PRIMARY KEY (question_id, field))"
    )
    rows = []
    skipped = []
    for qid, suffix in targets.items():
        path = chunk_file(qid)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        item = next(it for it in data["items"] if it["question_id"] == qid)
        old_note = str(item.get("note") or "")
        if ("错位" in old_note or "位移" in old_note) and qid in MISALIGN:
            skipped.append((qid, "已有错位说明"))
            continue
        new_note = old_note + suffix
        if len(new_note) > MAX_LEN:
            skipped.append((qid, "追加后 %d 字超限" % len(new_note)))
            continue
        rows.append((qid, "note", new_note))
    if rows:
        conn.executemany("INSERT OR REPLACE INTO patches (question_id, field, value) VALUES (?, ?, ?)", rows)
        conn.commit()
    main_conn = sqlite3.connect(MAIN_DB)
    synced = 0
    for qid, field, value in rows:
        cur = main_conn.execute(
            "UPDATE explain_collections SET content=? WHERE question_id=? AND fragment_type=?",
            (value, qid, field),
        )
        synced += cur.rowcount
    main_conn.commit()
    main_conn.close()
    conn.close()
    print("appended warnings: %d -> qids %s" % (len(rows), [r[0] for r in rows]))
    print("explain_collections synced: %d" % synced)
    if skipped:
        print("SKIPPED: %s" % skipped)
    print("APPEND NOTES DONE")


if __name__ == "__main__":
    main()
