# 中文英语考试真题数据源 (2026-08 实测)

## GAOKAO-Bench (OpenLMLab) — 高考真题, 自带答案, 首选
- repo: `https://github.com/OpenLMLab/GAOKAO-Bench` (clone 约几十MB)
- **2023-2024 补充**: `https://github.com/OpenLMLab/GAOKAO-Bench-Updates` — 独立 repo!
  `Data/GAOKAO-Bench-2023/` 和 `Data/GAOKAO-Bench-2024/` 下同名 `*_English_Fill_in_Blanks.json`(完形) / `*_English_Cloze_Test.json`(七选五)
- 数据: `Data/Objective_Questions/*.json`, 每个文件 `{"keywords":..., "example":[...]}` (注意 example 是数组!)
- 相关文件:
  - `2010-2022_English_Fill_in_Blanks.json` = **完形填空** (30条)
  - `2012-2022_English_Cloze_Test.json` = **七选五** (26条)
  - `2010-2022_English_Reading_Comp.json` = 阅读理解 (124条, 已导入过)
- 每条记录字段: `{year, category, question, answer(list), analysis, index, score}`
- **完形解析**: question = 指令 + 文章(空位 `___41___` 格式) + 尾部选项块 `41. A. xxx B. xxx C. xxx D. xxx`
  - 文章空位 regex: `_{3,}\s*(\d{1,3})\s*_{3,}` → 顺序映射为 {{blank:N}}
  - 选项块 regex: `^\s*(\d{1,3})[\.\s]+((?:[A-G]\.\s+[^\n]{2,80}\s*){2,7})`
  - answer 数组按空号顺序给出 (如 ['C','A','B','D',...])
- **七选五解析**: question = 指令 + 文章(空位 ___36___ 等) + 尾部 `A. 句子` 到 `G. 句子` 选项块 (7个含2干扰)
  - 选项块起始: 第一个匹配 `^\s*[A-G]\.\s` 的行; 每个空共用全部选项 → options_map 用 key 0, 每空 fallback
  - answer 数组 = 各空答案字母 (如 ['B','C','F','E','G'])

## wamich/english-exem-md — 四六级真题 markdown
- repo: `https://github.com/wamich/english-exem-md` (CET4/ CET6 目录, 2023.06 / 2023.12 各3套)
- **Section A = 选词填空/词库完形 (10空 + 15词库 A-O)**, 之前导入漏了这个题型!
  - **坑: md 文件有多个 `### Section A` (听力 Part II 也有!)** —— regex 必须从
    `## Part III / Reading Comprehension` 之后找 `### Section A`, 否则匹配到听力段解析出 0 空 (2023.12 实测)
  - 文章空位: `<u>&emsp;26&emsp;</u>` → regex `<u>\s*&emsp;\s*(\d{1,3})\s*&emsp;\s*</u>`
  - 词库表格: `| A) abstracts | I) nearly |` 双列 → regex `\|\s*([A-O])\s*\)\s*([a-zA-Z'\-]+)\s*\|\s*([A-O])\s*\)\s*([a-zA-Z'\-]+)\s*\|`
  - **无答案** → 基元律动标注 (每空从 A-O 选一词, 词不能重复用)
- Section B = 长篇匹配 (段落字母), Section C = 仔细阅读 (A-D)
- 注意: 文件无答案 (纯题目), 答案需 AI 标注或从别处找

## ayaka-notes/201-english — 考研英语一 LaTeX 真题 (2001-2023)
- repo: `https://github.com/ayaka-notes/201-english` (1/ 目录含各年 .tex)
- 结构: `\subsection{Text 1}` 文章 + `\begin{enumerate}` + `\item` 题干 + `\fourchoices{A}{B}{C}{D}` (宏可跨行!)
- 选项 regex: `\\fourchoices\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}\s*\{([^}]*)\}` (跨行要 \s*)
- Part B 新题型: 各年形式不同
  - 2016/2020: 阅读选最合适 (适合转 single_choice)
  - 2017/2018/2019: 排序 (wrong order, 不适合选择题结构)
  - 2021: 七选五选句 (`\begin{listmatch}` + `\linefill` 空位) — **最适合转 part_b** (5空 + 7选项)
- **无答案** → AI 标注
- clean_latex: 去 \emph/\textbf/\lineread, `` '' → ", --- → —

## 考研 PDF 数据源 (谨慎!)
- `Fantasia1999/kaoyanzhenti`: 英语一 1998-2026 + 英语二 2010-2026 (考场版 PDF)
  - 2015 英语二 PDF 文字可提取但 **OCR 噪声严重** (每行有断裂字母 y/g 等, 完形空位是孤立数字 1/2/3 难与真实数字区分)
- `zwd1216/yingyuer`: 考研二 PDF 字体无 ToUnicode → pdfplumber 提取全乱码 ($%&'()*)
- 结论: 自动解析考研 PDF 不可靠; 若必须 → OCR 或人工录入
- **考研二兜底方案 (cet-skill 模式)**: 基元律动生成模拟题, prompt 参考真题趋势
  (完形 20空/阅读 Text1 5题/新题型七选五 5空), license 明确注明 "AI 生成模拟题, 非真题"

## 导入后清理
- 临时脚本/ESQ 包用完删 (C:/Users/31954/AppData/Local/Temp/gaokao-esq 等)
- `cp backend/data/question_bank.db mobile-app/question_bank.db` (手机版离线库)
- git: backend/data/ 与 *.db 被 gitignore → 数据不进 git, 无需 push

## 词库/高频词源 (单词本分类用)
- **kajweb/dict** (github, 有道词书打包): `book/*.zip` 内含 JSONL, 每行一个对象
  - `{wordRank, headWord, content:{word:{content:{trans:[{pos,tranCn}], usphone, syno}}}}`
  - **wordRank = 真题词频排序** → 高频词直接取: CET4_1(四级真题核心词1162) / CET6_1(六级1228) / KaoYan_1(考研必考1341)
  - 注意 JSONL 逐行 json.loads; 整文件 load 报 "Extra data"
- **KyleBing/english-vocabulary** (github, MIT): txt `word\t释义` (高中6008/四级7508/六级5651/考研9602) — 完整词库, 无词频
- 热点词: 题库近两年真题 passage 词频统计 (year>=2023), 去停用词后取各级别 top300 → category "级别·热点"
