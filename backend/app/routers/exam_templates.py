"""Read-only exam template catalog used by import screens and API clients."""

from __future__ import annotations

from fastapi import APIRouter

from ..services.exam_templates import EXAM_TEMPLATES

router = APIRouter(prefix="/exam-templates", tags=["exam-templates"])


@router.get("")
def list_exam_templates() -> dict:
    """Return serializable template metadata without exposing Python ranges."""
    items = []
    for key, template in EXAM_TEMPLATES.items():
        items.append(
            {
                "key": key,
                "label": template["label"],
                "subject_default": template["subject_default"],
                "answer_number_start": template["answer_number_range"].start,
                "answer_number_end": template["answer_number_range"].stop - 1,
                "units": [
                    {
                        "type": unit["type"],
                        "subtype": unit["subtype"],
                        "title": unit["title"],
                        "sequence": unit["seq"],
                        "question_start": unit["numbers"].start,
                        "question_end": unit["numbers"].stop - 1,
                    }
                    for unit in template["units"]
                ],
            }
        )
    return {"items": items}
