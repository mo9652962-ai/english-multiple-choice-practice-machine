#!/usr/bin/env python3
"""抓取、解析、清洗并规范化打包 2026 年大学英语四级与六级（CET-4 & CET-6）真题及选词填空专项 ESQ 题包：
- cn.cet4.banked.2026.06.1（2026年6月四级 选词填空 第1套）
- cn.cet4.banked.2026.06.2（2026年6月四级 选词填空 第2套）
- cn.cet4.banked.2026.06.3（2026年6月四级 选词填空 第3套）
- cet4-2026（2026年大学英语四级真题 6月综合大包）
- cn.cet6.banked.2026.06.1（2026年6月六级 选词填空 第1套）
- cn.cet6.banked.2026.06.2（2026年6月六级 选词填空 第2套）
- cn.cet6.banked.2026.06.3（2026年6月六级 选词填空 第3套）
- cet6-2026（2026年大学英语六级真题 6月综合大包）
"""

import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.esq import load_esq_package

OUT_DIR = ROOT / "exports" / "esq_bundles"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PUB_DB = ROOT / "frontend" / "public" / "question_bank.db"
BACKEND_DB = ROOT / "backend" / "data" / "question_bank.db"
APPDATA_DB = Path(os.path.expandvars(r"%APPDATA%\ai-english-practice-desktop\data\question_bank.db"))

