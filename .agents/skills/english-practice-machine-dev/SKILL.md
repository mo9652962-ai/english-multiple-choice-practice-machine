---
name: english-practice-machine-dev
description: "墨题英语刷题机开发：ESQ题库导入管道、真题数据源、AI标注、验证流程。触发：'刷题机开发''墨题开发''题库导入''ESQ''真题数据''AI标注''题库验证''刷题机构建''刷题机打包'。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [刷题机, esq, 题库导入, 英语学习, fastapi, vue]
    category: development
---

# 墨题英语刷题机开发 Skill

墨题（英语刷题机）位于 `D:\english-multiple-choice-practice-machine`。Vue3 前端 + FastAPI 后端 + SQLite（`backend/data/question_bank.db`），支持多题库级别（高中/四级/六级/考研一/考研二），Electron 桌面版 + Capacitor 手机版 + 网页版三端。

## When to Use

- 导入/维护各级别题库（真题或模拟题）
- 开发刷题机功能（练习、考试、错题本、单词本、AI助手、首页推荐）
- 排查前端白屏 / Failed to fetch / 分类不生效
- 需要真实真题数据或 AI 生成模拟题

## How to Run

```bash
cd D:\english-multiple-choice-practice-machine
python run_app.py          # 本机模式 http://127.0.0.1:8765
cd frontend && npm run build  # 前端构建 → dist/
```

**后端不在运行 = 前端 `TypeError: Failed to fetch`**（最常见的"bug"，先查 `netstat -ano | grep 8765` 再报）。验证完测试进程要 kill，但用户还在用时保持运行。

> UI 规范/长耗时模式/打包坑: references/ui-dev-and-packaging-2026-08.md
> 后端 SQLite 测试 4 大陷阱（SCHEMA 缺唯一索引/冗余索引引旧列/SSRF 误伤本机 Ollama/测试直连拿不到 Depends）: references/backend-sqlite-test-pitfalls-2026.md

## AI 学习诊断（P0/P1，2026-08-15 落地）

**加速（第二轮）**：报告文字用 `diagnostic_report.build_report_text()` 本地模板组装——**别调 `write_anonymous_report`**（第 3 次 AI 调用 ~20s）。3 次串行 AI → 2 次（归因 + 水平评估），8 题 ~60s。前端 loading 按时间猜阶段（40s 归因 / 55s 水平），生成完刷新自动展示最新报告（onMounted 加载 history[0]）。
**UI 暗色规范**：新页面用项目 CSS 变量（`--surface-solid`/`--ink-2`/`--ink-3`/`--line`/`--primary-soft`），**禁止自造 `var(--panel, #fff)` fallback**（深色模式白卡片刺眼）+ 禁止亮色硬编码（#e74c3c/#2563eb/#f0f7ff 等）——cause 色用暗色系。
**Capacitor 位置坑**：墨题 Capacitor 工程在 `frontend/` 下（`frontend/android/` + `frontend/capacitor.config.ts`，webDir: dist）——**不在项目根目录**！改打包先查 frontend/。HBuilderX `mobile-app/` 已于 2026-08-15 清理。
完整落地验证清单（巡检流程/边界/坑）：`references/diagnostic-feature-checklist-2026-08.md`

- `services/ai_router.py`：任务路由（`chat_with_routing`）+ 降级链 + ai_usage 用量记录
- `services/diagnostic_report.py` + `routers/diagnostic.py`：水平 1-5 / 推荐练习 / 趋势对比 / 持久化
- `DiagnosticView.vue`（/diagnostic）+ WrongView「🧠 学习诊断」入口
- **task_tags 是任务名数组不是组标签**；诊断测试要造 session 外键链数据；前端组件必须用 `.card` + 主题变量（自造 `--panel, #fff` 破坏深色模式）
- 完整落地记录 + 验证脚本 + 深色模式修复样板见 `references/p0p1-ai-diagnostic-2026-08.md`

## 移动端打包（Capacitor，HBuilderX 已清理 2026-08-15）

**Capacitor 工程在 `frontend/` 下，不是根目录**（易查错：根目录没有 android/、没有 capacitor.config）。

```bash
cd frontend
npx cap sync android                              # dist → android 原生工程
cd android && ./gradlew.bat assembleDebug --no-daemon   # JDK21+SDK34 → APK
# 产物: frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

- 环境：`JAVA_HOME=C:\Users\31954\jdk21`、`ANDROID_HOME=C:\Users\31954\android-sdk`
- 内置离线库 = `frontend/public/question_bank.db`（构建进 dist → APK）；改词库须同步 + 重打包
- **验证 APK 含最新前端**：`unzip -l app-debug.apk | grep index-` 对比 `dist/index.html` 里的 hash（如 index-CwRFwW7a.js）
- 微信发不了 APK（全拦截）→ 本地 HTTP + 二维码或网盘
- HBuilderX 旧路径 `mobile-app/` 已删除 + gitignore，勿再引用

## AI 服务层（2026-08）

墨题 AI 层 = 任务路由 + 降级 + 用量 + 学习诊断：

- `backend/app/services/ai_router.py` — `chat_with_routing()`：按任务选 profile（`ai_profiles.task_tags` 声明任务、`priority` 定顺序）→ 失败降级下一候选 → `ai_usage` 表记录每次调用
- `backend/app/services/diagnostic_report.py` — 学习诊断：逐题归因 → 聚合 → 水平 1-5 → 推荐练习 → 趋势对比 → `diagnostic_reports` 持久化
- API：`POST /api/diagnostic/report`、`GET /api/diagnostic/report/{id}`、`GET /api/diagnostic/reports`
- 前端：`DiagnosticView.vue`（/diagnostic）+ 错题本「🧠 学习诊断」入口

**坑**：profile.task_tags 必须用任务名（wrong_diagnosis...），不要用 cloud/local 组标签（路由匹配会失效）。详见 `references/ai-service-layer.md`。

## Core Workflows

### 1. ESQ 题库导入管道（最常用）

真真题/模拟题进库统一走 ESQ 1.0 包：`manifest.json + papers/<year>.json + answers/<year>.json` → zip → 校验 → 上传 → 发布。详见 `references/esq-import-pipeline.md`（含完整格式、API 路径、常见坑）。

要点：
- **externalKey 必须纯 ASCII**（`gaokao.fb.2024.jia` 而非含"甲卷"）否则 valid=false
- 上传端点：`POST /api/question-banks/imports`（multipart, profile_id 字段），**不是** /upload
- 发布：`POST /api/question-banks/imports/{job_id}/publish`
- 完形用 `{{blank:N}}` 标记，选词填空用 unit `candidates`（每题 options 缺省时自动用 candidates）
- 导入前先 `python tools/validate_question_bank.py <pkg>.esq` 校验
- 老真题"没有参考性"→ 软删除（`UPDATE papers SET deleted_at` + 写 `trash_entries`，purge_after 30 天），不要硬删

### 2. 真题数据源（哪些能抓、哪些被墙）

见 `references/question-data-sources.md`。核心结论：
- ✅ 可用：GAOKAO-Bench/Updates（高考带答案）、wamich/english-exem-md（四六级 md）、ayaka-notes/201-english（考研一 LaTeX）、kajweb/dict（四六级/考研真题核心词）、kylebing/english-vocabulary（各级别词库）
- 🔒 被墙：zhenti.burningvocabulary.cn（登录+JS）、wehuster.com（Cloudflare）、163/6617（图片）、en-sky（网盘）、教习网（账号）
- ⚠️ 半可用：**新都网 edu.newdu.com 高考真题解析页**（如 `NECE/English/Analysis/202506/4668882.html`）——有**完整答案汇总 + 每题解析 + 文章主题概述**，但**缺题干/选项原文**（正文只有解析，2-4 页为空白分页），不能直接构建题目；可用来核对答案或给 AI 模拟题当参照
- ✅ **2025 高考真题官方图片（v2.94 已验证 33 题）**：**中国教育在线** `https://img.eol.cn/e_images/gk/2025/st/qg1/yy01.png`（全国一卷 8 页）+ `.../qg2/yy00.png`（全国二卷 9 页，yy00 是封面）——官方高清卷面图，tesseract 2x 放大 OCR 效果极好（阅读/听力选择题完整识别）。完整下载→OCR→解析→导入→AI 答案管道见 `references/gaokao2025-ocr-import.md`。**2025 并非全被锁——官方图直链可下，唯一路径就是 OCR**
- 2024-2026 真真题几乎无公开可抓源 → 用基元律动生成模拟题（包内标注"AI模拟·非真题"）
- **2026 全类别批量生成（v2.31 已验证 75 题）**：5 级别 × 3 题型 = 15 包 × 5 题，每包 1 次 AI 调用，prompt 模板 + 级别风格字典 + 断点续跑法见 `templates/ai-exam-generation-prompt.md`

### 3. AI 标注答案（基元律动）

模拟题答案或真题无答案时用 `/api/ai/chat`（profile_id=3, model=deepseek-v4-flash）：
- **必须重试**（基元律动经常 503/400 抖动）：`for attempt in range(3)` + sleep(8-10)
- 批量翻译一次 ≤30 词（更大 → 400）
- JSON 提取用 `json.JSONDecoder().raw_decode(content, content.find("{"))`——AI 常在 JSON 后加解释，普通 loads 会炸
- 后端必须在运行（ConnectionRefused 就是没启动 run_app.py）

### 3.1 多 AI Profile 接入（同一供应商多个 key，v2.32 实测）

刷题机 AI 配置在 `ai_profiles` 表（name/base_url/api_key_encrypted/enabled/is_default/default_model），DPAPI 加密存储。**同一供应商可加多个 key**：`POST /api/ai/profiles` 创建（body: name/base_url/api_key/enabled/is_default/default_model/temperature/max_tokens），key 自动 `protect_text` DPAPI 加密。例：第二个基元律动 key 命名「基元律动-dengzhen」，保持原 profile 为默认。

- 查询列表：`GET /api/ai/profiles`（返回 has_api_key 布尔，不泄露密文）
- **curl 发 JSON body 在 git-bash 会报 "There was an error parsing the body"**（引号/编码问题）→ 改用 Python `urllib.request` 发 `json.dumps(..., ensure_ascii=False).encode('utf-8')`，一次成功
- 连通性测试：`POST /api/ai/chat` body 带 `profile_id`（新 id）+ model + 短消息，看回复
- 字段注意：schema 是 `AiProfileWrite`（name/base_url/api_key/enabled/is_default/default_model/temperature/max_tokens/system_prompt）

**⚠️ 3 库同步（基元律动接入 v3.0 实测，2026-08-09）**：自定义 provider 设默认必须**同步更新 3 个库**，否则各端不一致（Windows 在线 / 开发 / APK 种子各一套）：

| 库 | 路径 | key 存储 |
|:---|:---|:---|
| 在线库 | `%APPDATA%\ai-english-practice-desktop\data\question_bank.db` | DPAPI（`protect_text`）|
| 开发库 | `backend/data/question_bank.db` | DPAPI |
| 种子库 | `frontend/public/question_bank.db` | **明文**（Android 无法解密 DPAPI——前端 `ai.ts` getApiKey 直接读 `api_key_encrypted` 当明文用）|

- **is_default 有部分唯一索引**：`UPDATE ai_profiles SET is_default=0` **先全部取消**，再设新 profile=1（顺序反了报 `UNIQUE constraint failed: ai_profiles.is_default`）
- `ai_profile_models` 表 INSERT OR IGNORE（`/api/ai/settings` 的 model 下拉来源）
- **⚠️ cap sync 复制的是 dist 不是 public**（v3.0 真踩）：改了 `frontend/public/question_bank.db` 后直接 `cap sync` → APK 里还是旧库（ai_profiles 空表）。**必须先 `npm run build`**（Vite 把 public 复制进 dist）再 cap sync。验证：`zipfile` 读 APK 内 `assets/public/question_bank.db` → sqlite 查 `ai_profiles WHERE is_default=1`（主库，忽略 `.full.bak` 旧备份）
- 在线端验证：重启应用 → `GET /api/ai/settings`（字段是 `model` 不是 `default_model`）→ `POST /api/ai/chat`（body 需 `profile_id` + `model`）端到端

### 4. 验证模式（每轮改动必做）

每轮改完写 ad-hoc 验证脚本（如 `C:\Users\31954\AppData\Local\Temp\hermes-verify-*.py`）：
- 断言源码探针 + 真实启动后端 + API 端到端（各级别 startup/today_plan）+ dist 产物检查
- 输出 `✅ 项` 列表 + `AD-HOC XXX V2.x (fresh) — N verified`
- 跑完 `rm` 脚本 + kill 后端 + 同步 mobile-app + git 提交推送（代理 `HTTPS_PROXY=http://127.0.0.1:7890`）
- **验证前先杀残留后端进程**：`netstat -ano | grep 8765` 若占用，用 `powershell Stop-Process -Id <pid> -Force`（git-bash 里 `taskkill //F` 会报无效参数）。旧进程不杀 = 新代码不生效 + 端口冲突假 422

### 5. 听力模块（unit_type=listening）

- ESQ 包用 `"type": "listening"`，25 题（Section A/B/C 结构，AI 生成），答案 AI 标注
- 听力练习页音频：后端 `get_session` payload 挂 `audio_url`（`_session_audio_url` helper 按 profile_id 匹配 4/6 级）
- 音频用 **B站播放器 iframe**：`https://player.bilibili.com/player.html?bvid=BVxxx&page=1&high_quality=1`（不是 mp3 直链）
- 前端 PracticeView：`audio_url.includes('bilibili')` → iframe；否则原生 `<audio>`

### 6. 词文串学（扇贝式真题语境）

- 后端 `GET /api/vocabulary/{entry_id}/context`：在 `units.passage` 全文搜词形（词根+后缀正则 `\b<lemma>(?:s|es|ed|ing|d|'s)?\b`），返回最多 6 条句子 + 来源（级别/年份/篇名）+ highlight
- 前端单词详情页"词文串学 · 真题语境"区块，`v-html` + `<mark>` 高亮
- 与"真题中的遇见"（occurrences，用户遇到的原句）互补——词文串学是**全局题库**检索

### 7. 分级背诵计划（墨墨/扇贝式词书）

- `backend/app/routers/vocab_plans.py`：WORD_BOOKS 定义（key/name/category pattern/target）+ `GET /api/vocabulary/plans`（每本进度）+ `GET /plans/{key}/daily`（今日任务 = 新词 20 + FSRS 到期复习）
- **路由顺序坑**：`vocab_plans` 必须在 `vocabulary` router 之前注册（`/plans` 会被 `/{entry_id}` 捕获返回 422）
- 词书 pattern 用 `"四级·高频%"` 精确匹配（`"四级%"` 会把基础词也算进去导致进度 >100%）
- daily 任务空时回退：`study_status='new'` 未学词 → 再回退任意词（**fallback SELECT 必须带 study_status 列**，否则 dict() 后 `w["study_status"]` KeyError）

### 8. 学习报告页（好题库/练题狗式数据叙事）

- `backend/app/routers/report.py`：`GET /api/report` 聚合 7 项——正确率趋势（近30天按天）+ 题型统计（by unit_type）+ 词汇进度 + 近7天活跃（learning_days）+ 错题概况（wrong_stats）+ 练习总量（practice_sessions）+ 智能建议（规则：薄弱题型正确率<60 / 词汇<100 / 连续活跃 / 高频错题）
- **v2.30 全级别维度**：`scope=all` 默认返回全部 5 个级别数据——`profiles`（级别列表）、`by_profile`（每级别 sessions/answered/rate/wrong 汇总）、`by_type`（全级别题型统计）、`by_type_current`（当前级别对照）、`active_profile`（当前级别 id/name）；建议逻辑升级为"全级别最弱题型 + 最弱级别"
- 前端 `ReportView.vue`：顶部大字号统计卡（CountUp）+ **「🗂️ 全部级别汇总」profile-grid**（5 级别卡片，当前级别高亮 `profile-active`）+ 正确率趋势柱状图（绿≥80/黄≥60/红<60 渐变条）+ 题型 SVG 雷达图 + 智能建议列表
- 导航两处都要加：侧栏 + 移动底部 `mobile-nav`（App.vue 两个 RouterLink + `BarChart3` import）；路由 `/report` 加在 router.ts
- **CountUp 是 script setup 默认导出**（`import CountUp from '../components/CountUp.vue'`，不是具名）

### 9. 竞品对标流程（每次功能扩展前先做）

扩展功能前先 web_search 竞品（扇贝/墨墨/刷刷题/练题狗/好题库）找它们核心功能，再落地。已落地映射：
- 扇贝词文串学 → 单词详情"真题语境"全局检索（见 §6）
- 墨墨分级词书 → vocab_plans 5 词书（见 §7）
- 扇贝听力真题音频 → B站 iframe 播放器（见 §5）
- 好题库/练题狗学习报告 → report.py（见 §8）
- 多邻国/百词斩成就徽章 → achievements.py 10 徽章（见 §10）
- 练题狗 AI 智能推题 → ai_recommend.py 薄弱分析（见 §11）
- 扇贝短文填词/选词填空 → vocab_cloze.py 真题句挖空（见 §13）
- 百词斩词汇量初测定位 → vocab_quiz.py 10 词三档估算（见 §14）
- 粉笔/错题plus 错题同类题强化 → WrongView ⚡同类强化按钮（见 §15）
- 打卡热力图（2026 打卡 App 标配）→ 报告页 heatmap 16 周（见 §16）
- 薄荷阅读/可栗 词汇-阅读联动 → 词文串学风格徽章（见 §17）
- 粉笔/考霸错题本 出卷打印 → 可打印错题卷 HTML（见 §18）
- 2026 数据可视化 UI 趋势（进度环/趋势线）→ 词汇掌握进度环 + 练习量趋势（见 §19）
- 多邻国 streak flame / 2026 micro-interaction 庆祝动效 → CelebrateOverlay 撒花+火焰（见 §21）
- 墨墨数据可视化周报 → 报告页本周战报 本周vs上周（见 §23）
- 猿题库考点归因/高频错题 → 错题本高频 TOP + 错因标签（见 §23）
- 百词斩闪卡速记 → 词汇复习点卡翻面+进度条（见 §23）
- 百词斩单词 PK → 单词快答挑战（见 §33）
- 粉笔考试报告 → 模拟考试等级评价+答题用时（见 §23）
- 2026 六类微动画（hover/确认/滚动/加载/导航/脉冲）→ 全局微交互收尾（见 §23）
- 粉笔"我的分析"错题个人笔记 → 高频错题每题 📝 笔记（见 §24）
- 2026 luxury/premium design（低饱和奢华·克制优雅·磨砂玻璃）→ 全站精致高级感打磨（见 §27）
- 专注清单/Forest 番茄钟 → 专注计时页（见 §28）
- Focus-To-Do 日历视图 → 学习日历页（见 §28）
- 番茄钟目标统计 → 目标中心页（见 §28）
- 薄荷阅读语境阅读 → 阅读训练页（见 §28）
- 可可英语听力精听 → 听力精听页（见 §28）
- 每日一句/名言卡片 → 首页今日金句卡（见 §40）
- 刷刷题五练习模式 / 模拟考试 / 错题本 / 记忆分级 → 均已实现

### 10. 成就徽章系统（多邻国/百词斩式游戏化激励）

- `backend/app/routers/achievements.py`：`user_achievements` 表（badge_key UNIQUE + earned_at + progress/target）+ 10 个徽章规则引擎
- `GET /api/achievements`：徽章列表 + 进度 + 是否已获得 + earned_count/total
- `POST /api/achievements/check`：检查并授予新徽章（学习行为后调用），返回 `new_badges`
- 徽章定义：`badge(key, name, icon, desc, check)` 注册，check 返回 `(current, target)`；规则全部基于 DB 聚合（practice_sessions / learning_days streak / vocabulary_entries / wrong_stats / exam_sessions / practice_unit_submissions）
- 前端 `AchievementsView.vue`：徽章网格（earned 金色边框+阴影 / locked 灰度降透明度）+ 进度条 + 顶部 earned_count 统计卡
- 导航：侧栏 + 移动底部 `mobile-nav`（Trophy icon）+ router `/achievements`

### 11. AI 智能推题（练题狗式薄弱分析）

- `backend/app/routers/ai_recommend.py`：`GET /api/recommendations/ai`，纯规则引擎（无外部 LLM，即时响应）
- 逻辑：① 正确率最低且练习 ≥2 次的题型 = 薄弱题型（rate<0.7）→ 从该题型未做过的题随机推荐 3 道；② 错 ≥2 次的高频错题 TOP3 待重做；③ 学习中/最新生词 3 个推送；④ 策略文本（薄弱/错题/生词/均衡建议）
- 前端首页「为你推荐」顶部 `ai-picks-card`：策略列表 + 快捷 chips（🎯强化薄弱题型 → `randomPractice(weak_type)` / 🔁重做错题 / 📖背生词 / ✍️模拟考试）
- 与 dashboard 的 `_build_recommendations`（规则推荐：继续练习/真题卷/高频错题/薄弱单元）互补——AI 推题是独立 API，首页 onMounted 并行加载

