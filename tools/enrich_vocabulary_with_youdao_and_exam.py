#!/usr/bin/env python3
"""词汇库数据增强全流程：
1. 同步已有的高质量中英双语例句与音标
2. 从 82 卷历史真题中反向挂载真题例句到 vocabulary_occurrences
3. 对缺失项使用有道 API（5 并发 + 两阶段 + WAL 模式）抓取补充
4. 3 库同步（frontend/public, backend/data, %APPDATA%/...）
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PUB_DB = ROOT / "frontend" / "public" / "question_bank.db"
BAK_DB = ROOT / "frontend" / "public" / "question_bank.db.bak-20260920-1535"
BACKEND_DB = ROOT / "backend" / "data" / "question_bank.db"
DIST_DB = ROOT / "frontend" / "dist" / "question_bank.db"
APPDATA_DB = Path(os.path.expandvars(r"%APPDATA%\ai-english-practice-desktop\data\question_bank.db"))


def open_sqlite(path: Path, wal: bool = True) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=60.0)
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def step1_sync_existing_appdata_examples(pub_conn: sqlite3.Connection) -> int:
    """把 APPDATA 库中已有且高质量的 7,630+ 条例句/音标同步到主库"""
    if not APPDATA_DB.exists():
        print("APPDATA 数据库不存在，跳过第 1 阶段已有例句同步")
        return 0

    print("=== 阶段 1: 同步 APPDATA 库中已有高质量例句与音标 ===")
    app_conn = open_sqlite(APPDATA_DB, wal=False)
    app_rows = app_conn.execute(
        """SELECT lower(term), phonetic, contextual_meaning 
           FROM vocabulary_entries 
           WHERE contextual_meaning IS NOT NULL AND length(contextual_meaning) > 10"""
    ).fetchall()
    app_conn.close()

    app_map = {r[0]: (r[1], r[2]) for r in app_rows}
    print(f"  从 APPDATA 载入 {len(app_map)} 条已有语境例句")

    cur = pub_conn.cursor()
    cur.execute("SELECT id, lower(term), phonetic, contextual_meaning FROM vocabulary_entries")
    pub_rows = cur.fetchall()

    updated = 0
    for wid, term, ph, ex in pub_rows:
        need_ph = not ph
        need_ex = not ex or len(ex.strip()) < 12
        if (need_ph or need_ex) and term in app_map:
            src_ph, src_ex = app_map[term]
            set_clauses = []
            params = []
            if need_ph and src_ph:
                set_clauses.append("phonetic = ?")
                params.append(src_ph)
            if need_ex and src_ex:
                set_clauses.append("contextual_meaning = ?")
                params.append(src_ex)
            if set_clauses:
                params.append(wid)
                cur.execute(f"UPDATE vocabulary_entries SET {', '.join(set_clauses)} WHERE id = ?", params)
                updated += 1

    pub_conn.commit()
    print(f"  ✓ 阶段 1 完成：为主库同步补齐 {updated} 词")
    return updated


def step2_mount_real_exam_sentences(pub_conn: sqlite3.Connection) -> int:
    """从 82 卷历史真题库提取原句并反向挂载到 vocabulary_occurrences"""
    if not BAK_DB.exists():
        print("备份真题库不存在，跳过真题原句提取")
        return 0

    print("=== 阶段 2: 从 82 卷真题反向挂载真题例句到 vocabulary_occurrences ===")
    bak_conn = open_sqlite(BAK_DB, wal=False)
    bak_conn.row_factory = sqlite3.Row

    # 提取所有文章及题干
    units = bak_conn.execute(
        """SELECT u.id as unit_id, u.title as unit_title, u.unit_type, u.passage, p.year
           FROM units u JOIN papers p ON u.paper_id = p.id
           WHERE u.passage IS NOT NULL AND u.passage != ''"""
    ).fetchall()

    questions = bak_conn.execute(
        """SELECT q.id as question_id, q.stem, q.unit_id, u.title as unit_title, u.unit_type, p.year
           FROM questions q 
           JOIN units u ON q.unit_id = u.id 
           JOIN papers p ON u.paper_id = p.id
           WHERE q.stem IS NOT NULL AND q.stem != ''"""
    ).fetchall()
    bak_conn.close()

    raw_candidates = []
    for u in units:
        clean = re.sub(r"\s+", " ", u["passage"] or "")
        for s in re.split(r"(?<=[.?!])\s+", clean):
            s = s.strip()
            if 25 <= len(s) <= 240 and re.match(r"^[A-Z]", s):
                s_clean = re.sub(r"\{+blank:\d+\}+", "______", s)
                raw_candidates.append({
                    "sentence": s_clean,
                    "unit_id": u["unit_id"],
                    "question_id": None,
                    "year": u["year"],
                    "unit_title": u["unit_title"] or "",
                    "unit_type": u["unit_type"] or "",
                })

    for q in questions:
        clean = re.sub(r"\s+", " ", q["stem"] or "")
        if 20 <= len(clean) <= 240:
            raw_candidates.append({
                "sentence": clean,
                "unit_id": q["unit_id"],
                "question_id": q["question_id"],
                "year": q["year"],
                "unit_title": q["unit_title"] or "",
                "unit_type": q["unit_type"] or "",
            })

    print(f"  从 82 卷提取了 {len(raw_candidates)} 条真题候选原句，建立单词索引...")

    # 预分词建反向索引
    word_to_sentences: dict[str, list[dict[str, Any]]] = {}
    for item in raw_candidates:
        words = set(re.findall(r"\b[a-zA-Z]{3,}\b", item["sentence"].lower()))
        for w in words:
            if w not in word_to_sentences:
                word_to_sentences[w] = []
            if len(word_to_sentences[w]) < 5:  # 每词保留最多 5 条高质量原句
                word_to_sentences[w].append(item)

    # 查生词表
    cur = pub_conn.cursor()
    cur.execute("SELECT id, term, normalized_term, contextual_meaning FROM vocabulary_entries")
    vocab_entries = cur.fetchall()

    occurrences_to_insert = []
    meaning_updates = []

    for wid, term, norm, ctx in vocab_entries:
        key = (norm or term).strip().lower()
        matched = word_to_sentences.get(key, [])
        if matched:
            for m in matched[:2]:  # 写入前 2 条到 occurrences 表
                occurrences_to_insert.append((
                    wid,
                    term,
                    m["sentence"],
                    "",
                    "",
                    m["unit_id"],
                    m["question_id"],
                    m["year"],
                    m["unit_title"],
                    m["unit_type"],
                ))
            # 若 contextual_meaning 仍为空，用真题第一句作为默认语境句
            if not ctx or len(ctx.strip()) < 10:
                meaning_updates.append((matched[0]["sentence"][:280], wid))

    # 清空旧 occurrences 并批量写入
    cur.execute("DELETE FROM vocabulary_occurrences")
    cur.executemany(
        """INSERT INTO vocabulary_occurrences 
           (entry_id, surface_form, context_sentence, context_before, context_after, unit_id, question_id, year, unit_title, unit_type)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        occurrences_to_insert,
    )

    if meaning_updates:
        cur.executemany(
            "UPDATE vocabulary_entries SET contextual_meaning = ? WHERE id = ?",
            meaning_updates,
        )

    pub_conn.commit()
    print(f"  ✓ 阶段 2 完成：成功挂载 {len(occurrences_to_insert)} 条真题出现记录，补充了 {len(meaning_updates)} 条语境句")
    return len(occurrences_to_insert)


