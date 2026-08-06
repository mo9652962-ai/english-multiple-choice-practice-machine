from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from .ai_client import chat_completion, parse_json_response
from .docx_parser import (
    apply_answers_to_draft,
    extract_blocks,
    objective_question_numbers,
    validate_draft,
)

def extract_attachment_text(path: Path) -> str:
    """Extract raw text from a DOC/DOCX/PDF answer attachment for the model."""
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    blocks, _, converted = extract_blocks(path)
    try:
        return "\n".join(blocks)
    finally:
        if converted:
            import shutil

            shutil.rmtree(converted.parent, ignore_errors=True)


def document_text(path: Path) -> str:
    blocks, _, converted = extract_blocks(path)
    try:
        return "\n".join(blocks)
    finally:
        if converted:
            import shutil

            shutil.rmtree(converted.parent, ignore_errors=True)


def infer_document_papers(
    blocks: list[str],
    source_name: str,
) -> list[dict[str, Any]]:
    """Detect repeated complete papers without requiring a model.

    This is the safe fallback when the configured model is unavailable. CET
    "全三套" Word exports consistently repeat ``Part I Writing`` and usually
    place a title page immediately before it.
    """
    writing_starts = [
        index
        for index, block in enumerate(blocks)
        if re.match(r"^\s*Part\s*I\s*Writing\b", block, re.I)
        or re.match(r"^\s*Part\s*IWriting\b", block, re.I)
    ]
    if len(writing_starts) <= 1:
        return [
            {
                "title": Path(source_name).stem,
                "year": _first_int(source_name, r"(20\d{2})"),
                "month": _first_int(source_name, r"(?:年|[._-])\s*(\d{1,2})\s*月?"),
                "set_number": 1,
                "start_block": 0,
                "end_block": max(0, len(blocks) - 1),
                "objective_start_block": 0,
                "objective_end_block": max(0, len(blocks) - 1),
                "has_objective_questions": True,
            }
        ]

    starts: list[int] = []
    for writing_start in writing_starts:
        search_start = max(0, writing_start - 35)
        title_candidates = [
            index
            for index in range(search_start, writing_start)
            if re.search(r"20\d{2}.*第\s*[一二三1-9]\s*套", blocks[index])
            or re.search(r"\(\s*20\d{2}.*第\s*[一二三1-9]\s*套\s*\)", blocks[index])
        ]
        if title_candidates:
            starts.append(title_candidates[-1])
            continue
        band_candidates = [
            index
            for index in range(search_start, writing_start)
            if "COLLEGE ENGLISH TEST" in blocks[index].upper()
        ]
        starts.append(band_candidates[-1] if band_candidates else writing_start)

    year = _first_int(source_name, r"(20\d{2})")
    month = _first_int(source_name, r"(?:年|[._-])\s*(\d{1,2})\s*月?")
    subject = "大学英语六级" if "六级" in source_name else "大学英语四级" if "四级" in source_name else "英语"
    papers: list[dict[str, Any]] = []
    for offset, start in enumerate(starts):
        end = starts[offset + 1] - 1 if offset + 1 < len(starts) else len(blocks) - 1
        segment = blocks[start : end + 1]
        nearby = "\n".join(segment[:40])
        set_number = _chinese_number(
            re.search(r"第\s*([一二三1-9])\s*套", nearby)
        ) or offset + 1
        has_objective = any(
            re.search(r"Listening\s+Comprehension|Reading\s+Comprehension", item, re.I)
            for item in segment
        )
        objective_positions = [
            start + index
            for index, item in enumerate(segment)
            if re.search(r"Part\s*(?:II|Ⅱ|III|Ⅲ)\s*(?:Listening|Reading)", item, re.I)
        ]
        title = (
            f"{year}年{month}月{subject}真题（第{set_number}套）"
            if year and month
            else f"{Path(source_name).stem}（第{set_number}套）"
        )
        papers.append(
            {
                "title": title,
                "year": year,
                "month": month,
                "set_number": set_number,
                "start_block": start,
                "end_block": end,
                "objective_start_block": (
                    min(objective_positions) if objective_positions else start
                ),
                "objective_end_block": end,
                "has_objective_questions": has_objective,
            }
        )
    return papers