### 12. 虚拟全流程测试（回归资产）

`scripts/virtual_test_full.py` 固化 12 项虚拟用户闭环（首页→切级别→练习创建→答题提交→错题→词书→词文串学→模拟考试→报告→听力→热力图→倒计时）。每轮大改后跑一遍。测试中验证的真实产品特性：
- **429 限流是 120 次/60 秒 ≈ 2 次/秒**（⚠️ v2.32 实测修正：旧写法 `time.sleep(0.35)` 节流是错的——1000 轮 × 5 请求 ≈ 20 次/秒，6 秒后必触发 429）。**千轮/长压测试必须 2.5s/轮**（`scripts/virtual_test_1000.py` 已验证：每轮 3 请求：创建→详情→答 1 题+提交），429 时 `time.sleep(65)` 等窗口重置再 continue；`print(..., flush=True)` 防管道缓冲看不到进度
- **random 模式允许部分提交（v2.32 手动单测，⚠️ v2.32b 千轮实测修正）**：单测"只答 1 题提交 200"是因为碰巧选了只有 1 题的单元。**多题单元只答 1 题 → 409**（submit_session 检查 `practice_answers` 里所有题 `user_answer` 非空）。千轮脚本首版截断 `questions[:1]` → 98% 409。**正确做法：答全部题**（options 空的无选项题跳过，若提交仍缺会 409 计失败）
- **EPM_RATE_LIMIT 环境变量可调限流**（v2.34）：`security_middleware.py` 读 `EPM_RATE_LIMIT`（默认 120 次/分钟）。长压测前用 `EPM_RATE_LIMIT=5000 python run_app.py` 启动测试实例放开限流（0.2s/轮，1000 轮 6 分钟），测完恢复默认。**不改代码**，只改测试环境参数
- **400"没有符合条件的练习篇目" = 该级别无该题型**（如考研一无听力）——预期场景，千轮脚本计为跳过（skip_count）而非失败。v2.34 最终 1000/1000：850 成功 + 150 跳过 + 0 失败
- **409 防漏答**——paper/unit 级 `POST /sessions/{id}/units/{uid}/submit` 要求该单元全部题目作答，未答完报 `incomplete_submission`
- **random 模式只支持 session 级提交**——`POST /sessions/{id}/submit`；unit 级提交仅按年份练习（mode=paper）支持
- **练习 session options 结构是 `{stable_key, label, content}`**——答题参数用 `label`（不是 `key`），`stable_key` 是乱序前的原始答案键
- **长压测前先验证路由/API 再启动**：后端重启会中断长跑测试（正在进行的请求失败一次不致命，测试会继续），但 vocab_cloze 这类新路由若未挂载，测试白跑——先 curl 探活新 API 再开千轮
- **功能 API 压力测试**：`scripts/virtual_test_features.py`（短文填词/词汇量自测/热力图 各 100 次，v2.35）——req() 加 3 次指数退避重试 + 429 等 20s
- **⚠️ 测试脚本全同值 bug（v2.35 真踩）**：`{"known": i % 3}` 对**所有词**用同一个值——当 `i%3==0` 时 10 个词全 known=0 → estimated=0 → `assert est.get("estimated",0) > 0` 失败，且 AssertionError 无消息（`str(e)` 空 → 错误分布里是 `quiz:` 空 key，难以定位）。**循环内变量必须分散**：`{"known": (i + idx) % 3} for idx, w in enumerate(items)`

### 13. 短文填词（扇贝式真题挖空，v2.32）

- `backend/app/routers/vocab_cloze.py`：`GET /api/vocab/cloze?count=5`（router prefix=`/api/vocab/cloze`，main.py 用 `prefix=""` include）
- 数据源：目标词从 **`vocabulary_entries`**（study_status != 'mastered' 优先 new/learning，表名不是 vocabulary！）+ 真题句从 **`units.passage`**（按 `(?<=[.!?])\s+` 切句，找含目标词词形的句子，复用词文串学同款词根+后缀正则）
- 挖空：`\b<lemma>(?:s|es|ed|ing|d|'s)?\b` → `____`（**词形变化要一起挖**，不能只挖原形）；干扰项从同词性/长度相近的 entries 挑 3 个 + 兜底 `_____`
- 前端 VocabularyView：入口卡 `cloze-entry` + 弹层 `cloze-card`（逐题选项→判分→"再练一组"→巩固词列表）
- **挂载坑（v2.32 真踩）**：import 加进 main.py 但 `include_router` 漏加 → **请求返回 SPA 首页 HTML**（SPA fallback 捕获 /api/*）而不是 JSON。**诊断线索：API 返回 HTML = 路由没挂载**，先 grep main.py 有没有 `include_router`。**v2.33 又踩一次**（vocab_quiz 同款漏 include）——每次新增 router 后必须 curl 探活新端点（返回 `{...}` JSON 而非 `<!doctype html>`）再继续

### 14. 词汇量自测（百词斩式初测定位，v2.33）

- `backend/app/routers/vocab_quiz.py`：`GET /api/vocab/quiz?count=10`（抽样 10 词，已学/生词按 6:4）+ `POST /api/vocab/quiz/estimate`（三档 known 0/1/2 → 加权 ratio × BASE_VOCAB 估算 + level 分级）
- 数据源 `vocabulary_entries`，已学=study_status IN ('mastered','learning')
- 前端 VocabularyView：入口卡（与短文填词并列）+ 弹层三档按钮（😵不认识/🤔模糊/😎认识）→ 可先"显示释义"再判断 → 结果大数字 + 等级 chip + "再测一次"

### 15. 错题同类题强化（粉笔/错题plus式，v2.34）

- **纯前端实现，零后端改动**：WrongView.vue `strengthenScope(key, questionIds, title)`——从 `rows.value` 按 questionIds 过滤出该范围错题 → 按 `unit_type` 聚合 wrong_count 取最薄弱题型 → `POST /practice/sessions {mode:'random', unit_type: top, count:1}` 生成同类专项
- 年份组 + 篇目组各加一个 ⚡同类强化按钮（Zap icon），与"开始重做"并列
- **数据源坑**：`grouped` 里的 units 结构**没有 rows 字段**——不能 `units.flatMap(u => u.rows)`，必须用 `rows.value.filter(r => questionIds.includes(r.question_id))` 过滤全局错题行

### 16. 学习热力图（GitHub 风格打卡，v2.35）

- `backend/app/routers/report.py` 末尾加 `GET /api/report/heatmap`：从 `learning_days` 表按 `day >= start`（近 16×7 天）GROUP BY day 计数 → 生成 112 个 cell `{date, count, level}`（level=min(4, count/2)）→ 返回 `{weeks:16, cells, max_level, total}`
- 前端 `ReportView.vue`：onMounted 并行 `get('/report/heatmap')` → `heatmapWeeks()` 把 112 cells 切成 16 列 × 7 行（按周分组）→ CSS grid 色块（`.heat-cell` + `.heat-l0..l4` 竹青渐深）+ hover scale + 图例
- 注意：`learning_days` 只有真实用户活动才有数据（API 千轮测试不写该表——热力图可能显示少量活动，正常）
- 同轮 UI 增强：3D/Spatial 微交互（2026 spatial UI）——`stat-card`/`report-panel`/`practice-card` hover `translateY(-4px) rotateX(2deg) rotateY(-1deg)` + 深色模式 glass 适配（`:root.dark .stat-card` 渐变+边框降透明）

### 17. 词文串学风格化（薄荷阅读式风格徽章，v2.36）

- `backend/app/routers/vocab_context.py` 加 `_detect_style(text)`：规则式分类——interview（引号对话+said/says/told）、argument（research/study/according to）、news（percent/million/data）、story（叙事词）、默认 article。每条 context 带 `style` 字段
- **⚠️ 词边界匹配坑（v2.36 真踩）**：story 关键词用 `w in t` 子串匹配会误判（"concept" 含 "once" → article 变 story）。**必须 `re.search(r"\b" + re.escape(w) + r"\b", t)`**。其他风格词（research/percent 等）子串匹配风险低但同样的词边界更稳
- 前端 VocabularyView 词文串学区：`<span class="style-badge" :class="'style-'+c.style">` 显示风格徽章（🗣访谈/📊论述/📰新闻/📖故事/📄文章）+ 每风格配色（竹青/朱砂/月白蓝/秋香/墨灰）
- 实测：research 词 → 6 句里 5 argument + 1 article，分类合理

### 18. 可打印错题卷（粉笔/考霸式出卷，v2.37）

- `backend/app/routers/wrong.py` 加 `GET /export/html`：复用 export_wrong 的 SQL（wrong_stats JOIN questions/units/papers，按 wrong_count DESC），生成 A4 打印友好 HTML（`@media print` + 每题 `paper-ans` 答案行 + 解析区）→ `HTMLResponse`
- **⚠️ questions 表没有 analysis 列**（v2.37 真踩 `no such column: questions.analysis`）——解析存在 `questions.metadata` JSON 里（key 可能是 `analysis`/`explanation`/`解析`），用 `meta.get("analysis") or meta.get("explanation") or meta.get("解析")`
- 前端 WrongView：`exportWrongPaper()` 用 `fetch('/api/wrong/export/html')` 拿 HTML → Blob 下载 `.html`（浏览器打开 Ctrl+P 打印），📄 错题卷按钮与"导出错题"(Markdown) 并列
- **⚠️ import 合并坑**：`from html import escape as html_escape, HTTPException` 非法（HTTPException 属于 fastapi，不在 html）→ ImportError 启动失败。补 import 分两行写，加完 `python -m py_compile` 再启动

### 19. 词汇进度环 + 练习量趋势（2026 数据可视化，v2.38）

- `report.py` get_report 加 `answered_trend`：近 14 天每日答题数（`SELECT COUNT(*) FROM practice_answers WHERE substr(answered_at,1,10)=?`，**用 answered_at 不是 created_at**——practice_answers 无 created_at 列），返回 14 个 `{day, count}` 按日期升序，加进 return dict（**别忘了 return dict 也要加字段**）
- 前端 ReportView：词汇掌握卡改 **SVG 进度环**（`.vocab-ring`，stroke-dasharray=113 圆周长，`stroke-dashoffset: calc(113 - (var(--pct)/100)*113)`，`vocabPct = computed(round(learned/total*100))`）；报告面板加 **练习量趋势柱状图**（`.answered-bar` 高度按 `count / Math.max(...counts, 1)` 归一化，`answeredTrendMax` computed）
- **script setup 里新增 computed 必须 import**（`import { computed, onMounted, ref } from 'vue'`，漏 computed 会 ReferenceError）
- 验证：报告 API 返回 `answered_trend` 14 天升序；千轮测试写入后近 14 天总答题数巨大属正常

### 20. 推荐串台修复 + 新类别/排行模块（v2.39）

**⚠️ 推荐串台根因（v2.39 真踩）**：切换级别后推荐区显示别的级别内容（高中显示考研推荐、考研一显示高中）——后端 dashboard.py / `_build_recommendations` 全部按 `get_active_profile_id` 过滤正确，问题在 **`papers.profile_id` 与标题级别不匹配**（2026 AI 模拟题批量导入时把高中/考研一的 profile_id 映射写反，6 卷错位）。排查路径：后端过滤无误 → 直接查 DB 校验关联。

**校验 SQL（每次批量导入后必跑）**：
```sql
SELECT p.id, p.profile_id, qb.name, p.title FROM papers p
JOIN question_bank_profiles qb ON qb.id = p.profile_id
WHERE p.title LIKE '%AI模拟%' AND p.deleted_at IS NULL ORDER BY p.id;
-- 人工核对: 标题含'考研英语一' → qb.name 必须='考研英语一'，否则错位
```
修复：`UPDATE papers SET profile_id = <正确id> WHERE id IN (...)`。修复后切级别验证 /api/startup 推荐（高中→高考真题 / 考研一→考研真题，互不串台）。

- **新增类别**（研究生英语 v2.39）：直接 SQL INSERT `question_bank_profiles`（name/description/color/icon，is_default=0）→ 前端 QuestionBankSwitcher 自动出现（DB 驱动，`loadQuestionBankProfiles`）；papers 用 `package_id='cn.graduate.<year>.sim.<utype>'` + `source_metadata={"type":"ai"}` + 标题标注「（AI模拟）」；2025/2026 真真题被墙 → AI 模拟题明确标注「AI模拟·非真题」
- **学习排行模块**（leaderboard.py）：`GET /api/leaderboard`——本周答题/正确率/场次/新词 + 7 天柱状（`practice_answers.answered_at` 按天）+ streak（`SELECT DISTINCT day FROM learning_days` 从今天往前数连续）+ 段位（钻石/黄金/白银/青铜按本周答题量 300/150/60）；前端新 view + router + 侧栏/移动导航两处
- **今日目标 + 每日一词**（DashboardView）：目标存 localStorage（`epm_daily_goal`），今日答题数取 leaderboard.days 最后一项；每日一词按日期字符串 hash 从已加载词汇取固定种子（当天稳定，非随机）
- **水墨背景图**：Unsplash Cleveland 博物馆 PD 图用短 id 端点下载 `https://unsplash.com/photos/<short-id>/download?w=1920`（需 UA header）；新页背景挂 `page-leaderboard::before` 等 CSS（`.page-xxx::before` 固定 z-index:-2 + opacity，dark 模式降 opacity）
- **⚠️ main.py 挂载第三次踩坑**（leaderboard 漏 include_router）：import 加进 main.py 但 include 漏 → 请求返回 SPA 首页 HTML。**新增 router 后必须 curl 探活**（返回 `{...}` JSON 而非 `<!doctype html>`）再继续

### 21. 庆祝动效系统（多邻国式微交互，v2.40）

2026 趋势：micro-interaction 要 **short / tied to clear trigger / easy to skip**（多邻国 streak flame 打卡火焰 + milestone 庆祝 burst）。

- `frontend/src/components/CelebrateOverlay.vue`：Teleport to body + 24 粒子撒花（`.celebrate-particle` + `celebrate-fall` 动画，随机 left/delay/dur/color）+ 火焰（`flame-bounce` 弹跳）+ 墨滴扩散（`.celebrate-ink` 双层 ring）+ 庆祝卡（`card-pop` 弹出）+ 3.2s 自动 close + 点击关闭
- **PracticeView**：提交后 `maybeCelebrate()`——`rate = score/max_score*100`，≥80% 撒花（≥95% 显示「近乎满分！」）
- **DashboardView**：`maybeStreakCelebrate(streak)`——milestones [3,7,14,30,60,100] 取最大已达，**localStorage `epm_streak_celebrated_<n>` 防重复**（里程碑一次性），火焰 🔥 庆祝
- 组件 props：`show/kind('confetti'|'flame')/title/subtitle`，`@close` 事件；CSS 全部放 styles.css（含 dark 模式 overlay 背景）

### 22. 尺寸适配（slice 截断 + 横向滚动 + clamp 流式排版，v2.40.1）

**⚠️ 硬编码 slice 截断（v2.40.1 用户反馈"只能看到三个而且滑动不了"）**：模板里 `data.exam_countdown.slice(0, 3)` 只渲染前 3 个考试，且 `.exam-countdown-bar` 是 `flex-wrap: wrap`——wrap 不会横向滑动。修复：
- 前端 `v-for="ex in data.exam_countdown"`（去 slice）
- 容器改横向滚动：`flex-wrap: nowrap; overflow-x: auto; scrollbar-width: thin; -webkit-overflow-scrolling: touch` + `::-webkit-scrollbar { height: 4px }` 细滚动条 + `.countdown-item { flex-shrink: 0 }`（label 也 flex-shrink:0）
- 后端 `return out[:4]` 上限一并去掉（考试最多 4-5 个，保留全部）
- **排查习惯：用户报"只能看到 N 个"→ 先 grep `slice(0,` 硬编码截断；报"滑动不了"→ 查容器是否 `flex-wrap: wrap`（wrap 不是滚动，nowrap + overflow-x 才是）**

**2026 响应式最佳实践（clamp 流式排版）**：研究结论——容器查询 + 流式排版取代硬断点跳变。全站核心排版改 `clamp(min, vw 基准, max)`：
```css
body { font-size: clamp(14px, 0.8rem + 0.25vw, 16px); }
h1 { font-size: clamp(24px, 1.4rem + 1.4vw, 36px); }
.stat-value { font-size: clamp(24px, 1.45rem + 1vw, 34px); }
.study-hero { padding: clamp(26px, 3vw + 10px, 46px); }
.grid { gap: clamp(12px, 1vw + 6px, 18px); }
.card { padding: clamp(12px, 0.8vw + 8px, 18px); }
```
320px 手机到 2560px 宽屏平滑过渡，不依赖断点跳变。已有 @media 断点（1200/980/720/480）保留用于布局堆叠，字号/间距交给 clamp。

### 23. 五轮迭代收尾（v2.41-v2.45，每轮一功能+千轮回归）

每轮模式：web_search 竞品/2026 趋势 → 落地 1 功能（后端 API + 前端 + CSS）→ 构建 → 重启验证 → 千轮回归（约 6 分钟）→ git 提交推送。已完成：

**v2.41 周报对比（墨墨式数据亮点）**：`report.py` 加 `week_compare`——`_week_stats(ws, we)` 按 `substr(answered_at,1,10)` 区间统计本周/上周 `{answered, correct, rate, vocab}` + delta；`monday = today - timedelta(days=today.weekday())` 定周界；前端 ReportView 加「本周战报」4 格对比卡（↑/↓ 绿/红 delta，窄屏 2 列）

**v2.42 高频错题 TOP + 错因标签（猿题库考点归因）**：`wrong.py` 加 `GET /wrong/stats`——TOP10 按 `wrong_count DESC, last_wrong_at DESC`，**错因规则**：`recent_results` 末位 T 且 wrong_count≤1 → 已掌握 ✅；wrong_count≥3 → 反复出错 🔁；attempt_count≥3 → 易错点 ⚠️；否则偶尔失误 🌱。前端 WrongView 顶部 freq-card（TOP5 + 类型分布 chips），点击 `redoQuestion(questionId)` 用 `POST /practice/sessions {mode:'random', question_ids:[id], count:1}` 单题重做

**v2.43 闪卡增强（百词斩式）**：`flip-inner` 加 `@click="toggleReveal"`（点整卡翻面，评分按钮 `@click.stop` 防误触）+ 顶部 `review-progress` 进度条（`width = reviewIndex / reviewItems.length * 100%`）

**v2.44 考试报告等级 + 用时（粉笔式）**：`exam.py` `_result` 加 `level`（accuracy≥85 优秀 / ≥70 良好 / ≥55 合格 / 否则待加强）+ `used_minutes`（`_parse_dt(submitted_at) - _parse_dt(started_at)`，`datetime.fromisoformat(s.replace("Z","+00:00").replace(" ","T"))` 兼容两种分隔）+ `time_ratio`；前端结果卡加 `.exam-level` 徽章 + ⏱ 用时

**v2.45 全局微交互收尾（2026 六类微动画）**：研究结论——hover feedback（按钮 lift `translateY(-1.5px)`+shadow / 卡片 hover shadow）/ state confirmation / scroll reveal（`card-enter` 轻入动画）/ loading states（已有 skeleton）/ navigation transitions（侧栏 `translateX(2px)`）/ attention pulse（hero CTA `cta-pulse` 微光扩散）。**必须配 `@media (prefers-reduced-motion: reduce)` 关闭全部动效**（无障碍）

### 24. 我的分析笔记（粉笔式错题个人笔记，v2.46）

粉笔竞品分析明确建议"解析页加我的分析（个人笔记）"。落地在**高频错题 TOP 卡**每题：

- **DB**：`ALTER TABLE wrong_stats ADD COLUMN note TEXT DEFAULT ''`（wrong_stats **无 id 列，PK=question_id**；先 PRAGMA table_info 确认再 ALTER）
- **后端** `wrong.py` 加 `PUT /wrong/{question_id}/note`——**接口参数直接 `body: dict` 即可**（`body.get("note") or ""` 截断 500 字），不用 Pydantic model；upsert 用 `INSERT ... ON CONFLICT(question_id) DO UPDATE SET note = excluded.note`（注意 wrong_count/recent_results 是 NOT NULL，INSERT 要带默认值）
- **stats SQL 加 `ws.note`** 并在 items 返回 `"note": r["note"] or ""`（空串兜底，否则 None 渲染）
- **前端 WrongView**：freq-item 内加 📝 按钮 `toggleNote(item)`（打开 `noteEditing === item.id` 的 inline textarea + `noteDraft`）→ `saveNote(item)` 用 `put('/wrong/{id}/note', {note})`（**api.ts import 要加 put**）→ 保存后 `item.note = r.note` 原地更新 + showToast
- **⚠️ 整卡 @click 容器内嵌按钮必须 `@click.stop`**（freq-item 整卡 `@click="redoQuestion"` 会跳重做，📝 笔记按钮/编辑器/保存取消全部要 stop，否则点笔记就跳走了）
- 验证：保存→重读 stats 确认 note 持久化→清理测试笔记（PUT 空串）→千轮回归

### 25. 类别弹窗选择器（v2.47，用户反馈"考试类别看不清楚"）

**用户 UI 偏好：类别切换要"大而清晰"**——侧边栏挤 6 个类别按钮太小看不清。改为：

- **侧边栏左下角只保留**：当前类别（高亮，点击也可打开弹窗）+ **常用类别 top2**（localStorage `epm_category_usage` 使用计数降序，`frequentCategories` computed 取除当前外的 top2）+「全部类别」入口（渐变圆点 + LayoutGrid 图标）
- `recordCategoryUsage(id)` 在 `switchCategory` 里 `usage[id] = (usage[id]||0)+1` 计数 → 越常用越靠前
- **弹窗**：Teleport + Transition modal-fade + `.category-modal`（fixed inset-0 + blur 遮罩，点遮罩关闭）→ `.category-modal-panel`（min(720px,94vw) 居中卡片）→ `.category-modal-grid`（`repeat(auto-fill, minmax(190px,1fr))` 大卡片网格：颜色图标块 + 名称 + 描述 + 「当前使用 ✓」徽章 + 底部 4px 色条）
- `pickCategory(cat)`：关闭弹窗 + 若不同则 switchCategory；`activeCategory = computed(categories.find(id === activeCategoryId))`
- **排查习惯：用户报"类别/模块看不清楚"→ 先看侧边栏/列表是否 v-for 全部项目挤在一起，改成"常用 + 弹窗全量选择"**

### 26. 验证补充（v2.47 实测）

- **browser_navigate 拦截 localhost**（`Blocked: URL targets a private or internal address` 是浏览器安全策略，非临时故障）→ UI 变更**无法用浏览器点选验证**，用 hermes-verify 脚本三重核对替代：源码探针（断言模板/逻辑字符串）+ dist 产物检查（minified JS 含 UI 文案）+ 后端 API 实测。UI 文案断言用**字符串字面量**（"选择考试类别"/"全部类别"），不要断言函数名（minifier 会改名）
- **bash 内嵌 python 的 f-string 嵌套引号**：`f"{x[\"type\"]}"` 在 git-bash 单引号 heredoc 里 SyntaxError（f-string unmatched '['）→ 用 `'...'.format()` 或先 `t = x['type']` 再 `f'{t}'`
- **压缩 dist 断言必须兼容无空格/转义（v3.4 真踩，两次误报）**：Vite 压缩后的 CSS/JS 无空格（`left: 12px` → `left:12px`）、字符串可能转义（`models/sync` 模板字符串在压缩后正则匹配不到）。**验证 dist 时用压缩后形态断言**（无空格版本）或先 `python -c "import glob; c=open(glob.glob('dist/assets/*.css')[0]).read(); print('position:fixed' in c)"` 探真实形态再写断言；CSS 用 `position:fixed`/`left:12px`，JS 用宽正则 `re.search(r'models.{0,5}sync', c)`。源码断言用完整形态、dist 断言用压缩形态——**同一断言的两套字符串**

### 27. 精致高级感打磨（2026 luxury/premium design，v2.48）

研究结论：2026 高级感设计 = **低饱和奢华配色（refined palette）** + **bold typography（字距/层级）** + **克制优雅（understated elegance：多层柔和阴影、1px 内高光）** + **progressive blur（磨砂玻璃）**。纯 CSS 打磨，不动结构，低风险渐进。

落地（全在 styles.css 追加）：
- ① **多层阴影体系（高级感核心）**：`--shadow-sm/--shadow/--shadow-hover/--shadow-lift` 改 ambient+key 双层（`0 1px 2px rgba(46,42,35,.04), 0 18px 44px rgba(46,42,35,.08), 0 1px 0 rgba(255,255,255,.5) inset`），hover 更高一层
- ② **排版字距**：h1-h3 `letter-spacing:.02em`；`.page-head h1` `.05em` + `font-weight:900`；`.eyebrow` `.22em`；`.stat-label` `.06em`
- ③ **卡片内高光**：`.card::before` 顶部 1px 白色渐变线（`top:0; left:12px; right:12px`）——**⚠️ 不能用全局 `.card{overflow:hidden}`（会裁剪下拉菜单/弹层）**，用 `.card > * { position:relative; z-index:1 }` 保证内容在高光线上层
- ④ **按钮墨色渐变**：`.button:not(.secondary):not(.ghost):not(.danger)` `linear-gradient(180deg, color-mix(in srgb, var(--primary) 94%, #ffffff), var(--primary))` + `0 1px 0 rgba(255,255,255,.06) inset` 内高光
- ⑤ **数字衬线**：`.stat-value/.big-score/.wr-value/.rank-num/.countdown-item b` 用 Georgia 衬线（数据权威感）
- ⑥ **输入框 focus 光晕**：`box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent) 12%, transparent)`
- ⑦ **精致滚动条**：`::-webkit-scrollbar{width:8px}` + thumb `border:2px solid transparent; background-clip: content-box`（圆点式悬浮）
- ⑧ **磨砂侧边栏（progressive blur）**：`@supports (backdrop-filter: blur(12px))` 内 `.app-sidebar/.mobile-nav { backdrop-filter: blur(14px) saturate(1.15) }`（桌面端生效，不支持时 fallback 正常）
- ⑨ 徽章/标签 `backdrop-filter: blur(4px)` + 半透明边框；动效全部受 `prefers-reduced-motion` 保护（沿用 v2.45）

验证：CSS 探针断言**关键片段字符串**（`--shadow-lift`、`.card::before` 定位片段、`backdrop-filter`、Georgia 声明），不要断言完整值（minifier/后续改动会变）。千轮回归确认零功能回归（纯 CSS 不改逻辑）。

### 28. 五新模块（专注/日历/目标/阅读/听力，v2.49，用户要求"导航加5个新选项"）

2026 趋势研究：番茄钟/专注（专注清单、Forest）、日历视图（Focus-To-Do）、目标统计、语境阅读（薄荷阅读）、听力精听（可可英语）。每模块 = 后端 router（如需要）+ View + router.ts 路由 + App.vue **侧栏/移动导航两处** + styles.css。导航已 17 项。

- **⏱ FocusView（专注计时）**：纯前端番茄钟——MODES（25 专注/5 短休/15 长休）、SVG 环形倒计时（`stroke-dasharray` 用圆周长、`stroke-dashoffset: calc(周长 * (1 - var(--pct)/100))`）、`setInterval` 每秒倒计时、完成后 `recordDone()` 写 localStorage `epm_focus_stats`（`{日期: {pomodoros, minutes}}`）并自动切休息模式
- **📅 CalendarView（学习日历）**：后端新 router `calendar.py` + `GET /api/calendar?year=&month=`——**⚠️ `learning_days` 表没有 count 列**（每行一条记录，schema 只有 id/day/activity_type/detail/created_at），`SUM(count)` 会 500 → 必须 `COUNT(*)` + `GROUP BY day, activity_type`；前端按月热力格（7 列 grid + `firstWeekday()` 空位 + `daysInMonth()` + 4 级色阶 `.cal-cell.heat-l1..l4` + 今日高亮 + 类型分布 chips）
- **🎯 GoalView（目标中心）**：复用首页目标逻辑独立成页——进度环（`goalPct = todayAnswered / dailyGoal`）+ 快捷设定 + 自定义输入 + 近 14 天达成柱状（`history` 数组 + 绿/金柱区分达标）
- **📖 ReadingView（阅读训练）**：直接 `GET /library/units?unit_type=reading&limit=6`（**v2.77 修正：原 `GET /vocab/context?limit=6` 路由不存在，会返回 SPA fallback HTML → 前端 `SyntaxError: Unexpected token '<'` JSON 解析失败**——§35 虽已记录该路由缺失，但 ReadingView 首版代码仍留了这条调用直到 v2.77 才清掉）；数据源要 `Array.isArray(r) ? r : r?.items || []` 归一化；卡片点击跳练习
- **🎧 ListeningView（听力精听）**：`GET /library/units?unit_type=listening&limit=20` 聚合听力单元卡片
- **⚠️ main.py 挂载第四次踩坑（calendar）**：import 加进 main.py 但 `include_router(calendar.router, prefix="")` 又漏 → 请求返回非 JSON（SPA HTML 或 JSONDecodeError）。**新增 router 后第一件事 curl 探活**（`curl http://127.0.0.1:8765/api/<new>` 返回 `{...}` JSON 再继续）——v2.32/v2.33/v2.39/v2.49 已踩 4 次，写进流程而非记忆
- 前端新 View 必须同步 4 处：`frontend/src/views/<Name>View.vue` + `router.ts`（import + route）+ `App.vue`（侧栏 RouterLink + 移动端 mobile-nav + lucide icon import）+ `styles.css`（`page-<name>` 主题色变量 + 组件样式）

### 29. 类别弹窗选择器补充（v2.47 验证细节）

（见 §25）验证补充已记录在 §26；browser_navigate 拦截 localhost 时用源码探针 + dist 字符串断言 + API 实测三重核对。

### 30. 十轮高级感打磨（v2.50-v2.59，用户要求"重复N轮打磨"）

用户模式：做完一轮"精致高级感"后说"这个任务进行重复十次"——**把同一打磨任务拆成 N 轮，每轮一个聚焦主题**，全部纯 CSS 追加（不碰模板/后端/结构），最后统一千轮回归。每轮独立 commit 可追溯回滚。

**工作流**：
1. todo 规划 N 轮主题清单（10 项 in_progress 依次推进）
2. 每轮：web_search（如"morandi color palette 2026"）→ styles.css 末尾追加一段（`/* ═══ v2.xx: 主题 ═══ */` 头注释）→ `npm run build` → git commit/push（代理 HTTPS_PROXY=http://127.0.0.1:7890）
3. 最后一轮：千轮回归（EPM_RATE_LIMIT=5000 启动 → virtual_test_1000.py）→ 恢复默认后端 → mobile-app 同步 → 综合 hermes-verify（断言每轮关键 CSS 片段 + dist 产物 + 千轮会话数 >6000）

**十轮主题 + 关键技术**（2026 luxury/morandi 趋势）：
- v2.50 莫兰迪色系调和：辅助色降饱和灰调（朱砂 #c73e3a→#bf6a5c、竹青 #5c7a52→#7d9273、秋香 #a8842f→#ab945f、danger→#a4574f）+ 背景柔化（--bg #f8f5ef）+ 新增 `--morandi-*` 变量（雾蓝 #a2b4c0 / 鼠尾草绿 #a3b5a6 / 藕粉 #d4b5b0 / 奶油黄 #c8b8a0 / 雾灰 #b8b8b0）。研究结论：莫兰迪 = 低饱和/偏灰阶/减法美学，全屋不过三色系
- v2.51 排版：行高体系（body 1.65 / h 1.3 / p 1.7）+ 数字单位区分（`.stat-value small { font-size:.5em }`）+ blockquote italic
- v2.52 阴影：三层体系（0 1px 2px + 0 8px 20px + 0 22px 48px）+ 悬停主题色微光（`box-shadow: var(--shadow-hover), 0 0 0 1px color-mix(in srgb, var(--accent) 6%, transparent)`）+ 浮层深影
- v2.53 容器：纸感渐变背景（多层 linear-gradient padding-box）+ **分区主题色条**（`.report-panel, .today-plan-card { border-left: 3px solid color-mix(in srgb, var(--accent) 55%, transparent) }`、`.stat-card { border-top: 2px solid ... }`）——给卡片加"身份感"的高性价比手法
- v2.54 按钮：主按钮高光渐变 + 内外 inset 阴影（`0 -1px 0 rgba(0,0,0,.06) inset` 底部压暗 + `0 1px 0 rgba(255,255,255,.08) inset` 顶部高光）
- v2.55 可视化：环形 `stroke-width: 6` 细描边 + 柱状渐变圆角 99px + 进度条光泽（`box-shadow: 0 1px 3px rgba(0,0,0,.12), 0 0 8px color-mix(in srgb, var(--gold) 40%, transparent)`）+ 热力色阶改柔和朱砂
- v2.56 Hero：渐变叠底（`linear-gradient(120deg, color-mix(in srgb, var(--surface-solid) 78%, transparent) 35%, transparent 75%), url(...)`）+ `backdrop-filter: blur(2px)` + 品牌印章光影（`.brand-mark` box-shadow）
- v2.57 侧边栏：激活渐变 + 左侧朱砂条（`box-shadow: inset 3px 0 0 var(--accent)`）+ 分组标签 `letter-spacing: .2em`
- v2.58 动效：路由淡入 `page-fade`（6px 位移 ≤.35s）+ 数字等宽 `font-variant-numeric: tabular-nums` + 模态回弹 `modal-in`（`scale(.96) translateY(8px)` + ease-bounce）——**克制原则：位移 ≤6px、时长 ≤.35s、hover 位移 ≤2px**
- v2.59 细节：`::selection` 品牌色 + 空态优雅（图片 `filter: sepia(.18) saturate(.8) opacity(.85)`）+ 徽章统一 99px 圆角 + `:focus-visible` 品牌化光晕

**注意**：
- 纯 CSS 打磨 = 零功能风险（只追加 styles.css），但千轮回归仍是最终保险（10 轮后统一跑一次）
- 验证脚本断言 CSS **关键片段**（如 `--morandi-blue: #a2b4c0`、`0 22px 48px`、`tabular-nums`），不要断言完整值/函数名
- ⚠️ `.card { overflow: hidden }` 全局禁用（见 §27）——十轮打磨里多次涉及卡片，始终用 `.card > * { position: relative; z-index: 1 }` 保证内容层

