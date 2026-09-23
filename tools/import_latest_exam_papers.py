#!/usr/bin/env python3
"""抓取、解析、清洗并规范化打包 2025-2026 最新真题/新题型全套 ESQ 题包：
1. 2026 年高考英语全国 I 卷（阅读 A-D 15 题 + 七选五 5 题 + 完形 15 题 = 35 题选择题全卷）
2. 2025 年考研英语（一）真题（完形 20 + 阅读 20 + 新题型 5 = 45 题完整客观卷）
3. 2025 年考研英语（二）真题（完形 20 + 阅读 20 + 新题型 5 = 45 题完整客观卷）
4. 2026 年考研英语（一）真题（完形 20 + 阅读 20 + 新题型 5 = 45 题完整客观卷）
5. 2026 年考研英语（二）真题（完形 20 + 阅读 20 + 新题型 5 = 45 题完整客观卷）
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.esq import load_esq_package, EsqValidationError

OUT_DIR = ROOT / "exports" / "esq_bundles"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PUB_DB = ROOT / "frontend" / "public" / "question_bank.db"
BACKEND_DB = ROOT / "backend" / "data" / "question_bank.db"
APPDATA_DB = Path(os.path.expandvars(r"%APPDATA%\ai-english-practice-desktop\data\question_bank.db"))

CACHE_EN_SKY = Path(os.environ.get("LOCALAPPDATA", "")) / "hermes" / "cache" / "web" / "www.en-sky.com-7b4a45f411.md"
ECHO_BASE = "https://raw.githubusercontent.com/Echo1LZJY/echo-kaoyan-english-skill/main/skills/kaoyan-english/references/papers"


def fetch_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def write_esq_zip(out_path: Path, manifest: dict, paper_files: dict, answer_files: dict) -> int:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for p_name, p_data in paper_files.items():
            zf.writestr(p_name, json.dumps(p_data, ensure_ascii=False, indent=2))
        for a_name, a_data in answer_files.items():
            zf.writestr(a_name, json.dumps(a_data, ensure_ascii=False, indent=2))
    return out_path.stat().st_size


# ==============================================================================
# 1. 2026 年高考英语全国 I 卷
# ==============================================================================
def build_gaokao_2026_package() -> Path:
    print("构建 [2026年高考英语全国I卷]...")
    if not CACHE_EN_SKY.exists():
        raise FileNotFoundError(f"缺失高考缓存: {CACHE_EN_SKY}")

    text = CACHE_EN_SKY.read_text(encoding="utf-8")
    text = text.replace(r"\.", ".").replace(r"\_", "_")

    READING_ANS = {
        "21": "B", "22": "A", "23": "C", "24": "A", "25": "D", "26": "C", "27": "B",
        "28": "C", "29": "C", "30": "B", "31": "A", "32": "B", "33": "A", "34": "D", "35": "D"
    }
    QIXUAN_ANS = {"36": "C", "37": "F", "38": "A", "39": "D", "40": "B"}
    CLOZE_ANS = {str(n): a for n, a in zip(range(41, 56), "CABCA DBCAD ABDCB".replace(" ", ""))}

    QNUM_RE = re.compile(r"^(\d+)\.\s*(.*)")
    OPT_RE = re.compile(r"^([A-G])\.\s*(.*)")

    # 1. 阅读理解 A-D
    start_read = text.index("第二部分阅读理解")
    end_read = text.index("第三部分语言知识运用")
    body_read = text[start_read:end_read]
    parts = re.split(r"\n(?=[A-D]\n)", body_read)

    paper_key = "cn.gaokao.2026.national1"
    units = []
    answers_map = {}

    for idx, part in enumerate(parts[1:5], 1):
        letter = part[0]
        # 截断第二节
        sub = part[2:].split("第二节")[0]
        u_key = f"{paper_key}.reading_{letter.lower()}"
        paras, questions = [], []
        for raw in sub.split("\n"):
            ln = raw.strip()
            if not ln:
                continue
            m_q = QNUM_RE.match(ln)
            if m_q:
                qnum, stem = m_q.group(1), m_q.group(2)
                questions.append({
                    "questionKey": f"{u_key}.q{qnum}",
                    "number": int(qnum),
                    "type": "single_choice",
                    "stem": stem,
                    "score": 2.5,
                    "options": [],
                })
                continue
            m_opt = OPT_RE.match(ln)
            if m_opt and questions:
                questions[-1]["options"].append({"key": m_opt.group(1), "content": m_opt.group(2)})
                continue
            paras.append(ln)

        for q in questions:
            num_str = str(q["number"])
            answers_map[q["questionKey"]] = {"correctOption": READING_ANS[num_str], "score": 2.5}

        blocks = [{"blockKey": f"{u_key}.b{b_idx:02d}", "type": "paragraph", "text": p} for b_idx, p in enumerate(paras, 1) if p]
        units.append({
            "unitKey": u_key,
            "type": "reading",
            "subtype": f"阅读{letter}篇",
            "title": f"阅读理解 ({letter}篇)",
            "sequence": idx,
            "passage": {"blocks": blocks},
            "questions": questions,
        })

    # 2. 七选五
    sec2_idx = body_read.index("第二节")
    sec2_text = body_read[sec2_idx:]
    sec2_lines = [l.strip() for l in sec2_text.split("\n") if l.strip()]

    u_key_qx = f"{paper_key}.part_b"
    qixuan_paras = []
    qixuan_candidates = []
    for l in sec2_lines:
        m_opt = OPT_RE.match(l)
        if m_opt:
            qixuan_candidates.append({"key": m_opt.group(1), "content": m_opt.group(2)})
        elif not l.startswith("第二节") and not l.startswith("阅读下面短文"):
            p_clean = re.sub(r"_{3,}\s*(\d{2})\s*_{3,}", r"{{blank:\1}}", l)
            qixuan_paras.append(p_clean)

    qixuan_questions = []
    for num in range(36, 41):
        q_key = f"{u_key_qx}.q{num}"
        qixuan_questions.append({
            "questionKey": q_key,
            "number": num,
            "type": "single_choice",
            "stem": f"根据文章上下文，从候选项中选出填入第 {num} 空的最佳选项。",
            "score": 2.5,
            "options": [{"key": c["key"], "content": c["content"]} for c in qixuan_candidates],
        })
        answers_map[q_key] = {"correctOption": QIXUAN_ANS[str(num)], "score": 2.5}

    blocks_qx = [{"blockKey": f"{u_key_qx}.b{b_idx:02d}", "type": "paragraph", "text": p} for b_idx, p in enumerate(qixuan_paras, 1) if p]
    units.append({
        "unitKey": u_key_qx,
        "type": "part_b",
        "subtype": "七选五",
        "title": "阅读理解 第二节 (七选五)",
        "sequence": 5,
        "passage": {"blocks": blocks_qx},
        "candidates": qixuan_candidates,
        "questions": qixuan_questions,
    })

    # 3. 完形填空
    start_lang = text.index("第三部分语言知识运用")
    end_lang = text.index("第四部分写作")
    body_lang = text[start_lang:end_lang]
    sec1_idx = body_lang.index("第一节")
    sec2_idx = body_lang.index("第二节")
    cloze_part = body_lang[sec1_idx:sec2_idx]

    u_key_cloze = f"{paper_key}.cloze"
    cloze_paras = []
    cloze_questions = []
    for l in cloze_part.split("\n"):
        ln = l.strip()
        if not ln or ln.startswith("第一节") or ln.startswith("阅读下面短文"):
            continue
        m_opts = re.findall(r"([A-D])\.\s*([^A-D]+)", ln)
        m_num = re.match(r"^(\d+)\.", ln)
        if m_num and len(m_opts) == 4:
            num = int(m_num.group(1))
            q_key = f"{u_key_cloze}.q{num}"
            cloze_questions.append({
                "questionKey": q_key,
                "number": num,
                "type": "single_choice",
                "stem": f"选出填入第 {num} 处的最佳词汇",
                "score": 1.0,
                "options": [{"key": k, "content": v.strip()} for k, v in m_opts],
            })
            answers_map[q_key] = {"correctOption": CLOZE_ANS[str(num)], "score": 1.0}
        else:
            p_clean = re.sub(r"_{2,}\s*(\d{2})\s*_{2,}", r"{{blank:\1}}", ln)
            cloze_paras.append(p_clean)

    blocks_cloze = [{"blockKey": f"{u_key_cloze}.b{b_idx:02d}", "type": "paragraph", "text": p} for b_idx, p in enumerate(cloze_paras, 1) if p]
    units.append({
        "unitKey": u_key_cloze,
        "type": "cloze",
        "subtype": "完形填空",
        "title": "语言知识运用 第一节 (完形填空)",
        "sequence": 6,
        "passage": {"blocks": blocks_cloze},
        "questions": cloze_questions,
    })

    paper_data = {
        "paperKey": paper_key,
        "year": 2026,
        "title": "2026年高考英语全国I卷",
        "subject": "高中英语",
        "units": units,
    }

    manifest = {
        "format": "esq",
        "schemaVersion": "1.0",
        "packageId": "cn.gaokao.2026.national1",
        "contentVersion": "1.0.0",
        "title": "2026年高考英语全国I卷（真题客观卷）",
        "subject": "高中英语",
        "language": "en",
        "locale": "zh-CN",
        "publisher": "墨题高考真题实验室",
        "license": {"spdx": "NOASSERTION", "notice": "高考全国I卷真题整理版，仅供学习研究使用。"},
        "source": {"type": "candidate_recollection", "description": "2026高考全国I卷真题公布稿 + 权威教研答案"},
        "papers": [{"paperKey": paper_key, "year": 2026, "title": "2026年高考英语全国I卷", "path": "papers/2026.json", "answerPath": "answers/2026.json"}],
        "features": {"hasAnswers": True, "hasAiLabels": False, "hasAssets": False},
        "generator": {"name": "墨题 ESQ 1.0 标准管线", "version": "1.0.0"},
    }

    out_file = OUT_DIR / "cn.gaokao.2026.national1.esq"
    write_esq_zip(out_file, manifest, {"papers/2026.json": paper_data}, {"answers/2026.json": {"paperKey": paper_key, "answers": answers_map}})
    load_esq_package(out_file)
    print(f"  ✓ 2026 高考全国 I 卷打包成功: {len(units)} 单元 / {sum(len(u['questions']) for u in units)} 题 -> {out_file.name}")
    return out_file


# ==============================================================================
# 2. 考研英语真题（2025、2026 英语一 & 英语二）
# ==============================================================================
def build_kaoyan_package(exam_code: str, year: int) -> Path:
    label = "英语（一）" if exam_code == "english-i" else "英语（二）"
    pkg_id = f"cn.kaoyan{'1' if exam_code == 'english-i' else '2'}.{year}"
    print(f"构建 [{year}年考研{label}真题]...")

    base_url = f"{ECHO_BASE}/{exam_code}/{year}"
    ans_data = json.loads(fetch_url(f"{base_url}/answers.json"))["answers"]
    cloze_md = fetch_url(f"{base_url}/cloze.md")
    r1_md = fetch_url(f"{base_url}/reading-text-1.md")
    r2_md = fetch_url(f"{base_url}/reading-text-2.md")
    r3_md = fetch_url(f"{base_url}/reading-text-3.md")
    r4_md = fetch_url(f"{base_url}/reading-text-4.md")
    new_type_md = fetch_url(f"{base_url}/new-question-type.md")

    paper_key = f"{pkg_id}.paper"
    units = []
    answers_map = {}

    # 1. Cloze
    u_key_cloze = f"{paper_key}.cloze"
    cloze_paras = []
    cloze_questions = []
    for line in cloze_md.splitlines():
        ln = line.strip()
        if not ln or ln.startswith("#") or ln.startswith("Section I") or ln.startswith("Directions:") or ln.startswith("<!--"):
            continue
        m_num = re.match(r"^(\d+)\.", ln)
        if m_num and 1 <= int(m_num.group(1)) <= 20:
            num = int(m_num.group(1))
            l_no_num = re.sub(r"^\d+\.\s*", "", ln)
            if "[" in l_no_num:
                raw_opts = re.findall(r"\[([A-D])\]\s*([^\[]+)", l_no_num)
                opts = [(k, v.strip()) for k, v in raw_opts]
            else:
                parts = re.split(r"(?:^|\s+)([A-D])\.\s*", l_no_num)
                opts = [(parts[i], parts[i + 1].strip()) for i in range(1, len(parts), 2) if i + 1 < len(parts)]

            if len(opts) == 4:
                q_key = f"{u_key_cloze}.q{num:02d}"
                cloze_questions.append({
                    "questionKey": q_key,
                    "number": num,
                    "type": "single_choice",
                    "stem": f"Choose the best word for blank {num}",
                    "score": 0.5,
                    "options": [{"key": k, "content": v} for k, v in opts],
                })
                answers_map[q_key] = {"correctOption": ans_data["cloze"][str(num)], "score": 0.5}
                continue

        # 排除分析说明段落
        if any(k in ln for k in ["篇章层面", "语言层面", "选项层面", "复盘层面", "选项观察", "易错点"]):
            continue
        ln_sub = re.sub(r"(?<=\s)(\d{1,2})(?=\s)", r"{{blank:\1}}", ln)
        cloze_paras.append(ln_sub)

    blocks_cloze = [{"blockKey": f"{u_key_cloze}.b{b_idx:02d}", "type": "paragraph", "text": p} for b_idx, p in enumerate(cloze_paras, 1) if p]
    units.append({
        "unitKey": u_key_cloze,
        "type": "cloze",
        "subtype": "完形填空",
        "title": "Section I Use of English (完形填空)",
        "sequence": 1,
        "passage": {"blocks": blocks_cloze},
        "questions": cloze_questions,
    })

    # 2. Reading Text 1-4
    reading_files = [("reading-text-1", r1_md), ("reading-text-2", r2_md), ("reading-text-3", r3_md), ("reading-text-4", r4_md)]
    for r_idx, (r_name, r_content) in enumerate(reading_files, 1):
        u_key_r = f"{paper_key}.text{r_idx}"
        r_paras = []
        r_questions = []
        cur_q = None
        for line in r_content.splitlines():
            ln = line.strip()
            if not ln or ln.startswith("#") or ln.startswith("Text "):
                continue
            m_q = re.match(r"^(\d+)\.\s*(.*)", ln)
            m_opt = re.match(r"^(?:\[([A-D])\]|([A-D])\.)\s*(.*)", ln)
            if m_q:
                # 标准化题号（自动纠正个别原稿中跳号笔误，如 31, 32, 34 -> 31, 32, 33）
                num = 20 + (r_idx - 1) * 5 + len(r_questions) + 1
                q_key = f"{u_key_r}.q{num:02d}"
                cur_q = {
                    "questionKey": q_key,
                    "number": num,
                    "type": "single_choice",
                    "stem": m_q.group(2).strip(),
                    "score": 2.0,
                    "options": [],
                }
                r_questions.append(cur_q)
                answers_map[q_key] = {"correctOption": ans_data[r_name][str(num)], "score": 2.0}
            elif m_opt and cur_q:
                k = m_opt.group(1) or m_opt.group(2)
                cur_q["options"].append({"key": k, "content": m_opt.group(3).strip()})
            elif not r_questions:
                r_paras.append(ln)

        blocks_r = [{"blockKey": f"{u_key_r}.b{b_idx:02d}", "type": "paragraph", "text": p} for b_idx, p in enumerate(r_paras, 1) if p]
        units.append({
            "unitKey": u_key_r,
            "type": "reading",
            "subtype": f"Text {r_idx}",
            "title": f"Section II Reading Part A (Text {r_idx})",
            "sequence": 1 + r_idx,
            "passage": {"blocks": blocks_r},
            "questions": r_questions,
        })

    # 3. New Question Type (Part B)
    u_key_b = f"{paper_key}.part_b"
    part_b_candidates = []
    part_b_questions = []
    part_b_paras = []

    # 候选提取逻辑：区分括号 [A-H] 与 A-H.
    if re.search(r"\[[A-H]\]", new_type_md):
        for m in re.finditer(r"\[([A-H])\]\s*([^\[]+)", new_type_md):
            clean_c = re.sub(r"\s*4[1-5]\..*$", "", m.group(2)).strip()
            clean_c = re.sub(r"\s*\d{2}\..*$", "", clean_c).strip()
            if clean_c:
                part_b_candidates.append({"key": m.group(1), "content": clean_c})
    else:
        parts = re.split(r"\n(?=[A-H]\.\s*)", new_type_md)
        for p in parts:
            m = re.match(r"^([A-H])\.\s*(.*)", p.strip(), re.DOTALL)
            if m:
                clean_c = re.sub(r"\s*4[1-5]\..*$", "", m.group(2)).strip()
                part_b_candidates.append({"key": m.group(1), "content": clean_c})

    # 题干 41-45
    raw_qs = re.findall(r"(\d{2})\.\s*([^\[\n\r]+)", new_type_md)
    stems_by_num = {}
    for num_str, stem_str in raw_qs:
        num = int(num_str)
        if 41 <= num <= 45:
            stems_by_num[num] = stem_str.strip()

    for num in range(41, 46):
        q_key = f"{u_key_b}.q{num:02d}"
        stem = stems_by_num.get(num, f"选择填入第 {num} 处的对应段落或标题")
        part_b_questions.append({
            "questionKey": q_key,
            "number": num,
            "type": "single_choice",
            "stem": stem,
            "score": 2.0,
            "options": [{"key": c["key"], "content": c["content"][:200]} for c in part_b_candidates],
        })
        answers_map[q_key] = {"correctOption": ans_data["new-question-type"][str(num)], "score": 2.0}

    # 提取说明段落
    lines_b = [l.strip() for l in new_type_md.splitlines() if l.strip() and not l.startswith("#")]
    for l in lines_b[:4]:
        part_b_paras.append(l)

    blocks_b = [{"blockKey": f"{u_key_b}.b{b_idx:02d}", "type": "paragraph", "text": p} for b_idx, p in enumerate(part_b_paras, 1) if p]
    units.append({
        "unitKey": u_key_b,
        "type": "part_b",
        "subtype": "新题型",
        "title": "Section II Reading Part B (新题型)",
        "sequence": 6,
        "passage": {"blocks": blocks_b},
        "candidates": part_b_candidates,
        "questions": part_b_questions,
    })

    paper_data = {
        "paperKey": paper_key,
        "year": year,
        "title": f"{year}年考研{label}真题",
        "subject": f"考研{label}",
        "units": units,
    }

    manifest = {
        "format": "esq",
        "schemaVersion": "1.0",
        "packageId": pkg_id,
        "contentVersion": "1.0.0",
        "title": f"{year}年全国硕士研究生招生考试{label}真题（客观卷）",
        "subject": f"考研{label}",
        "language": "en",
        "locale": "zh-CN",
        "publisher": "墨题考研实验室",
        "license": {"spdx": "NOASSERTION", "notice": "考研官方真题回忆整理版，仅供学习研究使用。"},
        "source": {"type": "candidate_recollection", "description": "Echo1LZJY 考研真题知识库开源数据集 + 官方标准答案"},
        "papers": [{"paperKey": paper_key, "year": year, "title": f"{year}年考研{label}真题", "path": f"papers/{year}.json", "answerPath": f"answers/{year}.json"}],
        "features": {"hasAnswers": True, "hasAiLabels": False, "hasAssets": False},
        "generator": {"name": "墨题 ESQ 1.0 标准管线", "version": "1.0.0"},
    }

    out_file = OUT_DIR / f"{pkg_id}.esq"
    write_esq_zip(out_file, manifest, {f"papers/{year}.json": paper_data}, {f"answers/{year}.json": {"paperKey": paper_key, "answers": answers_map}})
    load_esq_package(out_file)
    print(f"  ✓ {year} {label} 打包成功: {len(units)} 单元 / {sum(len(u['questions']) for u in units)} 题 -> {out_file.name}")
    return out_file


# ==============================================================================
# 3. 入库与三库同步
# ==============================================================================
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
        p_row = cur.execute("SELECT id FROM papers WHERE external_key = ?", (paper_key,)).fetchone()
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
            passage_text = unit.get("passageText", "")
            shared_data = json.dumps({"candidates": {c["key"]: c["content"] for c in unit.get("candidates", [])}}, ensure_ascii=False) if unit.get("candidates") else "{}"
            
            u_row = cur.execute("SELECT id FROM units WHERE paper_id = ? AND external_key = ?", (paper_id, unit_key)).fetchone()
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
                q_row = cur.execute("SELECT id FROM questions WHERE unit_id = ? AND external_key = ?", (unit_id, q_key)).fetchone()
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

                # options
                cur.execute("DELETE FROM options WHERE question_id = ?", (qid,))
                for oi, opt in enumerate(q.get("options", [])):
                    cur.execute(
                        """INSERT INTO options (question_id, stable_key, original_label, content, sequence)
                           VALUES (?, ?, ?, ?, ?)""",
                        (qid, opt["key"], opt["key"], opt["content"], oi),
                    )

    conn.commit()
    conn.close()


def main() -> int:
    print("=" * 70)
    print("🚀 开始批量抓取清洗并打包 2025-2026 最新真题/新题型 ESQ 题包")
    print("=" * 70)

    packages = []

    # 1. 2026 高考全国 I 卷 (Profile 422: 高中英语)
    p_gk = build_gaokao_2026_package()
    packages.append((p_gk, 422))

    # 2. 2025/2026 考研英语一 (Profile 1)
    p_k1_2025 = build_kaoyan_package("english-i", 2025)
    packages.append((p_k1_2025, 1))

    p_k1_2026 = build_kaoyan_package("english-i", 2026)
    packages.append((p_k1_2026, 1))

    # 3. 2025/2026 考研英语二 (Profile 5)
    p_k2_2025 = build_kaoyan_package("english-ii", 2025)
    packages.append((p_k2_2025, 5))

    p_k2_2026 = build_kaoyan_package("english-ii", 2026)
    packages.append((p_k2_2026, 5))

    print("\n" + "=" * 70)
    print("📥 开始入库与三库全端同步...")
    print("=" * 70)

    for esq_file, profile_id in packages:
        print(f"入库: {esq_file.name} -> profile_id={profile_id}")
        import_esq_to_sqlite(esq_file, PUB_DB, profile_id)
        if BACKEND_DB.exists():
            import_esq_to_sqlite(esq_file, BACKEND_DB, profile_id)
        if APPDATA_DB.exists():
            import_esq_to_sqlite(esq_file, APPDATA_DB, profile_id)

    print("\n✓ 全部最新真题已成功构建 ESQ 题包并入库三端！")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
