---
name: exam-question-bank-import
description: Use when 导入英语考试真题题库(ESQ)或补充题型/单词. 数据源+解析+导入管道+坑.
category: edtech
---
# 英语考试真题题库导入（ESQ 1.0）

> 应用于刷题机项目 `D:/english-multiple-choice-practice-machine`（后端 FastAPI + SQLite）
> 用途：从开源数据源采集真题 → 构造 ESQ 包 → 校验 → 上传发布 → AI 标注答案

## When to Use
- 用户要求"导入真题/补题型/更新题库"（四六级/考研/高考）
- 用户要求"导入高频词/热点词"到单词本
- 用户要求"只保留 2024+ 题库"（旧题"没有参考性"是明确偏好）

## 数据源清单（真实真题, 免费可商用）
> 具体 URL/文件路径/下载命令见 `references/data-sources.md`
> 2025-26 各源实测结论（登录墙/网盘/夸克 API/云解析）见 `references/2025-26-zhenti-sources.md`
| 考试 | 来源 | 格式 | 答案 |
|:---|:---|:---|:---|
| 高中完形/七选五 | OpenLMLab/GAOKAO-Bench (2010-2022) + GAOKAO-Bench-Updates (2023-2024) | JSON `{"example":[{year,category,question,answer[],analysis}]}` | ✅ 自带 |
| 四六级全文 | wamich/english-exem-md | markdown（含听力） | ❌ 选词填空需 AI 标注 |
| 考研一全文 | ayaka-notes/201-english (2001-2023) | LaTeX `.tex` | ❌ AI 标注 |
| 考研一 JSON | **XixiGod7/kaoyan-english** (1998-2025) | JSON (sections: cloze/reading-a/new-type) | ❌ AI 标注 |
| 考研二全文 | Fantasia1999/kaoyanzhenti | PDF（⚠ 部分字体编码乱码） | ❌ |
| 真题高频词 | kajweb/dict book/ 下 zip | JSONL（wordRank 排序） | ✅ |
| 完整词库 | KyleBing/english-vocabulary | txt `word\t释义`（高中/四级/六级/考研 乱序） | ✅ |
| 考研词频 | exam-data/NETEMVocabulary | json `{"5530考研词汇词频排序表":[{序号,词频,单词,释义,...}]}` | ✅ |
| 2025-2026 高考 I/II 卷 PDF | en-sky（百度网盘 8888）· **cc518.com（夸克网盘 98724fa5ca85）** | PDF+MP3 | ✅ 答案 PDF |
| 2025.12 四六级 | 新东方 cet4-6.xdf.cn | 听力有材料+选项但**缺题干/答案**；阅读页"整理中"空 | ❌ 碎片 |
| **2025.12/2026.6 四六级** | **环球网校 m.hqwx.com** | **PDF 免登录自动下载**（见 references）——但回忆版**缺干扰选项/阅读无原文** | ⚠️ 半成品 |
| 2026 考研 | 启航 jixun.iqihang.com | 真题是**图片**（PNG 截图） | ❌ 需 OCR |
| 2026 考研/B站 | bilibili 真题讲解 | **无字幕**（subtitle 空） | ❌ |
| 2024-2026 真真题 | 均被登录墙/网盘/图片/JS 挡（实测）| — | AI 模拟兜底 |

## ESQ 1.0 包结构
```
bank.esq (ZIP)
├── manifest.json    {format:"esq", schemaVersion:"1.0", packageId, contentVersion,
│                      title, subject, publisher, license:{notice}, source:{type,description},
│                      papers:[{paperKey, year, path, answerPath}], features:{hasAnswers}}
├── papers/2024.json {paperKey, year, title, subject, units:[{unitKey, type, title, sequence,
│                      passage:{blocks:[{blockKey, type:"paragraph", text}]},
│                      candidates:[{key:"A", content:...}], questions:[...]}]}
└── answers/2024.json {paperKey, answers:{<questionKey>:{correctOption:"A", score}}}
```
- **externalKey/unitKey/questionKey 必须纯 ASCII 3-200 位**（中文必校验失败）
- unit.type ∈ {cloze, reading, part_b}；cloze 空位用 `{{blank:N}}`（导入转 `N ______`）
- cloze questions 可不写 options → 自动用 unit.candidates（选词填空词库）
- ⚠️ **cloze 双渲染路径坑（2026-08-17 实测）**：前端对 cloze 单元有两条渲染路径——`shared_data.content_blocks` 存在 → 走 ContentBlocks 组件（只认 `{{blank:N}}` 格式，且旧版 blank 是**纯 span 无点击**）；不存在 → 走 passageSegments 正则（认 `N ______`/`(N)` 格式，v3.4 起可点击弹选项）。**导入时若带了 content_blocks，前端选词填空空格可能点不动**——修法见 english-practice-machine 技能 v3.6 段（ContentBlocks blank 改 button + emit blank-click + blankAnswers 回填；cloze 隐藏右侧面板）。