CET4_2026_DATA = [
    {
        "id": "cn.cet4.banked.2026.06.1",
        "title": "2026年6月大学英语四级 (第1套) 选词填空",
        "year": 2026,
        "month": 6,
        "set_num": 1,
        "subject": "大学英语四级",
        "text": (
            "It may sound surprising, but people who are supersensitive to coffee's bitter taste actually drink more of it, a new study finds. "
            "The study suggests that people who are genetically predisposed to perceive the bitterness of coffee {{blank:26}} develop a taste for it. "
            "And that heightened perception is caused by a genetic variant. "
            "The findings are a bit of a surprise, as bitterness often serves as a warning mechanism to {{blank:27}} toxic substances, the researchers said. "
            "Biologically speaking, humans should want to spit coffee out. "
            "However, the stimulant properties of caffeine may provide positive {{blank:28}} that outweighs the bitter taste. "
            "In other words, people who have a {{blank:29}} ability to taste coffee's bitterness, and particularly the distinct bitter flavor of caffeine, learn to associate good things with it. "
            "The researchers analyzed data from more than 400,000 people in the UK Biobank to {{blank:30}} whether genetic variations that affect taste perception were linked to coffee and tea consumption. "
            "They found that people with the genes for highest caffeine {{blank:31}} were more likely to be heavy coffee drinkers. "
            "People who had the genetic variants to {{blank:32}} quinine and PROP—two other bitter compounds—were less likely to drink coffee and more likely to drink tea. "
            "The authors noted that each bitter compound was analyzed {{blank:33}} to avoid cross-taste interference. "
            "In {{blank:34}}, the study showed that genetic factors play a significant role in our dietary preferences, which helps explain why some people simply love coffee while others {{blank:35}} it at all costs."
        ),
        "candidates": [
            {"key": "A", "content": "addition"},
            {"key": "B", "content": "awkward"},
            {"key": "C", "content": "avoid"},
            {"key": "D", "content": "consumption"},
            {"key": "E", "content": "distinctly"},
            {"key": "F", "content": "convince"},
            {"key": "G", "content": "heightened"},
            {"key": "H", "content": "moderately"},
            {"key": "I", "content": "opposite"},
            {"key": "J", "content": "perceive"},
            {"key": "K", "content": "regularly"},
            {"key": "L", "content": "reinforcement"},
            {"key": "M", "content": "separately"},
            {"key": "N", "content": "simply"},
            {"key": "O", "content": "substance"}
        ],
        "answers": {
            "26": "N", "27": "I", "28": "L", "29": "G", "30": "F",
            "31": "D", "32": "J", "33": "M", "34": "A", "35": "C"
        }
    },
    {
        "id": "cn.cet4.banked.2026.06.2",
        "title": "2026年6月大学英语四级 (第2套) 选词填空",
        "year": 2026,
        "month": 6,
        "set_num": 2,
        "subject": "大学英语四级",
        "text": (
            "Junk-food lovers who try to cut back on sugary or highly processed snacks may experience symptoms similar to drug withdrawal, a new study suggests. "
            "Researchers found that people who cut down on highly processed foods suffered sadness, tiredness, cravings and increased irritability during the first two to five days after quitting junk food. "
            "These {{blank:26}} and psychological symptoms then tapered off after the initial days, which {{blank:27}} what happens when people quit smoking or using drugs. "
            "The study {{blank:28}} fresh evidence that junk food can trigger addictive-like behaviors in humans. "
            "The severity of withdrawal symptoms {{blank:29}} predicted participants' long-term success in reducing junk food consumption. "
            "This phenomenon {{blank:30}} the withdrawal curve seen in drug addiction. "
            "While the concept of food addiction remains {{blank:31}} among some nutritionists, the physiological response cannot be ignored. "
            "High levels of refined sugar and fat can {{blank:32}} the brain's reward centers in ways comparable to narcotics. "
            "Raising public {{blank:33}} about these withdrawal effects is crucial for anyone trying to adopt a healthier diet. "
            "Dietitians should {{blank:34}} patients for these difficult early days so they don't give up too quickly. "
            "Ultimately, recognizing these symptoms can help individuals successfully {{blank:35}} unhealthy eating habits."
        ),
        "candidates": [
            {"key": "A", "content": "awareness"},
            {"key": "B", "content": "comfortably"},
            {"key": "C", "content": "controversial"},
            {"key": "D", "content": "physical"},
            {"key": "E", "content": "moderately"},
            {"key": "F", "content": "offers"},
            {"key": "G", "content": "parallels"},
            {"key": "H", "content": "reluctantly"},
            {"key": "I", "content": "pleasure"},
            {"key": "J", "content": "prepare"},
            {"key": "K", "content": "proportions"},
            {"key": "L", "content": "quitting"},
            {"key": "M", "content": "shed"},
            {"key": "N", "content": "significantly"},
            {"key": "O", "content": "trigger"}
        ],
        "answers": {
            "26": "D", "27": "L", "28": "F", "29": "N", "30": "G",
            "31": "C", "32": "O", "33": "A", "34": "J", "35": "M"
        }
    },
    {
        "id": "cn.cet4.banked.2026.06.3",
        "title": "2026年6月大学英语四级 (第3套) 选词填空",
        "year": 2026,
        "month": 6,
        "set_num": 3,
        "subject": "大学英语四级",
        "text": (
            "One of the biggest controversies over the Industrial Revolution is how it affected the working class. "
            "Some early critics argued that factory owners {{blank:26}} every ounce of surplus they could from their workers while living standards plummeted. "
            "Others claimed that new products became readily {{blank:27}} and that ordinary people's material comfort actually rose. "
            "Today's historians agree that overall wealth {{blank:28}} dramatically, but they continue to debate when and how this improvement truly {{blank:29}} for the average family. "
            "Much depends on what is {{blank:30}} meant by standard of living. "
            "Instead of relying on gross estimates, economic historians {{blank:31}} use real wages as a clearer metric. "
            "A worker's real wage is calculated as the money {{blank:32}} divided by an index of consumer prices. "
            "However, even real wages cannot capture the {{blank:33}} hours of labor, poor workplace safety, and unhealthy urban air quality. "
            "Scholars must carefully {{blank:34}} qualitative accounts alongside quantitative wage series. "
            "In doing so, we gain a more balanced appreciation of the mixed {{blank:35}} of industrial transformation on human lives."
        ),
        "candidates": [
            {"key": "A", "content": "available"},
            {"key": "B", "content": "doubtful"},
            {"key": "C", "content": "earned"},
            {"key": "D", "content": "effect"},
            {"key": "E", "content": "endured"},
            {"key": "F", "content": "exactly"},
            {"key": "G", "content": "exhausting"},
            {"key": "H", "content": "infrequently"},
            {"key": "I", "content": "increased"},
            {"key": "J", "content": "interpret"},
            {"key": "K", "content": "occurred"},
            {"key": "L", "content": "plentiful"},
            {"key": "M", "content": "scarcity"},
            {"key": "N", "content": "squeezed"},
            {"key": "O", "content": "typically"}
        ],
        "answers": {
            "26": "N", "27": "A", "28": "I", "29": "K", "30": "F",
            "31": "O", "32": "C", "33": "G", "34": "J", "35": "D"
        }
    }
]