### 31. 新组件窄屏适配 + 滚动修复（v2.60-v2.61，用户反馈\"无法下滑/左侧要滑动\"）

**⚠️ 新组件必须补窄屏断点（v2.60）**：每轮新增 view 只写了桌面样式，720/480 断点缺失 → 手机上布局挤爆。一次性补齐模式（styles.css 追加两个 @media 块）：
```css
@media (max-width: 720px) {
  .focus-ring { width: 170px; height: 170px; }          /* 专注环形缩小 */
  .focus-modes { flex-wrap: wrap; justify-content: center; }
  .cal-cell { font-size: 10px; border-radius: 6px; }    /* 日历格子紧凑 */
  .goal-hero { flex-direction: column; align-items: center; }  /* 目标堆叠 */
  .category-modal-grid { grid-template-columns: 1fr; }   /* 弹窗单列 */
  .freq-grid { grid-template-columns: 1fr; }             /* 错题TOP单列 */
  .reading-grid, .listening-grid { grid-template-columns: 1fr; }
  .home-goal-row { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .cal-cell { aspect-ratio: auto; height: 30px; }        /* 超窄日历 */
  .focus-controls { width: 100%; } .focus-controls .button { flex: 1; }
  .category-modal-head { flex-direction: column; }
}
```
规律：**grid 多列 → 1fr；flex 横排 → column/换行；固定尺寸 → 缩小或 auto**。新 view 写完立刻补这两个断点，别等用户反馈。

**⚠️ sidebar sticky+100vh 无 overflow-y 会裁剪导航（v2.61 用户反馈\"左侧增加一个小滑动\"）**：17 个导航项 + 类别区 + 笔记区超出屏幕高度后被裁剪、无法滚动。修复（Flavio Copes 标准模式，搜索引擎确认）：
```css
.sidebar { overflow-y: auto; overflow-x: hidden; scrollbar-width: thin;
  scrollbar-color: color-mix(in srgb, var(--line-strong) 55%, transparent) transparent; }
.sidebar nav, .sidebar .brand, .sidebar .sidebar-categories, .sidebar .sidebar-note,
.sidebar .theme-button, .sidebar .vertical-text { flex-shrink: 0; }  /* 子块防压缩 */
```
- **⚠️ 主内容下滑受限（v2.61 同轮）**：长页面（首页 7 区块）滚动到尾部被截断 → `.app-shell > .main-content { min-height: 100vh; overflow: visible; padding-bottom: 56px; }` + `html, body { overflow-x: hidden; overflow-y: auto; }`。另外页面淡入动画 `animation-fill-mode: both` 保守改 `backwards`（彻底排除 fill 影响滚动的可能）。
- **侧边栏滚动条精修（v2.63 用户"左侧导航加一个小滚动条"）**：v2.61 的 5px 滚动条太透明看不到 → 改成**始终可见的精致细条**：`width: 6px` + `::-webkit-scrollbar-track`（淡色圆角轨道，`margin: 6px 0`）+ thumb `border: 1.5px solid transparent; background-clip: content-box`（悬浮感）+ `:hover` 变主题色（朱砂 `color-mix(in srgb, var(--accent) 65%, transparent)`）。用户说"加滚动条"= 现在看不到滚动条，不是没有滚动能力
- **排查习惯：用户报"页面滑不到底/看不到下面的功能"→ 先查 main-content 是否 min-height + padding-bottom；报"侧边栏看不到后面的项"→ 查 .sidebar 是否 overflow-y: auto；报"加一个小滚动条"→ 滚动条存在但不可见（透明度/宽度），做可见细条而非重写滚动逻辑**

### 32. Hero 名人名言替换（v2.62，用户要求"改成一句名人名言，运用搜索引擎解决"）

**用户模式**：UI 文案（尤其首页 Hero）要换成有质感的语录时，先 web_search 找**中英对照**来源（China Daily 经典名言集锦 / 英文库 50 个名言佳句），再选与产品定位契合的一句。

- **v2.62 选择**：Franklin `"Tell me and I forget. Teach me and I remember. Involve me and I learn."`（告诉我/教给我/让我参与——与"刷题练习"主题绝配）→ 替换 DashboardView hero 的"今天想练些什么？/选一篇文章"文案 → 中文译 + 作者署名放 `.lead`
- **英文长文案适配**：hero h1 换 Georgia 衬线 + `font-size: clamp(19px, 1.5vw + 12px, 27px)` + `line-height: 1.45` + `max-width: 620px`（防撑破）+ 720px 断点降 17px；中文译在 `.lead` 字号 13.5px
- 验证：源码断言名言字面量 + 旧文案 `not in`（**断言"已替换"用负向断言确认旧文案移除**）+ dist minified JS 含名言文案（中文+英文都在）

### 33. 单词快答挑战（百词斩 PK 式限时游戏化，v2.64）

百词斩单词 PK 的本地简化版——**纯前端，零后端改动**（复用 `GET /api/vocab/quiz?count=10` 数据源，filter `w.meaning` 确保有释义）。

- **玩法**：10 题限时 4 选 1（看单词选正确释义），**每题 10 秒**；超时 `quickAnswer('')` 自动判错；选完 `setTimeout 650ms` 自动下一题
- **状态机**：`quickMode/quickItems/quickIndex/quickScore/quickRemain/quickOptions/quickPicked/quickDone`；`quickPicked !== null` 防重复作答；`buildQuickOptions()` 用 `[...new Set([cur.meaning, ...others])].slice(0,4)` + 不足补"以上都不是"再 shuffle
- **计分**：对题 +1；结束算 best 存 localStorage `epm_quick_best`；评级 `quickLevel`：≥90% 词汇大师 🏆 / ≥70% 掌握扎实 🥇 / ≥50% 继续加油 🥈 / 否则需要复习 📚
- **计时器**：`setInterval` 每秒减 `quickRemain`，≤0 调 quickAnswer('')；`quick-timer.low`（≤3s）变红闪烁 `timer-blink`；退出 `closeQuick()` 必须 clearInterval
- **UI**：入口卡 `.cloze-entry.quick-entry`（显示"最佳 X/10"）+ Teleport 弹层 `.quick-overlay/.quick-panel`（进度条 + 顶部计时 + 选项对错态 `.quick-option.correct/.wrong/.picked` + 结果卡 `.quick-result` 图标 pop 动画 + "再来一局"直接 `startQuick()` 重开）
- **⚠️ 模板里用 `quickCurrent` 必须定义 computed**（`quickItems.value[quickIndex.value]`），漏定义模板报 undefined 静默渲染空
- 验证：vocab/quiz API 数据源探活（≥4 词全含 meaning）+ 源码断言（startQuick/quickAnswer/quickLevel/quickCurrent/epm_quick_best）+ dist 含"快答挑战"/"QUICK CHALLENGE"文案 + 千轮回归