def fetch_from_youdao(word: str) -> tuple[str, str] | None:
    """调用有道免费 API 获取音标和双语例句"""
    try:
        url = f"https://dict.youdao.com/jsonapi?q={urllib.parse.quote(word)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8", "ignore"))

        ph = ""
        ec_word = data.get("ec", {}).get("word", [{}])
        if ec_word:
            ph = ec_word[0].get("ukphone") or ec_word[0].get("usphone") or ""

        ex = ""
        for s in data.get("blng_sents_part", {}).get("sentence-pair", []):
            en = (s.get("sentence") or "").strip()
            cn = (s.get("sentence-translation") or "").strip()
            if en and cn:
                ex = f"{en} {cn}"[:280]
                break

        if ph or ex:
            return ph, ex
        return None
    except Exception:
        return None


def step3_fill_missing_with_youdao_5_concurrent(pub_conn: sqlite3.Connection) -> int:
    """阶段 3：用有道 API 5 并发为依然缺失音标或例句的生词进行两阶段增强"""
    print("=== 阶段 3: 有道 API 5 并发补齐剩余生词（音标 + 双语例句）===")
    cur = pub_conn.cursor()
    words = cur.execute(
        """SELECT id, term FROM vocabulary_entries
           WHERE (phonetic IS NULL OR phonetic = '')
              OR (contextual_meaning IS NULL OR length(contextual_meaning) < 12)"""
    ).fetchall()

    total = len(words)
    print(f"  检测到 {total} 词仍需增强补全，启动 5 线程并发抓取...")
    if total == 0:
        print("  所有词汇均已有音标和例句，无需调用外部 API。")
        return 0

    # 阶段 3a: 并发抓取到内存
    fetched: dict[int, tuple[str, str]] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        future_to_wid = {
            pool.submit(fetch_from_youdao, item[1]): item[0] for item in words
        }
        for fut in as_completed(future_to_wid):
            wid = future_to_wid[fut]
            try:
                res = fut.result()
                if res:
                    fetched[wid] = res
            except Exception:
                pass
            done += 1
            if done % 50 == 0 or done == total:
                print(f"    抓取进度: {done}/{total}（成功命中: {len(fetched)}）", flush=True)

    print(f"  抓取完成，共获得 {len(fetched)} 词的新数据，开始批量写库...")

    # 阶段 3b: 单线程写库
    updated = 0
    for wid, (ph, ex) in fetched.items():
        for attempt in range(3):
            try:
                if ph:
                    cur.execute("UPDATE vocabulary_entries SET phonetic = ? WHERE id = ? AND (phonetic IS NULL OR phonetic = '')", (ph, wid))
                if ex:
                    cur.execute("UPDATE vocabulary_entries SET contextual_meaning = ? WHERE id = ? AND (contextual_meaning IS NULL OR length(contextual_meaning) < 12)", (ex, wid))
                updated += 1
                break
            except sqlite3.OperationalError:
                time.sleep(0.5)

    pub_conn.commit()
    print(f"  ✓ 阶段 3 完成：成功通过有道 API 补齐 {updated} 词")
    return updated