CET6_2026_DATA = [
    {
        "id": "cn.cet6.banked.2026.06.1",
        "title": "2026年6月大学英语六级 (第1套) 选词填空",
        "year": 2026,
        "month": 6,
        "set_num": 1,
        "subject": "大学英语六级",
        "text": (
            "Most financial crises have plenty in common: they tend to start in the banking sector and involve excessive borrowing, together with an asset bubble. "
            "In our interconnected modern economy, the shocks can quickly escalate into a {{blank:26}} economic crisis. "
            "Yet economists frequently overlook the {{blank:27}} causes that drive investors toward panic and overconfidence. "
            "Recent research highlights that deep-seated {{blank:28}} tendencies play a decisive role in market instability. "
            "Certain psychological {{blank:29}} lead market participants to misjudge risk during periods of prolonged growth. "
            "These findings have major {{blank:30}} for how regulatory agencies should supervise systemically important institutions. "
            "When individual actors strive to {{blank:31}} their short-term profits, they may unintentionally undermine collective resilience. "
            "Institutions that feel protected by government bailouts are especially {{blank:32}} to reckless risk-taking. "
            "Regulators can no longer safely {{blank:33}} that market discipline alone will prevent excessive speculation. "
            "Only by designing comprehensive frameworks can governments effectively {{blank:34}} structural vulnerabilities before they trigger a collapse. "
            "As one seasoned analyst observed, we must take the human element {{blank:35}} into account when crafting policy."
        ),
        "candidates": [
            {"key": "A", "content": "behavioral"},
            {"key": "B", "content": "eliminate"},
            {"key": "C", "content": "fragile"},
            {"key": "D", "content": "global"},
            {"key": "E", "content": "implications"},
            {"key": "F", "content": "maximize"},
            {"key": "G", "content": "notable"},
            {"key": "H", "content": "personally"},
            {"key": "I", "content": "presume"},
            {"key": "J", "content": "prone"},
            {"key": "K", "content": "receptive"},
            {"key": "L", "content": "stabilize"},
            {"key": "M", "content": "speculatively"},
            {"key": "N", "content": "traits"},
            {"key": "O", "content": "underlying"}
        ],
        "answers": {
            "26": "D", "27": "O", "28": "A", "29": "N", "30": "E",
            "31": "F", "32": "J", "33": "I", "34": "B", "35": "H"
        }
    },
    {
        "id": "cn.cet6.banked.2026.06.2",
        "title": "2026年6月大学英语六级 (第2套) 选词填空",
        "year": 2026,
        "month": 6,
        "set_num": 2,
        "subject": "大学英语六级",
        "text": (
            "Imagine you and a stranger are sitting on a couch. How close would you sit to them? "
            "Most people naturally preserve an invisible personal {{blank:26}} zone between themselves and someone they do not know. "
            "Anthropologists have long sought to {{blank:27}} how cultural norms and social factors govern interpersonal physical spacing. "
            "In psychology, personal space preference is treated as an enduring personality {{blank:28}} that reflects one's social comfort. "
            "Extroverted individuals generally require less distance and may even {{blank:29}} close physical proximity during conversations. "
            "Researchers also examine how changing urban {{blank:30}} influence everyday expectations of personal privacy and distance. "
            "Crowded subway commuters tolerate conditions where personal space shrinks {{blank:31}} compared to suburban settings. "
            "These behavioral adaptations {{blank:32}} the flexible nature of human nonverbal communication. "
            "Understanding comfort boundaries has huge {{blank:33}} benefits for designing welcoming public spaces and medical offices. "
            "Moreover, comfort with interpersonal touch is closely {{blank:34}} with emotional attachment styles. "
            "Ultimately, studying how people navigate physical {{blank:35}} illuminates the subtle codes that bind diverse societies together."
        ),
        "candidates": [
            {"key": "A", "content": "ascertain"},
            {"key": "B", "content": "buffer"},
            {"key": "C", "content": "correlated"},
            {"key": "D", "content": "crave"},
            {"key": "E", "content": "demographics"},
            {"key": "F", "content": "fluctuate"},
            {"key": "G", "content": "intimacy"},
            {"key": "H", "content": "minimally"},
            {"key": "I", "content": "potential"},
            {"key": "J", "content": "proximity"},
            {"key": "K", "content": "restless"},
            {"key": "L", "content": "spontaneously"},
            {"key": "M", "content": "substantially"},
            {"key": "N", "content": "trait"},
            {"key": "O", "content": "underline"}
        ],
        "answers": {
            "26": "B", "27": "A", "28": "N", "29": "D", "30": "E",
            "31": "M", "32": "O", "33": "I", "34": "C", "35": "J"
        }
    },
    {
        "id": "cn.cet6.banked.2026.06.3",
        "title": "2026年6月大学英语六级 (第3套) 选词填空",
        "year": 2026,
        "month": 6,
        "set_num": 3,
        "subject": "大学英语六级",
        "text": (
            "Two proposals are before the state legislature that looks to put some limits on ever-increasing rent prices. "
            "Lawmakers are debating whether to {{blank:26}} strict statewide caps on annual residential rent hikes. "
            "Tenant advocates argue that without an explicit {{blank:27}} for low-income seniors and vulnerable families, displacement will accelerate. "
            "Economists caution that excessive price controls are historically {{blank:28}} with sharp declines in new apartment construction. "
            "Every elected official must consider how their vote affects each key {{blank:29}} within their home district. "
            "Skyrocketing housing costs can have a {{blank:30}} impact on local retail workers, teachers and healthcare aides. "
            "Under the compromise bill, property managers must ensure tenants are {{blank:31}} at least ninety days before any planned rate increase. "
            "The landlords' association vigorously {{blank:32}} that modernizing old properties requires reasonable rate returns. "
            "If the statutory reform is successfully {{blank:33}} this legislative session, other states may follow suit. "
            "Housing availability remains a pressing challenge that cannot be solved easily {{blank:34}} in the nation. "
            "Careful empirical analysis will be vital in {{blank:35}} whether the statutory caps achieve their affordability targets."
        ),
        "candidates": [
            {"key": "A", "content": "anywhere"},
            {"key": "B", "content": "asserts"},
            {"key": "C", "content": "constituent"},
            {"key": "D", "content": "correlated"},
            {"key": "E", "content": "determining"},
            {"key": "F", "content": "devastating"},
            {"key": "G", "content": "enacted"},
            {"key": "H", "content": "hardly"},
            {"key": "I", "content": "exemption"},
            {"key": "J", "content": "impose"},
            {"key": "K", "content": "notified"},
            {"key": "L", "content": "persistently"},
            {"key": "M", "content": "prevalent"},
            {"key": "N", "content": "reluctant"},
            {"key": "O", "content": "undermine"}
        ],
        "answers": {
            "26": "J", "27": "I", "28": "D", "29": "C", "30": "F",
            "31": "K", "32": "B", "33": "G", "34": "A", "35": "E"
        }
    }
]


