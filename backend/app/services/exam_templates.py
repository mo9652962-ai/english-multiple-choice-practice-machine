"""Exam template registry for extensible exam type support."""

from __future__ import annotations

from typing import Any

EXAM_TEMPLATES: dict[str, dict[str, Any]] = {
    "cet4": {
        "label": "大学英语四级 (CET-4)",
        "subject_default": "大学英语四级",
        "answer_number_range": range(1, 56),
        "units": [
            {"type": "listening", "subtype": "news_report", "title": "听力 Section A — 新闻报告", "seq": 1, "numbers": range(1, 8)},
            {"type": "listening", "subtype": "long_conversation", "title": "听力 Section B — 长对话", "seq": 2, "numbers": range(8, 16)},
            {"type": "listening", "subtype": "passage", "title": "听力 Section C — 短文", "seq": 3, "numbers": range(16, 26)},
            {"type": "word_bank", "subtype": "word_bank", "title": "阅读 Section A — 选词填空", "seq": 4, "numbers": range(26, 36)},
            {"type": "paragraph_matching", "subtype": "paragraph_matching", "title": "阅读 Section B — 长篇匹配", "seq": 5, "numbers": range(36, 46)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Section C — Passage One", "seq": 6, "numbers": range(46, 51)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Section C — Passage Two", "seq": 7, "numbers": range(51, 56)},
        ],
    },
    "cet6": {
        "label": "大学英语六级 (CET-6)",
        "subject_default": "大学英语六级",
        "answer_number_range": range(1, 56),
        "units": [
            {"type": "listening", "subtype": "long_conversation", "title": "听力 Section A — 长对话", "seq": 1, "numbers": range(1, 9)},
            {"type": "listening", "subtype": "passage", "title": "听力 Section B — 短文", "seq": 2, "numbers": range(9, 16)},
            {"type": "listening", "subtype": "lecture", "title": "听力 Section C — 讲座/讲话", "seq": 3, "numbers": range(16, 26)},
            {"type": "word_bank", "subtype": "word_bank", "title": "阅读 Section A — 选词填空", "seq": 4, "numbers": range(26, 36)},
            {"type": "paragraph_matching", "subtype": "paragraph_matching", "title": "阅读 Section B — 长篇匹配", "seq": 5, "numbers": range(36, 46)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Section C — Passage One", "seq": 6, "numbers": range(46, 51)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Section C — Passage Two", "seq": 7, "numbers": range(51, 56)},
        ],
    },
    "postgraduate_english1": {
        "label": "考研英语（一）",
        "subject_default": "英语一",
        "answer_number_range": range(1, 46),
        "units": [
            {"type": "cloze", "subtype": "cloze", "title": "完型填空", "seq": 1, "numbers": range(1, 21)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 1", "seq": 2, "numbers": range(21, 26)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 2", "seq": 3, "numbers": range(26, 31)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 3", "seq": 4, "numbers": range(31, 36)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 4", "seq": 5, "numbers": range(36, 41)},
            {"type": "part_b", "subtype": "paragraph_insertion", "title": "阅读 Part B", "seq": 6, "numbers": range(41, 46)},
        ],
    },
    "postgraduate_english2": {
        "label": "考研英语（二）",
        "subject_default": "英语二",
        "answer_number_range": range(1, 46),
        "units": [
            {"type": "cloze", "subtype": "cloze", "title": "完型填空", "seq": 1, "numbers": range(1, 21)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 1", "seq": 2, "numbers": range(21, 26)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 2", "seq": 3, "numbers": range(26, 31)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 3", "seq": 4, "numbers": range(31, 36)},
            {"type": "reading", "subtype": "reading_a", "title": "阅读 Text 4", "seq": 5, "numbers": range(36, 41)},
            {"type": "part_b", "subtype": "true_false", "title": "阅读 Part B", "seq": 6, "numbers": range(41, 46)},
        ],
    },
}

ALLOWED_UNIT_TYPES = {
    "cloze",
    "reading",
    "part_b",
    "listening",
    "word_bank",
    "paragraph_matching",
}

def detect_exam_type(blocks_text: str, file_name: str = "") -> str | None:
    """Best-effort detection of exam type from document text and filename."""
    lower = blocks_text.lower()
    name_lower = file_name.lower()
    if "cet-6" in name_lower or "cet6" in name_lower or "六级" in name_lower or "六级" in lower[:3000]:
        return "cet6"
    if "cet-4" in name_lower or "cet4" in name_lower or "四级" in name_lower or "四级" in lower[:3000]:
        return "cet4"
    if "英语（二）" in lower[:3000] or "英语二" in lower[:3000] or "英语二" in name_lower or "英语2" in name_lower:
        return "postgraduate_english2"
    return "postgraduate_english1"


def template_units(exam_type: str) -> list[dict[str, Any]]:
    template = EXAM_TEMPLATES.get(exam_type)
    return template["units"] if template else []


def template_label(exam_type: str) -> str:
    template = EXAM_TEMPLATES.get(exam_type)
    return template["label"] if template else exam_type


def template_subject_default(exam_type: str) -> str:
    template = EXAM_TEMPLATES.get(exam_type)
    return template["subject_default"] if template else ""


def template_answer_numbers(exam_type: str) -> range:
    template = EXAM_TEMPLATES.get(exam_type)
    return template["answer_number_range"] if template else range(1, 46)
