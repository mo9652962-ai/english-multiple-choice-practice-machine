"""任务 E（第 2 部分）：题库解析批量生成脚本。

从题库读取尚未生成解析的题目，按批（默认 20 题/批）调用现有
backend/app/services/ai_client.chat_completion 一次生成整批解析，
解析校验通过后事务批量写入 question_explanations 表。

特性：
- 断点续传：默认跳过已有解析的题目（--force 强制重生成）
- 限速：每批调用间隔 --interval 秒（默认 1s）
- 失败重试：单批重试 2 次（ai_client 内部另有 429/5xx 自动重试），
  仍失败则记录到 failed.log 并继续下一批
- 进度日志：当前批/总批、成功/失败计数、剩余时间估算（EMA）

用法示例（在项目根目录执行）：
  python scripts/batch_generate_explanations.py --dry-run          # 预览批次
  python scripts/batch_generate_explanations.py                    # 生成 public 库
  python scripts/batch_generate_explanations.py --db backend/data/question_bank.db
  python scripts/batch_generate_explanations.py --limit 40 --profile-id 2
  python scripts/batch_generate_explanations.py --force            # 全量重生成

Python 3.11，无第三方新增依赖（httpx/fastapi 均为后端已有）。
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
for path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

# 复用后端现有 AI 客户端（profile 管理、429/5xx 重试、JSON 解析）
from app.services.ai_client import (  # noqa: E402
    chat_completion,
    get_ai_profile,
    parse_json_response,
)
from prompts.explain_prompt import (  # noqa: E402
    EXPLAIN_RESPONSE_FORMAT,
    EXPLAIN_SYSTEM_PROMPT,
    build_explain_user_prompt,
    explanation_to_content,
    validate_explanations,
)

DEFAULT_DB = PROJECT_ROOT / "frontend" / "public" / "question_bank.db"
DEFAULT_LOG = PROJECT_ROOT / "logs" / "failed.log"
BATCH_RETRY_ATTEMPTS = 2  # 单批失败重试次数（不含首次调用）


# ──────────────────────────── 数据读取 ────────────────────────────

def fetch_pending_questions(
    connection: sqlite3.Connection,
    *,
    force: bool,
    limit: int | None,
) -> list[sqlite3.Row]:
    """未生成解析的题目（force 时全量），按 试卷→单元→题序 排列。"""
    params: list[Any] = []
    sql = """
        SELECT q.id, q.unit_id, q.number, q.stem, q.answer, q.question_type,
               u.title AS unit_title, u.unit_type, u.subtype, u.passage,
               p.title AS paper_title
        FROM questions AS q
        JOIN units AS u ON u.id = q.unit_id
        JOIN papers AS p ON p.id = u.paper_id
    """
    if not force:
        sql += """
        LEFT JOIN question_explanations AS e ON e.question_id = q.id
        WHERE e.question_id IS NULL
        """
    sql += " ORDER BY p.id, u.sequence, q.sequence"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return connection.execute(sql, params).fetchall()


def fetch_options(connection: sqlite3.Connection, question_ids: list[int]) -> dict[int, list[dict]]:
    if not question_ids:
        return {}
    placeholders = ",".join("?" for _ in question_ids)
    rows = connection.execute(
        f"""
        SELECT question_id, stable_key, content
        FROM options
        WHERE question_id IN ({placeholders})
        ORDER BY question_id, sequence
        """,
        question_ids,
    ).fetchall()
    result: dict[int, list[dict]] = {}
    for row in rows:
        result.setdefault(row["question_id"], []).append(
            {"key": row["stable_key"], "content": row["content"] or ""}
        )
    return result


def build_batches(
    rows: list[sqlite3.Row],
    options_map: dict[int, list[dict]],
    *,
    batch_size: int,
) -> list[dict[str, Any]]:
    """按单元顺序贪心打包为批：同批题目共享其涉及单元的篇章上下文。"""
    batches: list[dict[str, Any]] = []
    current: dict[str, Any] = {"units": {}, "questions": []}

    def flush() -> None:
        nonlocal current
        if current["questions"]:
            batches.append(
                {
                    "units": list(current["units"].values()),
                    "questions": current["questions"],
                }
            )
        current = {"units": {}, "questions": []}

    for row in rows:
        if row["unit_id"] not in current["units"]:
            current["units"][row["unit_id"]] = {
                "id": row["unit_id"],
                "title": row["unit_title"] or f"单元 {row['unit_id']}",
                "unit_type": row["unit_type"],
                "subtype": row["subtype"],
                "passage": row["passage"] or "",
            }
        current["questions"].append(
            {
                "id": row["id"],
                "unit_id": row["unit_id"],
                "number": row["number"],
                "stem": row["stem"],
                "answer": row["answer"],
                "question_type": row["question_type"],
                "options": options_map.get(row["id"], []),
            }
        )
        if len(current["questions"]) >= batch_size:
            flush()
    flush()
    return batches


# ──────────────────────────── 生成与写库 ────────────────────────────

def generate_batch(
    connection: sqlite3.Connection,
    batch: dict[str, Any],
    *,
    profile_id: int | None,
    model: str | None,
    max_tokens: int | None,
    passage_limit: int,
) -> list[dict[str, Any]]:
    """调用一次 chat_completion 生成本批解析，返回校验后的解析列表。"""
    messages = [
        {"role": "system", "content": EXPLAIN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_explain_user_prompt(
                batch["units"], batch["questions"], passage_limit=passage_limit
            ),
        },
    ]
    raw = chat_completion(
        connection,
        messages,
        response_format=EXPLAIN_RESPONSE_FORMAT,
        profile_id=profile_id,
        model=model,
        max_tokens=max_tokens,
    )
    parsed = parse_json_response(raw)
    expected_ids = {question["id"] for question in batch["questions"]}
    return validate_explanations(parsed, expected_ids)


def save_explanations(
    connection: sqlite3.Connection,
    explanations: list[dict[str, Any]],
    *,
    source_model: str,
) -> int:
    """事务批量提交（UPSERT：重生成时覆盖并刷新 updated_at）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = [
        (item["id"], explanation_to_content(item), source_model, now)
        for item in explanations
    ]
    with connection:  # 事务：本批要么全部落库，要么全部回滚
        connection.executemany(
            """
            INSERT INTO question_explanations
                (question_id, content, source_model, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                content = excluded.content,
                source_model = excluded.source_model,
                updated_at = excluded.updated_at
            """,
            payload,
        )
    return len(payload)


