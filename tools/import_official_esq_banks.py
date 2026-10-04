#!/usr/bin/env python3
"""墨题真题题库官方导入管道：
一键将 exports/esq_bundles/ 下的历年考研真题（2010-2026 英语一 17 卷、2010-2025 英语二 16 卷）
全量导入到指定的运行数据库（如 backend/data/question_bank.db 或 APPDATA），
完整保留题目、篇章、选项、标准答案与 AI 智能解析。
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.services.esq import load_esq_package, publish_package

DEFAULT_PACKAGES = [
    {
        "name": "2010-2026 考研英语（一）官方真题大包",
        "path": ROOT / "exports" / "esq_bundles" / "wssfk.postgraduate-english-one.2010-2026.esq",
        "profile_id": 1,
    },
    {
        "name": "2010-2025 考研英语（二）官方真题大包",
        "path": ROOT / "exports" / "esq_bundles" / "local.english-practice.postgraduate-english-two.2010-2025.esq",
        "profile_id": 5,
    },
]


def import_bundles(db_path: Path, replace_existing: bool = True) -> None:
    if not db_path.exists():
        print(f"错误: 目标数据库不存在: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"=== 目标数据库: {db_path} ===")
    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")

    resolutions = {}
    if replace_existing:
        resolutions = {"*": "replace_with_imported"}

    total_imported_papers = 0
    total_imported_questions = 0

    try:
        for pkg_meta in DEFAULT_PACKAGES:
            pkg_path = pkg_meta["path"]
            if not pkg_path.exists():
                print(f"  跳过: 题包文件未找到: {pkg_path.name}")
                continue

            print(f"\n正在加载与解析题包: {pkg_meta['name']} ({pkg_path.name})...")
            pkg_data = load_esq_package(pkg_path)

            print(f"开始导入到 Profile {pkg_meta['profile_id']}...")
            res = publish_package(
                conn,
                pkg_data,
                pkg_path,
                resolutions=resolutions,
                import_ai_labels=True,
                profile_id=pkg_meta["profile_id"],
            )
            conn.commit()

            paper_count = len(res.get("papers", []))
            q_count = sum(p.get("questionCount", 0) for p in res.get("papers", []))
            total_imported_papers += paper_count
            total_imported_questions += q_count

            print(f"  ✓ 成功导入 {paper_count} 套真题卷，共 {q_count} 道客观题（AI 标注同步导入: {res.get('labelsImported', 0)} 条）")

        cur = conn.cursor()
        total_p = cur.execute("SELECT COUNT(*) FROM papers WHERE deleted_at IS NULL").fetchone()[0]
        total_q = cur.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        print(f"\n=== 全部导入完成 ✅ ===")
        print(f"当前数据库现有总试卷数: {total_p} 套 | 客观题总数: {total_q} 题")

    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="墨题官方历年真题包一键导入管道")
    parser.add_argument(
        "--db",
        type=str,
        default=str(ROOT / "backend" / "data" / "question_bank.db"),
        help="目标 SQLite 数据库路径 (默认: backend/data/question_bank.db)",
    )
    parser.add_argument(
        "--appdata",
        action="store_true",
        help="同步导入到桌面版应用数据目录 (%APPDATA%/ai-english-practice-desktop/...)",
    )
    args = parser.parse_args()

    target = Path(args.db)
    if args.appdata:
        target = Path(os.path.expandvars(r"%APPDATA%\ai-english-practice-desktop\data\question_bank.db"))

    import_bundles(target)


if __name__ == "__main__":
    main()