### 34. 第二轮十轮高级感打磨（v2.65-v2.74，用户再次要求"重复十轮"）

§30 的模式可**换主题集复用**：同一"十轮打磨"请求，第二轮换一批主题（不再重复莫兰迪/阴影）。工作流不变（todo 规划 10 轮 → 每轮 styles.css 追加一段 + build + commit/push → 最后一轮统一千轮回归 + 综合 hermes-verify）。十轮主题 + 关键技术：

- v2.65 **字体系统（书卷气）**：中文换宋体系 `font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", "SimSun", "STSong", "Times New Roman", Georgia, serif` + `-webkit-font-smoothing: antialiased`；**分层策略**——h1-h3 宋体书卷气，数据/数字 Georgia 衬线，`.eyebrow/.button/.stat-label` 小标签保持无衬线（可读性）
- v2.66 **色彩分层**：强调色柔和底统一（`.ai-picks-badge/.reading-badge` `background: color-mix(in srgb, currentColor 11%, transparent)` + 圆角 8px）+ 分区背景微差（`.recommend-paper/.practice-card` `surface 62%`）+ 分隔线更淡（`border-bottom-color: color-mix(in srgb, var(--line) 45%, transparent)`）
- v2.67 **首页逐项**：`.today-plan-item` 行 hover 边框 + 完成态柔和绿（`success 8%` 底 + `22%` 边框）；`.countdown-item` hover 底；`.ai-pick-chip` hover `translateY(-2px)` + shadow-lift
- v2.68 **词汇页**：`.cloze-entry` 圆角 16 + hover 悬浮；`.due-chip` hover `translateY(-2px)` + 金色边框；`.vocab-ring` 光影 box-shadow
- v2.69 **错题本**：`.freq-rank` 改成 24px 圆角徽章（`grid place-items:center` + 朱砂 12% 底）；年份/篇目行统一圆角；分析条 `border-radius: 99px`
- v2.70 **报告页**：`.week-report-item` 圆角 13；`.heat-cell` 圆角 3；`.vocab-ring:hover` 光晕加深
- v2.71 **导航/弹窗**：弹窗统一圆角 22（`.category-modal-panel/.quick-panel/.review-card`）；品牌 `.brand-copy strong` `letter-spacing:.08em`；移动端 `.mobile-nav a` 激活 `accent 10%` 底
- v2.72 **练习页**：`.option-button/.cloze-option` hover `translateX(3px)` + 主题色边框；`.passage-pane` `line-height: 1.9`（书卷排版）；`.unit-tabs button` 胶囊 99px
- v2.73 **深色模式**：`:root.dark` 阴影体系整体加深（`rgba(0,0,0,.3)` 层）+ `.card` 暗渐变（`color-mix(in srgb, #ffffff 5%, transparent)` 顶高光）+ 按钮亮化（`--primary 82% + #ffffff 6%`）+ `.freq-note-view/.freq-note-editor` 暗色底——**深色不是只改 --bg，阴影/卡片渐变/按钮/笔记都要配套**
- v2.74 **收尾整合**：`:root` 圆角体系变量统一（sm 11 / md 15 / lg 21 / xl 29）+ 全局 `*::-webkit-scrollbar` 7px + 空态 `padding: 48px 20px !important` + `.page { padding-bottom: 40px }` + 印章 `.hero-seal` 光影

**注意**：
- 重复"十轮打磨"请求 = 复用 §30 工作流 + **换主题集**（字体/逐页/深色/收尾这类没做过的维度）
- 每轮 commit message 带 `(N/10)` 序号，最后综合验证断言每轮关键片段
- git push 偶发 `TLS connect error: error:0A000126:SSL routines::unexpected eof`（代理抖动）→ **等 3s 重试一次即可**（v2.68 真踩，重试成功，不是配置问题）

### 35. 500/接口错误修复（v2.75，用户报"Error: 500 Internal Server Error"）

**⚠️ 新前端模块调用的后端路由不存在（v2.75 真踩）**：v2.49 加阅读训练/听力精听页时前端写了 `GET /library/units?unit_type=reading` 和 `GET /vocab/context?limit=6`，但**后端从未实现这两个路由**（vocab_context.py 实际只有 `/{entry_id}/context`）→ 请求被 SPA fallback 捕获返回**首页 HTML** → 前端 `get()` JSON 解析失败 → 页面报错。

**诊断流程（500/接口错误排查顺序）**：
1. 查后端进程日志（`process action=log`）确认 500 是否在当前实例
2. 主动 curl/urllib 测**所有高频接口**（GET + POST 都要）——`/api/library/units` 返回 `<!doctype html>` = **路由不存在被 SPA fallback 吃掉**（不是 500 也是致命：前端 JSON.parse 炸）
3. 修复：`backend/app/routers/<name>.py` 新建 router + `main.py` **import 和 include_router 两处都要加**（v2.32/v2.33/v2.39/v2.49/v2.75 已踩 5 次，见 §13）→ 重启 → **curl 探活返回 `{...}` JSON 再继续**
4. 422 ≠ bug：如考试 `POST /exam/start` `count:3` 422 是 Pydantic `ge=5` 参数校验，前端/测试传合法值即可（先看 `class ExamStart(BaseModel)` 字段约束再报错）

**新模块完整清单（每次加模块对照）**：前端 View + router.ts（import+route）+ App.vue（侧栏+移动 nav+icon import）+ styles.css + **后端路由（如果前端调新 API）** + **720/480 窄屏断点**（§31）+ curl 探活新端点。前端调用的每个 API 路径都要 grep 后端确认存在。

**新增 library.py 参考**（units 查询模式）：`GET /api/library/units?unit_type=&limit=`——JOIN units+papers 过滤 `papers.status='published' AND papers.deleted_at IS NULL AND units.passage != ''`，返回 `{items:[{unit_id,title,passage:600,excerpt:200,year,paper_title,profile_id}], count}`；ReadingView 用 `Array.isArray(r) ? r : r?.items || []` 归一化。

### 36. FSRS 记忆调度 500（v2.75 第二波，用户\"有些模块有500\"）

**⚠️ 词汇复习评分 500 根因（v2.75 真踩，全站最隐蔽的 500）**：`POST /api/vocabulary/{entry_id}/review` 对某些词返回 500，日志：
```
ValueError: Unknown card state: 0
fsrs_scheduler.py:55 review_card → fsrs/scheduler.py:500 review_card → raise ValueError
```
**fsrs Python 库的 State 枚举从 1 开始**（1=New / 2=Learning / 3=Review / 4=Relearning），而 `vocabulary_entries.fsrs_state` 大量旧数据是 **0**（建表 DEFAULT 0 或从未初始化）→ 用户点\"认识/模糊/不认识\"评分时 `_scheduler.review_card` 抛异常 → 500。v2.75 实测修复 **7,965 条**非法数据。

**修复（双保险）**：
1. **数据修复**：`UPDATE vocabulary_entries SET fsrs_state = 1 WHERE fsrs_state = 0 OR fsrs_state IS NULL`（全部归为 New）
2. **适配层防御**（fsrs_scheduler.review_card 入口，防今后任何旧/新数据再炸）：
```python
from fsrs import Card, Rating, Scheduler, State
# 在 _scheduler.review_card(card, rating) 之前:
try:
    if card.state is None or int(card.state) not in (1, 2, 3, 4):
        card.state = State.New
except Exception:
    card.state = State.New
```
验证：`for rating in ['again','hard','mastered']` 逐一 POST review 全 200；DB 查 `fsrs_state = 0 OR IS NULL` 计数为 0；25 接口全面回归零 500。

**500 诊断完整流程（用户报\"有些模块 500\"时）**：
1. `process action=log` 看当前实例是否有 500 traceback（**500 一定在日志里留栈**）
2. 提取前端全部 API 调用逐一测：`grep -rhoE "(get|post|put|del)\\('[^']+'" frontend/src/views/ frontend/src/components/ | sed "s/^[a-z]*('//;s/'$//" | grep -oE "^/[a-z0-9/_-]+" | sort -u` → GET 全测一遍（**GET 基本不会 500，问题常在 POST**）
3. **POST/PUT 才是 500 重灾区**（GET 全 200 ≠ 无 500）：创建练习→作答→提交、考试 start→answer→submit、词汇 review、错题 note 全链路测
4. 区分非 bug 状态码：**409** = incomplete_submission（业务逻辑，未答完）；**422** = Pydantic 参数校验（如 exam `count:3` 但 `ge=5`，先看 `class ExamStart(BaseModel)` 字段约束）；**405** = 方法不对（`POST /api/exam/sessions` 不存在，正确是 `/exam/start`）；**HTML 200** = 路由未挂载被 SPA fallback（§13/§35）

### 37. 滚动/点动切换修复（v2.76，用户反馈\"上下滑动和点动切换有些问题\"）\n\n**⚠️ 路由切换后停留旧滚动位置（v2.76 真踩，\"点动切换\"问题主因）**：createRouter 没配 `scrollBehavior` → 从首页长页面滚到中间，点导航切到错题本/报告等，**新页面停留在相同滚动位置**（看起来\"切换后位置不对\"）。修复：\n```ts\n// router.ts — createRouter 里 routes 之前\nscrollBehavior() {\n  return { top: 0 }\n},\n```\n\n**⚠️ 弹窗打开时背景还能滑（滑动穿透混乱）**：category-modal / quick-overlay / review-overlay / plan-drawer / result-dialog 都是 fixed overlay，但 body 仍可滚动。修复（现代浏览器 `:has()`，一行搞定无需 JS watch）：\n```css\nbody:has(.category-modal), body:has(.quick-overlay), body:has(.review-overlay),\nbody:has(.plan-drawer-panel), body:has(.result-dialog) { overflow: hidden; }\n```\n\n- 页面过渡 `animation-duration: .25s` 收敛（v2.45 的 `.4s ease-out both` 在快速连续点击时显得卡顿；`both` 保守改 `backwards` 防 fill 影响）\n- **排查习惯：用户报\"点动切换有问题/位置不对\"→ 先查 router 有没有 scrollBehavior（没有 = 必然停留旧位置）；报\"上下滑动乱\"→ 查弹窗是否锁 body 滚动（`:has()` 模式）**\n- 验证：router.ts 断言 `scrollBehavior()` + `top: 0` 且位于 `routes:` 之前；CSS 断言 5 个 `body:has(.xxx)`；dist minified JS 含 scrollBehavior；后端健康探活\n\n### 38. JSON 解析错误 + 全量 API 验证（v2.77，用户报 \"Unexpected token '<'\"）

**⚠️ 前端调了不存在的 API → SPA fallback 返回 HTML → JSON.parse 炸（v2.77 真踩）**：报错 `SyntaxError: Unexpected token '<', "<!doctype "... is not valid JSON`。根源是前端 `get()` 请求的路由后端不存在，FastAPI 的 SPA fallback 对任意 GET /api/* 都返回首页 HTML。v2.77 定位到 ReadingView 遗留的 `/vocab/context?limit=6` 调用（v2.49 加模块时写的，后端从未实现）——§35 修了 library/units 却漏了这条。

**修复后必做的系统性 GET 验证（v2.77 方法，防同类遗漏）**：
```python
# 1. 扫描前端所有 get() 调用（含动态模板字符串）
for f in glob.glob("frontend/src/**/*.vue", recursive=True) + glob.glob("frontend/src/**/*.ts", recursive=True):
    for m in re.finditer(r"\bget\(['\"`]([^'\"`]+)['\"`]", src):
        gets.add((os.path.basename(f), m.group(1)))
# 2. resolve 动态段为合理值（${id}→1, ${session.id}→15250, ${plan.key}→gaokao...）
# 3. 逐一 urlopen + 断言 Content-Type 含 application/json
```
v2.77 实测：36 个 get() 调用全部 JSON，零 HTML。**读/听力页的 fallback 残留是这类 bug 的温床**——修了主路由别忘了删前端的错误 fallback。

**全模块 QA 验证（用户\"所有功能和模块的验证和虚拟测试\"）**：一次性写 hermes-verify 脚本覆盖 8 组：① 首页/题库（startup/papers/profiles/library-units/recommendations/streak）② 练习链路（创建→详情→逐题作答→提交，**count=1 的 unit 实际含 5 题，要答完全部**）③ 考试链路（start→detail→answer→submit→history）④ 词汇（home/due-today/quiz/estimate/FSRS review/plans/anki）⑤ 错题（list/stats/export md/html/analysis-status/note）⑥ 数据（report/heatmap/leaderboard/calendar/achievements）⑦ 工具（imports/trash/ai-models）⑧ 前端完整性（17 View 文件 + 17 路由）。43 项全通过 = 系统稳定。**409 是正确业务保护（未答完），不是失败**——答完再提交 200。

### 39. 水墨背景图恢复 + 图片压缩（v2.78，用户"之前的水墨风图片没有"）

**⚠️ 页面背景图 z-index 层叠被 body 盖住（v2.78 真踩，图片"消失"的隐藏原因）**：图片文件一直存在（源/dist/mobile-app 三处齐全），但**看不见**——`.page-xxx::before` 背景图用了 `z-index: -2`，而 `body.ink-landscape::after`（body 层，`z-index: -1`）+ body 自身背景都在它之上 → 图片被完全遮挡。修复：页面背景图统一 `z-index: -2 → -1`（正文之下、body 层之上）。**排查"图片没了"先查 z-index 层叠，再怀疑文件缺失**（`ls frontend/dist/assets/backgrounds/` 三处核对）。

**全局水墨底（body 层叠加图 + 渐变）**：
```css
body.ink-landscape::after {
  background-image:
    radial-gradient(...), radial-gradient(...), radial-gradient(...),
    linear-gradient(180deg, rgba(247,243,238,.0) 55%, rgba(247,243,238,.75) 100%),
    url('/assets/backgrounds/ink-2-jiangnan.jpg');
  background-size: auto, auto, auto, auto, cover;  /* 每层对应, 图 cover */
  background-position: center;
  background-repeat: no-repeat;
}
```

**图片压缩（15MB → 3MB，加载快 5 倍）**：
```python
from PIL import Image
img = Image.open(path).convert("RGB")
w, h = img.size
if max(w, h) > 1600:  # 背景图最长边 1600 足够
    s = 1600 / max(w, h)
    img = img.resize((int(w*s), int(h*s)), Image.LANCZOS)
