# -*- coding: utf-8 -*-
"""题库数据修复：9 题答案键 + 26 题结构错位（stem/选项重排 + 粘连清理）。

设计：
- 变换式规格：新布局以「引用当前字段」表达（ref_stem/ref_opt），避免转写歧义；
- 锚点断言：应用前逐项校验当前数据含预期子串，不匹配即整库放弃（绝不半改）；
- 三库独立处理（开发库/种子库/在线库），各自先备份 .bak_keyfix_20260906 再修改。
- q1447 答案键保留库标 A（官方口径存在争议，原文证据两可，不做无把握改动）。
"""
import os
import shutil
import sqlite3

DBS = [
    r"D:\english-multiple-choice-practice-machine\backend\data\question_bank.db",
]
# 种子库(647题,id≤647)与在线库(338题,id≤338)不含 q1443+ 的试卷，结构与键修复不适用；
# 两库仅做 explain_collections 增量同步（见 sync_three_dbs.py）。
BACKUP_SUFFIX = ".bak_keyfix_20260906"
G_GLUED = "43.Katie Kelley44.Mayghin Levine"

# 结构修复：stem 引用 ("literal", 文本) / ("ref_passage_tail",) / ("ref_opt", "D")
# opts 值引用 ("ref_stem",) / ("ref_opt", key)；anchors 为当前字段必须包含的子串。
REPAIRS = [
    {"qid": 1443, "stem": ("literal", "According to Dr. Curtis, habits like hand washing with soap ."),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "A")},
     "answer": "A",
     "anchors": {"stem": ["should be further cultivated"], "A": ["changed gradually"],
                 "B": ["deeply rooted"], "C": ["private concerns"], "D": ["Bottled water"]}},
    {"qid": 1444, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "A")},
     "answer": "A",
     "anchors": {"stem": ["reveal their impact"], "A": ["urgent need"], "B": ["buying power"],
                 "C": ["significant role"], "D": ["NOT belong"]}},
    {"qid": 1445, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_stem",)},
     "answer": "C",
     "anchors": {"stem": ["Tide"], "A": ["Crest"], "B": ["Colgate"], "C": ["Unilever"],
                 "D": ["From the text we know"]}},
    {"qid": 1446, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "C",
     "anchors": {"stem": ["perfected art"], "A": ["automatic behavior"], "B": ["commercial promotions"],
                 "C": ["scientific experiments"], "D": ["attitude toward the influence"]}},
    {"qid": 1447, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D")},
     "answer": "A",
     "anchors": {"stem": ["."], "A": ["indifferent"], "B": ["negative"], "C": ["positive"], "D": ["biased"]}},
    {"qid": 1448, "stem": ("ref_passage_tail",),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "D",
     "anchors": {"stem": ["both literate and illiterate"], "A": ["immune"], "B": ["no age limit"],
                 "C": ["judgment should consider"], "D": ["elite jurors"]}},
    {"qid": 1449, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "A",
     "anchors": {"stem": ["inadequacy"], "A": ["prevalent discrimination"], "B": ["conflicting ideals"],
                 "C": ["arrogance"], "D": ["women were seldom"]}},
    {"qid": 1450, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_opt", "C"), "B": ("ref_opt", "B"), "C": ("ref_opt", "D"), "D": ("ref_opt", "A")},
     "answer": "A",
     "anchors": {"stem": ["."], "A": ["automatically banned"], "B": ["fell far short"],
                 "C": ["supposed to perform domestic"], "D": ["evade public engagement"]}},
    {"qid": 1523, "stem": ("ref_passage_tail",),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "A")},
     "answer": "A",
     "anchors": {"stem": ["receiving more criticism"], "A": ["gaining more preferences"],
                 "B": ["no longer an educational ritual"], "C": ["not required for advanced"],
                 "D": ["L.A. Unified has made the rule"]}},
    {"qid": 1524, "stem": ("ref_opt_of", 1523, "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D")},
     "answer": "C",
     "anchors": {"stem": ["."], "A": ["moderate expectations"], "B": ["different educational standard"],
                 "C": ["problems finishing"], "D": ["voiced their complaints"]}},
    {"qid": 1528, "stem": ("ref_passage_tail",),
     "opts": {"A": ("ref_opt", "B"), "B": ("ref_opt", "A"), "C": ("ref_stem",), "D": ("ref_opt", "C")},
     "answer": "A",
     "anchors": {"stem": ["lack of imagination"], "A": ["innocence"], "B": ["sole representation"],
                 "C": ["lives and interests"], "D": ["true of colours"]}},
    {"qid": 1529, "stem": ("ref_opt_of", 1528, "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_stem",)},
     "answer": "A",
     "anchors": {"stem": ["encoded in girls"], "A": ["Blue used to be"], "B": ["White is preferred"],
                 "C": ["neutral colour"], "D": ["perception of children"]}},
    {"qid": 1530, "stem": ("ref_opt_of", 1529, "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_stem",)},
     "answer": "A",
     "anchors": {"stem": ["observation of children"], "A": ["marketing of products"],
                 "B": ["researches into"], "C": ["childhood consumption"], "D": ["department stores were advised"]}},
    {"qid": 1531, "stem": ("ref_opt_of", 1530, "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D")},
     "answer": "A",
     "anchors": {"stem": ["."], "A": ["classify consumers"], "B": ["equal importance"],
                 "C": ["infant wear"], "D": ["common shoppers"]}},
    {"qid": 1533, "stem": ("ref_passage_tail",),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "A",
     "anchors": {"stem": ["genes to be patentable"], "A": ["BIO to issue"], "B": ["executives to be active"],
                 "C": ["rule out gene patenting"], "D": ["against gene patents"]}},
    {"qid": 1534, "stem": ("ref_opt_of", 1533, "D"),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "B",
     "anchors": {"stem": ["genetic tests are not reliable"], "A": ["man-made products"],
                 "B": ["depend much on innovation"], "C": ["restrict access"], "D": ["Hans Sauer"]}},
    {"qid": 1535, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "A",
     "anchors": {"stem": ["discovering gene interactions"], "A": ["disease correlations"],
                 "B": ["drawing pictures"], "C": ["identifying human DNA"], "D": ["Each meeting was packed"]}},
    {"qid": 1568, "stem": ("ref_passage_tail",),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "A",
     "anchors": {"stem": ["impact of technological advances"], "A": ["alleviation"], "B": ["shrinkage"],
                 "C": ["middle-class incomes"], "D": ["successful employee"]}},
    {"qid": 1569, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "D",
     "anchors": {"stem": ["cheap software"], "A": ["moderate salary"], "B": ["average lifestyle"],
                 "C": ["something unique"], "D": ["quotation in Paragraph 4"]}},
    {"qid": 1570, "stem": ("ref_opt", "D"),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "B",
     "anchors": {"stem": ["gains of technology"], "A": ["disappearing at a high speed"],
                 "B": ["less money"], "C": ["new jobs and services"], "D": ["reduce unemployment"]}},
    {"qid": 1571, "stem": ("ref_opt_of", 1570, "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D")},
     "answer": "B",
     "anchors": {"stem": ["."], "A": ["I. T. revolution"], "B": ["more education"],
                 "C": ["globalization"], "D": ["more bills"]}},
    {"qid": 1573, "stem": ("ref_passage_tail",),
     "opts": {"A": ("ref_stem",), "B": ("ref_opt", "A"), "C": ("ref_opt", "B"), "D": ("ref_opt", "C")},
     "answer": "A",
     "anchors": {"stem": ["temporarily"], "A": ["for good"], "B": ["Atlantic"],
                 "C": ["permanent jobs"], "D": ["immigration system"]}},
    {"qid": 1574, "stem": ("ref_opt_of", 1573, "D"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D")},
     "answer": "C",
     "anchors": {"stem": ["."], "A": ["immigrant categories"], "B": ["loosened control"],
                 "C": ["adapted to meet"], "D": ["political means"]}},
    {"qid": 2066, "stem": ("literal", "Several cities are mentioned in Paragraph 5 to show ."),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D")},
     "answer": "A",
     "anchors": {"stem": ["Several"], "A": ["uneven distribution"], "B": ["disappointing prospect"],
                 "C": ["fast progress"], "D": ["significance of US AI"]}},
    {"qid": 2085, "stem": ("literal", "Katie Kelley"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D"),
              "E": ("ref_opt", "E"), "F": ("ref_opt", "F"), "G": ("ref_opt", "G")},
     "answer": "A",
     "anchors": {"stem": ["43"], "A": ["stand out in a specific"], "G": [G_GLUED]}},
    {"qid": 2086, "stem": ("literal", "Mayghin Levine"),
     "opts": {"A": ("ref_opt", "A"), "B": ("ref_opt", "B"), "C": ("ref_opt", "C"), "D": ("ref_opt", "D"),
              "E": ("ref_opt", "E"), "F": ("ref_opt", "F"), "G": ("ref_opt", "G")},
     "answer": "G",
     "anchors": {"stem": ["44"], "A": ["stand out in a specific"], "G": [G_GLUED]}},
]