def _first_int(value: str, pattern: str) -> int | None:
    match = re.search(pattern, value)
    return int(match.group(1)) if match else None


def _chinese_number(match: re.Match[str] | None) -> int | None:
    if not match:
        return None
    value = match.group(1)
    return {"一": 1, "二": 2, "三": 3}.get(value, int(value) if value.isdigit() else None)


def detect_document_papers(
    connection: sqlite3.Connection,
    blocks: list[str],
    source_name: str,
    *,
    profile_id: int | None = None,
    model: str | None = None,
) -> tuple[list[dict[str, Any]], str]:
    """Ask the model how many papers exist and validate its block boundaries."""
    fallback = infer_document_papers(blocks, source_name)
    indexed_document = "\n".join(
        f"[BLOCK {index}] {block}" for index, block in enumerate(blocks)
    )
    prompt = """你是英语考试 Word 题库拆分器。先判断当前文档包含几套试卷，再逐套给出标题和边界。
边界必须使用用户提供的 BLOCK 编号，start_block/end_block 均为包含端点。
每套还要标出客观题（选择题、判断题、选词填空、段落匹配等）的开始与结束 BLOCK。
若某套只含写作或翻译、没有客观题，has_objective_questions 必须为 false。
不得把不同套次的题目或答案混在一起。只输出 JSON：
{"paper_count":3,"papers":[{"title":"...","year":2019,"month":6,"set_number":1,
"start_block":0,"end_block":220,"objective_start_block":27,
"objective_end_block":228,"has_objective_questions":true}],"notes":""}"""
    raw = chat_completion(
        connection,
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source_name": source_name,
                        "document_blocks": indexed_document,
                        "local_candidates": fallback,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={"type": "json_object"},
        profile_id=profile_id,
        model=model,
        max_tokens=None,
    )
    result = parse_json_response(raw)
    candidates = result.get("papers") if isinstance(result, dict) else None
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("模型没有返回试卷拆分列表")
    normalized: list[dict[str, Any]] = []
    last_end = -1
    for offset, item in enumerate(candidates):
        if not isinstance(item, dict):
            raise ValueError("模型返回的试卷拆分项无效")
        start = int(item.get("start_block", -1))
        end = int(item.get("end_block", -1))
        if start <= last_end or end < start or end >= len(blocks):
            raise ValueError("模型返回的试卷拆分边界无效或重叠")
        objective_start = int(item.get("objective_start_block", start))
        objective_end = int(item.get("objective_end_block", end))
        if not (start <= objective_start <= objective_end <= end):
            objective_start, objective_end = start, end
        normalized.append(
            {
                "title": str(item.get("title") or fallback[min(offset, len(fallback) - 1)]["title"]).strip(),
                "year": int(item.get("year") or 0) or fallback[min(offset, len(fallback) - 1)].get("year"),
                "month": int(item.get("month") or 0) or fallback[min(offset, len(fallback) - 1)].get("month"),
                "set_number": int(item.get("set_number") or offset + 1),
                "start_block": start,
                "end_block": end,
                "objective_start_block": objective_start,
                "objective_end_block": objective_end,
                "has_objective_questions": bool(item.get("has_objective_questions", True)),
            }
        )
        last_end = end
    if int(result.get("paper_count") or len(normalized)) != len(normalized):
        raise ValueError("模型返回的试卷数量与拆分列表不一致")
    return normalized, raw


def _draft_summary(draft: dict[str, Any]) -> dict[str, Any]:
    return {
        "year": draft.get("year"),
        "expected_numbers": [str(number) for number in objective_question_numbers(draft)],
        "units": [
            {
                "unit_type": unit.get("unit_type"),
                "title": unit.get("title"),
                "questions": [
                    {
                        "number": question.get("number"),
                        "stem": str(question.get("stem", ""))[:300],
                        "options": [
                            {
                                "key": option.get("key"),
                                "content": str(option.get("content", ""))[:200],
                            }
                            for option in question.get("options", [])
                        ],
                        "answer": question.get("answer", ""),
                    }
                    for question in unit.get("questions", [])
                ],
            }
            for unit in draft.get("units", [])
        ],
        "answers_found_locally": draft.get("answers", {}),
        "answer_sources": draft.get("answer_sources", {}),
    }


