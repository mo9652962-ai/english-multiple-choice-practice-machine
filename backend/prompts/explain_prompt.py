"""题目解析批量生成提示词模板（任务 E）。

供 scripts/batch_generate_explanations.py 与 backend/app/routers/explanations.py
共同复用。所有解析内容为结构化 JSON（不产出 HTML），由前端组件负责渲染。

content 字段的最终存储格式（与 question_explanations.content 一一对应）：
{
  "correct_analysis": "正确项分析（中文，面向学生）",
  "wrong_options": [{"key": "B", "reason": "该选项错误的原因"}],
  "knowledge_points": ["知识点标签", ...],
  "study_advice": "复习建议"
}
"""
from __future__ import annotations

import json
from typing import Any

# ── 系统提示词：一次请求生成一批题的解析，严格 JSON 输出 ──
EXPLAIN_SYSTEM_PROMPT = """
你是资深的英语考试教研专家，精通中国各类英语考试（四六级、考研、高考）的命题规律，
负责为题库中的每道题撰写高质量中文解析，帮助学生不仅知道答案，更掌握解题方法。

【输出要求——必须严格遵守】
1. 只输出一个合法 JSON 对象，不要输出任何解释性文字、Markdown 代码块标记或注释。
2. 顶层结构：{"explanations": [ ... ]}，数组内每个元素对应输入中的一道题。
3. 每个元素的字段：
   {"id": 题目ID(整数，必须与输入一致),
    "correct_analysis": "正确项分析",
    "wrong_options": [{"key": "选项字母", "reason": "错误原因"}, ...],
    "knowledge_points": ["知识点1", "知识点2"],
    "study_advice": "复习建议"}
4. 每个输入的题目 id 必须恰好输出一次，不得遗漏、不得新增。
5. wrong_options 覆盖该题除正确项外的所有选项；若题型没有可逐一分析的干扰项
   （如段落匹配、七选五），wrong_options 允许为空数组 []，但需把易错点并入 correct_analysis。

【内容要求——专业且面向学生】
- correct_analysis：120～200 字中文。先定位（文中哪句话/哪个空），引用关键英文原句
  （短句可原文引用），再说明为什么正确项成立；段落匹配题须点明匹配依据的关键词同义改写。
- wrong_options[].reason：30～80 字中文，指出每个干扰项的典型错误类型
  （张冠李戴/偷换概念/过度推断/范围扩大/无中生有/词义误用等）并给出判据。
- knowledge_points：1～3 个简短标签，如 "同义改写定位"、"虚拟语气"、"逻辑衔接词"、
  "词义辨析"，供前端展示为标签。
- study_advice：30～80 字中文，针对本题考点给出可操作的复习建议（背什么、练什么方法）。
- 语言使用教研口吻：客观、具体、可执行，避免空话套话；不透露"作为 AI"等身份信息。
""".strip()

# JSON Schema 说明（用于支持 response_format=json_object 的接口）
EXPLAIN_RESPONSE_FORMAT = {"type": "json_object"}

# v9.26: 深度精讲提示词（P0 真题精讲——4 选项逐项解构 + 陷阱标签 + 长难句 + 同类推荐）
DEEP_EXPLAIN_SYSTEM_PROMPT = """
你是精通考研英语命题规律的殿堂级名师。请针对提供的阅读/完形/新题型题目及文章上下文，
进行全方位的解题思路剖析与干扰项设坑逻辑拆解。

【解析要求】
1. 准确定位题目类型（主旨题/细节题/词汇题/推理题/态度题/新题型）。
2. 提供 3 步式清晰解题路径（定位 -> 辨析 -> 排除），每步 20~50 字。
3. 必须对 A/B/C/D 四个选项逐一解构：
   - 正确项：status=correct，指出对应原文的同义替换词（synonym）。
   - 干扰项：status=wrong，打上经典陷阱标签（无中生有/偷换概念/正反混淆/答非所问/
     以偏概全/绝对化表达/过度推断/张冠李戴）。
4. 长难句语法剖析：提炼主谓宾核心骨架（core_skeleton）+ 30 字内语法点拨。
5. 只输出一个合法 JSON 对象，不得包含 Markdown 代码块标记或杂质。

【输出 JSON 规范】
{
  "question_type_label": "细节事实题",
  "core_skill": "长难句同义改写定位",
  "locator_sentence": "对应原文关键定位句",
  "solution_steps": ["第一步：...", "第二步：...", "第三步：..."],
  "options_analysis": {
    "A": {"status": "wrong", "trap_type": "偷换概念", "analysis": "解析（40字内）"},
    "B": {"status": "correct", "trap_type": "正确项", "analysis": "同义替换解析"},
    "C": {"status": "wrong", "trap_type": "无中生有", "analysis": "解析"},
    "D": {"status": "wrong", "trap_type": "反向干扰", "analysis": "解析"}
  },
  "sentence_grammar": {"core_skeleton": "主谓宾核心提炼", "grammar_note": "难点语法点拨（30字内）"},
  "knowledge_points": ["知识点1", "知识点2"],
  "study_advice": "复习建议（40字内）"
}
""".strip()