KEY_FIXES = [
    {"qid": 1487, "expect": "D", "new": "A"},
    {"qid": 1492, "expect": "C", "new": "B"},
    {"qid": 1527, "expect": "B", "new": "A"},
    {"qid": 1532, "expect": "B", "new": "C"},
    {"qid": 1577, "expect": "A", "new": "D"},
    {"qid": 1582, "expect": "C", "new": "B"},
    {"qid": 1667, "expect": "A", "new": "D"},
    {"qid": 2083, "expect": "C", "new": "E"},
    {"qid": 2084, "expect": "E", "new": "C"},
]


def normalize_stem(text: str) -> str:
    text = text.strip()
    if not text.endswith((".", "?", "_")):
        text = text + " ."
    return text


def repair_db(path: str) -> str:
    if not os.path.exists(path):
        return "SKIP(不存在): %s" % path
    conn = sqlite3.connect(path)
    conn.row_factory = None
    problems = []
    plans = []
    for spec in REPAIRS:
        qid = spec["qid"]
        row = conn.execute(
            "SELECT q.stem, q.answer, u.passage FROM questions q JOIN units u ON u.id=q.unit_id WHERE q.id=?",
            (qid,),
        ).fetchone()
        if row is None:
            problems.append("q%d 不存在" % qid)
            continue
        stem, answer, passage = row[0], row[1], row[2] or ""
        opts = dict(conn.execute(
            "SELECT stable_key, content FROM options WHERE question_id=?", (qid,)))
        for field, needles in spec["anchors"].items():
            value = stem if field == "stem" else opts.get(field, "")
            for needle in needles:
                if needle not in value:
                    problems.append("q%d 锚点失配 %s: %r 不含 %r" % (qid, field, value[:60], needle))
        if problems:
            continue
        if spec["stem"][0] == "literal":
            new_stem = spec["stem"][1]
        elif spec["stem"][0] == "ref_passage_tail":
            new_stem = passage.split("\n")[-1].strip()
        elif spec["stem"][0] == "ref_opt":
            new_stem = opts[spec["stem"][1]]
        elif spec["stem"][0] == "ref_opt_of":
            ref_qid, ref_key = spec["stem"][1], spec["stem"][2]
            new_stem = conn.execute(
                "SELECT content FROM options WHERE question_id=? AND stable_key=?",
                (ref_qid, ref_key)).fetchone()[0]
        else:
            problems.append("q%d stem 引用非法" % qid)
            continue
        new_stem = normalize_stem(new_stem)
        new_opts = {}
        for key, ref in spec["opts"].items():
            if ref[0] == "ref_stem":
                new_opts[key] = stem
            elif ref[0] == "ref_opt":
                new_opts[key] = opts[ref[1]]
            else:
                problems.append("q%d 选项引用非法" % qid)
        if problems:
            continue
        if len(set(new_opts.values())) != len(new_opts):
            problems.append("q%d 新选项文本有重复" % qid)
            continue
        plans.append((qid, new_stem, new_opts, spec["answer"], stem, opts, answer))
    key_plans = []
    for kf in KEY_FIXES:
        row = conn.execute("SELECT answer FROM questions WHERE id=?", (kf["qid"],)).fetchone()
        if row is None:
            problems.append("q%d 不存在(键修复)" % kf["qid"])
            continue
        if row[0] != kf["expect"]:
            problems.append("q%d 当前答案 %r 与预期 %s 不符" % (kf["qid"], row[0], kf["expect"]))
            continue
        key_plans.append((kf["qid"], kf["new"]))
    if problems:
        conn.close()
        return "ABORT %s: %s" % (path, "; ".join(problems[:8]))
    shutil.copyfile(path, path + BACKUP_SUFFIX)
    for qid, new_stem, new_opts, new_answer, old_stem, old_opts, old_answer in plans:
        conn.execute("UPDATE questions SET stem=?, answer=? WHERE id=?", (new_stem, new_answer, qid))
        for key, value in new_opts.items():
            if old_opts.get(key) != value:
                conn.execute(
                    "UPDATE options SET content=? WHERE question_id=? AND stable_key=?",
                    (value, qid, key))
    for qid, new_answer in key_plans:
        conn.execute("UPDATE questions SET answer=? WHERE id=?", (new_answer, qid))
    cleaned = conn.execute(
        "UPDATE options SET content=REPLACE(content, ?, '') WHERE content LIKE ?",
        (G_GLUED, "%" + G_GLUED)).rowcount
    conn.commit()
    conn.close()
    return "OK %s: 结构修复 %d 题, 键修复 %d 题, G 选项清理 %d 行 (备份 %s)" % (
        path, len(plans), len(key_plans), cleaned, path + BACKUP_SUFFIX)


def main() -> None:
    for path in DBS:
        print(repair_db(path))
    print("FIX BANK DATA DONE")


if __name__ == "__main__":
    main()
