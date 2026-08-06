from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

from .passage_cleanup import repair_inline_blank_paragraph_breaks


def parse_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def serialize_question(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    shuffle: bool,
    option_order: list[str] | None = None,
    include_answer: bool = False,
    preserve_option_labels: bool = False,
) -> dict[str, Any]:
    option_rows = connection.execute(
        """
        SELECT id, stable_key, original_label, content, sequence, metadata
        FROM options
        WHERE question_id = ?
        ORDER BY sequence
        """,
        (row["id"],),
    ).fetchall()
    options = [dict(option) for option in option_rows]
    if option_order:
        order_index = {key: index for index, key in enumerate(option_order)}
        options.sort(key=lambda option: order_index.get(option["stable_key"], 999))
    elif shuffle and len(options) > 1:
        random.shuffle(options)

    display_options = []
    for index, option in enumerate(options):
        option_metadata = parse_json(option["metadata"], {})
        display_options.append(
            {
                "stable_key": option["stable_key"],
                "label": (
                    option["original_label"]
                    if preserve_option_labels
                    else chr(ord("A") + index)
                ),
                "content": option["content"],
                "metadata": option_metadata,
                "content_blocks": option_metadata.get("content_blocks", []),
            }
        )

    question_metadata = parse_json(row["metadata"], {})
    payload = {
        "id": row["id"],
        "number": row["number"],
        "stem": row["stem"],
        "question_type": row["question_type"],
        "score": row["score"],
        "metadata": question_metadata,
        "stem_blocks": question_metadata.get("content_blocks", []),
        "options": display_options,
        "option_order": [option["stable_key"] for option in options],
    }
    if include_answer:
        payload["answer"] = row["answer"]
    return payload


def serialize_unit(
    connection: sqlite3.Connection,
    unit_id: int,
    *,
    shuffle_options: bool,
    answer_orders: dict[int, list[str]] | None = None,
    include_answers: bool = False,
    only_question_ids: set[int] | None = None,
) -> dict[str, Any]:
    unit = connection.execute(
        """
        SELECT units.*, papers.year, papers.subject
        FROM units
        JOIN papers ON papers.id = units.paper_id
        WHERE units.id = ?
        """,
        (unit_id,),
    ).fetchone()
    if unit is None:
        raise LookupError("未找到练习单元")

    question_rows = connection.execute(
        "SELECT * FROM questions WHERE unit_id = ? ORDER BY sequence",
        (unit_id,),
    ).fetchall()
    if only_question_ids is not None:
        question_rows = [row for row in question_rows if row["id"] in only_question_ids]

    shared_part_b_order: list[str] | None = None
    if (
        unit["unit_type"] == "part_b"
        and question_rows
        and shuffle_options
        and not answer_orders
    ):
        option_rows = connection.execute(
            "SELECT stable_key FROM options WHERE question_id = ? ORDER BY sequence",
            (question_rows[0]["id"],),
        ).fetchall()
        shared_part_b_order = [row["stable_key"] for row in option_rows]
        random.shuffle(shared_part_b_order)

    questions = [
        serialize_question(
            connection,
            row,
            shuffle=shuffle_options and shared_part_b_order is None,
            option_order=(answer_orders or {}).get(row["id"]) or shared_part_b_order,
            include_answer=include_answers,
            preserve_option_labels=unit["subtype"] == "true_false",
        )
        for row in question_rows
    ]
    return {
        "id": unit["id"],
        "paper_id": unit["paper_id"],
        "year": unit["year"],
        "subject": unit["subject"],
        "unit_type": unit["unit_type"],
        "subtype": unit["subtype"],
        "title": unit["title"],
        "sequence": unit["sequence"],
        "passage": repair_inline_blank_paragraph_breaks(unit["passage"]),
        "shared_data": parse_json(unit["shared_data"], {}),
        "content_blocks": parse_json(unit["shared_data"], {}).get("content_blocks", []),
        "questions": questions,
        "max_score": sum(question["score"] for question in questions),
    }
