"""前端离线库同步迁移（任务 E 收尾·问题 1）。

背景：后端启动时 initialize_database() 只迁移 backend/data/question_bank.db；
打包进 APK/PWA 的 frontend/public/question_bank.db 不会自动迁移，导致离线端
缺少新表（如 question_explanations）。且离线模式首次启动会把该文件 seed 进
IndexedDB，之后一直用旧副本——即使打包文件更新，存量设备也不会拿到新表。

本脚本提供两层机制（单一事实来源 = backend/app/database.py）：

  层 1【构建期·源头保证】
     对目标库执行与 initialize_database() 完全相同的迁移
     （executescript(SCHEMA) + _run_migrations(conn)，全幂等）。
     以后在 database.py 新增表/列，重跑本脚本即可让前端库自动跟上。

  层 2【运行期·存量设备保证】
     迁移后从 sqlite_master 导出结构快照，生成幂等 DDL 清单
     frontend/public/offline_migrations.json（随前端一起打包）。
     前端 db.ts 启动时按清单检测缺失对象并补建（见
     frontend/src/services/offline-migrations.ts），旧 IndexedDB 副本自动升级。

用法：
  python scripts/migrate_frontend_db.py            # 迁移前端库 + 生成清单
  python scripts/migrate_frontend_db.py --all      # 同时迁移 backend/data 库
  python scripts/migrate_frontend_db.py --db PATH  # 迁移指定库
  python scripts/migrate_frontend_db.py --check    # 只检查差异，不修改

幂等性：CREATE ... IF NOT EXISTS / INSERT ... WHERE NOT EXISTS /
        _ensure_column（列存在即跳过）/ papers 重建仅针对旧 UNIQUE year schema。
        已是新结构的库重跑零副作用。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SCHEMA, _run_migrations  # noqa: E402

FRONTEND_DB = PROJECT_ROOT / "frontend" / "public" / "question_bank.db"
BACKEND_DB = PROJECT_ROOT / "backend" / "data" / "question_bank.db"
DEFAULT_MANIFEST = PROJECT_ROOT / "frontend" / "public" / "offline_migrations.json"


def _open_db(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _schema_objects(connection: sqlite3.Connection) -> set[tuple[str, str]]:
    """当前库中的用户对象集合 {(type, name)}。"""
    rows = connection.execute(
        """
        SELECT type, name FROM sqlite_master
        WHERE name NOT LIKE 'sqlite_%'
        """
    ).fetchall()
    return {(row["type"], row["name"]) for row in rows}


def migrate_database(path: Path, *, check_only: bool = False) -> list[str]:
    """对单个库执行与 initialize_database() 等价的幂等迁移，返回补建对象描述。"""
    if not path.exists():
        raise FileNotFoundError(f"数据库不存在: {path}")
    connection = _open_db(path)
    before = _schema_objects(connection)
    if check_only:
        connection.close()
        # 检查模式：对比 SCHEMA 声明的对象与库内现状（只报告，不执行）
        probe = sqlite3.connect(":memory:")
        probe.executescript(SCHEMA)
        raw = probe.execute(
            """
            SELECT type, name FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            """
        ).fetchall()
        declared = {(r[0], r[1]) for r in raw}
        probe.close()
        missing = sorted(f"{t} {n}" for t, n in declared - before if t in ("table", "index"))
        return missing

    connection.executescript(SCHEMA)
    _run_migrations(connection)
    connection.commit()
    after = _schema_objects(connection)
    connection.close()
    created = sorted(f"{t} {n}" for t, n in after - before if t in ("table", "index"))
    return created


def export_manifest(source_db: Path, output: Path) -> dict:
    """从迁移后的库导出幂等 DDL 清单（前端运行时迁移用）。

    sqlite_master.sql 是规范化后的 CREATE 语句（无 IF NOT EXISTS），
    导出时补回 IF NOT EXISTS 使其可安全重放；自动索引（sql 为 NULL）跳过。
    """
    connection = _open_db(source_db)
    rows = connection.execute(
        """
        SELECT type, name, sql FROM sqlite_master
        WHERE type IN ('table', 'index')
          AND name NOT LIKE 'sqlite_%'
          AND sql IS NOT NULL
        ORDER BY type, name
        """
    ).fetchall()
    connection.close()

    objects: list[dict[str, str]] = []
    for row in rows:
        sql = row["sql"].strip()
        if row["type"] == "table":
            idempotent = sql.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
        else:
            idempotent = sql.replace("CREATE INDEX ", "CREATE INDEX IF NOT EXISTS ", 1)
        objects.append({"type": row["type"], "name": row["name"], "sql": idempotent})

    fingerprint = hashlib.sha1(
        "\n".join(f"{o['type']}:{o['name']}" for o in objects).encode("utf-8")
    ).hexdigest()[:12]
    manifest = {
        "version": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fingerprint": fingerprint,
        "object_count": len(objects),
        "objects": objects,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="前端离线库同步迁移（幂等）")
    parser.add_argument("--db", default=None, help="指定库路径（默认前端 public 库）")
    parser.add_argument("--all", action="store_true", help="同时迁移 backend/data 库")
    parser.add_argument("--check", action="store_true", help="只检查缺失对象，不修改")
    parser.add_argument(
        "--manifest", default=str(DEFAULT_MANIFEST),
        help=f"离线迁移清单输出路径（默认 {DEFAULT_MANIFEST}）",
    )
    parser.add_argument("--no-manifest", action="store_true", help="不生成/更新清单")
    args = parser.parse_args()

    targets = [Path(args.db)] if args.db else [FRONTEND_DB]
    if args.all:
        targets.append(BACKEND_DB)

    failed = False
    for target in targets:
        try:
            if args.check:
                missing = migrate_database(target, check_only=True)
                status = "缺少: " + ", ".join(missing) if missing else "已最新"
                print(f"[check] {target}: {status}")
                continue
            created = migrate_database(target)
            note = f"补建 {len(created)} 个对象: {', '.join(created)}" if created else "已是最新（无变更）"
            print(f"[migrate] {target}: {note}")
        except (FileNotFoundError, sqlite3.Error, RuntimeError) as error:
            print(f"[migrate] {target}: 失败 — {error}", file=sys.stderr)
            failed = True

    if args.check:
        return 1 if failed else 0
    if not args.no_manifest and not failed:
        manifest = export_manifest(FRONTEND_DB, Path(args.manifest))
        print(
            f"[manifest] {args.manifest}: {manifest['object_count']} objects, "
            f"fingerprint {manifest['fingerprint']}"
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