img.save(path, "JPEG", quality=72, optimize=True, progressive=True)
```
一次性处理 public/assets/backgrounds 全部 jpg；dist/mobile-app 由构建/同步带上压缩后版本。**加图后 mobile-app 体积也受控**。

**纯 CSS 水墨装饰元素（不依赖图片）**：
- 飘叶动画：`.ink-falling-leaf` fixed + `leaf-fall`（translateY(-5vh→105vh) + rotate(300deg) + opacity 渐现渐隐），页面放 5 片（不同 left/duration/delay）；**z-index: 0 + `.main-content { position: relative; z-index: 1 }`** 保证叶子在背景之上内容之下
- 印章式分区标题：`.section-title h2::before { content: '◈'; color: color-mix(in srgb, var(--accent) 65%, transparent); }`
- 卡片墨迹角：`.card::after` 右上角 3 个 radial-gradient 墨点（opacity .14，dark 模式 .2）

验证：断言 `z-index: -2` 不在 CSS + `ink-2-jiangnan.jpg` 在 body 层 + 13 张图 dist 完整 + 源/dist/app 三处图片总量 <4MB + 千轮回归。

### 40. 今日金句卡（每日一句趋势，v2.79）

**日期种子轮换模式（v2.39 每日一词 + v2.79 今日金句 两次复用）**：要\"每天换一条但当天稳定\"的内容（每日一词/每日一句/每日一签），用日期字符串 hash 选索引——同一天任何刷新/重载都得到同一条，第二天自动换：

```ts
function pickQuote(seedOffset = 0) {
  const day = new Date().toISOString().slice(0, 10)  // 'YYYY-MM-DD'
  let h = seedOffset
  for (const ch of day) h = (h * 31 + ch.charCodeAt(0)) % 997
  todayQuote.value = QUOTES[h % QUOTES.length]
}
function nextQuote() { pickQuote(Math.floor(Math.random() * 997)) }  // 点击换一句
pickQuote()  // 挂载时取当日
```

- **名言库**：12 句学习/坚持主题中英对照（乔布斯/丘吉尔/罗斯福/富勒/德鲁克/达·芬奇/B.B. King/老子/孔子/苏斯博士/马克·吐温），对象 `{en, cn, author}`——中文译放 `.lead` 同区，作者用 `——` 署名
- **UI**：DashboardView 备考倒计时下方 `.quote-card`——左侧朱砂引号 ❝（`.quote-mark` 44px Georgia）+ 英文衬线斜体（`.quote-en` italic 15px）+ 中文译（`.quote-cn` 12.5px muted）+ 右下角 `.quote-hint`（\"每日一句 · 点击换一句\"）；整卡 `@click="nextQuote"`（title 提示可点击）
- **英文长文案防撑破**：`.quote-en { max-width 由卡容器控制 }` + 720px 断点降字号（13px）
- 与 Hero 名言（v2.62）区别：Hero 是固定一句话，金句卡是每日轮换 + 点击可换——两者并存形成\"首屏名言层\"。搜索来源：China Daily 经典名言集锦 / 英文库 50 名言佳句（中英对照权威来源）
- 验证：断言名言库 ≥12 条（`src.count('cn: "') >= 12`）+ 作者名抽查 + **dist 断言英文原文**（中文可能被 unicode 转义，英文原文稳定）

### 41. 第三轮十轮高级感打磨（v2.80-v2.89，用户第三次要求"重复十轮"）

§30/§34 的模式第三次复用：todo 规划 10 轮 → 每轮 styles.css 追加一段（`/* ═══ v2.xx: 主题 ═══ */`）+ build + 独立 commit（`v2.xx: 第三轮高级感N/10 — 主题`）→ 最后一轮统一千轮回归 + 综合 hermes-verify。**换主题集**——第一轮莫兰迪/阴影、第二轮字体/深色，第三轮主轴是**渐变体系 + 微交互收尾**：

- v2.80 **配色再深化（金/朱/墨三渐变）**：定义 `--gold-grad: linear-gradient(135deg, #b89a55, #a8842f 60%, #c9a24a)`、`--accent-grad`（朱砂系）、`--ink-grad`（墨色系）；**渐变文字模式**（金句作者/印章/品牌名）：`background: var(--gold-grad); -webkit-background-clip: text; background-clip: text; color: transparent`；主按钮改 `background: var(--ink-grad)`
- v2.81 **排版精修**：标题 `font-size: clamp(16px, 1.1vw + 10px, 19px)` + 字距统一（`.section-title h2 { letter-spacing: .05em }`）；数字等宽 `font-variant-numeric: tabular-nums lining-nums`（`.stat-value/.rank-num/.big-score/.focus-time/.quick-word`）；`.eyebrow { letter-spacing: .18em }`（高辨识小标签）
- v2.82 **卡片细节**：`.card { border: 1px solid color-mix(in srgb, var(--line) 82%, transparent) }`；`.stat-card { box-shadow: inset 0 1px 0 #fff 55%, var(--shadow-sm) }`（内高光）；`.card:hover::before` 主题色渐变扫线（叠加在顶部高光线上）；徽章统一 `border-radius: 99px`
- v2.83 **按钮光扫**：`.button:not(:disabled)::after` 白色 18% 渐变斜条 `left: -80% → 130%` + `skewX(-20deg)`（hover 光扫过按钮）+ `:active { transform: scale(.965) }` 按下微弹 + `.button.secondary` 内高光
- v2.84 **可视化渐变**：SVG 环形 `stroke: url(#ringGrad) !important`（渐变描边）；柱状 `background: linear-gradient(180deg, #c9a24a, #a8842f 55%, #bf6a5c)`（金→朱）；`.heat-cell:hover { transform: scale(1.25); filter: brightness(1.08) }`；`.goal-day.done .goal-day-bar` 达成发光；`.rank-level` 毛玻璃底
- v2.85 **Hero 金边**：`.study-hero { border: 1px solid color-mix(in srgb, var(--gold) 22%, var(--line)) }` + h1 `text-shadow` 双层光晕 + CTA 按钮 `background: var(--gold-grad)` 金色渐变（hover brightness 1.06）
- v2.86 **侧边栏**：`background: linear-gradient(180deg, surface 92%, surface 84%)` + `.brand { padding-bottom: 22px; border-bottom: 1px solid line 55% }` 分隔 + 激活项 `font-weight: 750` + `.sidebar-category:hover { padding-left: 16px }` 滑入
- v2.87 **弹窗质感**：弹窗渐变底（`linear-gradient(165deg, surface 97%, #fff → surface 90%, #f3efe6)`）+ 头部细线（`border-bottom: line 45%`）+ `.app-toast` 双层阴影（环境光 + 1px 描边）+ 圆角 14
- v2.88 **深色再深化**：**渐变文字在 `:root.dark` 要重声明**（background-clip: text + color: transparent 需在 dark 选择器下重写一遍，因为色变量被 dark 覆盖）；侧边栏暗渐变（`surface 94%, #24221c → 86%, #1b1a15`）；CTA 深阴影 + inset 白 12% 描边；`.sidebar-note` gold 10% 底
- v2.89 **收尾整合**：全局 `transition-duration: .22s` 统一 + `:focus-visible { outline: 2px solid color-mix(in srgb, var(--gold) 55%, transparent) }` 焦点金环 + `.illustrated-empty:hover img { transform: scale(1.04) rotate(-1deg) }` 空态微动 + `.page { padding-bottom: 48px }` + **`@media (prefers-reduced-motion: reduce)` 完整覆盖**（`.button::after, .ink-falling-leaf, .card` 动画全关）

**注意**：
- 每轮 commit 可回滚；验证脚本断言每轮**关键片段**（如 `--gold-grad`、`skewX(-20deg)`、`url(#ringGrad)`、`scale(.965)`、`outline: 2px solid color-mix(in srgb, var(--gold) 55%`）
- 第三轮与第一/二轮不重叠：莫兰迪（§30）、字体/逐页（§34）、渐变/微交互（本段）——**第三次"重复十轮"就换渐变/收尾这类新维度**

### 42. 侧边栏 fixed（v2.90，用户"右侧滑动时左侧固定"）

**⚠️ `position: sticky` 在 CSS Grid 网格项上失效（v2.90 真踩）**：`.app-shell { display: grid; grid-template-columns: 248px minmax(0,1fr) }` 布局里 `.sidebar { position: sticky; top: 0; height: 100vh }` 看起来正确，但 **grid 项被拉伸到单元格全高，sticky 的 top 参考失效** → 右侧滚动时左侧跟着滚走。v2.61 的 sticky 方案在 grid 布局下不成立。

修复（fixed 绝对可靠，不依赖 sticky 的 grid 兼容性）：
```css
.sidebar { position: fixed; top: 0; left: 0; width: 248px; height: 100vh;
  overflow-y: auto; overflow-x: hidden; }
```
- fixed 脱离 grid 流后，`.app-shell > .main-content { grid-column: 2 }` 仍生效（内容从 248px 处开始），第 1 列留空正好被 fixed sidebar 覆盖
- 侧边栏 17 项超高 → `overflow-y: auto` **自身内部滚动**（细滚动条 §31）——左侧固定 + 内容可滚，互不干扰
- **响应式断点必须同步 sidebar width**：1200px 断点 `grid-template-columns: 218px` 时 `.sidebar { width: 218px }`；980px 移动端 sidebar 仍 fixed 底部导航（`inset: auto 0 0; width: 100%; height: 68px`）不受影响
- **排查习惯：用户报"右侧滑动左侧跟着跑"→ 先确认布局是不是 grid（grid 里 sticky 不可靠，直接换 fixed）；fixed 后 main 的 grid-column 显式保留 + 断点 width 同步**
- 验证：CSS 断言 `.sidebar` 主定义含 `position: fixed` + `left: 0` + `width: 248px` + `overflow-y: auto`、该段无 `sticky`；980px 断点仍 `inset: auto 0 0`；1200 断点 `width: 218px`；dist 构建含 fixed；千轮回归核对

### 43. 学习日历精致化（v2.91，用户\"日历的比例做小一些，做得高级精致一些\"）

用户嫌日历格子太大（原 `.cal-cell { aspect-ratio: 1 }` 全宽 1fr 自适应 ≈ 100px+）。改造三件套：**缩小比例 + 莫兰迪热力 + 细节精致**，纯 CSS 追加：

```css
.calendar-card { max-width: 620px; margin: 0 auto; }                 /* 卡片紧凑居中 */
.cal-grid, .cal-weekdays { grid-template-columns: repeat(7, 36px); justify-content: center; gap: 6px; }
.cal-cell { width: 36px; height: 36px; font-size: 11px; font-variant-numeric: tabular-nums; border-radius: 9px; }
```

- **莫兰迪墨绿热力**（替代原朱橙 #c97b4a 系，更雅）：`heat-l1 #9db5a5 22% → l2 #7fa08c 38% → l3 #5e846f 62% → l4 linear-gradient(145deg,#4f7462,#3d5c4c)`（最深带内高光 `inset 0 1px 0 #fff 14%` + 柔影）
- **今日标记**：朱砂细环——`border-color: color-mix(in srgb, var(--accent) 85%, transparent)` + `box-shadow: 0 0 0 2px accent 22%, 0 2px 8px accent 20%`（细环+微光，不是粗框）
- **星期行**：10px 小字 + `letter-spacing: .1em` + **周末朱砂色**（`.cal-weekdays span:nth-child(6/7)`）
- **图例精致**：13px 小方块（每档配对应色）+ `border-top: 1px dashed line 60%` 分隔线；月份切换按钮 30px 圆角 + hover 朱砂描边
- 响应式 720px：`repeat(7, 34px)` + 格子 34px + 圆角 8px
- **排查习惯：用户报\"XX 比例做小一点\"→ 先看是否 `1fr`/`aspect-ratio` 全宽自适应，改成固定尺寸 + 容器 max-width 居中；高级感靠色系降饱和 + 细描边 + 微光，不是加粗**。验证：断言 `max-width: 620px` + `repeat(7, 36px)` + 莫兰迪色值 + dist CSS

### 44. 全 17 模块水墨背景覆盖（v2.92，用户\"所有模块都加入不同的水墨风图片\"）

用户要求每模块不同的水墨背景。**先盘点再分配**：

1. **盘点挂载清单**：`grep -n "page-.*::before" frontend/src/styles.css` → 对比 17 模块清单（home/library/exam/wrong/vocab/import/assistant/settings/practice/leaderboard/report/achievements/focus/calendar/goal/reading/listening）→ 找出缺挂载的模块（v2.92 缺 5 个新模块：focus/calendar/goal/reading/listening）
2. **确认类名**：`grep -oE 'class=\"page-[a-z-]+\"' frontend/src/views/<Name>View.vue`——页面 root class 是各 View 自己写的（`<div class=\"page page-focus\">`），不是 App.vue 映射
3. **分配主题**（13 张博物馆图覆盖 17 模块，复用低频对合理）：
   - 专注→ink-4-chushan（楚山秋霁·静心）、日历→ink-5-shu（秋水·时光）、目标→ink-1-tiandu（天都·登峰）、阅读→ink-2-jiangnan（江南·书卷）、听力→ink-3-peach（桃花·听音）
   - 复用 pair：practice→library、goal→ink-1（与 leaderboard 同图，主题契合：登顶/排名）、reading→vocab、listening→ai
4. **dark 模式同步**：`:root.dark .page-focus::before, ... { opacity: .16 }`（新增页都要补）
5. **⚠️ 下载新图失败别卡住**：Unsplash 搜索页是 JS 渲染（curl/web_extract 拿不到 `images.unsplash.com/photo-` id）、Wikimedia API 只返回分类页 → **网络受限时用现有 13 张高清馆藏图重映射**（每页主题寓意匹配），这是务实路径，不阻塞交付
6. 验证：grep 17 个 `.page-xxx::before { background-image: url(` 全在 + 13 张图 dist 存在 + 5 新模块类名对应 + dark 适配 + 千轮回归核对

**排查习惯：用户报\"某模块没图/图片没有了\"→ 先 grep 挂载清单对比全模块数（缺哪个补哪个），再查 z-index（§39），最后才怀疑文件缺失**——v2.92 缺的 5 个是 v2.49 加模块时只写了页面没配背景。

### 45. 卡片清晰度修复（v2.93，用户\"卡片都要看得清楚，这部分有些透明看不清\"）

**⚠️ 半透明卡片 + 多层水墨背景叠加 = 内容看不清（v2.93 真踩）**：`.card { background: var(--surface) }` 且 `--surface: rgba(253,250,243,.92)`（92% 透明），页面背景图 opacity .26-.34 + 全局水墨底 `body.ink-landscape::after` opacity .5——**两层背景透过 92% 透明的卡片** → 文字/选项与背景图案混在一起看不清。修复三件套：

1. **卡片背景提实**：`--surface: rgba(253, 250, 243, .92) → .97`（浅色）+ `rgba(31, 29, 24, .92) → .97`（深色）——几乎不透明但保留一点质感，所有用 `var(--surface)` 的容器（card/exam-question/option/dictation-input）自动跟随
2. **全局水墨底降淡**：`body.ink-landscape::after { opacity: .5 → .26 }`（dark 版 .4 → 相应降）
3. **页面背景图统一降淡到 .10-.25**：home .20 / library .20 / exam .21 / wrong .20 / vocab .20 / import .20 / assistant .20 / settings .18 / practice .12 / leaderboard-report-achievements .16 / 5 新模块 .16 / dark 再降

**⚠️ 链式 str.replace 会级联过度调整（v2.93 真踩）**：批量降 opacity 用连续替换链：
```python
css = css.replace("opacity: .30;", "opacity: .20;")
css = css.replace("opacity: .20;", "opacity: .14;")   # 会把刚改的 .20 再降一次!
css = css.replace("opacity: .14;", "opacity: .09;")   # 再降……
```
**后一个 replace 会把前一个 replace 刚写出的值当旧值再处理** → settings .28→.18→.12→.09、library .34→.22→.14 过度降淡。修复：**单遍正则替换**（`re.sub(r'opacity: \.(\d+)', ...)` 带映射表）或**每处精确匹配完整行**（`".page-settings::before { ... opacity: .09;"` 整行 replace 到目标值）。改完 grep 每页最终 opacity 断言在区间内。

验证：断言 `rgba(253, 250, 243, .97)` + body 层 `.26` + 17 页背景图 opacity 全在 .10-.25 + dist CSS 含 .97 + 千轮回归核对。

### 46. 2025 高考真题导入 + DeepSeek 推理模型答案 + PWA v3（v2.94，用户\"真题补充/移动端/内测方案都进行\"）

**2025 高考真题官方图片 → OCR → 导入全管道**（33 题入库：一卷阅读 15 + 二卷听力 18），完整复现配方见 `references/gaokao2025-ocr-import.md`。要点：

- **下载**：`https://img.eol.cn/e_images/gk/2025/st/qg1/yy01.png`（一卷 8 页）+ `.../qg2/yy00.png`（二卷 9 页）；**git-bash 的 /tmp 写文件会 exit 23/0B**（curl 报写失败）→ 用 Windows 路径 `C:/Users/31954/AppData/Local/Temp/...`
- **OCR**：tesseract `-l chi_sim+eng --psm 3` + **2x 放大灰度**（PIL LANCZOS）效果极好（阅读 A-D/七选五/完形/语法/听力全识别）
- **解析**：题号+题干正则 + **同行多选项** `re.split(r'\s(?=[A-D]\.\s)', line)`（OCR 里 `A. x B. y C. z D. w` 常在一行）；**题号去重**（OCR 噪声如 6 出现两次 → `seen` set 只留第一个）；答案页也是图（未 OCR 时用 AI 生成）
- **⚠️ questions 表没有 profile_id**（只有 unit_id → units → papers → profile 链）；**papers.profile_id 必须等于当前激活 profile 才被 API 看到**（`get_active_profile_id` 读 `app_settings` key LIKE '%profile%'）——v2.94 导入到 profile 2（高中英语）但激活是 5（考研二）→ API 返回\"试卷不存在\"。语义正确不用改，**用户切到对应类别即可刷**；验证时可临时改 app_settings 再改回

**⚠️ DeepSeek v4-flash 直连 API 是推理模型（v2.94 真踩，答案生成为空）**：`https://api.deepseek.com/chat/completions` 直连时，模型把 token 全花在 `reasoning_content`（思考过程），`content` 为空——`max_tokens` 小（200-500）时**连思考都写不完，content 永远空**。表现：API 单独测 `1+1=?` 正常，批量生成返回空字符串。对策：
1. **max_tokens 调大（≥2000）** + system prompt 强制\"只输出答案行\"（`content` 才有东西）
2. 或**从 `reasoning_content` 解析**（`c = d['choices'][0]['message'].get('content') or ''; rc = ...get('reasoning_content') or ''; return (c or rc)`）
3. **⚠️ 从 reasoning_content 抓字母不可靠**：模型会在思考里写\"如 A/B/C/D\"举例，`re.findall(r'\b([A-D])\b')` 会抓到举例不是答案。**稳定方案：让模型按题号顺序输出字母序列**（每批 ≤5 题），再 zip 到题号
4. 仍不全 → **务实止损**：已生成部分入库 + 剩余 `answer='A'` 占位 + 整体标注\"AI辅助答案需人工核对\"（不要无限重试耗 token）

**PWA 移动端优化（sw.js v3）**：网络优先（HTML/JS，发布后拿新版）+ **图片/字体/静态资产缓存优先**（`\.png|\.jpe?g|\.webp|\.svg|\.woff2?|\.ttf|\.wasm|\.db` 正则分支，不变内容加速启动）+ **缓存版本号 v2→v3**（大 UI 改版后强制换版本，防旧缓存引用已删资源白屏——v9.20.1 的老坑）；manifest 品牌升级（`lang: zh-CN` + `categories: [education, productivity]`）。**PWA 改完要验证 mobile-app 同步含新 sw.js**。

**内测方案**（用户要求）：`docs/内测方案.md`——招募 10-20 人（闲鱼老客/B站/家长群）+ 反馈收集（内置反馈入口/每周访谈/埋点，**直接复用已有 learning_days/practice_sessions 表无需新开发**）+ 核心指标（周留存≥40%/完成率≥60%/NPS≥30）+ 2 周执行计划 + 预算 200 元红包。

### 47. 选项打乱（竞品 fork 回收，v3.0，用户认可"最小改动立刻受益"）

**借鉴 wssfk12138/android-english-multiple-choice-practice-machine（我们项目的 fork，2026-08-04 独立）**——它加了"每次打开题目练习对选项随机排序，判分用稳定键"。落地：

- `PracticeView.vue` 加 `shuffleOptions(questions)`：Fisher-Yates（`for i=len-1..1: j=Math.floor(Math.random()*(i+1)); [opts[i],opts[j]]=[opts[j],opts[i]]`）——**只打乱显示顺序**，判分走 `stable_key` 零影响
- **排序题豁免**：`question.question_type === 'ordering'` 跳过（语义是用户自己排序，乱了没法做）
- **触发时机**：`load()` 里对 `session.value.units[].questions` 全部打乱（每次进入练习都随机）
- **设置开关**：localStorage `epm_shuffle_options`（默认开，`'false'` 关）——SettingsView「练习偏好」区（`pref-switch` 样式，`role="switch"` + `:aria-checked`），toggle 写 localStorage
- **判分链路确认**：`select()` 提交 `answer: key`（stable_key）+ `option_order`——后端判分只看 stable_key，显示顺序无副作用
- 验证：源码断言（shuffleOptions/Fisher-Yates/ordering 跳过/epm_shuffle_options）+ dist minified JS 含 `epm_shuffle_options` + 判分稳定键断言

**竞品回收清单（fork 未回收项，v3.0-beta.12 已全部完成）**：
- ✅ **听力音频**（MP3 导入+播放器+计时禁拖进度条）——见 §49
- ✅ **错题迭代**（重做只显示本次错的，越做越少）——见 §50
- ✅ 长按选词入单词本（后台翻译+语境释义+高频🌟）——**本就已有**（selectionchange + pendingVocabulary 队列 + is_frequent/encounter_count）
- ✅ 模型辅助导入（AI 定位题目/答案+用户校对）——**后端本就已有**（use_model_assist + model_assist_correct_structure + 智能标注）
- ✅ **Keystore/AES-GCM 安全存储**（现 APK 明文 key）——见 §51
- ✅ 更新 SHA-256 校验——**electron-updater 内置**（latest.yml 的 sha512 字段，electron-builder 发布自动生成）
- ✅ 同义/反义/形近词辨析——**本就已有**（vocabulary_entries.synonyms/antonyms/similar_forms + VocabularyView 辨析筛选）
- ✅ ESQ 1.1 兼容——**本就已有**（esq.py 校验/导出 1.0/1.1；对方 fork 才 1.0）
**我方优势（它没有，保持差异化）**：标注笔记、学习报告/雷达/排行、水墨 UI、三端。

### 48. 透明面板彻底实色化（v3.0 完整版——补充 §45，用户"取消所有类似透明"）

§45（v2.93）只把 `--surface` 提到 .97——**不够**。用户再报"看不清"时挖出完整根因（v3.0 真踩）：

**⚠️ 透明面板的完整清单（不止 --surface）**：
1. **`.today-plan-card, .recommend-section .card` 用 `linear-gradient(165deg, color-mix(...92%...), color-mix(...78%...))` 透明渐变覆盖了 `.card` 的实色**（specificity 更高）——**每日一词透明的主因**（截图里其他卡实色、就它透）
2. `.stat-card` 88%→72% + blur、`.streak-card` 90%→70%、`.report-panel` 90%→74%、`.profile-grid` 92%→76%、`.exam-countdown-bar/.study-hero` 88%→72%、`.button.secondary` 80%
3. **深色模式再覆盖**：`:root.dark .stat-card, ... .today-plan-card, ... { linear-gradient(160deg, 80%→66%) }`——暗色下也透明
4. 侧边栏 `color-mix(...88%...)` + blur；`--surface` 三处（亮/暗/浅色变体）各自 rgba .92-.97

**彻底修复**（用户"取消所有类似透明"= 大面积面板全部 100% 实色）：
- `--surface: #fdfaf3`（100% 实色，不再 rgba）——三处变体同步
- 所有上述面板类 `background: var(--surface-solid)`（保留类名，覆盖掉渐变）
- 侧边栏 `background: var(--surface-solid)`
- **保留**：小 badge/热力色块/遮罩 overlay 的半透明（设计意图，文字对比够）
- **⚠️ 排查习惯：用户报"某卡片透明/看不清"→ 不要只看 --surface 变量，先 grep 该类是否有 `linear-gradient(...color-mix(...%, transparent))` 覆盖（specificity 更高的类），再查深色模式块是否又覆盖一层**。`.card` 实色 ≠ 页面实色——子类可覆盖
- 验证：grep 无 `rgba(.*0.[0-8])` 大面积面板背景 + 无 `%, transparent)` 卡片渐变（排除 ::before 高光装饰）+ 深色块实色 + vision 截图验收（无花纹透出）

### 49. 听力音频链路（竞品回收，v3.0-beta.12）

**现状**：后端导入管线**本就支持音频**（`imports.py` 的 `audio_files` 参数 + `ALLOWED_AUDIO_SUFFIXES = {.mp3, .m4a, .wav, .ogg}` → 存 `UPLOAD_DIR`（uuid 命名））；前端 PracticeView **本就有播放器**（`activeUnit.audio_url` + 计时禁拖 `audioSeekable`）。缺的是**后端存储/透出链路**——beta.12 补齐：

- **数据库**：`units` 表加 `audio_path TEXT`（`_ensure_column` 条件迁移，database.py `init_db` 里和 external_key 并列）
- **静态挂载**：`main.py` 挂 `app.mount("/audio", StaticFiles(directory=UPLOAD_DIR), name="audio")`（注意在 `if FRONTEND_DIST.exists()` 块内，且先 `if UPLOAD_DIR.exists()`）
- **API 透出**：`library.py list_units` 的 SELECT 加 `units.audio_path` + 返回 `audio_url`（`f"/audio/{path.split('/')[-1]}"`，None 兜底）；**放宽过滤**（`(units.passage != '' OR units.audio_path IS NOT NULL)`——纯听力单元可能无 passage）；`services/questions.py serialize_unit` 同样加 `audio_url`（**PracticeView 模板用的是 `activeUnit.audio_url`，不是 `session.audio_url`**——get_session 返回 `units[].audio_url`，改模板字段是常见遗漏）
- **入库关联**：`docx_parser.py` INSERT INTO units 加 audio_path 列——`draft["audio_paths"][0]` 关联到**首个听力单元**（无听力单元则首个单元）
- **前端 ListeningView**：列表卡有 `audio_url` 显示 🔊 徽章 + 圆形播放按钮（复用单个隐藏 `<audio>` 元素切换 src，`@click.stop` 防整卡跳转）

### 50. 错题迭代（竞品回收，v3.0-beta.12）

**逻辑**：wrong 模式重做后**作对的题 wrong_count 减 1**（越做越少，从错题本消失）；作错保持 +1。

- `practice.py _update_wrong_stat(connection, question_id, is_correct, reduce_on_correct=False)`——`delta = 0 if is_correct else 1; if reduce_on_correct and is_correct: delta = -1`；`new_wrong_count = max(0, row["wrong_count"] + delta)`
- `_grade_answer_rows(connection, rows, reduce_on_correct=False)` 透传参数
- **调用点 threading**：`submit_unit`（L558 附近）**没有 session 对象**——需 `connection.execute("SELECT mode FROM practice_sessions WHERE id=?", (session_id,)).fetchone()["mode"] == "wrong"` 查一次；`submit_session` 直接用 `session["mode"] == "wrong"`
- 现有 wrong 模式已实现"重做只显示本次错的"（create_session 的 `only_by_unit` 按 wrong_stats.wrong_count>0 过滤）

### 51. SecureStorage AES-GCM（竞品回收，v3.0-beta.12）

APK 端 key 明文 → Android Keystore AES/GCM 原生插件（DPAPI 是 Windows 专用，Android 无法解密）：

- **插件**：`frontend/android/app/src/main/java/com/moti/englishpractice/SecureStoragePlugin.java`——`@CapacitorPlugin(name="SecureStorage")`，`getOrCreateKey()` 用 `KeyGenParameterSpec`（PURPOSE_ENCRYPT|DECRYPT + BLOCK_MODE_GCM + NoPadding）从 `AndroidKeyStore` 取/建；encrypt/decrypt 格式 `base64(iv):base64(ciphertext)`（`Base64.NO_WRAP`，IV 12 字节，GCM_TAG_BITS=128）
- **注册**：`MainActivity.onCreate` `registerPlugin(SecureStoragePlugin.class)`（放 `super.onCreate` 之前）
- **前端封装**：`src/services/secure-storage.ts`——`(window as any).Capacitor.Plugins.SecureStorage`（**不能用 `@capacitor/core` 的 `Capacitor.Plugins` 类型——TS 报 `Property 'Plugins' does not exist`——用 window 断言取运行时**）
- **读取解密**：`ai.ts getApiKey`——值含 `:` 且 `^[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+$`（加密格式）→ `isNativePlatform()` 时插件解密；否则兼容旧明文
- **⚠️ ai.ts 是死代码（v3.0 真踩）**：`grep -rln "services/ai\|chatCompletion" frontend/src/` **无引用**——PWA 直连客户端是遗留，实际走 api.ts 后端 → **tree-shake 掉，dist 里没有 SecureStorage**（验证别断言 dist 含它）。**已接线"保存时加密"（v3.0-beta.12 完成）**：
  - `api-adapter.ts`：离线 `GET /ai/profiles`（返回 `has_api_key` 布尔，密文不回显）、离线 `POST /ai/profiles`（`saveAiProfileOffline` 调 `SecureStorage.encrypt` 加密后存 `api_key_encrypted`）、离线 `PUT /ai/profiles/{id}`（`updateAiProfileOffline`——body 带 api_key 才重新加密，否则保留旧密文）、`export apiPut`（在线走 fetch / 离线走 offlinePut）
  - `encryptKey(value)`：`cap?.isNativePlatform?.()` 时调 `SecureStorage.encrypt`，非原生/失败回退明文
  - `api.ts`：`get/post/put` 改为 async + `if (isOffline())` 动态 `import('./services/api-adapter')` 路由（**isOffline 是同步读 `_offlineReady`——app 启动时 initOfflineMode 异步，极端时序下 SettingsView 可能仍走 fetch 失败，可接受**）
  - **⚠️ 动态导入 → api-adapter 是独立 chunk**：dist 里是 `api-adapter-<hash>.js` 不是主 index——验证脚本要 glob `dist/assets/*.js` 或直接查 `api-adapter-*.js`
  - **⚠️ `lastInsertRowId()` 无参数**（db.ts 内部读 `SELECT last_insert_rowid()`）——传 result 进去 TS2554
  - **⚠️ `@capacitor/core` 的 `Capacitor.Plugins` 类型不存在**——secure-storage.ts 用 `(window as any).Capacitor` 断言取运行时插件

### 52. EPM_DATA_DIR 与安装版后端调试（v3.0-beta.12 真踩）

**⚠️ 手动启动安装版后端必须传 EPM_DATA_DIR**：Electron main.js spawn 后端时传 `env: { ...process.env, EPM_DATA_DIR: path.join(app.getPath('userData'), 'data'), ... }`——**手动裸启动 `resources/backend_app/backend_app.exe` 不传 env → 连 `resources/backend_app/backend/data/question_bank.db`（空库，只有默认 5 profiles，papers=0）** → 网页版 `GET /api/papers` 返回空列表假象。症状：`/api/profiles` 正常（5 个默认）但 `papers: 0`——不是数据丢，是连错库。

- 正确手动启动：`export EPM_DATA_DIR="C:\Users\31954\AppData\Roaming\ai-english-practice-desktop\data"` 再跑 exe（**注意：bash `VAR="C:\..."` 反斜杠路径可能不生效，用 `/c/...` 或 PowerShell `$env:` 也不一定——最可靠是让 Electron 应用自己 spawn**）
- **⚠️ 端口占用导致"后端一直 502"**：手动启动的 backend_app 进程**杀不干净**（`taskkill //F //PID` 可能静默失败——用 `powershell Stop-Process -Id <pid> -Force` 确认进程数归 0）→ Electron 应用 spawn 后端因端口被占失败 → 502。症状链：502 → 进程列表有旧 backend_app → Stop-Process 清掉 → 重启应用
- **应用启动即退（code 0）→ 重装修复**：beta.12 安装后 `Start-Process` 启动应用 10 秒内退出（crash.log 无新条目）→ 重跑 `epm-setup-2.0.0-beta.12.exe /S` 后正常。安装损坏时重装是第一条路
- **⚠️ seed 覆盖隐患（v3.0 曾误报，已确认不存在）**：Electron main.js 的 seed 复制**有 `if (!fs.existsSync(userDb))` 外层检查**（L148，仅首次复制）——安装版 app.asar 与源码一致，学习记录不会被覆盖。**教训：排查"覆盖/丢失"类问题时 sed 片段会漏看外层条件（当时只看到内层 `if (fs.existsSync(seedDb))` 就下结论）——先 `grep -n` 确认完整嵌套，再下判断**。真正的隐患是 §52 的 EPM_DATA_DIR 连错库（papers=0 假象）

### 53. en-sky 2026 高考真题导入（免费数据源突破，v3.0-beta.12）

**en-sky.com 的"试题含答案解析"文章页有完整真题全文**（不是只有网盘链接！）——`https://www.en-sky.com/post/1238.html`（2026 全国 I 卷）全文 35K 字符：阅读 A-D 文章+题目+选项、七选五、完形、语法填空、**完整答案区**（`21-23 BAC` / `41-45 CABCA` 格式）+ 听力材料文本。web_extract 抓取 → 解析导入 45 题（2026 高考 I 卷，高中 profile）。完整流程：

1. `web_extract` 抓 post 页 → 全文存 `C:\Users\31954\AppData\Local\hermes\cache\web\<domain>-<hash>.md` → **read_file 分页读全**（head+tail+中段）
2. 答案硬编码（页面"英语答案"区清晰：`21-23 BAC` 等）
3. 解析脚本（import 到 `frontend/public/question_bank.db`，profile=2 高中）：
   - **⚠️ 缓存 md 题目行是 `21\. `（反斜杠转义点）**——正则必须 `r"^\d+[\\\.]+\.\s"`（数字+任意反斜杠/点序列+点+空格）——普通 `^\d+\.\s` 不匹配，A-D 篇全解析为空
   - **⚠️ parse 函数用局部行数组**（`text_block.split("\n")`），**不要用全局 lines**（第一次实现用全局 → 读到听力部分，阅读 A-D 全变成听力题 1-7）——函数签名 `parse_reading(text_block, qnums)`
   - 完形选项行 `41\. A. fantasyB. prejudiceC...`（同行多选项无空格）→ `re.findall(r"([A-D])\.\s*([^A-D]+)", rest)`
   - 七选五选项 A-G 判断用 `len(qx_passage) > 3`（避免把文章开头当选项）
4. **同步到所有端（保留学习记录）**：不能 deploy_full_bank（会清学习记录）——写增量同步脚本：源库 → `%APPDATA%/data/question_bank.db` + `frontend/dist/question_bank.db`，只复制新 paper/units/questions/options（**lastrowid 在 cursor 上不是 connection**：`cur_d = d.execute(...)` 然后 `cur_d.lastrowid`）
5. APK 重建：`npx cap sync android`（**先 npm run build**——cap sync 复制 dist 不是 public）→ gradle assembleDebug
6. 验证：paper_stats（源库/在线库/dist/APK 内库各 45 题）+ 答案抽查（21=B / 41=C / 56=to be held）+ 题库总量 647+45=692

**其他类别（四六级/考研 2025-26）**：见 `references/question-data-sources.md`（v3.1 更新）——**环球网校 hqwx.com 四六级真题 PDF 可直接 curl 下载**（详情页 HTML 有 oss-hqwx-video 直链，无需登录），但**考生回忆版缺干扰选项**（听力材料/题干/答案齐全 ≠ 可建 4 选 1 题）；夸克网盘分享免登录只能列文件不能下载（API 端点见 reference）；考研最新 25-26 仍需 B 站私聊/网盘。

- **patch 超时 ≠ 未写入（v2.43 真踩）**：大 patch（数百行）报 `Command timed out after 15s`，但**文件实际已写入**。接着用旧内容重试小 patch → `Could not find a match`（因为已改）。**patch 报超时后先 read_file 确认现状再决定重试**；重试用短唯一锚点（如 `function closeQuiz() {` 而非大段上下文）
- **⚠️ 大 patch 用短锚点（v2.42/2.43 连续踩）**：几百行的 old_string 在 CRLF 文件上容易整体失配（`_warning: modified since last read`）或超时。拆小：先小 patch 成功 + 补丁，再大改；CRLF 差异用唯一短锚点绕开
- **patch 超时后可能部分写入 → 模板重复块（v2.42 真踩）**：第一次大 patch 超时（实际已写入），第二次短锚点 patch 又插一份 → 同一组件出现 3 次。**验证脚本断言 `count == 1`**（如 `wv.count("freq-card") == 1`）防重复
- **前端引用字段必须后端已返回（v2.41 真踩）**：ReportView 用了 `report.total_rate`/`report.total_answered`，但 report API 返回 dict 没有这俩 → 页面显示 `undefined`。**前端加新字段引用前先 grep 后端 return dict 确认字段存在**，缺就补（report API 曾补 total_answered/total_rate）
- **sqlite3.Row 没有 `.get()`**：`(profile or {}).get("name")` 会 AttributeError → 用 `dict(profile).get(...)`
- **FastAPI 路由顺序**：具体路径 router（/plans）必须在含参数路径 router（/{entry_id}）之前注册，否则被吞掉返回 422
- **cron script 参数**：cron `script` 字段不支持带参数（"xxx.py morning" 当文件名找）→ 拆成独立脚本文件；no_agent 任务后端离线时静默（watchdog 模式，空输出=不打扰）
- **Windows 端口残留**：`taskkill //F` 在 git-bash 报"无效参数"，用 `powershell Stop-Process -Id <pid> -Force`；验证前必杀 8765 旧进程
- **OCR 提题**：真题图片 OCR 后文章常提取为空（422），题目+答案才是核心，先导入；中文解析噪声用 `re.sub(r'[^\x00-\x7F]{4,}', '', text)` 清除；阅读选项可能**竖排**（`A.` 单独行 + 内容下一行）需先规范化再正则；**跨页**（题目在 p0、选项 A-D 跨 p0-p1）必须拼 all_text 统一解析；**选项字母 OCR 丢失**（`A.` 变 `.` 或乱码）先试图片预处理（2x 放大+灰度+对比度+autocontrast+`--psm 6`）再决定跳过，不要直接放弃（详见 `references/ocr-exam-images.md`）
- **首页 embedded 缓存**：`window.__LINJIAN_STARTUP__` 让 loadHome 用旧数据 → 切换级别必须 `loadHome(true)` 强制刷新
- **⚠️ 推荐串台 ≠ 前端缓存**：切换级别后推荐显示别的级别内容，先查 DB 的 `papers.profile_id` 与标题级别一致性（校验 SQL 见 §20），再怀疑前端——后端过滤正确时问题几乎都在导入关联错位
- **批量导入后必校验 profile 关联**：AI 模拟题/真题批量导入后跑 §20 校验 SQL，标题含级别名必须与 `question_bank_profiles.name` 匹配，否则用户切级别即串台（v2.39 6 卷错位的直接原因）
- **cron script 参数**：cron `script` 字段不支持带参数（"xxx.py morning" 当文件名找）→ 拆成独立脚本文件
- **练习会话 body**：`POST /api/practice/sessions` 必须带 `mode`（paper/random）+ paper_id 或 unit_type
- **词汇表字段**：`term` 不是 `word`；`questions.prompt` 不存在（是 `stem`）；wrong_stats 无 id 列（用 question_id）
- **JSONL 词库**：kajweb/dict 的 zip 里是 JSONL（每行一个对象），不是单个 JSON 数组
- **高考新课标空位格式**：2024 新课标卷用 `（N）` 全角括号空位（不是 `___N___`），选项块 `（3）A.asking B.looking...` 无空格——两个正则都要支持
- **模块级常量/函数名在 dist 里会被 minifier 改名**——验证脚本不要断言源码函数名，断言字符串字面量（"备考倒计时" 等）
- **practice_answers 用 `answered_at` 不是 `created_at`**（report 聚合按天必须用 answered_at，否则 "no such column"）
- **streak_state 表不存在**——判断今天是否活跃用 `learning_days` 查 day=today，不要查 streak_state（No such table）
- **⚠️ chat_completion 签名（v2.96 真踩）**：`backend/app/services/ai_client.py::chat_completion(connection, messages, *, response_format, profile_id, model, max_tokens)`——**没有 temperature 参数**（传 `temperature=0.9` → TypeError 被 except 吞掉 → 返回 `{"error": "AI 生成失败: chat_completion() got an unexpected keyword argument 'temperature'", "questions": []}`，前端看到空列表但看不到 error）；**返回 str 不是 dict**（`response.get("content")` → `'str' object has no attribute 'get'`）。调用前先 `grep "def chat_completion"` 看签名；返回值直接当 str 用（或 `isinstance` 兜底）
- **⚠️ 后端 API 存在但前端未接线（v2.96 发现）**：`POST /api/ai/similar-questions`（similar_questions.py，v9.19 就有）前端**从未调用**——"同类强化"按钮走的是规则推题（practice/sessions random），AI 变体题是隐藏功能。排查习惯：新功能先 `grep -rn "api 路径" frontend/src/` 看有没有调用方；后端有前端无 = 要么接线要么删。接线模式：WrongView 每行加按钮 → POST /ai/similar-questions {question_ids: 前5} → 弹窗渲染 questions（stem/options/answer）
- **验证脚本不要内嵌 netstat 清端口**：Windows 下 `subprocess.run(["netstat"], text=True)` 会 GBK UnicodeDecodeError。先手动 `netstat -ano | grep 8765` + `powershell Stop-Process` 清掉旧进程，再跑验证脚本（旧进程不杀 = 新代码不生效 + 端口冲突假 422）
- **view 里用 showToast 必须 import**：`import { showToast } from '../services/toast'`（DashboardView v2.39 真踩 TS2304 `Cannot find name 'showToast'`）——不是全局注入
- **整卡 @click 容器内嵌按钮必须 `@click.stop`**（v2.46 真踩）：freq-item 整卡 `@click="redoQuestion"` 跳转，内部 📝 笔记按钮/编辑器若不带 stop → 点笔记直接跳重做。凡"可点击整卡 + 内部独立控件"都是这个模式
- **后端加字段先确认前端引用**：前端模板引用了后端 API 返回里没有的字段 → 渲染 `undefined`（v2.41 report.total_rate 真踩）。加新字段双向核对：后端 return dict 补字段 或 前端去掉引用
- **learning_days 表没有 count 列**（v2.49 真踩 500）：schema 只有 id/day/activity_type/detail/created_at，每行一条活动记录。聚合必须 `COUNT(*)` + GROUP BY，不要 `SUM(count)`（No such column）
- **FSRS State 枚举从 1 开始，fsrs_state=0 是非法旧数据**（v2.75 真踩 500）：`vocabulary_entries.fsrs_state` 为 0 的词，`POST /vocabulary/{id}/review` 评分 → `ValueError: Unknown card state: 0`。修数据（0→1）+ 适配层防御（`int(card.state) not in (1,2,3,4)` → `State.New`）。**用户报\"有些模块 500\"时 GET 全 200 也要测 POST 链路（词汇 review 是重灾区）**
- **新 view 写完必须补 720/480 窄屏断点**（v2.60）：grid 多列 → 1fr、flex 横排 → column/换行、固定尺寸（focus-ring 220px 等）→ 缩小/auto。等用户反馈\"手机上挤爆\"就晚了
- **createRouter 必须配 `scrollBehavior() { return { top: 0 } }`**（v2.76）：不配则路由切换后浏览器保留旧滚动位置——用户报\"点动切换有问题/切过去位置不对\"时第一排查项
- **页面背景图 z-index 必须 ≥ -1**（v2.78 真踩）：`.page-xxx::before` 用 `z-index: -2` 会被 `body.ink-landscape::after`（-1）和 body 背景盖住 → 水墨图\"消失\"。全局/页面背景统一 -1，内容层 `.card > * { position:relative; z-index:1 }`。**用户报\"之前的图片没有了\"先查 z-index 层叠（文件可能都在），再查文件缺失**
- **`position: sticky` 在 CSS Grid 网格项上不可靠（v2.90 真踩）**：grid 项被拉伸到单元格全高，sticky top 参考失效 → 右侧滚动时左侧跟着跑。侧边栏固定改用 `position: fixed; top: 0; left: 0; width: 248px`（main 保持 `grid-column: 2` 内容即从 248px 开始）；fixed 脱离流后第 1 列留空由 sidebar 覆盖；**响应式断点同步 sidebar width**（1200px 断点 218px），980px 移动端底部导航 fixed 不变
- **弹窗必须锁背景滚动**（v2.76）：fixed overlay 不锁 body 会滑动穿透（背景跟着滑）→ `body:has(.category-modal), body:has(.quick-overlay), ... { overflow: hidden }`（现代浏览器 `:has()` 无需 JS watch）
- **sidebar sticky+100vh 必须 overflow-y: auto + 子块 flex-shrink:0**（v2.61）：17 个导航项超出高度被裁剪、无法滑动（用户\"左侧也增加一个小滑动\"）。主内容长页面滑不到底 = `.app-shell > .main-content` 缺 `min-height:100vh + overflow:visible + padding-bottom`
- **批量生成脚本 tuple 里不要写 dict 冒号**（import_graduate.py 真踩）：数据文件用 `("passage", ["answers"])` 元组结构时，第二元素误写 `"answers": [...]`（dict 语法）→ SyntaxError。写大段数据脚本时元素结构统一用位置值，不用 `"key": value`
- **链式 str.replace 会级联过度调整**（v2.93 真踩）：`replace(".30",".20")` 后再 `replace(".20",".14")` 会把**刚改出的 .20 又降一次**（.28→.18→.12→.09 三级跳水）。批量调同类数值用**单遍正则 + 映射表**，或每处匹配完整行，改完 grep 最终值断言区间
- **web_extract 缓存 md 题目行是 `21\\. ` 转义点**（v3.0 真踩）：`re.match(r"^\\d+\\.\\s")` 不匹配 → 阅读 A-D 解析全空。用 `r"^\\d+[\\\\\\\\.]+\\.\\s"`（数字+任意反斜杠/点+点+空格）；**parse 函数用局部行数组**（`text_block.split("\\n")`），用全局 lines 会读到别的部分（A-D 全变听力题）——详见 §53
- **sqlite3 lastrowid 在 cursor 上**（v3.0 真踩）：`d.lastrowid` 报 `'sqlite3.Connection' object has no attribute 'lastrowid'`——`cur = d.execute(...)` 后 `cur.lastrowid`
- **安装版后端手动启动必须传 EPM_DATA_DIR**（v3.0 真踩）：裸启动 `resources/backend_app/backend_app.exe` 连 `resources/backend_app/backend/data` 空库（5 默认 profiles + 0 papers）→ `GET /api/papers` 空列表假象。最可靠是让 Electron 应用自己 spawn；调试端口占用时 `powershell Stop-Process` 清干净（taskkill 可能静默失败）——详见 §52
- **electron main.js seed 无条件覆盖用户库**（v3.0 发现未修）：`fs.copyFileSync(seedDb, userDb)` 每次启动执行（注释说"首次"但代码没有 exists 判断）→ 学习记录会被旧 seed 覆盖。修复方向 `if (!fs.existsSync(userDb))`
- **DeepSeek v4-flash 直连 API 是推理模型**（v2.94 真踩）：token 全进 `reasoning_content`，`content` 空；max_tokens 小（<1000）时连思考都写不完。答案生成要么 max_tokens≥2000 + system 强制输出，要么解析 reasoning_content；**从思考里正则抓字母不可靠**（模型会写\"如 A/B/C/D\"举例），用\"按题号顺序输出字母序列\"再 zip
- **git-bash 里 /tmp 写文件会失败**（v2.94 真踩）：curl `-o /tmp/x.png` 报 exit 23 / 0 B——用 Windows 路径 `C:/Users/31954/AppData/Local/Temp/...`
- **papers.profile_id 必须匹配当前激活 profile 才被 API 看到**（v2.94 真踩）：导入到语义正确 profile（高中英语=2）但激活是 5 → `GET /api/papers` 不返回、`POST /practice/sessions {mode:'paper'}` 报\"试卷不存在或不属于当前题库配置\"。不是 bug，**用户切到对应类别即可刷**；验证时临时改 `app_settings`（key LIKE '%profile%'）再改回
- **dashboard 推荐卡显示 `p.year · p.subject`——subject 字段必须与标题语义一致**（v3.0-beta.12 真踩）：导入 2026 高考卷时 subject 错成 '英语一'（应 '高中英语'）→ 首页推荐卡显示\"2026 年 · 英语一\"。修复：`UPDATE papers SET subject = '高中英语' WHERE title LIKE '%2026%全国I卷%'`（源库 + %APPDATA% 在线库 + dist 三库同步，改完 curl /api/startup 复验）。**导入新卷时显式设置 subject**（不依赖默认值）
- **Hermes 模型切换后 cron 会 fail closed（v3.0 真踩）**：把 Hermes 默认模型从 deepseek 直连切到基元律动后，**所有未 pin 的 cron（provider_snapshot 旧值）下次运行报 `RuntimeError: Skipped to prevent unintended spend: global inference config drifted`**——不是任务坏了，是保护性跳过。修复：`hermes cron edit <job_id> --model deepseek-v4-flash-0731 --provider custom:jiyuanlvdong`（CLI 的 edit 支持 pin；cronjob 工具无 provider/model 参数）。**批量迁移**：`hermes cron list` 找 provider=deepseek 的任务 → for 循环逐个 edit。迁移后 `cronjob action=run` 验证 last_status: ok

### 54. 推荐卡片按年份去重 + 卷别标签（v3.1，用户两次反馈"UI 还是有点问题"）

**⚠️ 同一年多张卷标题相似 = 用户视觉"重复"（v3.1 真踩）**：高中 profile 有 2023 甲卷 + 2023 全国卷 + 2023 乙卷，推荐区 `slice(0,4)` 取 2026/2024/2023甲/2023全国——标题都是"2023年高考英语全国X卷阅读理解"，**用户看起来就是两张重复卡**（数据其实无重复！）。诊断顺序：

1. **先 API/DOM 级确认数据无重复**（不要信视觉判断）：`curl /api/startup` 看 `recommendations.papers`（6 张：2026/2024/2023甲/2023全国/2023乙/2022甲——无重复）→ headless Chrome `--dump-dom` 提取卡片文本（`grep -oE '<a[^>]*class="card recommend-paper"[^>]*>.*?</a>'` 正则逐卡解析 year/title）——**vision_analyze 会把相似的"全国卷"误读成"甲卷"**（长中文标题识别不可靠），判定重复以 DOM 为准
2. **前端首屏用 `window.__LINJIAN_STARTUP__` embedded 数据**（不是实时 fetch）——排查时 `curl 8765/ | grep -oE '"papers": \[[^]]*\]'` 看 embedded 内容，别只测 /api/startup
3. 数据无重复但用户觉得重复 = **视觉区分度问题** → 两个修复一起上：

**修复①：推荐卷按年份去重**（每年只显示最新一张，覆盖更多年份）：
```ts
const recommendPapers = computed(() => {
  const papers = data.value?.recommendations?.papers || []
  const seen = new Set<number>()
  return papers.filter((p: any) => {
    if (seen.has(p.year)) return false
    seen.add(p.year)
    return true
  }).slice(0, 4)  // 2026/2024/2023/2022 各一张
})
```

**修复②：卷别标签增强区分**（DashboardView 卡片加彩色徽章）：
```ts
function paperSet(title: string): string {
  const m = title.match(/(新高考[ⅠI一二]?卷|全国[甲乙]卷|全国I?I?卷|新课标[ⅠI一二]?卷|[甲乙]卷)/)
  return m ? m[1] : ''
}
function paperKind(title: string): string {
  return title.replace(/^\d{4}年/, '').replace(/(...卷正则...)/, '').replace(/^高考英语/, '').trim()
}
function setClass(title: string): string {
  const s = paperSet(title)
  if (s.includes('甲')) return 'set-jia'   // 红
  if (s.includes('乙')) return 'set-yi'    // 蓝
  if (s.includes('新')) return 'set-new'   // 绿
  return 'set-default'                     // 灰
}
```
模板：`<small><span class="paper-set-tag" :class="setClass(p.title)">{{ paperSet(p.title) }}</span>{{ paperKind(p.title) }}</small>`

**⚠️ build 后必须把 dist 同步到安装版**（v3.1 真踩）：8765 伺服的是 `resources/frontend/dist`（EPM_FRONTEND_DIST），`npm run build` 只更新 frontend/dist——**前端改动要 `cp -r dist/* "C:\Users\31954\Desktop\ai-english-practice-desktop\resources\frontend\dist\"` 才生效**（网页版立即看到，桌面版下次发布带上）。

- 验证：源码断言（paperSet/paperKind/setClass/recommendPapers + `seen.has(p.year)`）+ 纯逻辑测试（6 张 → [2026,2024,2023,2022]）+ dist 含 `paper-set-tag` + **DOM dump 断言 4 卡年份去重**（`len(set(card_years)) == 4`）+ 卷别识别正确（全国I卷/甲卷/乙卷/新高考）
- **排查习惯：用户报"UI 还是有点问题/看着重复"→ 先 DOM/API 级确认（不信 vision），数据无重复 = 视觉区分度问题（去重+标签），有重复 = 数据/缓存问题（embedded 旧数据/导入重复）**

### 55. 全类别核心词汇库导入（v3.1-beta.14 实测，7751 词）

**用户需求**：\"导入全类别的高频/经典/热点/核心词汇\"（高考/四级/六级/考研）。数据源研究选定：

| 源 | 内容 | 下载 |
|---|---|---|
| **KyleBing/english-vocabulary** | 高中 6008 / 四级 7508 / 六级 5651 / 考研 9602（`单词\t释义` UTF-8 txt） | `https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/<URL编码文件名>.txt`——**文件名含中文+空格**（`2 高中-乱序.txt` → `2%20%E9%AB%98%E4%B8%AD-%E4%B9%B1%E5%BA%8F.txt`）——先用 `gh api repos/KyleBing/english-vocabulary/contents/ --jq '.[].name'` 拿真实文件名再编码（API rate limit 时 gh 走认证不受限） |
| **exam-data/NETEMVocabulary** | 考研 5530 词**词频排序**（200 套真题统计，前 2444 为高频） | `netem_full_list.json`（dict：`{'5530考研词汇词频排序表': [{序号,词频,单词,释义,其他拼写,分类,子分类}]}`） |

**导入管道**（写临时脚本 `hermes-verify-`/`vocab-import.py` 风格，跑完删）：
1. 解析 KyleBing txt：`line.split(\"\t\", 1)` → `(term.lower(), meaning)`；过滤 `re.match(r\"^[A-Za-z'\\- ]+$\", term)`
2. 解析考研 json：`item.get(\"单词\")` / `item.get(\"释义\")`（字段名确认——不同 repo 结构不同，先 `json.dumps(items[0])` 看字段）
3. **词性拆解**：释义开头正则 `^(n\\.|v\\.|adj\\.|adv\\.|prep\\.|conj\\.|pron\\.|num\\.|art\\.|int\\.|aux\\.|vt\\.|vi\\.)` → `part_of_speech`（映射 n.→noun 等）；中文释义 `cn.split(\"；\")[0]`（取第一条核心义）
4. **⚠️ `vocabulary_entries.normalized_term` 有 UNIQUE 约束**（v3.1 真踩 `IntegrityError: UNIQUE constraint failed`）——**导入前查 `SELECT 1 FROM vocabulary_entries WHERE normalized_term = ?` 跳过已存在词**（重叠词跨类别共享，只插专属新词；不要用 `INSERT OR IGNORE` 之外的复杂合并）
5. 分类写 `category`（'高考'/'四级'/'六级'/'考研'）——**前缀匹配是后端过滤逻辑**（`LIKE '高中%'` 匹配 '高中·高频'）
6. **3 库同步**（源库 `frontend/public` + 在线库 `%APPDATA%\\ai-english-practice-desktop\\data` + `frontend/dist`——dist 才是发布/APK 用的）
7. 验证：分类分布 GROUP BY + 空释义计数=0 + API `GET /api/vocabulary/home?limit=5` 返回词条（**⚠️ API 首屏按 encounter_count 排序，断言别依赖特定词**——词序随机/变化；断言 items 非空 + 释义非空即可）
8. **API 透出 category**（v3.1-beta.14）：`vocabulary.py home_words` 的 SELECT 加 `category` 列（前端分类筛选基石）——**安装版后端是 PyInstaller exe，后端改动要下次发布才生效**（源码级验证用 SQL 直查用户库断言字段返回）

**实测结果**（每类别 2000 起 → 去重后）：高考 2702 / 四级 1989 / 六级 2232 / 考研 828 专属（考研完整 5530 中 4700+ 与四六级重叠已保留在库）——总 7751。**考研"专属"少是正常的**（考研词表包含四六级基础词——重叠词已入库但归入先导入的类别）。

### 56. 移动端 P0+P1（竞品 wssfk12138 竖屏架构参考，v3.2-beta.14）

**竞品参考**：`wssfk12138/android-english-multiple-choice-practice-machine` 文章宣称\"竖屏界面从 0 重新开发\"——四项底部导航（首页/笔记/AI/设置）+ 竖屏练习上下分区 + 动态首页（无听力不显示听力入口）。我们**已有移动适配基础**（27 个 @media 断点 + mobile-nav），差距补齐四件套：

**① 竖屏练习上下分区（文章区/题目区独立滚动 + 可拖分隔条）**——PracticeView：
```css
@media (max-width: 767px) and (min-width: 400px) {
  .practice-layout {
    grid-template-columns: 1fr;
    grid-template-rows: minmax(180px, var(--passage-ratio, 45%)) 10px minmax(0, 1fr);
    height: calc(100vh - 68px - 56px);   /* 顶栏 + 底部导航 */
    --passage-ratio: 45%;
  }
  .passage-pane { overflow: auto; min-height: 0; }   /* 独立滚动必须有 min-height:0 */
  .question-pane { overflow: auto; min-height: 0; }
  .pane-divider { cursor: row-resize; touch-action: none; }
}
```
模板在 `</section>(passage-pane)` 和 `<section class="question-pane">` 之间插 `<div class="pane-divider" @pointerdown="startDragDivider">`；Vue：`isMobileSplit`（`window.innerWidth < 768`）+ `startDragDivider(e)`（`pointerdown` 记 startY + rect → `pointermove` 算 ratio `Math.min(72, Math.max(25, (ev.clientY - rect.top)/rect.height*100))` → `container.style.setProperty('--passage-ratio', ...)`）——**pointer 事件 + window 监听 + 清理函数**。**听力单元不用分区**（`!isListening`）。

**② 动态首页入口**（DashboardView）——`practiceCards` computed 已有 `enabled: counts.X > 0`，**补听力卡 + 渲染过滤**：
```ts
{ key: 'listening', title: '听力理解', enabled: (counts.listening || 0) > 0, type: 'listening' }
const visiblePracticeCards = computed(() => practiceCards.value.filter(c => c.enabled))
```
模板 `v-for="card in visiblePracticeCards"`（去掉 disabled 态——**没有该题型就不显示**，不是灰显）。

**③ 底部导航合并**（App.vue mobile-nav 6→5）——错题+单词合并为"笔记"（/notes）。**NotesView 已是"我的笔记"（annotations）**——升级 3 tabs（错题本/单词本/我的笔记）：`activeTab` ref + 动态组件 `<WrongView v-if="activeTab==='wrong'" />`（直接 import 复用）+ `<template v-else>` 包原内容。**桌面侧边栏保留错题/单词独立入口**（只有移动导航合并——用户要的是手机清爽）。

**④ 答题卡抽屉**（移动端题目导航）——PracticeView 顶部工具栏加按钮（`v-if="isMobileSplit"`）→ `answerSheetOpen` → fixed 抽屉（顶部滑下）→ 题目网格：
```ts
function isAnswered(qid: number): boolean {
  const q = activeUnit.value?.questions.find((x: any) => x.id === qid)
  return !!(q && (q.user_answer || q.answer_selected))   // ⚠️ 答案状态在 question.user_answer，不是独立 answersMap
}
function jumpToQuestion(index: number) {
  // 关抽屉 + highlightedQuestionId + scrollIntoView({block:'center'}) + 2.4s 后清高亮
}
```
CSS：`.answer-sheet-cell.answered { background: var(--primary); color: #fff }` + `.current` outline + Transition sheet-fade。**桌面端隐藏按钮**（`@media (min-width:768px) { display:none }`）。

**验证**：源码断言（pane-divider/startDragDivider/isMobileSplit/visiblePracticeCards/answer-sheet/activeTab）+ 纯逻辑测试（去重/已答）+ dist 含字符串 + **build 后 `cp -r dist/* resources/frontend/dist/` 同步安装版**（§54 坑）。验证脚本断言 mobile-nav 区域**用切片**（`app[app.find('class=\"mobile-nav\"'):app.find('</nav>', start)]`）——App.vue 有桌面侧栏 + 移动 nav 两处，`to=\"/wrong\"` 在桌面侧栏仍存在是**设计正确**，别断言整个文件。

### 57. 移动端离线时序修复（v3.3-beta.15，手机版首页空白）

**⚠️ 症状：手机 APK 打开主界面空白（底部导航在但内容区空）**——Capacitor WebView 没有本地 FastAPI 后端，前端必须切 sql.js 离线模式（`api.ts` PWA 离线检测）。空白根因不是数据缺失，是**时序**：

**根因**（v3.3 真踩）：
- `main.ts` 原版 `initOfflineMode().then(...)` 是**异步不阻塞**——`createApp().mount('#app')` 立即执行
- `initOfflineMode()` 先 `fetch('/api/health')` 2 秒超时 → 才初始化 sql.js——**mount 时 offline 未就绪**（`isOffline()` false）
- DashboardView `loadHome()` 调 `get('/startup')`——isOffline false → 走 HTTP fetch → 手机无后端 → 失败重试一次（500ms）仍失败 → `error.value='主页数据暂时没有加载成功'`（或 embedded 未设置显示空）

**修复（双管齐下）**：
1. **api.ts**：`initOfflineMode(skipHealthCheck = false)`——Capacitor 原生平台跳过 health 检查直接 sql.js：
```ts
export async function initOfflineMode(skipHealthCheck = false): Promise<boolean> {
  if (_offlinePromise) return _offlinePromise
  _offlinePromise = (async () => {
    if (!skipHealthCheck) {
      try {
        const resp = await fetch('/api/health', { signal: AbortSignal.timeout(2000) })
        if (resp.ok) { _offlineReady = false; return false }
      } catch { /* 后端不可用 → sql.js */ }
    }
    try {
      const { initDatabase } = await import('./services/db')
      await initDatabase()
      _offlineReady = true
      return true
    } catch { _offlineReady = false; return false }
  })()
  return _offlinePromise
}
```
2. **main.ts**：bootstrap——**先 await 离线初始化再 mount**（mount 时 offline 已就绪，DashboardView 走 sql.js）：
```ts
async function bootstrap() {
  const isNative = !!(window as any).Capacitor?.isNativePlatform
  const offline = await initOfflineMode(isNative)
  if (!offline) setupAutoReload()
  if (offline) { (window as any).__LINJIAN_STARTUP__ = { ... } }
  createApp(App).use(router).mount('#app')
}
bootstrap()
```

**APK 资产预检**（排查前先确认资源在包里——避免怀疑代码前先排除打包遗漏）：
```bash
unzip -l <app>.apk | grep -iE "sql-wasm\.wasm|question_bank\.db$"
# 必须有：assets/public/sql-wasm.wasm (660KB) + assets/public/question_bank.db (5.8MB)
# cap sync 复制的是 dist 不是 public——改 public 数据必须先 npm run build（§51 已踩）
```

**验证**：源码断言（`skipHealthCheck` + `bootstrap` + `isNativePlatform` + `await initOfflineMode(isNative)`）+ dist minified JS 断言**字符串**（`isNativePlatform`/`initDatabase`/`__LINJIAN_STARTUP__`——**函数名会被 minify 改名，别断言 bootstrap 函数名**）+ 重打 APK 用户重装验证。

**⚠️ 验证脚本陷阱**：`hermes-verify` 的 `npm run build` 检查在 Windows subprocess 会 `FileNotFoundError`（npm 是 .cmd 需要 shell）——检查 dist 产物时间戳或改用 terminal 跑构建。

### 58. Windows 端三问题（v3.3-beta.15，用户报练习白屏/考试无题目/报告500）

**① 练习白屏（做一半/提交后白屏——hash 路由修复）**：
- 症状：首页正常，但深层页（/practice/1、/exam）白屏；console：`Failed to load module script: ... MIME type of "text/html" ... /practice/assets/index-*.js`
- 根因：`vite.config base: './'`（为 5+App file:// 设相对路径）+ `createWebHistory`——深层页 URL `/practice/1` 里 `./assets/index-*.js` 解析为 `/practice/assets/index-*.js` → 后端 SPA fallback 找不到文件返回 index.html（text/html）→ JS MIME 检查失败 → 模块不加载 → 白屏
- 修复（一行）：`createWebHistory()` → `createWebHashHistory()`——URL 变 `/#/practice/1`，页面路径恒为 `/`，`./assets/...` 永远相对根（http/file:///Capacitor 全对）。代价：URL 带 #；旧直链落首页（不白屏可接受）
- 排查工具：Chrome headless `--enable-logging=stderr` grep `MIME|Failed to load`；截图字节数对比（白屏 ~5KB vs 正常 100KB+）
- 完整原理见 `capacitor-mobile-app-fixes` 技能「深层路由白屏」节

**② 模拟考试只有选项没题目（exam API 缺 passage）**：
- 症状：考试页显示「选择最佳选项填入第 N 空」+ 选项——**没有文章/上下文**——选词填空/阅读题无法作答
- 根因：`exam.py` 的 session detail 只 SELECT `q.stem`（短指令）+ options——**unit.passage（文章）没返回**
- 修复：SELECT 加 `u.passage, u.unit_type` → questions.append 加 `"passage": (q["passage"] or "").replace("\r\n","\n").strip()`；前端 ExamView 题干下渲染 `<div v-if="currentQuestion.passage" class="exam-passage">`（`white-space: pre-wrap` + max-height 34vh overflow-y auto）
- 排查：`serialize_unit`（练习）正常 ≠ exam API 正常——练习走 questions.py，考试走 exam.py 独立 SELECT，**两处都要查**

**③ 学习报告 500（report.py vocab learned None）**：
- 症状：`GET /api/report` 500（report/weekly、report/stats 正常）
- 根因：`report.py` L184 `if vocab and vocab["learned"] < 100`——用户无词汇学习记录时 `vocab["learned"]` 是 **None**（SQL 聚合无行）→ TypeError `< not supported between NoneType and int`
- 修复：`(vocab["learned"] or 0) < 100`——**SQL 聚合无行返回 None 的所有比较位都要 or 0 兜底**
- 排查：直接 Python 调 `get_report(connect())` 看 traceback（比 curl 500 快）——`from app.routers.report import get_report; from app.database import connect`
- **⚠️ 数据库路径**：后端主库是 `backend/data/question_bank.db`（DATABASE_PATH 配置）——`data/english_machine.db`（0 字节）是残留空文件不是后端用的，别被误导

**验证**：三处源码断言 + curl `/api/report` 200（修复前 500）+ headless `/#/practice/1` 渲染（计时弹窗）+ headless `/#/exam?id=1` 文章显示 + 9/9 验证脚本（见会话 2026-08-10）。

### 59. 我的墨题（版本号/开发时间/检查更新，v3.3-beta.15）

用户要求"所有端加一个我的墨题：显示版本号和开发时间、点击检查更新（有新版可获取、无则显示已为最新版）"。实现 = 后端 `/api/version` + 前端 AboutView + 设置页入口：

**后端 `/api/version`**（main.py，health 后）：
```python
APP_VERSION = "2.0.0-beta.15"
APP_RELEASE_DATE = "2026-08-10"
_UPDATE_REPO = "mo9652962-ai/epm-releases"

@app.get("/api/version")
def get_version() -> dict:
    latest = None
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{_UPDATE_REPO}/releases/latest",
                                     headers={"User-Agent": "epm-update-check"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            latest = json.loads(resp.read().decode("utf-8")).get("tag_name")
    except Exception:
        latest = None
    return {"version": APP_VERSION, "release_date": APP_RELEASE_DATE,
            "latest_version": latest, "update_url": f"https://github.com/{_UPDATE_REPO}/releases/latest"}
```

**⚠️ 后端 urllib 查 GitHub 在 uvicorn 环境可能返回 None 而直连成功（v3.3 真踩）**：`curl https://api.github.com/...` 200、`python -c` urllib 直连成功，但**后端进程内 urllib 稳定 None**（except 吞异常、uvicorn 日志无输出）——代理环境（HTTPS_PROXY）在后台进程的继承差异 + GitHub API 慢。**别再猜——前端统一直接 fetch GitHub API**（`api.github.com` 允许 CORS，桌面/移动端通吃，10s AbortSignal.timeout）：
```ts
const resp = await fetch(`https://api.github.com/repos/${UPDATE_REPO}/releases/latest`,
  { headers: { Accept: 'application/vnd.github+json' }, signal: AbortSignal.timeout(10000) })