def run_model_assist(
    connection: sqlite3.Connection,
    draft: dict[str, Any],
    document_text: str,
    answer_text: str = "",
    *,
    profile_id: int | None = None,
    model: str | None = None,
    correct_structure: bool = False,
    max_tokens: int | None = None,
) -> tuple[dict[str, Any], str]:
    """Ask the model to locate questions and map answers, returning parsed JSON."""
    prompt = """
你是考研英语真题导入解析助手。用户上传了 Word 试卷（可能附带答案文件），程序已经用规则解析出一份草稿。
你的任务是提高导入精确度，只能依据提供的材料，绝对不能编造或推测答案、题干、选项或文章内容。

请完成三件事：
1. 答案对应：在 document_text 或 answer_text 中找到答案区（例如“参考答案”“答案速查”“1-5 BACDC”等），
   输出完整准确的 answer_map（题号 → 答案字母）。答案只能来自材料；材料中没有答案时 answer_map 保持空对象。
2. 题号核对：对照材料检查草稿中每道题的题号（完形 1-20、阅读 21-40、Part B 41-45）。
   只有材料能明确证明题号错位时，才在 number_map 中给出 old -> new；否则留空。
3. 结构问题：列出材料与草稿明显不一致的问题（选项归属错误、题干断行、答案数量与题目数不符、
   完形或 Part B 空位缺失等），每条一句话放入 issues。

注意：draft_summary 中列出的 expected_numbers 是本次实际导入的客观题题号。
如果材料中的 Part B 是“translate the underlined segments into Chinese”等翻译题，且草稿没有导入 41-45，
这是预期行为，不要把“缺少 Part B 41-45”列为 issues，也不要要求把翻译题强行转换成客观题。

"""
    if correct_structure:
        prompt += """
4. 结构修正（已启用）：如果题干或选项归属与材料明显不一致，可以在 question_fixes 中给出修正。
   question_fixes: [{"number": 5, "stem": "修正后的题干",
     "options": [{"key": "A", "content": "..."}, {"key": "B", "content": "..."},
                 {"key": "C", "content": "..."}, {"key": "D", "content": "..."}]}]
   只依据材料修正，不能凭空改写或补全；选项数量必须与原题一致；没有把握的题不要放入。
5. unit_replacements 在本次回答中保持空数组；程序会按单元另行请求重建，避免一次输出过长。

"""
    prompt += """
只输出 JSON，格式：
{"answer_map": {"1": "B"}, "number_map": {"12": "13"},
 "question_fixes": [{"number": 5, "stem": "...", "options": [{"key": "A", "content": "..."}]}],
 "unit_replacements": [],
 "issues": ["第5题选项疑似属于第6题"], "notes": "简要说明"}
answer_map 的题号使用材料核对后的最终题号；number_map 只描述草稿旧题号到最终题号的变化。
answer_map 的值只能是单个字母 A-O，或判断题使用 T/F；没有把握的题不要填。不要输出逐题解析，不要翻译文章。
""".strip()
    payload = {
        "document_text": document_text,
        "answer_text": answer_text,
        "draft_summary": _draft_summary(draft),
    }
    raw = chat_completion(
        connection,
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        response_format={"type": "json_object"},
        profile_id=profile_id,
        model=model,
        max_tokens=None,
    )
    result = parse_json_response(raw)
    if not isinstance(result, dict):
        raise ValueError("模型没有返回有效的 JSON 对象")
    result["unit_replacements"] = []
    if correct_structure and draft.get("exam_type") in {"cet4", "cet6"}:
        reconstruction_issues: list[str] = []
        for unit in draft.get("units", []):
            try:
                replacement = _reconstruct_exam_unit(
                    connection,
                    draft,
                    unit,
                    document_text,
                    answer_text,
                    profile_id=profile_id,
                    model=model,
                )
                result["unit_replacements"].append(replacement)
            except Exception as error:
                reconstruction_issues.append(
                    f"{unit.get('title', '未知单元')}重建失败：{str(error)[:120]}"
                )
        if reconstruction_issues:
            result.setdefault("issues", [])
            if isinstance(result["issues"], list):
                result["issues"].extend(reconstruction_issues)
    return result, raw


