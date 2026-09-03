# -*- coding: utf-8 -*-
"""AI 英语刷题机 — AI 文章生成器（基于单词本生成语境短文辅助记忆）

来自社区需求 (2026-08): "单词本里单词能不能利用AI生成文章辅助记忆"
参考: Context App (语境记忆理论)、QuizFlow (交互式闪卡)、Subs2SRS (媒体词汇提取)

设计:
  - 从单词本取 5-10 个待复习/高频词
  - 调 DeepSeek V4-Flash 生成包含这些词的英文短文
  - 短文长度可控 (paragraph / short / micro)
  - 可选主题 (考研/科技/日常/随机)
  - 高亮文中的目标词汇
"""
from __future__ import annotations

import json, sqlite3
from typing import Any

from .ai_client import chat_completion


ARTICLE_PROMPTS = {
    "考研": "Write a short English article suitable for Chinese postgraduate entrance exam (考研英语) reading level. "
            "The article should naturally incorporate ALL of the following words: {words}. "
            "Topic: academic or social commentary. Length: 200-300 words. "
            "After the article, list each target word with its Chinese meaning.",
    "科技": "Write a tech blog post in English that naturally uses ALL these vocabulary words: {words}. "
           "Style: informal but professional. Length: 150-250 words.",
    "日常": "Write a short story or diary entry in English that naturally includes ALL of these words: {words}. "
           "Tone: casual and relatable. Length: 150-200 words.",
    "随机": "Write an engaging English passage that naturally incorporates ALL of these words: {words}. "
           "Be creative with the topic. Length: 150-250 words. "
           "After the passage, bold each target word and provide its Chinese translation.",
}


def _pick_words(connection: sqlite3.Connection, count: int = 8, user_id: int | None = None) -> list[dict]:
    """从单词本选词：优先待复习 > 高频词 > 随机（按用户隔离）"""
    # 先查待复习
    rows = connection.execute(
        """SELECT term, common_meaning, encounter_count
           FROM vocabulary_entries
           WHERE user_id IS ?
             AND translation_status = 'ready'
             AND study_status = 'learning'
           ORDER BY encounter_count DESC
           LIMIT ?""",
        (user_id, count * 2,),
    ).fetchall()
    
    words = [dict(r) for r in rows]
    
    # 如果不够，补高频词
    if len(words) < count:
        existing_terms = {w["term"] for w in words}
        more = connection.execute(
            """SELECT term, common_meaning, encounter_count
               FROM vocabulary_entries
               WHERE user_id IS ?
                 AND translation_status = 'ready'
                 AND term NOT IN ({})
               ORDER BY encounter_count DESC
               LIMIT ?""".format(",".join("?" * len(existing_terms)) if existing_terms else "''"),
            (user_id, *existing_terms, count - len(words)),
        ).fetchall()
        words.extend(dict(r) for r in more)
    
    return words[:count]


def generate_article(
    connection: sqlite3.Connection,
    topic: str = "随机",
    word_count: int = 8,
    user_id: int | None = None,
) -> dict[str, Any]:
    """从单词本选词 + 生成语境短文
    
    Args:
        connection: 数据库连接
        topic: "考研" | "科技" | "日常" | "随机"
        word_count: 包含的目标单词数 (5-15)
    
    Returns:
        {"words": [...], "article": "...", "topic": "...", "word_count": N}
    """
    word_count = max(5, min(15, word_count))
    topic = topic if topic in ARTICLE_PROMPTS else "随机"
    
    words = _pick_words(connection, word_count, user_id=user_id)
    if len(words) < 3:
        return {"error": "单词本词汇不足，请先添加至少 3 个已完成翻译的单词", "words": words}
    
    word_list = ", ".join(w["term"] for w in words)
    prompt = ARTICLE_PROMPTS[topic].format(words=word_list)
    
    try:
        article = chat_completion(
            connection,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
        )
    except Exception as e:
        return {"error": f"AI 生成失败: {e}", "words": words}
    
    # 构建带高亮的 HTML
    html = article
    for w in words:
        term = w["term"]
        meaning = w.get("common_meaning", "")
        html = html.replace(
            term,
            f'<mark class="vocab-highlight" title="{meaning}">{term}</mark>'
        )
    
    return {
        "words": [{"term": w["term"], "meaning": w.get("common_meaning", "")} for w in words],
        "article": article,
        "article_html": html,
        "topic": topic,
        "word_count": len(words),
    }
