# -*- coding: utf-8 -*-
"""只读打印一个 chunk 的正文（供生成代理获取题目材料）。

用法：
  python print_chunk.py 3          # 打印 chunk 003 全文（末尾必有 CHUNK END 标记）
  python print_chunk.py 3 a        # 只打印前半（输出过大时分段看）
  python print_chunk.py 3 b        # 只打印后半
若输出里看不到「CHUNK NNN END」标记，说明 stdout 被截断，必须用 a/b 分段重看。
"""
import sqlite3
import sys

CHUNKS_DB = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen\data\chunks.db"


def load_chunks() -> dict:
    """读取 chunks.db 全部正文，返回 {chunk_no: body}。只读，无外部输入参与查询。"""
    conn = sqlite3.connect(CHUNKS_DB)
    rows = conn.execute("SELECT no, body FROM chunks ORDER BY no").fetchall()
    conn.close()
    return dict(rows)


def main() -> None:
    args = sys.argv[1:]
    if not args or not args[0].isdigit():
        print("usage: python print_chunk.py <chunk_no> [a|b]")
        sys.exit(2)
    no = int(args[0])
    if not 1 <= no <= 999:
        print("chunk_no out of range")
        sys.exit(2)
    part = args[1] if len(args) > 1 else ""
    bodies = load_chunks()
    if no not in bodies:
        print("chunk %03d not found" % no)
        sys.exit(1)
    body = bodies[no]
    if part == "a":
        half = len(body) // 2
        print(body[:half])
        print("\n[PART a END —— 后半用 `python print_chunk.py %d b` 查看]" % no)
    elif part == "b":
        half = len(body) // 2
        print(body[half:])
        print("\n[PART b END]")
    else:
        print(body)
    print("\n#### CHUNK %03d END (%d chars) ####" % (no, len(body)))


if __name__ == "__main__":
    main()