_MAX_WRONG_OPTIONS = 12
_MAX_KNOWLEDGE_POINTS = 5


def build_explain_user_prompt(
    units: list[dict[str, Any]],
    questions: list[dict[str, Any]],
    *,
    passage_limit: int = 4000,
) -> str:
    """组装一次批量解析请求的用户消息。

    units: [{"id", "title", "unit_type", "subtype", "passage"}]
    questions: [{"id", "number", "stem", "answer", "options": [{"key", "content"}]}]
    """
    trimmed_units = [
        {
            "id": unit["id"],
            "title": unit.get("title") or "",
            "unit_type": unit.get("unit_type") or "",
            "subtype": unit.get("subtype") or "",
            "passage": (unit.get("passage") or "")[:passage_limit],
        }
        for unit in units
    ]
    payload = {
        "说明": "units 是本批题目所属的篇章（题目通过 unit_id 关联）；"
        "请为 questions 中每道题输出解析，answer 字段是该题正确答案。",
        "units": trimmed_units,
        "questions": questions,
    }
    return json.dumps(payload, ensure_ascii=False)


def validate_explanations(
    parsed: Any,
    expected_ids: set[int],
) -> list[dict[str, Any]]:
    """校验模型返回并清洗为可入库格式；不合法时抛 ValueError。"""
    items = parsed.get("explanations") if isinstance(parsed, dict) else None
    if not isinstance(items, list):
        raise ValueError("模型未按约定返回 {\"explanations\": [...]} 结构")

    cleaned: dict[int, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            question_id = int(item["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if question_id not in expected_ids or question_id in cleaned:
            continue
        analysis = str(item.get("correct_analysis") or "").strip()
        if not analysis:
            continue

        wrong_options: list[dict[str, str]] = []
        for wrong in item.get("wrong_options") or []:
            if not isinstance(wrong, dict):
                continue
            key = str(wrong.get("key") or "").strip()
            reason = str(wrong.get("reason") or "").strip()
            if key and reason and len(wrong_options) < _MAX_WRONG_OPTIONS:
                wrong_options.append({"key": key, "reason": reason})

        knowledge_points: list[str] = []
        for point in item.get("knowledge_points") or []:
            text = str(point or "").strip()
            if text and len(knowledge_points) < _MAX_KNOWLEDGE_POINTS:
                knowledge_points.append(text)

        cleaned[question_id] = {
            "correct_analysis": analysis,
            "wrong_options": wrong_options,
            "knowledge_points": knowledge_points,
            "study_advice": str(item.get("study_advice") or "").strip(),
        }

    missing = expected_ids - set(cleaned)
    if missing:
        raise ValueError(f"模型返回的解析不完整，缺少题目: {sorted(missing)}")
    return [dict(cleaned[question_id], id=question_id) for question_id in sorted(cleaned)]


def explanation_to_content(explanation: dict[str, Any]) -> str:
    """把单条解析序列化为 question_explanations.content 的存储格式。"""
    content = {
        "correct_analysis": explanation["correct_analysis"],
        "wrong_options": explanation.get("wrong_options") or [],
        "knowledge_points": explanation.get("knowledge_points") or [],
        "study_advice": explanation.get("study_advice") or "",
    }
    return json.dumps(content, ensure_ascii=False)