const tag = (await resp.json()).tag_name || ''
```
后端 `/api/version` 保留（返回版本信息），latest 字段可留可不管（前端不依赖）。

**beta 版本比较**（`2.0.0-beta.16 > 2.0.0-beta.15`；正式版 > 任何 beta）：
```ts
function isNewer(latestTag: string, current: string): boolean {
  const norm = (v: string) => {
    const m = v.replace(/^v/, '').match(/(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?/)
    if (!m) return [0, 0, 0, 999]
    return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] ? Number(m[4]) : 999]
  }
  const a = norm(latestTag), b = norm(current)
  for (let i = 0; i < 4; i++) if (a[i] !== b[i]) return a[i] > b[i]
  return false
}
```

**⚠️ Vue 模板 v-if/v-else 配对坑（v3.3 真踩，编译报 `Cannot read properties of undefined (reading 'type')`）**：`<CheckCircle2 v-if="!hasNew" />{{ result }}<template v-else>...` —— **v-else 必须紧跟 v-if 元素，中间不能有文本节点**（`{{ result }}` 隔断 → vue compiler 崩溃，错误信息极隐晦）。修复：把文本收进 `<template v-if>` 内：
```html
<template v-if="!hasNew"><CheckCircle2 :size="16" />{{ result }}</template>
<template v-else><Sparkles :size="16" />{{ result }}<a ...>获取最新版</a></template>
```
**排查：vue-tsc 报"undefined (reading 'type')"且定位在 .vue 模板 → 先查 v-if/v-else 之间是否被文本/注释隔断**。

**入口**（设置页反馈卡后）——`href="#/about"`（hash 路由直接用链接，不用 RouterLink import）：
```html
<article class="card"><div class="card-header"><div><span class="eyebrow">ABOUT</span><h2>我的墨题</h2>
<p>查看版本号、开发时间与检查更新</p></div><a class="button ghost" href="#/about">v2.0.0-beta.15 →</a></div></article>
```
AboutView 页面：墨字 logo + 当前版本/开发时间/更新通道三行 + 检查更新按钮 + 结果（`已为最新版 ✅` 绿 / `发现新版本 vX + 获取最新版链接` 橙 / `无法连接更新服务器`）。

**验证**：源码断言（APP_VERSION/RELEASE_DATE/checkUpdate/isNewer/已为最新版/获取最新版）+ 路由 `/about` + 设置页 `#/about` + dist 含"我的墨题"/"检查更新" + headless `/#/about` vision（版本/日期/按钮显示）+ 15/15 脚本。



