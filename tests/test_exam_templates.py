from __future__ import annotations

import unittest

from backend.app.services.exam_templates import (
    ALLOWED_UNIT_TYPES,
    EXAM_TEMPLATES,
    detect_exam_type,
    supported_exam_types,
)


class ExamTemplateTests(unittest.TestCase):
    def test_registry_contains_additional_public_templates(self) -> None:
        self.assertTrue({"gaokao", "tem4", "tem8"}.issubset(EXAM_TEMPLATES))
        self.assertEqual(set(supported_exam_types()), set(EXAM_TEMPLATES))

    def test_template_units_use_importer_unit_types(self) -> None:
        for template in EXAM_TEMPLATES.values():
            for unit in template["units"]:
                self.assertIn(unit["type"], ALLOWED_UNIT_TYPES)
                self.assertLess(unit["numbers"].start, unit["numbers"].stop)

    def test_detection_prefers_specific_exam_markers(self) -> None:
        self.assertEqual(detect_exam_type("", "2025-tem8-paper.docx"), "tem8")
        self.assertEqual(detect_exam_type("高考英语全国卷", "paper.docx"), "gaokao")


if __name__ == "__main__":
    unittest.main()