# ──────────────────────────── 日志与进度 ────────────────────────────

def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


def append_failed_log(log_path: Path, batch_index: int, batch: dict[str, Any], message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    question_ids = [str(item["id"]) for item in batch["questions"]]
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 批次 {batch_index} "
            f"题目[{','.join(question_ids)}] 失败: {message}\n"
        )


# ──────────────────────────── 主流程 ────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="题库解析批量生成（任务 E）")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"题库路径（默认 {DEFAULT_DB}）",
    )
    parser.add_argument("--batch-size", type=int, default=20, help="每批题目数（默认 20）")
    parser.add_argument("--limit", type=int, default=None, help="最多处理题目数（调试用）")
    parser.add_argument("--force", action="store_true", help="重生成已有解析（默认跳过）")
    parser.add_argument("--profile-id", type=int, default=None, help="AI 配置 ID（默认取启用配置）")
    parser.add_argument("--model", default=None, help="覆盖 profile 的模型名")
    parser.add_argument("--max-tokens", type=int, default=None, help="覆盖 profile 的 max_tokens")
    parser.add_argument(
        "--passage-limit", type=int, default=4000,
        help="每个单元篇章注入 prompt 的字符上限（默认 4000）",
    )
    parser.add_argument("--interval", type=float, default=1.0, help="批间限速秒数（默认 1）")
    parser.add_argument("--failed-log", default=str(DEFAULT_LOG), help=f"失败日志路径（默认 {DEFAULT_LOG}）")
    parser.add_argument("--dry-run", action="store_true", help="只列出批次计划，不调用模型不写库")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"错误：题库不存在: {db_path}", file=sys.stderr)
        return 2

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    # 幂等建表：与 backend/app/database.py 的 SCHEMA 保持一致，
    # 旧库未跑迁移脚本时这里自动补齐。
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS question_explanations (
            question_id INTEGER PRIMARY KEY,
            content TEXT NOT NULL,
            source_model TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_question_explanations_updated
            ON question_explanations(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_question_explanations_model
            ON question_explanations(source_model);
        """
    )
    connection.commit()

    rows = fetch_pending_questions(connection, force=args.force, limit=args.limit)
    total_existing = connection.execute(
        "SELECT COUNT(*) AS c FROM question_explanations"
    ).fetchone()["c"]
    total_questions = connection.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]
    if not rows:
        print(
            f"没有待处理的题目（题库 {total_questions} 题，已有解析 {total_existing} 题）。"
            "如需重生成请加 --force。"
        )
        return 0

    try:
        profile = get_ai_profile(connection, args.profile_id)
        source_model = args.model or profile["default_model"]
        profile_note = f"（profile #{profile['id']} {profile['name']}）"
    except LookupError:
        if args.dry_run:
            source_model, profile_note = "dry-run", "（未配置 AI，仅预览）"
        else:
            print("错误：库中没有可用的 AI 配置（ai_profiles 为空），请先在设置页配置。", file=sys.stderr)
            return 2

    options_map = fetch_options(connection, [row["id"] for row in rows])
    batches = build_batches(rows, options_map, batch_size=args.batch_size)

    print(
        f"题库: {db_path}\n"
        f"待生成: {len(rows)} 题 / {len(batches)} 批（每批 ≤ {args.batch_size} 题）"
        f" | 已有解析 {total_existing}/{total_questions} 题\n"
        f"模型: {source_model} {profile_note}"
    )
    if args.dry_run:
        for index, batch in enumerate(batches, 1):
            units = ", ".join(f"#{u['id']}{u['title'][:18]}" for u in batch["units"])
            print(
                f"  批 {index:>3}/{len(batches)}: {len(batch['questions'])} 题 "
                f"[{batch['questions'][0]['id']}~{batch['questions'][-1]['id']}] 单元 {units}"
            )
        print("dry-run 结束，未调用模型、未写库。")
        return 0

    log_path = Path(args.failed_log)
    succeeded = failed_batches = 0
    done_questions = 0
    avg_batch_seconds: float | None = None  # EMA 用于剩余时间估算
    started_at = time.monotonic()

    for index, batch in enumerate(batches, 1):
        batch_started = time.monotonic()
        explanations: list[dict[str, Any]] | None = None
        last_error = ""
        for attempt in range(1 + BATCH_RETRY_ATTEMPTS):
            try:
                explanations = generate_batch(
                    connection,
                    batch,
                    profile_id=args.profile_id,
                    model=args.model,
                    max_tokens=args.max_tokens,
                    passage_limit=args.passage_limit,
                )
                break
            except (ValueError, json.JSONDecodeError, sqlite3.Error) as error:
                last_error = str(error)[:300]
                if attempt < BATCH_RETRY_ATTEMPTS:
                    time.sleep(2.0)  # 重试前短暂退避
        batch_seconds = time.monotonic() - batch_started
        avg_batch_seconds = (
            batch_seconds if avg_batch_seconds is None
            else 0.7 * avg_batch_seconds + 0.3 * batch_seconds
        )

        if explanations is None:
            failed_batches += 1
            append_failed_log(log_path, index, batch, last_error)
            print(
                f"[{index}/{len(batches)}] 失败（已重试 {BATCH_RETRY_ATTEMPTS} 次，记录到 {log_path}）"
                f"：{last_error}"
            )
        else:
            saved = save_explanations(connection, explanations, source_model=source_model)
            succeeded += saved
            done_questions += len(batch["questions"])

        remaining_batches = len(batches) - index
        eta = (
            format_duration(avg_batch_seconds * remaining_batches)
            if avg_batch_seconds and remaining_batches else "—"
        )
        print(
            f"[{index}/{len(batches)}] 本批 {len(batch['questions'])} 题 | "
            f"累计成功 {succeeded} / 待生成 {len(rows)} | 失败批次 {failed_batches} | "
            f"本批耗时 {format_duration(batch_seconds)} | 预计剩余 {eta}"
        )

        if index < len(batches) and args.interval > 0:
            time.sleep(args.interval)

    elapsed = time.monotonic() - started_at
    print(
        f"\n完成：成功 {succeeded} 题，失败 {failed_batches} 批"
        f"（涉及题目见 {log_path}），总耗时 {format_duration(elapsed)}。"
    )
    connection.close()
    return 0 if failed_batches == 0 else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\n已中断。已成功批次均已提交落库，重新运行将自动跳过它们（断点续传）。")
        raise SystemExit(130)