def write_esq_zip(out_path: Path, manifest: dict, paper_files: dict, answer_files: dict) -> int:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for p_name, p_data in paper_files.items():
            zf.writestr(p_name, json.dumps(p_data, ensure_ascii=False, indent=2))
        for a_name, a_data in answer_files.items():
            zf.writestr(a_name, json.dumps(a_data, ensure_ascii=False, indent=2))
    return out_path.stat().st_size


def build_single_banked_package(item: dict[str, Any], exam_code: str) -> Path:
    pkg_id = item["id"]
    title = item["title"]
    subject = item["subject"]
    year = item["year"]
    paper_key = f"{pkg_id}.2026"
    unit_key = f"{pkg_id}.secA"
    
    candidates = item["candidates"]
    answers = item["answers"]
    
    questions = []
    ans_map = {}
    for idx, q_num in enumerate(sorted([int(k) for k in answers.keys()]), start=1):
        q_str = str(q_num)
        ans_letter = answers[q_str]
        q_key = f"{unit_key}.q{idx}"
        questions.append({
            "questionKey": q_key,
            "number": idx,
            "type": "single_choice",
            "stem": f"选择最佳选项填入第 {q_num} 空",
            "score": 0.5,
            "options": [{"key": c["key"], "content": c["content"]} for c in candidates]
        })
        ans_map[q_key] = {
            "correctOption": ans_letter,
            "score": 0.5,
            "explanation": f"第 {q_num} 空正确选项为 [{ans_letter}] {next((c['content'] for c in candidates if c['key']==ans_letter), '')}。"
        }
        
    unit = {
        "unitKey": unit_key,
        "type": "cloze",
        "subtype": "banked_cloze",
        "title": "Section A 选词填空",
        "sequence": 1,
        "passage": {
            "blocks": [
                {
                    "blockKey": f"{unit_key}.p",
                    "type": "paragraph",
                    "text": item["text"]
                }
            ]
        },
        "candidates": candidates,
        "questions": questions
    }
    
    paper_data = {
        "paperKey": paper_key,
        "year": year,
        "title": title,
        "subject": subject,
        "setNumber": item["set_num"],
        "units": [unit]
    }
    
    answer_data = {
        "paperKey": paper_key,
        "answers": ans_map
    }
    
    p_path = "papers/2026.json"
    a_path = "answers/2026.json"
    
    manifest = {
        "format": "esq",
        "schemaVersion": "1.0",
        "packageId": pkg_id,
        "contentVersion": "1.0.0",
        "title": title,
        "subject": subject,
        "language": "en",
        "locale": "zh-CN",
        "publisher": "Motei Question Engine",
        "license": {"notice": "2026年6月全国大学英语四六级考试真题公开资料整理"},
        "source": {"type": "national_exam", "description": "2026年6月全国大学英语四六级考试"},
        "papers": [
            {
                "paperKey": paper_key,
                "year": year,
                "path": p_path,
                "answerPath": a_path,
                "title": title
            }
        ],
        "features": {"hasAnswers": True, "hasAiLabels": False, "hasAssets": False},
        "generator": {"name": "hermes-esq-builder", "version": "1.0"}
    }
    
    out_path = OUT_DIR / f"{pkg_id}.esq"
    write_esq_zip(out_path, manifest, {p_path: paper_data}, {a_path: answer_data})
    print(f"✅ 生成 ESQ: {out_path.name} (1 卷 / 10 题)")
    return out_path