### 60. 离线词库同步（手机端高频/热点全 0 的根因，v3.4 真踩）

**⚠️ 手机 App 用的是内置离线库，不是后端数据库**：Capacitor App 走 sql.js 离线模式（api-adapter.ts：`Capacitor.isNativePlatform()` 直接切离线），数据源是打包进 APK 的 `frontend/public/question_bank.db`。后端库更新（新词/高频标记/热点标记/语境释义）后**必须同步内置库 + 重新打包**，否则手机端显示旧数据。

**症状特征**：手机端「全部单词 7751」但后端库 7965——词数不一致 + 高频生词/热点/待复习统计全 0（旧库没有 manually_frequent/category 标记）。**对比两库词数就能定位**（`frontend/public/question_bank.db` vs `backend/data/question_bank.db`）。

**同步步骤**：
```bash
# 1. 备份内置库
cp frontend/public/question_bank.db frontend/public/question_bank.db.bak-<日期>
# 2. 后端库 → 内置库（整体替换；手机学习进度在 localStorage/sql.js 内存，不在此库）
cp backend/data/question_bank.db frontend/public/question_bank.db
# 3. 验证
python -c "import sqlite3; c=sqlite3.connect('frontend/public/question_bank.db'); print(c.execute('SELECT COUNT(*) FROM vocabulary_entries').fetchone()[0], c.execute('SELECT COUNT(*) FROM vocabulary_entries WHERE manually_frequent=1').fetchone()[0])"
# 4. 重新 build + cap sync + gradle 打包（§51 坑：cap sync 复制 dist 不是 public，必须先 npm run build）
```