def _reconstruct_exam_unit(
    connection: sqlite3.Connection,
    draft: dict[str, Any],
    unit: dict[str, Any],
    document_text: str,
    answer_text: str,
    *,
    profile_id: int | None,
    model: str | None,
) -> dict[str, Any]:
    numbers = [
        int(question.get("number"))
        for question in unit.get("questions", [])
        if str(question.get("number", "")).isdigit()
    ]
    prompt = """你是英语客观题题库的单元重建器。只依据试卷与答案材料，不得编造。
只重建用户指定的一个单元，并只输出 JSON 对象：
{"sequence":1,"unit_type":"listening","subtype":"long_conversation","title":"...",
"passage":"","shared_data":{},"questions":[
 {"number":1,"stem":"","options":[{"key":"A","content":"..."}],"answer":"B","score":1}
]}
questions 的题号集合必须与 expected_numbers 完全一致。
CET 听力原文和题干通常不在试卷中：passage 与 stem 留空，准确抄录 A-D 选项。
选词填空：passage 保留带题号空位的原文，shared_data.candidates 为 A-O 词库，每题 options 也使用同一词库。
段落匹配：passage 保留完整文章，shared_data.paragraphs 保存 A-K 段落，36-45 的 stem 是十条陈述，options 为 A-K。
阅读理解：passage 只放本篇文章，完整抄录五道题干与 A-D 选项。
答案只能从材料的标准答案区获取；没有可靠答案时 answer 留空。"""
    raw = chat_completion(
        connection,
        [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "paper": {
                            "title": draft.get("title"),
                            "exam_type": draft.get("exam_type"),
                            "year": draft.get("year"),
                            "month": draft.get("exam_month"),
                            "set_number": draft.get("set_number"),
                        },
                        "target_unit": {
                            "sequence": unit.get("sequence"),
                            "unit_type": unit.get("unit_type"),
                            "subtype": unit.get("subtype"),
                            "title": unit.get("title"),
                            "expected_numbers": numbers,
                        },
                        "document_text": document_text,
                        "answer_text": answer_text,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        response_format={"type": "json_object"},
        profile_id=profile_id,
        model=model,
        max_tokens=None,
    )
    result = parse_json_response(raw)
    if not isinstance(result, dict):
        raise ValueError("模型没有返回有效单元 JSON")
    return result


def apply_model_assist(
    draft: dict[str, Any],
    result: dict[str, Any],
    model_name: str = "",
    *,
    correct_structure: bool = False,
) -> dict[str, Any]:
    """Apply a validated model result directly into the draft."""
    issues = result.get("issues")
    if not isinstance(issues, list):
        issues = []
    issue_texts = [str(item).strip()[:160] for item in issues if str(item).strip()]

    applied_number_fixes = 0
    normalized_number_map: dict[str, str] = {}
    number_map = result.get("number_map")
    if isinstance(number_map, dict) and number_map:
        question_rows = [
            (unit, question)
            for unit in draft.get("units", [])
            for question in unit.get("questions", [])
        ]
        questions = [question for _, question in question_rows]
        original_numbers = [str(question.get("number", "")).strip() for question in questions]
        for old_number, new_number in number_map.items():
            old = str(old_number).strip()
            new = str(new_number).strip()
            matching_row = next(
                (
                    (unit, question)
                    for unit, question in question_rows
                    if str(question.get("number", "")).strip() == old
                ),
                None,
            )
            if matching_row is None or not old.isdigit() or not new.isdigit():
                continue
            unit, _ = matching_row
            normalized_new = int(new)
            unit_type = str(unit.get("unit_type", ""))
            allowed = (
                range(1, 21)
                if unit_type == "cloze"
                else range(21, 41)
                if unit_type == "reading"
                else range(41, 46)
                if unit_type == "part_b"
                else range(1, 46)
            )
            if normalized_new in allowed:
                normalized_number_map[old] = str(normalized_new)
        remapped_numbers = [
            normalized_number_map.get(number, number) for number in original_numbers
        ]
        if normalized_number_map and len(set(remapped_numbers)) == len(remapped_numbers):
            for question, old_number, new_number in zip(
                questions, original_numbers, remapped_numbers
            ):
                if old_number != new_number:
                    question["number"] = int(new_number)
                    applied_number_fixes += 1
            old_answers = dict(draft.setdefault("answers", {}))
            old_sources = dict(draft.setdefault("answer_sources", {}))
            draft["answers"] = {
                normalized_number_map.get(str(number), str(number)): answer
                for number, answer in old_answers.items()
            }
            draft["answer_sources"] = {
                normalized_number_map.get(str(number), str(number)): source
                for number, source in old_sources.items()
            }
        elif normalized_number_map:
            issue_texts.append("题号修正会产生重复题号，已拒绝自动应用，请人工核对")

    answers = draft.setdefault("answers", {})
    answer_sources = draft.setdefault("answer_sources", {})
    expected_numbers = {str(number) for number in objective_question_numbers(draft)}
    applied_answers = 0
    answer_map = result.get("answer_map")
    if isinstance(answer_map, dict):
        for number, letter in answer_map.items():
            # answer_map and question_fixes refer to the corrected/material
            # question numbers; number_map has already renamed the draft.
            normalized_number = str(number).strip()
            normalized_letter = str(letter or "").strip().upper()
            if normalized_number not in expected_numbers:
                continue
            if len(normalized_letter) != 1 or normalized_letter not in "ABCDEFGHIJKLMNOT":
                continue
            answers[normalized_number] = normalized_letter
            answer_sources[normalized_number] = "模型辅助"
            applied_answers += 1

    applied_unit_replacements = 0
    unit_replacements = result.get("unit_replacements")
    if correct_structure and isinstance(unit_replacements, list):
        units = draft.get("units", [])
        for replacement in unit_replacements:
            if not isinstance(replacement, dict):
                continue
            sequence = int(replacement.get("sequence") or 0)
            target_index = next(
                (
                    index
                    for index, unit in enumerate(units)
                    if int(unit.get("sequence") or 0) == sequence
                ),
                -1,
            )
            if target_index < 0:
                continue
            target = units[target_index]
            expected = {
                int(question.get("number"))
                for question in target.get("questions", [])
                if str(question.get("number", "")).isdigit()
            }
            questions = replacement.get("questions")
            if not isinstance(questions, list) or not questions:
                continue
            replacement_numbers = {
                int(question.get("number"))
                for question in questions
                if isinstance(question, dict)
                and str(question.get("number", "")).isdigit()
            }
            if replacement_numbers != expected or len(questions) != len(expected):
                issue_texts.append(
                    f"第 {sequence} 单元的模型重建题号集合不完整，已拒绝应用"
                )
                continue
            cleaned_questions: list[dict[str, Any]] = []
            valid = True
            for question in questions:
                number = int(question["number"])
                option_rows = question.get("options")
                if not isinstance(option_rows, list) or len(option_rows) < 2:
                    valid = False
                    break
                cleaned_options: list[dict[str, str]] = []
                for option in option_rows:
                    if not isinstance(option, dict):
                        valid = False
                        break
                    key = str(option.get("key", "")).strip().upper()
                    content = str(option.get("content", "")).strip()
                    if not key or not content:
                        valid = False
                        break
                    cleaned_options.append({"key": key, "content": content[:3000]})
                if not valid or len({item["key"] for item in cleaned_options}) != len(
                    cleaned_options
                ):
                    valid = False
                    break
                answer = str(
                    question.get("answer")
                    or answers.get(str(number))
                    or ""
                ).strip().upper()
                cleaned_questions.append(
                    {
                        "number": number,
                        "stem": str(question.get("stem", "") or "").strip()[:4000],
                        "options": cleaned_options,
                        "answer": answer,
                        "score": float(
                            question.get("score")
                            or target.get("questions", [{}])[0].get("score")
                            or 1
                        ),
                        "question_type": str(
                            question.get("question_type") or "single_choice"
                        ),
                    }
                )
                if answer:
                    answers[str(number)] = answer
                    answer_sources[str(number)] = "模型辅助"
            if not valid:
                issue_texts.append(
                    f"第 {sequence} 单元的模型重建选项不完整，已拒绝应用"
                )
                continue
            shared_data = replacement.get("shared_data")
            units[target_index] = {
                "unit_type": str(
                    replacement.get("unit_type") or target.get("unit_type") or ""
                ),
                "subtype": str(
                    replacement.get("subtype") or target.get("subtype") or ""
                ),
                "title": str(
                    replacement.get("title") or target.get("title") or ""
                )[:200],
                "sequence": sequence,
                "passage": str(replacement.get("passage", "") or "")[:50000],
                "shared_data": shared_data if isinstance(shared_data, dict) else {},
                "questions": cleaned_questions,
            }
            applied_unit_replacements += 1

    applied_fixes = 0
    question_fixes = result.get("question_fixes")
    if correct_structure and isinstance(question_fixes, list):
        for fix in question_fixes:
            if not isinstance(fix, dict):
                continue
            number = str(fix.get("number", "")).strip()
            if number not in expected_numbers:
                continue
            target = None
            for unit in draft.get("units", []):
                for question in unit.get("questions", []):
                    if str(question.get("number")) == number:
                        target = question
                        break
                if target is not None:
                    break
            if target is None:
                continue
            changed = False
            stem = fix.get("stem")
            if isinstance(stem, str) and stem.strip() and stem.strip() != target.get("stem"):
                target["stem"] = stem.strip()[:2000]
                changed = True
            options = fix.get("options")
            if isinstance(options, list) and len(options) == len(target.get("options", [])):
                cleaned: list[dict[str, str]] = []
                valid = True
                for option in options:
                    if not isinstance(option, dict):
                        valid = False
                        break
                    key = str(option.get("key", "")).strip().upper()
                    content = str(option.get("content", "")).strip()
                    if not key or not content:
                        valid = False
                        break
                    cleaned.append({"key": key, "content": content[:1000]})
                old_keys = [
                    str(item.get("key", "")).strip().upper()
                    for item in target["options"]
                ]
                new_keys = [item["key"] for item in cleaned]
                if valid and new_keys == old_keys and len(set(new_keys)) == len(new_keys):
                    old_contents = [str(item.get("content", "")) for item in target["options"]]
                    new_contents = [item["content"] for item in cleaned]
                    if old_contents != new_contents:
                        target["options"] = cleaned
                        changed = True
            if changed:
                applied_fixes += 1

    issue_texts = list(dict.fromkeys(issue_texts))[:20]

    draft["model_assist"] = {
        "status": "applied",
        "applied_answers": applied_answers,
        "applied_fixes": applied_fixes,
        "applied_unit_replacements": applied_unit_replacements,
        "applied_number_fixes": applied_number_fixes,
        "answer_total": sum(1 for value in answers.values() if value),
        "issue_count": len(issue_texts),
        "issues": issue_texts,
        "notes": str(result.get("notes", "") or "")[:300],
        "model_name": model_name,
        "applied_at": datetime.now().isoformat(timespec="seconds"),
    }
    # When a complete answer map is returned and there are no unresolved
    # structural issues, the model has performed the requested one-click
    # proofreading.  Mark the answer set confirmed so a complete Word+answer
    # import is publishable without a redundant manual save step.  Incomplete
    # or disputed results retain the existing manual-review gate.
    expected_answer_numbers = {
        str(number) for number in objective_question_numbers(draft)
    }
    answered_numbers = {
        str(number)
        for number, value in answers.items()
        if str(value or "").strip()
    }
    fully_verified = bool(expected_answer_numbers) and expected_answer_numbers <= answered_numbers and not issue_texts
    if fully_verified:
        draft["answers_confirmed"] = True
        draft["answer_source"] = "模型辅助"
        draft["answer_status"] = {
            "status": "confirmed",
            "message": "模型已完成答案与题目结构校对",
        }
        draft["model_assist"]["answers_confirmed_by_model"] = True
    else:
        draft["model_assist"]["answers_confirmed_by_model"] = False
    apply_answers_to_draft(draft)
    draft["warnings"] = validate_draft(draft)
    existing = set(draft["warnings"])
    for item in issue_texts:
        text = f"[模型辅助] {item}"
        if text not in existing and len(draft["warnings"]) < 25:
            draft["warnings"].append(text)
            existing.add(text)
    return draft
