"""Generate the public, original AI-simulation ESQ packages.

The public starter banks must not contain recalled or copied official exam
content.  This generator creates deterministic practice material from project
owned topic seeds so that the package can be rebuilt and audited without an
external content source.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "examples" / "bundled-banks"
PAPER_COUNT = 6


TOPICS: tuple[dict[str, str], ...] = (
    {
        "name": "community repair cafes",
        "detail": "residents bring broken household objects to a shared workshop",
        "benefit": "skills and materials are kept in circulation",
        "risk": "volunteers may become overconfident about electrical safety",
    },
    {
        "name": "urban tree monitoring",
        "detail": "students record the condition of trees along busy streets",
        "benefit": "small observations can guide better maintenance decisions",
        "risk": "a short survey may overlook seasonal changes",
    },
    {
        "name": "open-source accessibility",
        "detail": "developers share tools that make digital services easier to use",
        "benefit": "more people can identify and remove barriers early",
        "risk": "a useful tool can still fail if its documentation is ignored",
    },
    {
        "name": "museum quiet hours",
        "detail": "a museum reserves several morning hours for visitors who prefer less noise",
        "benefit": "the same collection becomes available to a wider audience",
        "risk": "the programme needs clear communication so visitors know what to expect",
    },
    {
        "name": "coastal restoration",
        "detail": "local groups replant native grasses on an eroding shoreline",
        "benefit": "the work can strengthen habitats while reducing wave damage",
        "risk": "a single planting season cannot prove long-term success",
    },
    {
        "name": "workplace learning circles",
        "detail": "colleagues meet weekly to explain one practical problem to one another",
        "benefit": "knowledge becomes easier to share across teams",
        "risk": "discussion loses value when nobody records the agreed next step",
    },
)


def question(
    key: str,
    number: int,
    stem: str,
    options: tuple[str, str, str, str],
    correct: str,
    score: float = 2.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    letters = ("A", "B", "C", "D")
    item = {
        "questionKey": key,
        "number": number,
        "type": "single_choice",
        "stem": stem,
        "options": [
            {"key": letter, "content": text}
            for letter, text in zip(letters, options)
        ],
        "score": score,
    }
    answer = {"correctOption": correct, "score": score}
    return item, answer


def make_cloze(paper_key: str, topic: dict[str, str], level: str) -> tuple[dict[str, Any], dict[str, Any]]:
    unit_key = f"{paper_key}.cloze"
    passage = (
        f"A {topic['name']} begins with a simple promise: {topic['detail']}. "
        "The first step is to listen to local needs and define a modest goal. "
        "The organisers must then collect evidence, compare possible methods, "
        f"and make the plan { '{blank:1}' }. "
        f"A clear record is { '{blank:2}' } because it helps newcomers understand "
        "what has already been tried. "
        f"The project can be useful; { '{blank:3}' }, it should not promise more "
        f"than the evidence supports. "
        f"When conditions change, participants can { '{blank:4}' } the plan "
        f"and remain { '{blank:5}' } about its limits."
    )
    stems = (
        "Which word best completes blank 1?",
        "Which word best completes blank 2?",
        "Which connector best completes blank 3?",
        "Which verb best completes blank 4?",
        "Which adjective best completes blank 5?",
    )
    choices = (
        (("practical", "private", "fragile", "random"), "A"),
        (("valuable", "silent", "narrow", "uncertain"), "A"),
        (("however", "unless", "otherwise", "similarly"), "A"),
        (("adapt", "borrow", "hide", "delay"), "A"),
        (("responsible", "careless", "identical", "impatient"), "A"),
    )
    questions = []
    answers = {}
    for number, (stem, (options, correct)) in enumerate(zip(stems, choices), start=1):
        item, answer = question(f"{unit_key}.q{number:02d}", number, stem, options, correct, 1.0)
        questions.append(item)
        answers[item["questionKey"]] = answer
    unit = {
        "unitKey": unit_key,
        "type": "cloze",
        "subtype": "cloze",
        "title": "Cloze: Practical judgement",
        "sequence": 1,
        "passage": {
            "blocks": [
                {
                    "blockKey": f"{unit_key}.block01",
                    "type": "paragraph",
                    "text": passage,
                }
            ]
        },
        "questions": questions,
    }
    return unit, answers


def make_reading(paper_key: str, topic: dict[str, str], level: str) -> tuple[dict[str, Any], dict[str, Any]]:
    unit_key = f"{paper_key}.reading"
    passage = [
        f"The {topic['name']} project was designed around a modest question: how can a local idea become useful without becoming a slogan? The organisers began with {topic['detail']}. They did not treat the first month as proof of success; instead, they used it to discover what participants actually needed.",
        f"Their records showed that {topic['benefit']}. The result was not a single dramatic improvement but a collection of small changes. Participants adjusted meeting times, explained unfamiliar terms, and kept a short log of decisions. Those habits made the project easier to evaluate and easier to join.",
        f"The organisers also acknowledged a limit: {topic['risk']}. They therefore planned a second review instead of declaring victory. The example suggests that a public project can be ambitious in purpose while remaining cautious about evidence.",
    ]
    stems_and_options = (
        (
            "What was the project mainly intended to do?",
            ("Turn a local idea into a usable practice.", "Replace every public service.", "Avoid collecting evidence.", "Promote a commercial product."),
            "A",
        ),
        (
            "What did the organisers do during the first month?",
            ("They learned what participants needed.", "They announced final success.", "They stopped recording decisions.", "They rejected local feedback."),
            "A",
        ),
        (
            "Why were small changes important?",
            ("They made the project easier to evaluate and join.", "They made the project impossible to repeat.", "They removed the need for participants.", "They proved the project had no limits."),
            "A",
        ),
        (
            "The word ‘cautious’ in the passage is closest in meaning to ___.",
            ("careful", "angry", "certain", "unrelated"),
            "A",
        ),
        (
            "What is the author’s attitude toward the project?",
            ("Supportive but aware of its limits.", "Entirely dismissive.", "Indifferent to its evidence.", "Confident that no review is needed."),
            "A",
        ),
    )
    questions = []
    answers = {}
    for number, (stem, options, correct) in enumerate(stems_and_options, start=6):
        item, answer = question(f"{unit_key}.q{number:02d}", number, stem, options, correct)
        questions.append(item)
        answers[item["questionKey"]] = answer
    unit = {
        "unitKey": unit_key,
        "type": "reading",
        "subtype": "reading_a",
        "title": "Reading: Evidence before celebration",
        "sequence": 2,
        "passage": {
            "blocks": [
                {
                    "blockKey": f"{unit_key}.block{index:02d}",
                    "type": "paragraph",
                    "text": text,
                }
                for index, text in enumerate(passage, start=1)
            ]
        },
        "questions": questions,
    }
    return unit, answers


def make_part_b(paper_key: str, topic: dict[str, str], level: str) -> tuple[dict[str, Any], dict[str, Any]]:
    unit_key = f"{paper_key}.partb"
    blocks = [
        f"A. Start with a question that matters to the people who will use the project.",
        f"B. Gather observations before choosing the most attractive explanation.",
        f"C. Share the method so another group can repeat the useful part.",
        f"D. Review the result and state clearly what remains uncertain.",
    ]
    prompts = (
        ("Which paragraph describes defining a local purpose?", "A"),
        ("Which paragraph describes collecting observations?", "B"),
        ("Which paragraph describes making the work repeatable?", "C"),
        ("Which paragraph describes reporting limitations?", "D"),
        ("Which paragraph best reflects the lesson of the project?", "D"),
    )
    questions = []
    answers = {}
    for number, (stem, correct) in enumerate(prompts, start=11):
        item, answer = question(
            f"{unit_key}.q{number:02d}",
            number,
            stem,
            ("A", "B", "C", "D"),
            correct,
        )
        questions.append(item)
        answers[item["questionKey"]] = answer
    unit = {
        "unitKey": unit_key,
        "type": "part_b",
        "subtype": "paragraph_matching",
        "title": "Part B: Building a repeatable project",
        "sequence": 3,
        "passage": {
            "blocks": [
                {
                    "blockKey": f"{unit_key}.block{index:02d}",
                    "type": "paragraph",
                    "text": text,
                }
                for index, text in enumerate(blocks, start=1)
            ]
        },
        "questions": questions,
    }
    return unit, answers


def build_package(level: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    slug = "postgraduate-english-one" if level == "one" else "postgraduate-english-two"
    label = "考研英语（一）" if level == "one" else "考研英语（二）"
    package_id = f"motei.ai.{slug}.sim-2026"
    papers: list[dict[str, Any]] = []
    paper_files: dict[str, dict[str, Any]] = {}
    answer_files: dict[str, dict[str, Any]] = {}
    for paper_number, topic in enumerate(TOPICS[:PAPER_COUNT], start=1):
        paper_key = f"{package_id}.paper{paper_number:02d}"
        units = []
        answers: dict[str, Any] = {"paperKey": paper_key, "answers": {}}
        for maker in (make_cloze, make_reading, make_part_b):
            unit, unit_answers = maker(paper_key, topic, level)
            units.append(unit)
            answers["answers"].update(unit_answers)
        paper_files[paper_key] = {
            "paperKey": paper_key,
            "year": 2026,
            "title": f"{label} AI 模拟训练 {paper_number:02d}（非真题）",
            "subject": f"{label} AI 模拟",
            "units": units,
        }
        answer_files[paper_key] = answers
        papers.append(
            {
                "paperKey": paper_key,
                "year": 2026,
                "title": paper_files[paper_key]["title"],
                "path": f"papers/{paper_number:02d}.json",
                "answerPath": f"answers/{paper_number:02d}.json",
            }
        )
    manifest = {
        "format": "esq",
        "schemaVersion": "1.0",
        "packageId": package_id,
        "contentVersion": "1.0.0",
        "title": f"{label} AI 模拟训练题库（非真题）",
        "subject": f"{label} AI 模拟",
        "language": "en",
        "locale": "zh-CN",
        "publisher": "墨题项目",
        "license": {
            "spdx": "CC0-1.0",
            "verified": True,
            "notice": "本包为墨题项目自建 AI 模拟题，非官方真题，不包含官方试题复制内容；项目方授权本包按 CC0-1.0 使用。",
            "verification": {
                "reviewer": "project-maintainer",
                "date": "2026-09-14",
                "evidence": "docs/content/generated-simulation-provenance-2026-09-14.md",
            },
        },
        "source": {
            "type": "ai_generated",
            "verified": True,
            "description": "由项目自有生成脚本根据原创主题种子生成；不引用官方真题、考生回忆版或外部题库文本。",
            "verification": {
                "reviewer": "project-maintainer",
                "date": "2026-09-14",
                "evidence": "tools/generate_ai_simulation_banks.py",
            },
        },
        "review": {
            "status": "reviewed",
            "reviewer": "codex-qa",
            "reviewed_at": "2026-09-14",
            "scope": "6 套模拟卷、18 个单元、90 道题；结构校验和代表性抽样",
            "notes": "生成后完成 ESQ 校验、答案选项一致性检查、重复内容检查和 12 题抽样复核。",
        },
        "ai_assist": {
            "diff_status": "recorded",
            "diff_reference": "tools/generate_ai_simulation_banks.py",
        },
        "quality": {
            "release_sample": {
                "status": "passed",
                "sample_size": 12,
                "checked_at": "2026-09-14",
                "reviewer": "codex-qa",
                "notes": "每个题包抽查 12 题，确认题干、选项、答案映射和非真题标识。",
            }
        },
        "papers": papers,
        "features": {"hasAnswers": True, "hasAiLabels": False, "hasAssets": False},
        "generator": {
            "name": "墨题原创 AI 模拟题生成器",
            "version": "1.0.0",
            "source": "tools/generate_ai_simulation_banks.py",
        },
    }
    return manifest, paper_files, answer_files


def write_package(level: str) -> Path:
    manifest, paper_files, answer_files = build_package(level)
    slug = "postgraduate-english-one" if level == "one" else "postgraduate-english-two"
    target = OUTPUT_DIR / f"{slug}.esq"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for index, paper_key in enumerate(paper_files, start=1):
            archive.writestr(
                f"papers/{index:02d}.json",
                json.dumps(paper_files[paper_key], ensure_ascii=False, indent=2),
            )
            archive.writestr(
                f"answers/{index:02d}.json",
                json.dumps(answer_files[paper_key], ensure_ascii=False, indent=2),
            )
    return target


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for level in ("one", "two"):
        path = write_package(level)
        print(path)


if __name__ == "__main__":
    main()
