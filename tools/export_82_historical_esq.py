#!/usr/bin/env python3
"""把备份库 (question_bank.db.bak-20260920-1535) 中的 82 卷真题抽离归档，
批量生成带有规范 metadata 的 ESQ 题包集合，并通过官方 ESQ 校验器验证。
"""

from __future__ import annotations

import io
import json
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.esq import (
    load_esq_package,
    _blocks_from_unit,
    EsqValidationError,
)

DB_PATH = ROOT / "frontend" / "public" / "question_bank.db.bak-20260920-1535"
OUTPUT_DIR = ROOT / "exports" / "esq_bundles"


def export_package_from_db(
    conn: sqlite3.Connection,
    pkg_row: sqlite3.Row,
    out_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    package_id = pkg_row["package_id"]
    raw_manifest = json.loads(pkg_row["manifest_data"]) if pkg_row["manifest_data"] else {}

    # 查该包下的所有 paper
    papers_rows = conn.execute(
        "SELECT * FROM papers WHERE package_id = ? ORDER BY year, id",
        (package_id,),
    ).fetchall()

    if not papers_rows:
        raise ValueError(f"包 {package_id} 下没有试卷")

    # 建立映射以防路径丢失
    ref_map = {}
    for ref in raw_manifest.get("papers", []):
        ref_map[ref.get("paperKey")] = ref

    manifest_papers: list[dict[str, Any]] = []
    paper_files: dict[str, dict[str, Any]] = {}
    answer_files: dict[str, dict[str, Any]] = {}
    label_files: dict[str, dict[str, Any]] = {}

    for paper_row in papers_rows:
        paper_key = paper_row["external_key"] or f"local.english-practice.{paper_row['year']}"
        existing_ref = ref_map.get(paper_key, {})
        paper_path = existing_ref.get("path") or f"papers/{paper_row['year']}.json"
        answer_path = existing_ref.get("answerPath") or f"answers/{paper_row['year']}.json"

        paper_data: dict[str, Any] = {
            "paperKey": paper_key,
            "year": paper_row["year"],
            "title": paper_row["title"],
            "subject": paper_row["subject"] or "英语",
            "units": [],
        }

        # 选填字段
        if "exam_type" in paper_row.keys() and paper_row["exam_type"]:
            paper_data["examType"] = paper_row["exam_type"]
        if "exam_month" in paper_row.keys() and paper_row["exam_month"]:
            paper_data["examMonth"] = paper_row["exam_month"]
        if "set_number" in paper_row.keys() and paper_row["set_number"]:
            paper_data["setNumber"] = paper_row["set_number"]

        answers: dict[str, Any] = {}
        labels: dict[str, Any] = {}

        units_rows = conn.execute(
            "SELECT * FROM units WHERE paper_id = ? ORDER BY sequence",
            (paper_row["id"],),
        ).fetchall()

        for unit_row in units_rows:
            unit_key = unit_row["external_key"] or f"{paper_key}.unit{unit_row['sequence']}"
            unit_data: dict[str, Any] = {
                "unitKey": unit_key,
                "type": unit_row["unit_type"],
                "subtype": unit_row["subtype"],
                "title": unit_row["title"],
                "sequence": unit_row["sequence"],
                "passage": {"blocks": _blocks_from_unit(unit_row)},
                "questions": [],
            }

            try:
                shared = json.loads(unit_row["shared_data"] or "{}")
            except Exception:
                shared = {}

            if shared.get("directions"):
                unit_data["instructions"] = shared["directions"]
            candidates = shared.get("candidates")
            if isinstance(candidates, dict):
                unit_data["candidates"] = [
                    {"key": key, "content": value}
                    for key, value in sorted(candidates.items())
                ]

            questions_rows = conn.execute(
                "SELECT * FROM questions WHERE unit_id = ? ORDER BY sequence",
                (unit_row["id"],),
            ).fetchall()

            for q_row in questions_rows:
                q_key = q_row["external_key"] or f"{paper_key}.q{q_row['number']:02d}"
                try:
                    q_meta = json.loads(q_row["metadata"] or "{}")
                except Exception:
                    q_meta = {}

                question_data: dict[str, Any] = {
                    "questionKey": q_key,
                    "number": q_row["number"],
                    "type": q_row["question_type"],
                    "stem": q_row["stem"],
                    "score": q_row["score"] or 1.0,
                    "options": [],
                }
                if q_meta.get("content_blocks"):
                    question_data["stemBlocks"] = q_meta["content_blocks"]

                options_rows = conn.execute(
                    "SELECT * FROM options WHERE question_id = ? ORDER BY sequence",
                    (q_row["id"],),
                ).fetchall()

                for opt_row in options_rows:
                    opt_data: dict[str, Any] = {
                        "key": opt_row["stable_key"],
                        "content": opt_row["content"],
                    }
                    try:
                        opt_meta = json.loads(opt_row["metadata"] or "{}")
                    except Exception:
                        opt_meta = {}
                    if opt_meta.get("content_blocks"):
                        opt_data["contentBlocks"] = opt_meta["content_blocks"]
                    question_data["options"].append(opt_data)

                unit_data["questions"].append(question_data)

                answers[q_key] = {
                    "correctOption": q_row["answer"],
                    "score": q_row["score"] or 1.0,
                }

                # AI labels
                label_row = conn.execute(
                    "SELECT * FROM question_ai_labels WHERE question_id = ?",
                    (q_row["id"],),
                ).fetchone()
                if label_row:
                    labels[q_key] = {
                        "questionContentHash": q_row["content_hash"] or "",
                        "primarySkill": label_row["primary_skill"],
                        "secondarySkills": json.loads(label_row["secondary_skills"] or "[]"),
                        "trapTypes": json.loads(label_row["trap_types"] or "[]"),
                        "attentionPoints": json.loads(label_row["attention_points"] or "[]"),
                        "vocabularyDemand": label_row["vocabulary_demand"],
                        "contextDependency": label_row["context_dependency"],
                        "grammarDependency": label_row["grammar_dependency"],
                        "confidence": label_row["confidence"],
                        "source": label_row["model_name"] or "local",
                        "reviewStatus": "locked" if label_row["locked"] else "unreviewed",
                    }

            paper_data["units"].append(unit_data)

        # 登记引用
        ref_entry = dict(existing_ref)
        ref_entry["paperKey"] = paper_key
        ref_entry["year"] = paper_row["year"]
        ref_entry["title"] = paper_row["title"]
        ref_entry["path"] = paper_path
        ref_entry["answerPath"] = answer_path

        if labels:
            label_path = existing_ref.get("labelPath") or f"labels/{paper_row['year']}.json"
            ref_entry["labelPath"] = label_path
            label_files[label_path] = {
                "paperKey": paper_key,
                "labelVersion": "1.0",
                "labels": labels,
            }

        manifest_papers.append(ref_entry)
        paper_files[paper_path] = paper_data
        answer_files[answer_path] = {"paperKey": paper_key, "answers": answers}

    # 规范化 manifest
    manifest = dict(raw_manifest)
    manifest["format"] = "esq"
    manifest["schemaVersion"] = manifest.get("schemaVersion") or "1.0"
    manifest["packageId"] = package_id
    manifest["contentVersion"] = pkg_row["content_version"] or manifest.get("contentVersion") or "1.0.0"
    manifest["title"] = manifest.get("title") or f"题库 {package_id}"
    manifest["subject"] = manifest.get("subject") or papers_rows[0]["subject"] or "英语"
    manifest["language"] = manifest.get("language") or "en"
    manifest["locale"] = manifest.get("locale") or "zh-CN"
    manifest["publisher"] = manifest.get("publisher") or "墨题团队"
    if "license" not in manifest:
        manifest["license"] = {
            "spdx": "NOASSERTION",
            "notice": "真题整理版，仅供学习研究使用。",
        }
    if "source" not in manifest:
        manifest["source"] = {
            "type": "local_export",
            "description": "从墨题历史题库备份库抽离归档",
        }
    manifest["papers"] = manifest_papers
    manifest["features"] = {
        "hasAnswers": True,
        "hasAiLabels": bool(label_files),
        "hasAssets": False,
    }

    # 打包成 ZIP
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{package_id}.esq"

    with zipfile.ZipFile(out_file, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for p_name, payload in paper_files.items():
            archive.writestr(p_name, json.dumps(payload, ensure_ascii=False, indent=2))
        for a_name, payload in answer_files.items():
            archive.writestr(a_name, json.dumps(payload, ensure_ascii=False, indent=2))
        for l_name, payload in label_files.items():
            archive.writestr(l_name, json.dumps(payload, ensure_ascii=False, indent=2))

    summary = {
        "packageId": package_id,
        "title": manifest["title"],
        "papers": len(manifest_papers),
        "units": sum(len(p["units"]) for p in paper_files.values()),
        "questions": sum(
            len(u["questions"])
            for p in paper_files.values()
            for u in p["units"]
        ),
        "sizeBytes": out_file.stat().st_size,
    }
    return out_file, summary


def main() -> int:
    if not DB_PATH.exists():
        print(f"Error: 备份数据库不存在: {DB_PATH}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    packages = conn.execute("SELECT * FROM question_bank_packages ORDER BY id").fetchall()
    print(f"找到 {len(packages)} 个题包定义，开始抽离归档...")

    results = []
    total_papers = 0
    total_questions = 0

    for pkg_row in packages:
        try:
            esq_path, summary = export_package_from_db(conn, pkg_row, OUTPUT_DIR)
            # 校验
            validated = load_esq_package(esq_path)
            summary["valid"] = True
            summary["path"] = str(esq_path.relative_to(ROOT))
            results.append(summary)
            total_papers += summary["papers"]
            total_questions += summary["questions"]
            print(f"✓ [{summary['packageId']}] {summary['title']} -> {summary['papers']} 卷 / {summary['questions']} 题 ({summary['sizeBytes']:,} B)")
        except EsqValidationError as err:
            print(f"✗ 校验失败 [{pkg_row['package_id']}]: {err.details}", file=sys.stderr)
            return 2
        except Exception as err:
            print(f"✗ 导出失败 [{pkg_row['package_id']}]: {err}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return 3

    print(f"\n全部完成！共归档 {len(results)} 个 ESQ 包，包含 {total_papers} 卷 / {total_questions} 道试题。")

    # 生成 README 归档清单
    readme_path = OUTPUT_DIR / "README.md"
    readme_lines = [
        "# 墨题 82 卷历史真题 ESQ 题包归档清单",
        "",
        f"> 数据源：`frontend/public/question_bank.db.bak-20260920-1535`  ",
        f"> 格式规范：ESQ 1.0 / 1.1 规范题包（通过 `tools/validate_question_bank.py` 官方校验门禁）  ",
        f"> 归档汇总：**{len(results)} 个标准化 ESQ 题包 / {total_papers} 套完整试卷 / {total_questions} 道题目**",
        "",
        "| 序号 | 题包 Package ID | 题包名称 | 卷数 | 题目数 | 文件大小 | 校验状态 |",
        "|:---|:---|:---|:---|:---|:---|:---|",
    ]
    for idx, r in enumerate(results, 1):
        readme_lines.append(
            f"| {idx} | `{r['packageId']}` | {r['title']} | {r['papers']} | {r['questions']} | {r['sizeBytes']:,} B | ✅ 通过 |"
        )
    readme_path.write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    print(f"清单已生成: {readme_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
