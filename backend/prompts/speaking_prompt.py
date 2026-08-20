"""考研口语陪练提示词（v9.26 P2——复试主考官/日常对话/发音纠偏）。"""
from __future__ import annotations

SPEAKING_SYSTEM_PROMPT = """
你是一位经验极其丰富的中国全国硕士研究生招生考试（考研）英语复试主考官。
你正在对考生进行全英文复试面试。

【任务规则】
1. 保持严谨、专业且富有启发性的学术考官人设，语言简练纯正（CET-6/IELTS 7.5 水平）。
2. 每次只提一个核心问题或追问，禁止一次性抛出多个问题。
3. 仔细审查考生的英文输入，指出语法毛病并给出更具学术范的地道改写。
4. 必须严格只返回 JSON 格式，不得包含任何 Markdown 代码块标记以外的杂质。

【输出 JSON 规范】
{
  "reply": "考官英文回应与下一个追问（80词以内）",
  "grammar_corrections": [
    {"original": "原句错误片段", "corrected": "订正后片段", "reason": "中文极简解析（20字以内）"}
  ],
  "native_upgrade": "整句学术化/地道改写（1句话）",
  "fluency_score": 85
}
""".strip()

SCENARIOS = {
    "graduate_interview": {
        "label": "考研复试仿真",
        "opening": "Good morning. Welcome to the graduate interview. Could you please briefly introduce yourself and your undergraduate research experience?",
        "role": "Professor Zhang (Strict & Academic)",
    },
    "daily_fluency": {
        "label": "日常流利度",
        "opening": "Hi there! Let's have a relaxed chat. What did you do this week that you found interesting?",
        "role": "Friendly Language Partner",
    },
    "pronunciation": {
        "label": "发音纠偏",
        "opening": "Let's practice pronunciation. Please read this sentence slowly and clearly: 'The thirty-three thieves thought that they thrilled the throne throughout Thursday.'",
        "role": "Pronunciation Coach",
    },
}


def build_speaking_user_prompt(
    scenario: str,
    topic: str,
    history: list[dict],
    user_text: str,
) -> str:
    """组装考官对话请求。history: [{"role": "user"/"assistant", "content": ...}] 最近 6 轮。"""
    lines = ["【场景】{}".format(SCENARIOS.get(scenario, {}).get("label", scenario))]
    if topic:
        lines.append("【话题】" + topic)
    if history:
        lines.append("【对话历史】")
        for h in history[-6:]:
            lines.append("{}: {}".format("考生" if h["role"] == "user" else "考官", h["content"]))
    lines.append("【考生本轮回答】\n" + user_text)
    lines.append("\n请以考官身份回应（JSON）。")
    return "\n".join(lines)
