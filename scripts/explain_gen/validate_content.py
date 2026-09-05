# -*- coding: utf-8 -*-
"""校验 content/batchN/chunk_NNN.json：结构、覆盖、长度。用法：python validate_content.py 1 2（批次号，缺省全部）"""
import json
import os
import sqlite3
import sys

BASE = r"D:\english-multiple-choice-practice-machine\scripts\explain_gen"
CHUNKS_DB = os.path.join(BASE, "data", "chunks.db")
CONTENT_DIR = os.path.join(BASE, "content")
FRAG_KEYS = ("long_sentence", "option", "keyword", "note")
MIN_LEN = 10
MAX_LEN = 320
NAME_RE = __import__("re").compile(r"chunk_([0-9]{3})\.json")


def load_expected() -> dict:
    conn = sqlite3.connect(CHUNKS_DB)
    out = {}
    for no, qids in conn.execute("SELECT no, qids FROM chunks ORDER BY no"):
        out[int(no)] = [int(x) for x in qids.split(",")]
    conn.close()
    return out


def check_file(path: str, chunk_no: int, expect_ids: list, problems: list) -> None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        problems.append("chunk %03d: JSON 解析失败 %s" % (chunk_no, e))
        return
    if data.get("chunk") not in (chunk_no, None):
        problems.append("chunk %03d: 文件内 chunk 字段=%r 不符" % (chunk_no, data.get("chunk")))
    items = data.get("items")
    if not isinstance(items, list):
        problems.append("chunk %03d: items 不是数组" % chunk_no)
        return
    got_ids = [it.get("question_id") for it in items if isinstance(it, dict)]
    if sorted(x for x in got_ids if isinstance(x, int)) != sorted(expect_ids):
        missing = set(expect_ids) - set(got_ids)
        extra = set(got_ids) - set(expect_ids)
        problems.append("chunk %03d: 覆盖不符 missing=%s extra=%s" % (chunk_no, sorted(missing), sorted(extra)))
        return
    if len(got_ids) != len(set(got_ids)):
        problems.append("chunk %03d: 有重复 question_id" % chunk_no)
    for it in items:
        qid = it["question_id"]
        for k in FRAG_KEYS:
            v = it.get(k)
            if not isinstance(v, str) or not v.strip():
                problems.append("chunk %03d q%d: %s 缺失或非字符串" % (chunk_no, qid, k))
                continue
            n = len(v.strip())
            if n < MIN_LEN:
                problems.append("chunk %03d q%d: %s 太短(%d字) %r" % (chunk_no, qid, k, n, v.strip()[:30]))
            elif n > MAX_LEN:
                problems.append("chunk %03d q%d: %s 太长(%d字) %r" % (chunk_no, qid, k, n, v.strip()[:40]))


def main() -> None:
    batches = [int(a) for a in sys.argv[1:]] or [1, 2, 3, 4, 5]
    expected = load_expected()
    problems = []
    done = 0
    for b in batches:
        bdir = os.path.join(CONTENT_DIR, "batch%d" % b)
        if not os.path.isdir(bdir):
            print("batch%d: 无内容目录" % b)
            continue
        for fn in sorted(os.listdir(bdir)):
            m = NAME_RE.fullmatch(fn)
            if not m:
                continue
            chunk_no = int(m.group(1))
            if chunk_no not in expected:
                problems.append("chunk %03d: chunks.db 中不存在" % chunk_no)
                continue
            if (chunk_no - 1) // 20 + 1 != b:
                problems.append("chunk %03d: 放在 batch%d 目录但应属 batch%d" % (chunk_no, b, (chunk_no - 1) // 20 + 1))
            done += 1
            before = len(problems)
            check_file(os.path.join(bdir, fn), chunk_no, expected[chunk_no], problems)
            print("batch%d chunk %03d: %s" % (b, chunk_no, "OK" if len(problems) == before else "FAIL"))
    print("\nscanned content files = %d" % done)
    if problems:
        print("\n%d PROBLEMS:" % len(problems))
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print("ALL CONTENT VALID")


if __name__ == "__main__":
    main()
