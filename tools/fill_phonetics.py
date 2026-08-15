#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_phonetics.py — 给 SQLite 词库批量补音标（有道免费 API）

用法:
    python fill_phonetics.py [--limit N] [--db PATH]

流程:
    1. 从 vocabulary_entries 选出 phonetic 为空的行 (id, term)
    2. 5 并发 ThreadPoolExecutor 调用有道 jsonapi 抓音标, 先全部抓到内存 dict
       (worker 不写数据库, 避免 SQLite 写锁竞争)
    3. 抓完后串行 UPDATE, 只更新 phonetic 为空的行
    4. 结束打印统计: 成功/失败数 + 失败词样例

特性:
    - 断点续传: 已有音标(非空)的行直接跳过, 重跑不重复抓
    - 网络异常每个词重试 3 次
    - SQLite 写库 OperationalError + sleep(1) 重试 3 次
    - --limit N 只处理前 N 个缺音标词(用于测试); 无参数跑全量
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

DEFAULT_DB = r"D:\english-multiple-choice-practice-machine\frontend\public\question_bank.db"
USER_AGENT = "Mozilla/5.0"
API_URL = "https://dict.youdao.com/jsonapi"
FETCH_WORKERS = 5
NETWORK_RETRIES = 3
DB_RETRIES = 3
REQUEST_TIMEOUT = 10
PROGRESS_EVERY = 200


def fetch_phonetic(term: str) -> str:
    """
    用有道 jsonapi 查单个词的音标, 返回英国音标(ukphone),
    为空则退回美国音标(usphone); 全部失败返回 ""。
    网络/解析异常按 NETWORK_RETRIES 重试。
    """
    url = API_URL + "?" + urllib.parse.urlencode({"q": term})
    last_err = None
    for attempt in range(NETWORK_RETRIES):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            data = json.loads(text)
            ec = data.get("ec") or {}
            words = ec.get("word") or []
            if not words:
                return ""  # 有道无该词条, 不重试(重试也无效)
            first = words[0]
            uk = (first.get("ukphone") or "").strip()
            if uk:
                return uk
            us = (first.get("usphone") or "").strip()
            if us:
                return us
            return ""
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, OSError, ValueError) as e:
            last_err = e
            if attempt < NETWORK_RETRIES - 1:
                time.sleep(1 + attempt)  # 1s, 2s 退避
    print(f"  [warn] 抓取失败(重试{NETWORK_RETRIES}次): {term!r} -> {last_err!r}", flush=True)
    return ""


def open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def load_missing(conn: sqlite3.Connection, limit: int | None):
    """返回缺音标行的 [(id, term), ...], 按 id 排序, 可选 --limit 截断。"""
    sql = (
        "SELECT id, term FROM vocabulary_entries "
        "WHERE phonetic IS NULL OR phonetic='' ORDER BY id"
    )
    rows = conn.execute(sql).fetchall()
    if limit is not None:
        rows = rows[:limit]
    return rows


def fetch_all(rows) -> dict:
    """
    并发抓取所有音标到内存 dict: {id: phonetic}。
    返回 (phonetic_by_id, failed_terms) 元组由调用方拆包。
    """
    phonetic_by_id: dict = {}
    failed_terms: list = []
    done = 0
    total = len(rows)

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        future_map = {pool.submit(fetch_phonetic, term): (wid, term) for wid, term in rows}
        for future in as_completed(future_map):
            wid, term = future_map[future]
            phone = future.result()  # fetch_phonetic 内部已处理异常, 不会抛
            phonetic_by_id[wid] = phone
            if not phone:
                failed_terms.append(term)
            done += 1
            if done % PROGRESS_EVERY == 0 or done == total:
                print(f"[fetch] {done}/{total}", flush=True)

    return phonetic_by_id, failed_terms


def update_all(conn: sqlite3.Connection, phonetic_by_id: dict) -> int:
    """
    串行 UPDATE, 只更新 phonetic 为空的行(天然只作用于待补词)。
    写库 OperationalError 时 sleep(1) 重试 DB_RETRIES 次。
    返回成功写入的行数。
    """
    updated = 0
    total = len(phonetic_by_id)
    done = 0
    for wid, phone in phonetic_by_id.items():
        if not phone:
            done += 1  # 抓取失败的词跳过写库, 保持空以便重跑
            if done % PROGRESS_EVERY == 0 or done == total:
                print(f"[write] {done}/{total} (含跳过 {done - updated})", flush=True)
            continue
        success = False
        for attempt in range(DB_RETRIES):
            try:
                with conn:  # 每条独立事务, 逐条提交, 天然支持断点续传
                    conn.execute(
                        "UPDATE vocabulary_entries SET phonetic=? WHERE id=?",
                        (phone, wid),
                    )
                success = True
                break
            except sqlite3.OperationalError as e:
                if attempt < DB_RETRIES - 1:
                    time.sleep(1)
                else:
                    print(f"  [warn] 写库失败 id={wid}: {e!r}", flush=True)
        if success:
            updated += 1
        done += 1
        if done % PROGRESS_EVERY == 0 or done == total:
            print(f"[write] {done}/{total}", flush=True)
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="给 SQLite 词库批量补音标(有道 API)")
    parser.add_argument("--limit", type=int, default=None,
                        help="只处理前 N 个缺音标词(测试用); 缺省跑全量")
    parser.add_argument("--db", default=DEFAULT_DB, help="SQLite 词库路径")
    args = parser.parse_args()

    if args.limit is not None and args.limit < 1:
        parser.error("--limit 必须是正整数")

    print(f"[db] {args.db}", flush=True)
    conn = open_db(args.db)
    try:
        rows = load_missing(conn, args.limit)
        total = len(rows)
        print(f"[scan] 缺音标词共 {total} 个"
              f"{' (--limit 截断)' if args.limit is not None else ''}", flush=True)
        if total == 0:
            print("[done] 没有需要补音标的词, 退出", flush=True)
            return 0

        print(f"[fetch] 开始并发抓取(workers={FETCH_WORKERS})...", flush=True)
        phonetic_by_id, failed_terms = fetch_all(rows)

        fetched_ok = sum(1 for p in phonetic_by_id.values() if p)
        print(f"[fetch] 抓取完成: 成功 {fetched_ok}, 失败 {len(failed_terms)}", flush=True)

        print("[write] 开始串行写库...", flush=True)
        updated = update_all(conn, phonetic_by_id)

        # 统计: 成功 = 抓取成功且写库成功; 失败 = 抓取失败或写库失败
        write_failed = fetched_ok - updated
        failed_total = len(failed_terms) + write_failed
        print("\n===== 统计 =====", flush=True)
        print(f"成功补音标: {updated} 个", flush=True)
        print(f"失败: {failed_total} 个 (抓取失败 {len(failed_terms)}, 写库失败 {write_failed})", flush=True)
        if failed_terms:
            print("失败词样例(前10): " + ", ".join(repr(t) for t in failed_terms[:10]), flush=True)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