def step4_sync_all_databases() -> None:
    """阶段 4：三库全端同步（源库 -> 用户运行库 -> 构建发布库）"""
    print("=== 阶段 4: 三库全端同步 (3-DB Synchronization) ===")
    targets = [BACKEND_DB, APPDATA_DB, DIST_DB]

    src_conn = open_sqlite(PUB_DB, wal=False)
    phon_map = dict(src_conn.execute("SELECT term, phonetic FROM vocabulary_entries WHERE phonetic IS NOT NULL AND phonetic != ''").fetchall())
    ctx_map = dict(src_conn.execute("SELECT term, contextual_meaning FROM vocabulary_entries WHERE contextual_meaning IS NOT NULL AND length(contextual_meaning) > 10").fetchall())
    occurrences_data = src_conn.execute("SELECT entry_id, surface_form, context_sentence, context_before, context_after, unit_id, question_id, year, unit_title, unit_type FROM vocabulary_occurrences").fetchall()
    src_conn.close()

    for target in targets:
        if not target.exists():
            continue
        try:
            t_conn = open_sqlite(target, wal=True)
            t_cur = t_conn.cursor()
            
            # 更新音标
            p_cnt = 0
            for term, ph in phon_map.items():
                p_cnt += t_cur.execute("UPDATE vocabulary_entries SET phonetic = ? WHERE term = ? AND (phonetic IS NULL OR phonetic = '')", (ph, term)).rowcount
            
            # 更新例句
            c_cnt = 0
            for term, ctx in ctx_map.items():
                c_cnt += t_cur.execute("UPDATE vocabulary_entries SET contextual_meaning = ? WHERE term = ? AND (contextual_meaning IS NULL OR length(contextual_meaning) < 10)", (ctx, term)).rowcount

            # 同步 occurrences
            has_occ = t_conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vocabulary_occurrences'").fetchone()
            if has_occ:
                t_cur.execute("DELETE FROM vocabulary_occurrences")
                t_cur.executemany(
                    """INSERT INTO vocabulary_occurrences 
                       (entry_id, surface_form, context_sentence, context_before, context_after, unit_id, question_id, year, unit_title, unit_type)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    occurrences_data,
                )

            t_conn.commit()
            t_conn.close()
            print(f"  ✓ 已同步到 {target.name} ({target.parent.name}): 补齐音标 {p_cnt}, 补齐例句 {c_cnt}")
        except Exception as err:
            print(f"  ✗ 同步到 {target} 失败: {err}")


def print_final_audit() -> None:
    """阶段 5: 最终覆盖率审计"""
    print("\n" + "=" * 65)
    print("=== 词汇库增强最终覆盖率统计 ===")
    print("=" * 65)
    conn = open_sqlite(PUB_DB, wal=False)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM vocabulary_entries")
    total = c.fetchone()[0]

    c.execute("SELECT count(*) FROM vocabulary_entries WHERE phonetic IS NOT NULL AND phonetic != ''")
    ph_cnt = c.fetchone()[0]

    c.execute("SELECT count(*) FROM vocabulary_entries WHERE contextual_meaning IS NOT NULL AND length(contextual_meaning) >= 12")
    ctx_cnt = c.fetchone()[0]

    c.execute("SELECT count(*) FROM vocabulary_occurrences")
    occ_cnt = c.fetchone()[0]

    print(f"词汇库总容量: {total:,} 词")
    print(f"音标覆盖率  : {ph_cnt:,} / {total:,} ({ph_cnt / total * 100:.2f}%)")
    print(f"例句覆盖率  : {ctx_cnt:,} / {total:,} ({ctx_cnt / total * 100:.2f}%)")
    print(f"真题出现记录: {occ_cnt:,} 条")

    print("\n--- 抽查 5 个生词样本 ---")
    c.execute("SELECT term, phonetic, common_meaning, contextual_meaning FROM vocabulary_entries ORDER BY id DESC LIMIT 5")
    for r in c.fetchall():
        print(f"• 【{r[0]}】 /{r[1]}/ : {r[2]}")
        print(f"   语境例句: {r[3]}")
    conn.close()


def main() -> int:
    if not PUB_DB.exists():
        print(f"Error: 主库不存在: {PUB_DB}", file=sys.stderr)
        return 1

    pub_conn = open_sqlite(PUB_DB, wal=True)
    step1_sync_existing_appdata_examples(pub_conn)
    step2_mount_real_exam_sentences(pub_conn)
    step3_fill_missing_with_youdao_5_concurrent(pub_conn)
    pub_conn.close()

    step4_sync_all_databases()
    print_final_audit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