## 解析要点（各数据源格式差异）
- 高考完形/七选五**两种空位格式**: `___41___` 下划线 与 `（3）` 全角括号（2024 新课标）
- 选项块两种: `41. A. xxx B. xxx C. xxx D. xxx` 与 `（3）A.asking B.looking...`
- 四六级 md **听力也有 Section A**：regex 必须从 `## Part III / Reading Comprehension` 之后找
- 考研一 LaTeX: `\fourchoices` 宏跨行（regex 加 `\s*`）；`\linefill` 是七选五空位；
  排序题（listmatch wrong order）不适合转选择题，选七选五年份（2021 等）
- 考研二 PDF 字体编码乱码（pdfplumber 提取 `$%&'()*`）→ 换源或 AI 模拟

## 导入流程
```bash
# 1. 校验（必须先跑, valid:true 才导入）
python tools/validate_question_bank.py path/to/bank.esq

# 2. 上传 + 发布（multipart file + profile_id 表单）
POST /api/question-banks/imports
POST /api/question-banks/imports/{job_id}/publish   # body: {}
```
- profile_id: 1考研一 2高中 3四级 4六级 5考研二
- 软删除旧卷: UPDATE papers SET deleted_at=now,status='deleted' + INSERT trash_entries
  **trash_entries.purge_after 非空约束** → 必须填 `datetime('now','+30 days')`

## AI 标注答案（基元律动）
```python
POST /api/ai/chat  {"profile_id":3, "model":"deepseek-v4-flash", "message": prompt}
```
- prompt 要求"只输出 JSON"；**返回用 `json.JSONDecoder().raw_decode` 取第一个对象**
  （模型常输出解释+JSON，整体 loads 报 Extra data）
- 批量翻译单词 30 词/批（60 词报 400）；503 偶发 → 重试 3 次间隔 8-10s

## 听力题解析（wamich md 四六级 Part II）
- 听力在 `## Part II / Listening Comprehension`（不是 Part III 阅读），Section A→B→C
- 题目组: `**Questions 1 and 2 are based on...**` 后跟选项行
- 选项在多行: `A) text\n   B) text\n   C) text\n   D) text`
- 解析 regex: `([A-D])\)\s*(.+?)(?=\s*\n\s*[A-D]\)|\s*$)` 切每题选项块
- 无听力原文（仅题目+选项），答案需 AI 标注
- 导入 unit_type="listening"（自由字符串），前端 UNIT_TYPE_NAMES/UNIT_TYPE_PARAMS 加映射
- 2026 AI 生成: 基元律动 prompt 输出 `{"questions":[{"number","stem","options":{"A":...},"answer":"A"}]}`

## 单词本高频/热点词
- 高频词: kajweb/dict 真题核心词 zip → JSONL，category="四级·高频" 等
- 热点词: 从近两年真题文章 TF 统计（过滤停用词）→ category="考研·热点"
- category 后端用**前缀匹配**（`LIKE ?` + `f"{cat}%`）支持 "高中"→"高中·高频"
- 热词是变形（employees）词库查不到 → 词形还原匹配或 AI 批量翻译

