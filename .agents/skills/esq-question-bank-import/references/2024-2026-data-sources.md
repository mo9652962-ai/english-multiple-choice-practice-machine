# 2024-2026 新增数据源 (2026-08 实测)

## XixiGod7/kaoyan-english — 考研一 1998-2025 真题 JSON (首选)
- GitHub: `https://github.com/XixiGod7/kaoyan-english` (2026-06 更新)
- 数据: `public/data/1998.json` ~ `2025.json` (考研英语一)
- 结构: `{year, sections: {cloze, reading-a, new-type, translation, writing-a, writing-b}}`
- **reading-a**: `texts[4]` (每篇 article 全文) + `questions[20]` ({number, stem, choices[{label, text}]})
  - 按题号 21-40 分组到 4 篇 Text: `(ti*5+21) <= q["number"] <= (ti*5+25)`
- **cloze**: `article` (数字标记空位 1-20) + `text` (选项行 `1.[A] Through [B] Despite...`)
  - **坑**: text 可能被 PDF 截断仅前 2 题有选项 → 选项不足 4 的题跳过
- **new-type**: 4 题 (42-45), stem 含文章片段 + choices A-G; 2025 可能 0 题(提取失败)
- 答案: 无 → AI 标注 (基元律动 profile=3)
- 转换要点: article 孤立数字 → {{blank:N}}; 空选项 content 过滤 `if v.strip()`; 不足 4 选项的题跳过; 不用完形(数据截断)

## wamich 四六级听力 Part II
- CET4/CET6 md 的 `## Part II / Listening Comprehension` 含 Section A/B/C
- 格式: `**Questions 1 and 2 are based on...**` → 每题 `1. A) text\n   B) text\n   C) text\n   D) text`
- 选项按 `[A-D])` 拆分(不在同一行!); 正则 `([A-D])\)\s*(.+?)(?=\s*\n\s*[A-D]\)|\s*$)` 逐题切
- unit_type: `listening`, subtype: `听力理解`
- 无脚本/音频, 文本默认 "(听力音频请自行播放对应真题音频)"

## GAOKAO 2024 新课标 I/II 特殊格式
- 空位: `（N）` 全角括号 (非 `___N___`), 需双正则: `_{3,}\s*(\d{1,3})\s*_{3,}` + `[（(]\s*(\d{1,3})\s*[）)]`
- 完形选项: `（3）A.asking B.looking C.waiting D.training` 内嵌格式, 正则 `[（(]\s*(\d{1,3})\s*[）)]\s*((?:[A-G]\.\s*[^\s（(]{2,60}\s*){2,7})`
- 七选五选项: `A.I don't often...` (A.后无空格!) → 正则 `^\s*[A-G]\.(?!\s*[A-Z]\.)` 匹配选项起始行