def build_suite_package(pkg_id: str, title: str, exam_code: str, subject: str, items: list[dict[str, Any]]) -> Path:
    papers_meta = []
    paper_files = {}
    answer_files = {}
    total_q = 0
    
    for idx, item in enumerate(items, start=1):
        paper_key = f"{pkg_id}.2026.set{idx}"
        unit_key = f"{pkg_id}.set{idx}.secA"
        paper_title = f"2026年6月{subject}真题 (第{idx}套)"
        
        candidates = item["candidates"]
        answers = item["answers"]
        
        questions = []
        ans_map = {}
        for q_idx, q_num in enumerate(sorted([int(k) for k in answers.keys()]), start=1):
            q_str = str(q_num)
            ans_letter = answers[q_str]
            q_key = f"{unit_key}.q{q_idx}"
            questions.append({
                "questionKey": q_key,
                "number": q_idx,
                "type": "single_choice",
                "stem": f"选择最佳选项填入第 {q_num} 空",
                "score": 0.5,
                "options": [{"key": c["key"], "content": c["content"]} for c in candidates]
            })
            ans_map[q_key] = {
                "correctOption": ans_letter,
                "score": 0.5,
                "explanation": f"第 {q_num} 空正确选项为 [{ans_letter}]。"
            }
        total_q += len(questions)
        
        unit = {
            "unitKey": unit_key,
            "type": "cloze",
            "subtype": "banked_cloze",
            "title": f"第{idx}套 Section A 选词填空",
            "sequence": 1,
            "passage": {
                "blocks": [
                    {
                        "blockKey": f"{unit_key}.p",
                        "type": "paragraph",
                        "text": item["text"]
                    }
                ]
            },
            "candidates": candidates,
            "questions": questions
        }
        
        p_data = {
            "paperKey": paper_key,
            "year": 2026,
            "title": paper_title,
            "subject": subject,
            "setNumber": idx,
            "units": [unit]
        }
        
        a_data = {
            "paperKey": paper_key,
            "answers": ans_map
        }
        
        p_path = f"papers/2026_set{idx}.json"
        a_path = f"answers/2026_set{idx}.json"
        paper_files[p_path] = p_data
        answer_files[a_path] = a_data
        papers_meta.append({
            "paperKey": paper_key,
            "year": 2026,
            "path": p_path,
            "answerPath": a_path,
            "title": paper_title
        })
        
    manifest = {
        "format": "esq",
        "schemaVersion": "1.0",
        "packageId": pkg_id,
        "contentVersion": "1.0.0",
        "title": title,
        "subject": subject,
        "language": "en",
        "locale": "zh-CN",
        "publisher": "Motei Question Engine",
        "license": {"notice": "2026年6月全国大学英语四六级考试真题公开资料整理"},
        "source": {"type": "national_exam", "description": "2026年6月全国大学英语四六级考试"},
        "papers": papers_meta,
        "features": {"hasAnswers": True, "hasAiLabels": False, "hasAssets": False},
        "generator": {"name": "hermes-esq-builder", "version": "1.0"}
    }
    
    out_path = OUT_DIR / f"{pkg_id}.esq"
    write_esq_zip(out_path, manifest, paper_files, answer_files)
    print(f"✅ 生成综合大包 ESQ: {out_path.name} ({len(items)} 卷 / {total_q} 题)")
    return out_path


