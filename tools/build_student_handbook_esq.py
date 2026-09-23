"""把《学生手册总题库》xlsx 转成 ESQ 1.0 题库包。

源文件是双行表头（第 6 行字段名、第 7 行填写说明），数据从第 8 行开始，
共 500 道单选。题型是「无文章的单题」，用空 passage 的 reading 单元承载
——ESQ 校验器允许 passage.blocks 为空数组，实测已通过。

源数据有两处必须修正、两处必须清洗：

修正（否则导入后判分错误或选项异常）：
  * 第 163 行答案列填的是选项 A 的文本 "5"，不是序号，应为 1。
  * 第 76 行只有 3 个选项（答案 C 有效，保留但记录到 metadata 备查）。

清洗（否则前端渲染出莫名换行与空白）：
  * 单元格内的换行/制表符 → 空格，连续空白折叠。
  * 手工排版残留的前导 "·" 与不换行空格（U+00A0）。

注意：源文件版权归属不明（文档属性显示整理者「沈效辰」，2015 创建 / 2021 修改），
因此 license 只能如实标注，不得为了过发布门禁而编造授权。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import unicodedata
import zipfile
from pathlib import Path

import openpyxl

DATA_START_ROW = 8
EXPECTED_COLUMNS = 17

# 源表答案列填的是选项序号（1=A）；这一个是填了选项文本的笔误。
ANSWER_CELL_TYPOS = {163: (5, 1)}

# 手工排版残留：前导的间隔号与整串不换行空格。
LEADING_ARTIFACT = re.compile(r"^[·•]\s*")


def clean_text(value: object) -> str:
    """把单元格文本收敛成适合展示的单行内容。"""
    if value is None:
        return ""
    text = str(value)
    # 不换行空格是排版残留，规范成普通空格后才能被后面的折叠规则吃掉。
    text = text.replace("\u00a0", " ")
    # CJK 全角空格同理，它和半角空格混用时折叠会漏。
    text = text.replace("\u3000", " ")
    text = unicodedata.normalize("NFKC", text)
    # 单元格内换行/制表符原本是人肉折行，不是语义换行。
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = LEADING_ARTIFACT.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def load_rows(xlsx_path: Path) -> list[tuple]:
    workbook = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    sheet = workbook["Sheet1"]
    rows = list(sheet.iter_rows(min_row=DATA_START_ROW, values_only=True))
    workbook.close()
    return [row for row in rows if row and row[3] is not None]


def normalize_answer(raw: object, row_number: int, option_count: int, issues: list[dict]) -> int:
    """答案列的值是选项序号（1 起）。返回 0 表示无法确定。"""
    if row_number in ANSWER_CELL_TYPOS:
        original, corrected = ANSWER_CELL_TYPOS[row_number]
        if raw == original:
            issues.append(
                {
                    "row": row_number,
                    "kind": "answer_cell_typo",
                    "original": raw,
                    "corrected": corrected,
                    "note": "答案列填了选项文本而非序号，已按选项文本所指位置修正",
                }
            )
            return corrected

    try:
        value = int(raw)
    except (TypeError, ValueError):
        issues.append({"row": row_number, "kind": "answer_unparsable", "original": raw})
        return 0

    if not 1 <= value <= option_count:
        issues.append(
            {
                "row": row_number,
                "kind": "answer_out_of_range",
                "original": raw,
                "option_count": option_count,
            }
        )
        return 0
    return value


def build_package(xlsx_path: Path, output_path: Path, *, paper_title: str, year: int) -> dict:
    rows = load_rows(xlsx_path)
    issues: list[dict] = []
    questions: list[dict] = []
    answers: dict[str, dict] = {}
    skipped: list[dict] = []

    for index, row in enumerate(rows, DATA_START_ROW):
        stem = clean_text(row[3])
        if not stem:
            skipped.append({"row": index, "reason": "题干为空"})
            continue

        options = []
        for offset, letter in enumerate("ABC DEF".replace(" ", "")):
            raw = row[4 + offset]
            content = clean_text(raw)
            if content:
                options.append({"key": letter, "content": content})

        if not options:
            skipped.append({"row": index, "reason": "无有效选项"})
            continue

        # 源表选项顺序就是 A/B/C/D，字母重排后会与答案序号错位，所以按出现顺序编号。
        for position, option in enumerate(options, 1):
            option["key"] = "ABCDEF"[position - 1]

        answer_index = normalize_answer(row[10], index, len(options), issues)
        if not answer_index:
            skipped.append({"row": index, "reason": "答案无法确定", "raw_answer": row[10]})
            continue

        sequence = len(questions) + 1
        question_key = f"cn.studenthandbook.q{sequence:04d}"
        metadata: dict[str, object] = {}
        source_index = row[1]
        if isinstance(source_index, (int, float)):
            metadata["sourceSection"] = int(source_index)
        difficulty = row[12]
        if isinstance(difficulty, (int, float)):
            metadata["difficulty"] = int(difficulty)
        if len(options) < 4:
            # 少选项的题保留，但标出来：解析器/前端若假设恒有 4 个选项会踩到。
            metadata["optionCount"] = len(options)
            issues.append(
                {
                    "row": index,
                    "kind": "fewer_than_four_options",
                    "option_count": len(options),
                    "questionKey": question_key,
                }
            )

        question = {
            "questionKey": question_key,
            "number": sequence,
            "type": "single_choice",
            "stem": stem,
            "options": options,
            "score": 2,
        }
        if metadata:
            question["metadata"] = metadata

        dedup = [option["content"] for option in options]
        if len(set(dedup)) != len(dedup):
            issues.append(
                {
                    "row": index,
                    "kind": "duplicate_option_text",
                    "questionKey": question_key,
                }
            )

        questions.append(question)
        answers[question_key] = {
            "correctOption": "ABCDEF"[answer_index - 1],
            "score": 2,
        }

    if not questions:
        raise SystemExit("没有解析出任何题目，检查源文件格式是否变化。")

    paper_key = "cn.studenthandbook.2024"
    manifest = {
        "format": "esq",
        "schemaVersion": "1.0",
        "packageId": "cn.studenthandbook.package.v1",
        "contentVersion": "1.0.0",
        "title": paper_title,
        "subject": "学生手册",
        "publisher": "未标注",
        "license": {
            "notice": (
                "来源为流通过的学生手册题库整理版，版权归属未标注，未经授权核验；"
                "仅限本地个人学习使用，请勿公开分发。"
            )
        },
        "source": {
            "description": (
                "由《学生手册总题库(1).xlsx》转换，共 %d 道单选题；"
                "原始整理者与授权状态均未标注。" % len(questions)
            )
        },
        "papers": [
            {
                "paperKey": paper_key,
                "year": year,
                "path": f"papers/{year}.json",
                "answerPath": f"answers/{year}.json",
            }
        ],
    }

    paper = {
        "paperKey": paper_key,
        "year": year,
        "title": paper_title,
        "units": [
            {
                "unitKey": "cn.studenthandbook.unit1",
                "type": "reading",
                "title": "学生手册题库",
                "sequence": 1,
                "passage": {"blocks": []},
                "questions": questions,
            }
        ],
    }

    payload = {
        "manifest.json": manifest,
        f"papers/{year}.json": paper,
        f"answers/{year}.json": {"paperKey": paper_key, "answers": answers},
    }

    if output_path.exists():
        output_path.unlink()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in payload.items():
            archive.writestr(name, json.dumps(data, ensure_ascii=False, indent=2))

    return {
        "output": str(output_path),
        "questions": len(questions),
        "skipped": skipped,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="构建学生手册 ESQ 题库包")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--title", default="学生手册题库")
    parser.add_argument("--year", type=int, default=2024)
    args = parser.parse_args()

    if not args.source.exists():
        print(json.dumps({"error": f"源文件不存在：{args.source}"}, ensure_ascii=False))
        return 2

    report = build_package(args.source, args.output, paper_title=args.title, year=args.year)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
