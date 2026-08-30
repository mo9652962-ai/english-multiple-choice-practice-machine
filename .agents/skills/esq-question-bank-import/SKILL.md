---
name: esq-question-bank-import
description: 构建/校验/导入 ESQ 题库包。触发：'补题型''导入题库''题库数据源'。
---
# ESQ 1.0 题库包导入管道

为墨题刷题机 (D:/english-multiple-choice-practice-machine) 补充/构建题库的正规流程。
**禁止直接改 SQLite 塞题** —— 走 ESQ 包 + 官方导入 API，校验器保证结构与答案完整。

## When to Use
- 某个题库级别(考研一/高中/四级/六级/考研二)缺题型(完形/阅读/PartB)需要补
- 从公开数据集(GAOKAO-Bench / wamich / ayaka-notes)转 ESQ 导入
- 需要给无答案真题做 AI 标注(基元律动)

## 核心流程
1. **构造 ESQ 包**(ZIP): manifest.json + papers/<year>.json + answers/<year>.json
   - manifest: format=esq, schemaVersion=1.0, packageId(纯ASCII), papers=[{paperKey,year,path,answerPath}]
   - paper JSON: units=[{unitKey, type(cloze|reading|part_b), title, sequence, passage:{blocks:[{blockKey,type:"paragraph",text}]}, questions:[...]}]
   - cloze: passage text 用 `{{blank:1}}` 双花括号标记空位(注意不是单花括号!); 词库题(四六级选词填空)用 unit.candidates=[{key:"A",content:"..."}] + questions 不写 options(自动用 candidates)
   - question: {questionKey, number, type:"single_choice", stem, options:[{key:"A",content}], score}
   - answers JSON: {paperKey, answers:{<questionKey>:{correctOption:"B", score}}}
2. **校验**: `python tools/validate_question_bank.py <file.esq>` → valid:true + 0 errors
3. **上传导入**: POST `/api/question-banks/imports` (multipart: file + profile_id) → 返回 job_id
4. **发布**: POST `/api/question-banks/imports/{job_id}/publish` (body `{}` 或 resolutions)

## Pitfalls (全部踩过)
- **上传路径是 `/api/question-banks/imports`，不是 `/upload`**(会 405)! publish 是 `/imports/{job_id}/publish`
- **externalKey 必须纯 ASCII 3-200 位** `[A-Za-z0-9._:-]` —— 含中文(如 unitKey="gaokao-cloze-2021-新课标Ⅰ")校验直接失败!
  用 `cn.gaokao.cloze.y2021.u1` 风格
- **ESQ 用 `{{blank:N}}` 双花括号**; 库里存储是单花括号 `{blank:N}`(导入器转换)
- answers 每空必填 correctOption; 题目 options 与答案字母必须对应(答案字母必须存在于该题 options)
- **级别切换机制**: 激活级别在 `app_settings.active_question_bank_profile_id`(value=profile_id 字符串),
  不是 question_bank_profiles.is_default! 测试切级别必须写 app_settings (INSERT ... ON CONFLICT(key) DO UPDATE)
- **前端 embedded 缓存坑**: 后端首页注入 `window.__LINJIAN_STARTUP__` 首屏缓存, DashboardView.loadHome() 发现它就不请求后端 →
  切题库级别后推荐/题型仍是旧级别! 修复: loadHome(force=true) 且切换器传 true 跳过缓存
- **段落匹配归一化**: unit_type=paragraph_matching 在前端归一化到 part_b 卡(randomPractice param 'part_b')
- **startup 题型可用性**: /api/startup → recommendations.unit_type_counts {cloze:N, reading:N, paragraph_matching:N}
  前端 practiceCards 据此动态显示三卡/灰化
- **AI 标注答案**: POST /api/ai/chat {profile_id:3, model:"deepseek-v4-flash", message} → 提取 content 中 JSON
  **必须用 `json.JSONDecoder().raw_decode(content, content.find("{"))` 取第一个对象** —— AI 常在 JSON 前后加解释文本,
  find/rfind 截取会报 Extra data (实测踩过); profile_id=3 是基元律动(TokenRhythm); 注意后端必须先启动
- **AI 批量/限流**: 批量翻译单词 30 词/批 (60 词触发 400); 模型服务 503 抖动时重试 3 次间隔 10s (瞬时恢复, 不是配置问题)
- **MSYS 路径坑**: git-bash `/tmp` = C:/Users/31954/AppData/Local/Temp; 但 write_file 到 `C:\tmp` 是真实 C 盘根!
  clone 下来的 repo 在 AppData/Temp, 脚本路径要用 C:/Users/31954/AppData/Local/Temp/...
- **wamich md 多个 Section A**: CET md 文件有听力 Section A + 阅读 Section A! regex 必须从
  `## Part III / Reading Comprehension` 之后找 `### Section A`, 否则解析出 0 空
- **PDF 文字抽取质量**: 解析前先打印 extract_text 前 200 字, 乱码(`$%&'()*`)立即换源或 AI 模拟, 别投资解析
- **验证后记得**: cp backend/data/question_bank.db mobile-app/question_bank.db (手机版离线题库)
  backend/data/ 与 *.db 被 gitignore, 数据不进 git

## 单词本高频/热点词分类 (v2.15)
- **高频词源**: `kajweb/dict` (github) book/*.zip 的 JSONL —— 每行一个对象
  `{wordRank, headWord, content:{word:{content:{trans, usphone, syno}}}}`, **wordRank=真题词频排序**
  = 四级真题核心词1162 / 六级1228 / 考研必考1341 (天然高频); JSONL 必须逐行 json.loads (整文件报 Extra data)
- **热点词**: 近两年 (year>=2023) 真题 passage 词频统计, 去停用词, `[a-zA-Z][a-zA-Z'-]{3,}` → 每级别 top300 标 `级别·热点`
- **分类区分**: category 用 "级别·高频"/"级别·热点"; 后端过滤 `category LIKE '级别%'` 前缀匹配
  (精确 `=` 会筛不出 "高中·高频"); 前端双维 chips (级别行 + ⭐高频/🔥热点/📚基础 行, 组合参数)
- 去重: normalized_term 已存在 → 只更新 category 追加 "·高频" + manually_frequent=1, 不重复插入
- 释义缺失(热点词是复数/变形, 词库查不到): AI 批量翻译 30 词/批补齐

## References
- `references/chinese-exam-datasets.md` — 各真题数据源格式细节与解析要点
- `templates/upload_and_publish.py` — multipart 上传 + 发布的可复用脚本模板

## Verification
- validate_question_bank.py 0 errors
- 导入发布后: SELECT unit_type FROM units JOIN papers ... WHERE profile_id=? 确认三卡(cloze/reading/part_b)齐全
- API: /api/startup recommendations.unit_type_counts 三卡全亮; random practice 真实出题