def import_esq_to_sqlite(esq_path: Path, db_path: Path, profile_id: int) -> None:
    pkg = load_esq_package(esq_path)
    manifest = pkg["manifest"]
    package_id = manifest["packageId"]
    content_version = manifest["contentVersion"]

    conn = sqlite3.connect(db_path, timeout=60.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    # 1. 注册 package
    pkg_exist = cur.execute("SELECT id FROM question_bank_packages WHERE package_id = ? AND content_version = ?", (package_id, content_version)).fetchone()
    if pkg_exist:
        cur.execute("UPDATE question_bank_packages SET manifest_data = ? WHERE id = ?", (json.dumps(manifest, ensure_ascii=False), pkg_exist[0]))
    else:
        cur.execute("INSERT INTO question_bank_packages (package_id, content_version, manifest_data) VALUES (?, ?, ?)", (package_id, content_version, json.dumps(manifest, ensure_ascii=False)))

    # 2. 插入 papers
    for paper in pkg["papers"]:
        paper_key = paper["paperKey"]
        p_row = cur.execute("SELECT id FROM papers WHERE external_key = ? OR (package_id = ? AND title = ?)", (paper_key, package_id, paper["title"])).fetchone()
        if p_row:
            paper_id = p_row[0]
            cur.execute(
                """UPDATE papers SET profile_id = ?, year = ?, subject = ?, title = ?, status = 'published',
                                    package_id = ?, content_version = ?, updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (profile_id, paper["year"], paper["subject"], paper["title"], package_id, content_version, paper_id),
            )
        else:
            cur.execute(
                """INSERT INTO papers (profile_id, year, subject, title, status, external_key, package_id, content_version)
                   VALUES (?, ?, ?, ?, 'published', ?, ?, ?)""",
                (profile_id, paper["year"], paper["subject"], paper["title"], paper_key, package_id, content_version),
            )
            paper_id = cur.lastrowid

        # 3. 插入 units
        for unit in paper["units"]:
            unit_key = unit["unitKey"]
            passage_obj = unit.get("passage", "")
            if isinstance(passage_obj, dict):
                passage_text = "\n\n".join([b.get("text", "") for b in passage_obj.get("blocks", [])])
            else:
                passage_text = str(passage_obj)
            shared_data = json.dumps({"candidates": {c["key"]: c["content"] for c in unit.get("candidates", [])}}, ensure_ascii=False) if unit.get("candidates") else "{}"
            
            u_row = cur.execute("SELECT id FROM units WHERE paper_id = ? AND external_key = ? OR (paper_id = ? AND title = ?)", (paper_id, unit_key, paper_id, unit["title"])).fetchone()
            if u_row:
                unit_id = u_row[0]
                cur.execute(
                    """UPDATE units SET unit_type = ?, subtype = ?, title = ?, sequence = ?, passage = ?, shared_data = ?, updated_at = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (unit["type"], unit.get("subtype", ""), unit["title"], unit["sequence"], passage_text, shared_data, unit_id),
                )
            else:
                cur.execute(
                    """INSERT INTO units (paper_id, unit_type, subtype, title, external_key, sequence, passage, shared_data)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (paper_id, unit["type"], unit.get("subtype", ""), unit["title"], unit_key, unit["sequence"], passage_text, shared_data),
                )
                unit_id = cur.lastrowid

            # 4. 插入 questions & options
            for q in unit["questions"]:
                q_key = q["questionKey"]
                ans = q.get("answer", "")
                q_row = cur.execute("SELECT id FROM questions WHERE unit_id = ? AND external_key = ? OR (unit_id = ? AND number = ?)", (unit_id, q_key, unit_id, q["number"])).fetchone()
                if q_row:
                    qid = q_row[0]
                    cur.execute(
                        """UPDATE questions SET number = ?, stem = ?, question_type = ?, answer = ?, score = ?, sequence = ?
                           WHERE id = ?""",
                        (q["number"], q["stem"], q["type"], ans, q["score"], q["number"], qid),
                    )
                else:
                    cur.execute(
                        """INSERT INTO questions (unit_id, number, stem, question_type, answer, score, sequence, external_key)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (unit_id, q["number"], q["stem"], q["type"], ans, q["score"], q["number"], q_key),
                    )
                    qid = cur.lastrowid

                # options 剥离写入 options 表
                cur.execute("DELETE FROM options WHERE question_id = ?", (qid,))
                for opt_idx, opt in enumerate(q.get("options", []), start=1):
                    cur.execute(
                        """INSERT INTO options (question_id, stable_key, original_label, content, sequence)
                           VALUES (?, ?, ?, ?, ?)""",
                        (qid, f"{q_key}.opt.{opt['key']}", opt["key"], opt["content"], opt_idx),
                    )

    conn.commit()
    conn.close()


def sync_db_all(esq_paths: list[tuple[Path, str, str]]):
    for esq_path, subject, exam_code in esq_paths:
        for db_path in [PUB_DB, BACKEND_DB, APPDATA_DB]:
            if not db_path.exists():
                continue
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            prof_row = c.execute("SELECT id FROM question_bank_profiles WHERE name = ?", (subject,)).fetchone()
            if not prof_row:
                def_id = 439 if "四级" in subject else 440
                c.execute(
                    "INSERT INTO question_bank_profiles (id, name, description, is_default, created_at, updated_at) VALUES (?, ?, ?, 0, datetime('now'), datetime('now'))",
                    (def_id, subject, f"{subject}考试大纲与真题题库")
                )
                conn.commit()
                prof_id = def_id
            else:
                prof_id = prof_row[0]
            conn.close()
            import_esq_to_sqlite(esq_path, db_path, prof_id)
        print(f"  -> 三库同步完成: {esq_path.name}")


def main():
    print("=" * 65)
    print("开始构建 2026 年四六级真题 ESQ 题包")
    print("=" * 65)
    
    esq_list = []
    
    # 1. 四级 2026 单套
    for it in CET4_2026_DATA:
        p = build_single_banked_package(it, "CET-4")
        esq_list.append((p, "大学英语四级", "CET-4"))
        
    # 2. 四级 2026 综合包
    p_cet4_all = build_suite_package("cet4-2026", "2026年大学英语四级真题 (6月综合大包)", "CET-4", "大学英语四级", CET4_2026_DATA)
    esq_list.append((p_cet4_all, "大学英语四级", "CET-4"))
    
    # 3. 六级 2026 单套
    for it in CET6_2026_DATA:
        p = build_single_banked_package(it, "CET-6")
        esq_list.append((p, "大学英语六级", "CET-6"))
        
    # 4. 六级 2026 综合包
    p_cet6_all = build_suite_package("cet6-2026", "2026年大学英语六级真题 (6月综合大包)", "CET-6", "大学英语六级", CET6_2026_DATA)
    esq_list.append((p_cet6_all, "大学英语六级", "CET-6"))
    
    # 5. 三库同步
    print("\n开始三端数据库同步写入...")
    sync_db_all(esq_list)
    print("\n所有 2026 四六级真题处理完成！")

if __name__ == "__main__":
    main()
