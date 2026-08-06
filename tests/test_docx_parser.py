from __future__ import annotations

import unittest

from lxml import etree

from backend.app.services.docx_parser import (
    NS,
    _extract_answers_from_text,
    _detect_subject,
    _ensure_numbered_blanks,
    _extract_ooxml_text,
    _has_objective_part_b,
    _parse_part_b,
    _remove_duplicate_cloze_number_noise,
    apply_answers_to_draft,
    clean_text,
    extract_answer_key,
    validate_draft,
)
from backend.app.services.passage_cleanup import repair_inline_blank_paragraph_breaks


class OoxmlBlankExtractionTests(unittest.TestCase):
    def test_private_word_control_character_is_removed(self) -> None:
        self.assertEqual(clean_text("Text 3\ue004"), "Text 3")

    def test_underlined_question_number_becomes_visible_blank(self) -> None:
        paragraph = etree.fromstring(
            f"""
            <w:p xmlns:w="{NS['w']}">
              <w:r><w:t>The court cannot </w:t></w:r>
              <w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t xml:space="preserve"> 1 </w:t></w:r>
              <w:r><w:t> its legitimacy.</w:t></w:r>
            </w:p>
            """
        )
        self.assertEqual(
            clean_text(_extract_ooxml_text(paragraph)),
            "The court cannot 1 ______ its legitimacy.",
        )

    def test_underlined_word_is_not_converted_to_a_blank(self) -> None:
        paragraph = etree.fromstring(
            f"""
            <w:p xmlns:w="{NS['w']}">
              <w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>Directions</w:t></w:r>
            </w:p>
            """
        )
        self.assertEqual(clean_text(_extract_ooxml_text(paragraph)), "Directions")

    def test_explicit_underscores_are_preserved(self) -> None:
        paragraph = etree.fromstring(
            f"""
            <w:p xmlns:w="{NS['w']}">
              <w:r><w:t>(42) _________</w:t></w:r>
            </w:p>
            """
        )
        self.assertEqual(
            clean_text(_extract_ooxml_text(paragraph)),
            "(42) _________",
        )

    def test_sequential_bare_numbers_become_blanks(self) -> None:
        passage = (
            "The site dates to 3500 B.C. It is 1 prone to earthquakes, "
            "which caused it to 2 sink. The rise 3 covered the city."
        )
        self.assertEqual(
            _ensure_numbered_blanks(passage, range(1, 4)),
            "The site dates to 3500 B.C. It is 1 ______ prone to earthquakes, "
            "which caused it to 2 ______ sink. The rise 3 ______ covered the city.",
        )

    def test_part_b_parenthesized_positions_are_normalized(self) -> None:
        self.assertEqual(
            _ensure_numbered_blanks(
                "First paragraph. (41) Second paragraph. (42) _________ Third.",
                range(41, 43),
            ),
            "First paragraph. 41 ______ Second paragraph. 42 ______ Third.",
        )

    def test_missing_number_at_broken_text_frame_is_recovered(self) -> None:
        passage = (
            "shifting 6 and climate change eroded a barrier that\n\n"
            "Pavlopetri. A survey was\n\n"
            "data to analyze sea levels 9 British researchers returned."
        )
        repaired = _ensure_numbered_blanks(passage, range(6, 10))
        self.assertIn("barrier that 7 ______ Pavlopetri", repaired)
        self.assertIn("survey was 8 ______ data", repaired)

    def test_duplicate_early_cloze_number_noise_is_removed(self) -> None:
        passage = (
            "Our lives. 1 ______ 9 AI also has the potential hazard of "
            "2 ______ changing experiences. Later they 9 ______ their preferences."
        )
        self.assertEqual(
            _remove_duplicate_cloze_number_noise(passage),
            "Our lives. 1 ______ AI also has the potential hazard of "
            "2 ______ changing experiences. Later they 9 ______ their preferences.",
        )

    def test_inline_blank_does_not_start_a_false_paragraph(self) -> None:
        passage = (
            "At first glance this might seem like a strength that\n\n"
            "1 ______ the ability to make judgments.\n\n"
            "A genuine new paragraph starts here."
        )
        self.assertEqual(
            repair_inline_blank_paragraph_breaks(passage),
            "At first glance this might seem like a strength that "
            "1 ______ the ability to make judgments.\n\n"
            "A genuine new paragraph starts here.",
        )

    def test_sentence_ending_before_blank_keeps_paragraph_break(self) -> None:
        passage = "Here are some tips:\n\n41 ______ First tip."
        self.assertEqual(
            repair_inline_blank_paragraph_breaks(passage),
            "Here are some tips: 41 ______ First tip.",
        )

        completed = "This is a complete sentence.\n\n41 ______ New paragraph."
        self.assertEqual(
            repair_inline_blank_paragraph_breaks(completed),
            completed,
        )

    def test_question_body_is_not_mistaken_for_answer_key(self) -> None:
        blocks = [
            "Mark your answers on ANSWER SHEET 1.",
            "26. How should the author respond?",
            "[A] Carefully. [B] Directly.",
        ]
        self.assertEqual(extract_answer_key(blocks), {})

    def test_grouped_answer_ranges_are_supported(self) -> None:
        self.assertEqual(
            _extract_answers_from_text("1-5: ADCBB\n6-10: ADDCB"),
            {
                1: "A", 2: "D", 3: "C", 4: "B", 5: "B",
                6: "A", 7: "D", 8: "D", 9: "C", 10: "B",
            },
        )

    def test_cet_answer_ranges_support_questions_46_to_55_and_a_to_o(self) -> None:
        answers = _extract_answers_from_text(
            "26-35: I L B N G E O A D C\n46-50: B C A D C\n51-55: B C D A B"
        )
        self.assertEqual([answers[n] for n in range(26, 36)], list("ILBNGEOADC"))
        self.assertEqual([answers[n] for n in range(46, 56)], list("BCADCBCDAB"))

    def test_english_two_embedded_answer_layout_is_supported(self) -> None:
        blocks = [
            "2010年英语二参考真题答案",
            "1.D 2.C 3.B 4.A 5.A",
            "Text 121~25D A B C CText 226~30A C B D B",
            "Part B",
            "41.F 42.T 43.F 44.T 45.F",
        ]
        answers = extract_answer_key(blocks)
        self.assertEqual([answers[n] for n in range(21, 26)], list("DABCC"))
        self.assertEqual([answers[n] for n in range(41, 46)], list("FTFTF"))

    def test_english_two_subject_is_detected_from_header(self) -> None:
        self.assertEqual(
            _detect_subject(
                "2010年考研英语二真题.doc",
                ["2010 年全国硕士研究生招生考试", "英语（二）", "（科目代码：204）"],
            ),
            "英语二",
        )

    def test_true_false_part_b_is_parsed_as_objective_questions(self) -> None:
        blocks = [
            "Section II Reading Comprehension",
            "Part B",
            "Directions:",
            "Read the following text and decide whether each of the statements is true or false. Choose T if the statement is true or F if the statement is not true.",
            "Article paragraph one.",
            "Article paragraph two.",
            "Statement one.",
            "Statement two.",
            "Statement three.",
            "Statement four.",
            "Statement five.",
            "Section IIITranslation",
        ]
        self.assertTrue(_has_objective_part_b(blocks))
        unit = _parse_part_b(
            blocks,
            {41: "F", 42: "T", 43: "F", 44: "T", 45: "F"},
        )
        self.assertEqual(unit["subtype"], "true_false")
        self.assertEqual(unit["passage"], "Article paragraph one.\n\nArticle paragraph two.")
        self.assertEqual([question["stem"] for question in unit["questions"]], [
            "Statement one.",
            "Statement two.",
            "Statement three.",
            "Statement four.",
            "Statement five.",
        ])
        self.assertEqual(
            [option["key"] for option in unit["questions"][0]["options"]],
            ["T", "F"],
        )

    def test_translation_part_b_is_not_treated_as_objective(self) -> None:
        blocks = [
            "Part B",
            "Read the following text carefully and then translate the underlined segments into Chinese.",
        ]
        self.assertFalse(_has_objective_part_b(blocks))

    def test_validation_uses_questions_present_in_the_draft(self) -> None:
        def unit(unit_type: str, title: str, sequence: int, numbers: range) -> dict:
            return {
                "unit_type": unit_type,
                "subtype": "cloze" if unit_type == "cloze" else "reading_a",
                "title": title,
                "sequence": sequence,
                "passage": "Passage",
                "shared_data": {},
                "questions": [
                    {
                        "number": number,
                        "stem": "",
                        "options": [
                            {"key": key, "content": key}
                            for key in ("A", "B", "C", "D")
                        ],
                        "answer": "A",
                        "score": 0.5 if number <= 20 else 2.0,
                    }
                    for number in numbers
                ],
            }

        draft = {
            "answers": {str(number): "A" for number in range(1, 41)},
            "answer_status": {"status": "confirmed"},
            "answers_confirmed": True,
            "units": [
                unit("cloze", "完型填空", 1, range(1, 21)),
                unit("reading", "阅读 Text 1", 2, range(21, 26)),
                unit("reading", "阅读 Text 2", 3, range(26, 31)),
                unit("reading", "阅读 Text 3", 4, range(31, 36)),
                unit("reading", "阅读 Text 4", 5, range(36, 41)),
            ],
        }
        apply_answers_to_draft(draft)
        self.assertEqual(validate_draft(draft), [])


if __name__ == "__main__":
    unittest.main()