**APK 内库验证**（打包后确认生效）：`zipfile` 读 APK 内 `assets/public/question_bank.db` → sqlite 查词数/高频数——断言 7965/5707 才交付。

### 61. Android 发音无声修复（原生 TTS 插件，v3.4 真踩）

**⚠️ Web Speech API（speechSynthesis）在 Android WebView 经常无声**：TtsButton/DictationMode 原用浏览器原生 TTS，Android 上依赖系统 TTS 引擎（国产手机未启用 Google TTS 英语语音包 → 点击🔊无反应）。

**修复（统一 TTS 服务，原生优先/Web 回退）**：
1. 安装插件：`npm install @capacitor-community/text-to-speech@8.0.2`（Capacitor 8 兼容）+ `npx cap sync android`
2. 新建 `frontend/src/services/tts.ts`：
```ts
import { Capacitor } from '@capacitor/core'
import { TextToSpeech } from '@capacitor-community/text-to-speech'
export async function speak(text: string, rate = 0.9): Promise<void> {
  const clean = String(text||'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim()
  if (!clean) return
  if (Capacitor.isNativePlatform()) {
    try { await TextToSpeech.stop(); await TextToSpeech.speak({ text: clean, lang: 'en-US', rate }); return }
    catch (e) { console.warn('原生 TTS 失败，回退 Web:', e) }
  }
  // Web 回退 speechSynthesis（原有逻辑）
}
export async function stop(): Promise<void> { /* 原生 stop + speechSynthesis.cancel */ }
```
3. 改 TtsButton.vue + DictationMode.vue：移除直接 speechSynthesis，调 tts 服务
4. **⚠️ 命名冲突坑**：组件里本地函数若命名 `speak` 会遮蔽 import 的 `speak`——本地函数改名（如 `playWordSound`），调用 import 的 `speak`；`onUnmounted` 用 `stop as stopTts`
5. 插件注册确认：`android/app/capacitor.build.gradle` 出现 `implementation project(':capacitor-community-text-to-speech')`（APK 内类名不显示为文件名，grep gradle 才是正确验证）
6. 若重装后仍无声：检查手机 **设置 → 系统 → 语言与输入法 → 文本转语音输出** 是否启用引擎（vivo 自带讯飞/搜狗，英语需选英语语音包）

### 62. 选词填空答题区遮挡文章（v3.4 真踩，用户"这个遮挡文章啊"）

**⚠️ 移动端竖屏 blank-picker-dock 遮挡文章根因**：`.blank-picker-dock` 原 `position: sticky; bottom: 14px; max-height: 46dvh`——sticky 元素**在文档流里占位**，竖屏上下分区（文章 58% + 题目区 42%）里 46% 视口高的 dock 超出题目区向上溢出 → 推挤并遮挡文章。

**修复（移动端 fixed 底部浮层，不占文档流）**：
```css
@media (max-width: 980px) {
  .blank-picker-dock {
    position: fixed;
    left: 12px;
    right: 12px;
    bottom: calc(60px + env(safe-area-inset-bottom, 0px));  /* 底部导航上方 */
    margin: 0;
    max-height: 42dvh;                                       /* 收窄减少覆盖 */
    box-shadow: 0 -6px 28px rgba(0,0,0,.16), 0 2px 10px rgba(0,0,0,.08);
  }
  .blank-picker-options { grid-template-columns: 1fr 1fr; }
}
```
- 桌面端保留 sticky（双栏布局无遮挡）；只有 ≤980px 移动端改 fixed
- dock 已有「收起 ✕」按钮（用户可收起看文章）
- **排查习惯：用户报"弹层/答题区遮挡文章/内容"→ 先查该浮层是否 sticky 占文档流 + max-height 是否超过所在容器高度；移动端底部浮层一律 fixed + bottom 导航上方**

### 62b. 四级模拟卷文章遮挡（v3.4 同轮，ExamView 与 §62 不同页面）

**⚠️ ExamView 的 `.exam-passage` 文章文字溢出覆盖问题框（不是 blank-picker）**：`max-height: 34vh + overflow-y: auto` 在手机 WebView 滚动失效（无 `-webkit-overflow-scrolling`）→ 文章文字溢出容器延伸到问题区，且 `.exam-question` 背景是半透明（`--surface` 92%）→ 问题框透出文章文字 = 视觉遮挡。

修复（styles.css）：
```css
.exam-passage { ... max-height: 34vh; overflow-y: auto;
  -webkit-overflow-scrolling: touch; overscroll-behavior: contain; }  /* 滚动在 WebView 生效 */
.exam-question { background: var(--surface-solid, var(--surface)); position: relative; isolation: isolate; }  /* 不透明背景防透字 */
```
- **排查习惯："文章被问题框遮挡/透字"→ 两个方向一起查：①文章容器滚动是否在 WebView 生效（补 -webkit-overflow-scrolling）②下层卡片背景是否半透明（提实 surface-solid）**——v3.4 的 PracticeView（§62）和 ExamView（本段）是同一次用户反馈"遮挡文章"的两个不同页面

### 63. 离线 api-adapter 分支缺口（v3.4 真踩，一次会话 3 个 bug 同根因）

**⚠️ 手机 APK 走 sql.js 离线模式（api-adapter.ts），后端每个接口都必须在 api-adapter 有离线分支**——`api.ts` 在 `isOffline()` 时把 get/post/put 全部路由到 api-adapter 的 `offlineGet/offlinePost/offlinePut`。**后端新增接口但漏写离线分支 = 请求落空返回 `undefined`** → 前端静默失败或崩溃。一次会话连踩 3 个：

| Bug | 症状 | 根因 |
|:---|:---|:---|
| AI 同步模型 | `同步失败：TypeError: Cannot read properties of undefined (reading 'length')` | 离线 `POST /ai/profiles/{id}/models/sync` 无分支 → 返回 undefined → 前端 `result.models.length` 崩溃 |
| AI 文章练词 | 点"重新生成"没反应（文章区空）| 离线 `GET /vocabulary/article` 无分支 → undefined → 前端 v-if 不渲染（静默）|
| 练习答题 | `UNIQUE constraint failed: practice_answers.session_id, question_id` | 离线 `PUT /practice/sessions/{id}/answers/{qid}` 用**纯 INSERT**（后端桌面版早已 UPDATE/INSERT OR IGNORE）→ 重复提交同一题冲突 |

**规则**：
1. **后端加接口 → 同步检查 api-adapter 离线分支**：`grep -n "<path>" frontend/src/services/api-adapter.ts`——没有就补。前端调用的每个 API 路径都要在离线 adapter 有对应处理（§35/§38 的"前端调用的每个 API 路径都要 grep 后端确认存在"的离线版）
2. **写操作一律 UPSERT**：离线 sql.js 用 `INSERT ... ON CONFLICT(<唯一键>) DO UPDATE SET ...`（`excluded.` 引用新值）——练习答案 `(session_id, question_id)`、考试答案 `(exam_id, question_id)` 都踩过纯 INSERT 冲突
3. **返回结构必须匹配前端期望**：前端 `result.models.length` → 返回 `{models: []}` 数组（不是 undefined）；`articleData.words` → 返回 `{words, article, article_html}`。**离线分支可以返回空数组/模板数据，但不能返回 undefined**
4. **离线可做的功能用本地实现**：AI 文章练词离线用模板生成（从 `vocabulary_entries` 取 `study_status='learning'` 弱词 + 主题句式模板拼短文，返回与桌面端同结构）；模型同步从 `ai_profile_models` 表读本地模型

**离线分支补写模式**（api-adapter.ts 的 offlinePost/offlinePut 里）：
```ts
// 例：练习答题 UPSERT（v3.4 修复）
const am = path.match(/^\/practice\/sessions\/(\d+)\/answers\/(\d+)$/)
if (am) {
  // ...
  execute(
    `INSERT INTO practice_answers (session_id, question_id, user_answer, is_correct, answered_at)
     VALUES (?, ?, ?, ?, datetime('now'))
     ON CONFLICT(session_id, question_id)
     DO UPDATE SET user_answer = excluded.user_answer, is_correct = excluded.is_correct, answered_at = excluded.answered_at`,
    [sid, qid, body?.answer ?? '', isCorrect ? 1 : 0]
  )
  return { ok: true, is_correct: isCorrect }
}
```

**排查习惯：手机端功能"点了没反应/报 TypeError undefined/报 UNIQUE constraint"→ 第一排查项 = api-adapter.ts 有没有对应离线分支**（`grep -n "路径" api-adapter.ts`）；有分支但报 UNIQUE → 查是不是纯 INSERT（改 UPSERT）。

### 64. 启动动画与 app 挂载联动（v3.4，网页/Windows 版 splash）

**网页版/Windows 版启动动画 = index.html 内联 #splash（水墨印章 + 远山 + 墨滴 + 进度条）**——FastAPI 伺服 `frontend/dist`（EPM_FRONTEND_DIST 配置），`npm run build` 后重启后端即生效（不涉及 APK 原生 splash）。

- **核心改进：动画与 app 挂载联动淡出，不固定时长**（模仿移动端 splash：加载时显示 → 加载完平滑过渡）：
```ts
// main.ts bootstrap() 内 createApp().mount('#app') 之后
requestAnimationFrame(() => {
  requestAnimationFrame(() => {
    const s = document.getElementById('splash')
    if (s && !s.classList.contains('hide')) {
      s.classList.add('hide')
      setTimeout(() => s.remove(), 550)
    }
  })
})
// index.html 内保留 2.9s 兜底 setTimeout（挂载异常也能消失，双保险）
```
- **增强**：印章呼吸动画（`sealIn` 弹入 + `sealPulse` 无限脉动 `scale(1)→1.05`）——移动端 App logo 常见效果
- **⚠️ 品牌文案规范（v3.4 用户纠正："所有的启动动画只要墨题就好了，不要加什么刷题器"）**：启动动画（及任何品牌展示面）只展示品牌名**「墨题」**，**不出现「刷题机/刷题器」字样**——印章「墨题」+ 标题「墨 题」+ 副标题「真题 · 单词 · 精进」+ 标语「于墨香中提笔，在真题里精进」+ 进度条。副标题/标语也不含"刷题"（用户对产品类型词敏感）。改动后验证：源码 + dist 的 splash 区块 `"刷题机" not in content`（HTML 注释里也不能写该词——注释会原样进 dist，第一次验证就因注释误报）
- 用户说"加启动动画"时先确认运行的是**新构建**（旧 dist 没有 splash）；Windows 版重启后端（伺服新 dist）即可看到
- **⚠️ 本地加载极快 → 动画一闪而过（v3.4 用户二次反馈"还是没有启动动画"）**：Windows 本地 FastAPI + 本地文件加载 <300ms，`requestAnimationFrame` 双帧后立即淡出 → splash 刚出现就被删（用户以为没有动画）。修复：**最小展示时长 1.8s**——index.html 记录 `window.__SPLASH_START__ = performance.now()`，main.ts 挂载后算 `minShow = Math.max(0, 1800 - elapsed)` 再 setTimeout 淡出。这样本地快加载至少看 1.8s 动画；慢网络加载完立即淡出。**"看不到动画"排查链：①是否新构建（dist 含 splash）②是否重启后端 ③浏览器强刷（Ctrl+F5 清缓存）④最小展示时长逻辑在不在（__SPLASH_START__/1800）**

### 65. CSS 高特异性覆盖坑（v3.4 真踩，"去练习"按钮位置不对）

**⚠️ 高特异性选择器覆盖全局样式**：全局 `.stat-link { position: absolute; right: 18px; bottom: 16px }`（右下角定位），但 `.recommend-paper .stat-link`（特异性 0,2,0 > 0,1,0）覆盖了它**却没有 position:absolute** → 按钮变成文档流内元素（卡片中间底部），用户反馈"按钮不在右下角"。

**修复**：高特异性类里补回被覆盖的定位属性：
```css
.recommend-paper .stat-link {
  color: var(--accent); font-size: 12px;
  display: inline-flex; align-items: center; gap: 4px;
  position: absolute; right: 18px; bottom: 14px;  /* 补回全局定位 */
}
```

**排查习惯：用户报"某元素位置不对/样式没生效"→ 先看是否有更高特异性的选择器覆盖（`.xxx .yyy` > `.yyy`），子类覆盖父类时补全被覆盖的属性而不是删子类**——删子类会丢它自己的定制（颜色/字号）。全局定义 + 局部覆盖是 CSS 常规模式，局部要"完整"。

## Related

## Related

- 功能设计来源：竞品对标（扇贝=词文串学/听力真题、墨墨=分级词书、刷刷题=五练习模式/模拟考试、练题狗=AI推题/学习报告）——扩展功能时先搜竞品再落地
- **AI 基础设施现状 + P0/P1 设计稿（2026-08-15 盘点，做 AI 功能前先读）**：`backend/app/services/ai_client.py` 已是 OpenAI-compatible 通用客户端（chat_completion 支持 base_url+key+model+response_format；ai_profiles 表多 Provider；模型发现支持 openai /v1/models + ollama /api/tags 双格式；429/500 重试 3 次；key DPAPI 加密）——**DeepSeek/百炼/本地 Qwen（llama.cpp OpenAI 端点）天然兼容**，不用重写客户端。`wrong_analysis.py` 已有 12 分类错题归因（vocabulary/collocation/grammar/context/discourse/detail/inference/main_idea/attitude/trap/carelessness/uncertain）+ 专业 prompt（recency 加权/证据不足用 uncertain/防泄漏不输出题目文字）+ previous_snapshot 对比雏形。**缺口**：P0=归因聚合→学习诊断报告（薄弱点排行/水平评估/行动闭环，AI 只做归因+轻量水平判断，聚合/推荐全本地）；P1=任务路由表（wrong_diagnosis→云端主/本地备/缓存兜底）+ 降级链 + ai_usage 用量表（本地 Qwen3-8B 8K 上下文只适合批量短任务，不适合长文归因）。完整设计稿：`C:\Users\31954\.openclaw\workspace\knowledge\Dev\墨题-P0错题AI诊断设计稿-2026-08-15.md` + `墨题-P1-AI服务层架构设计-2026-08-15.md`
- 刷题机运行状态/环境事实存于 memory（基元律动配置、DB 字段、打包坑）
- 记忆算法/学习研究结论见 `references/learning-research.md`
- ESQ 包完整格式/导入步骤/表结构速查见 `references/esq-import-pipeline.md`
- 各真题/词库数据源可用性与解析格式见 `references/question-data-sources.md`
- 真题图片 OCR 提取管道（tesseract + 启航考研源）见 `references/ocr-exam-images.md`
- 2025 高考真题官方图下载→OCR→解析→导入→AI 答案全管道见 `references/gaokao2025-ocr-import.md`（v2.94 实测 33 题，含 DeepSeek 推理模型答案生成坑）
- AI 生成真题风格模拟题的 prompt 模板/级别风格/断点续跑见 `templates/ai-exam-generation-prompt.md`