## 全类别核心词汇批量导入（2026-08 实测，5083 词）
> 适用：用户要"导入全类别高频/核心/热点词汇"到单词本
```python
# 数据源
# 1) KyleBing/english-vocabulary: 文件名"2 高中-乱序.txt"/"3 四级-乱序.txt"/"4 六级-乱序.txt"/"5 考研-乱序.txt"
#    raw URL: https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/<URL编码文件名>
#    txt 格式: `although\tconj. 尽管；虽然；但是；然而`（单词 TAB 释义）
# 2) exam-data/NETEMVocabulary netem_full_list.json: {"5530考研词汇词频排序表":[{序号,词频,单词,释义,分类,子分类}]}
#    （词频排序——真高频；大文件 1MB+ 用 curl 下载，raw 直链可能被限速→用代理）

# 解析+导入要点
# - 每类别取 2000 → 跨类别去重后约 5000（考研与四六级大量重叠）
# - 释义拆词性: re.match(r"^(n\.|v\.|adj\.|adv\.|prep\.|conj\.|pron\.|num\.|art\.|int\.|aux\.|vt\.|vi\.)")
# - 中文释义取第一条（"；"分割 [0]）→ common_meaning 核心义
# - INSERT vocabulary_entries: term/normalized_term/lemma=小写, part_of_speech, common_meaning,
#   translation_status='ready', category='高考/四级/六级/考研', study_status='new'
# - 同词保留首个分类（先导高考→考研专属词只剩 ~500——合理，重叠词已在库）
# - **同步 3 库**: frontend/public + %APPDATA%/ai-english-practice-desktop/data + frontend/dist
# - question_bank.db 被 .gitignore → git 提交看不到，dist 库会随 release_all.py 进安装包

## 完整词库导入（扩展：用户要"完整词库"时，不用 limit=2000）
- 解析全部行（四级 7508 / 六级 5651 / 考研 5530 / 高中 6008）→ 跨类别去重
- **normalized_term 有 UNIQUE 约束** → 插入已存在的词报 `IntegrityError: UNIQUE constraint failed`：
  **导入前先查 `SELECT 1 FROM vocabulary_entries WHERE normalized_term = ?` 跳过**（重叠词已入库——只补专属新词）
- 实测：完整四级/六级/考研解析 18689 → 去重后新增 1965 专属（四级+661/六级+1040/考研+264）→ 总库 7751
- 完整词库每类别只比 2000 版多几百专属（重叠词大量跨类别——基础词跨高中/四级/六级/考研）
- 高中完整 6008 → 高考类新增 703（其余与四级/六级/考研重叠已入库）

## 分类标签坑（2026-08-09 实测：单词本分类空）
- **前端 VocabularyView 筛选按钮传 `category='高中'`**（"🏫 高中"按钮），**但导入脚本用 `category='高考'`** → 高中分类查不到任何词 → 页面显示"这里还没有符合条件的单词"
- **必须统一为 '高中'**（前端标签为准）：`UPDATE vocabulary_entries SET category='高中' WHERE category='高考'`（3 库同步：public/data/dist）
- 四级/六级/考研标签前后端一致（无此坑）；只在导入时自定义分类名时出现
- 修复后验证：`curl "http://127.0.0.1:8765/api/vocabulary/home?limit=5&category=%E9%AB%98%E4%B8%AD"` 应返回词条

## 新东方四六级真题页结构（cet4-6.xdf.cn）
- **目录页**（如 15047556 "2025年12月四级试题及答案完整版第一套"）只列子页链接（听力/阅读/翻译/作文）——正文在**子页面**
- 提取子页 URL：`grep -oE 'href="[^"]*"[^>]*>[^<]*(阅读|听力|翻译)[^<]*'`（目录页 HTML 内 href 完整）
- 阅读子页（如 15047563）含选词填空+长篇阅读+仔细阅读——但**仔细阅读（46-55）也只有正确选项**（回忆版——`46.A) ... 47.C) ...` 每题仅 1 行）——**无完整 4 选项，不可构建选择题**
- 判断 DOCX/PDF 是否完整：python-docx 统计 `^(\d{1,2})[\.、]\s*([A-D])[\)\.]` 行——完整题每题 4 行（4 选项），回忆版每题 1 行（仅答案）

## Pitfalls
- sqlite3.Row 无 `.get()` 方法 → 用 `dict(row)` 或 `row["key"]`（FastAPI get_db 的 row_factory=Row）
- **vocabulary_entries.normalized_term 有 UNIQUE 约束**——导入重复词报 IntegrityError → 先查跳过（重叠词已入库）
- 下载的真题 PDF 先查**文本层**（`pymupdf`/`fitz`: `sum(len(p.get_text()) for p in doc)`）——回忆版 PDF 有文本层可提取；扫描版需 OCR（明确提示不伪装成功）
- 新加路由/改后端 → 删 `__pycache__` + 重启（否则旧代码生效）
- 题库数据在 `backend/data/question_bank.db`（被 .gitignore，本地管理）；打包时 cp 到 mobile-app/
- 验证 ad-hoc 脚本放 Temp 目录（git-bash `/tmp` = `C:/Users/<user>/AppData/Local/Temp`，不是 C:\tmp）
