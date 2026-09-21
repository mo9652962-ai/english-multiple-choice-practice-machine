# 墨题（英语刷题机）· Agent 交接文档

> 供 AI Coding Agent（Hermes/Codex 等）接手时直达根因。最后更新：2026-09-13（版本/内容发布门禁、学习闭环与本地指标落地）。

## 知识库优先规则（2026-09-04 补充，来自「AI不翻知识库」研究）

- 接手任何任务 → 先查本项目 AGENTS.md + 相关 skills，再动手，不要凭空发挥
- 涉及领域知识（英语教学/题库/ESQ 格式/词汇标注）→ 先查团队知识库 knowledge/ 对应分类
- 解决完新问题 → 沉淀回知识库或更新本文件（learn→research→apply）
- 项目规则层（本文件）是强制约束；记忆/会话是辅助召回，不能替代本文件

## 项目一句话

本地优先的英语客观题刷题工具（考研/四六级/高考），Windows Web + Android（Capacitor），题库自由导入（Word/ESQ），AI 辅助（错题归因/词汇/标注）但**不依赖 AI 也能刷题**。

## 技术栈与目录

| 层 | 技术 | 位置 |
|:---|:---|:---|
| 前端 | Vue 3 + Vite + vue-router（hash）| `frontend/src/`（views/ 每页一个，api.ts 封装 fetch）|
| 后端 | FastAPI + sqlite3（原生，无 ORM）| `backend/app/`（routers/ + services/）|
| 数据库 | SQLite，多库 | `backend/data/*.db`（app.db 主库）|
| 移动端 | Capacitor 8.5 | `frontend/android/`（生成目录，不入库；CI 先 `cap add android` 再 `cap sync` → `gradlew assembleDebug`，JDK21）|

**路由注册**：`backend/app/main.py` 顶部 import + `app.include_router(...)`（prefix 有 `/api` 和 `""` 两种）。
**数据库迁移**：`backend/app/database.py` 的 `_run_migrations()`——新列用 `_ensure_column(conn, table, column, declaration)`（幂等），新表直接 `CREATE TABLE IF NOT EXISTS`。

## ⚠️ 三库同步规则（改数据必看）

- `backend/data/app.db`（后端主库）+ `frontend/public/question_bank.db`（Web 端内置离线库）+ 手机端内置库
- **改后端词库数据 → 必须同步前端离线库 + 重新打包 APK**，否则三端不一致
- 改**代码**不影响（代码走 API）；改**数据**才需要同步

## P0/P1 已落地（2026-08-15）——AI 学习诊断

### 调用链总览

```
前端 DiagnosticView.vue (/diagnostic)
  → POST /api/diagnostic/report {question_ids, previous_report_id}
    → services/diagnostic_report.py generate_diagnostic_report()
      ├─ wrong_analysis.diagnose_wrong_answers()  # 逐题归因（12 分类，AI）
      ├─ wrong_analysis.aggregate_diagnoses()     # 本地聚合（cause 分布/百分比/置信度）
      ├─ assess_level()                           # 水平 1-5（AI，只输入匿名统计）
      ├─ build_recommendations()                  # 推荐练习（本地 SQL，不调 AI）
      ├─ compare_snapshots()                      # 与上次报告对比（本地）
      └─ _save_report()                           # 持久化 diagnostic_reports 表
```

### AI 服务层（P1）

- `services/ai_client.py`：OpenAI-compatible 通用客户端（`chat_completion(connection, messages, profile_id=...)`），多 profile（ai_profiles 表：base_url/api_key_encrypted/enabled/is_default/default_model/temperature/max_tokens/**task_tags**/**priority**），内置 429/5xx 重试 + response_format 降级。
- `services/ai_router.py`（新增）：`chat_with_routing(connection, task, messages)`——按 **task_tags 匹配任务 + priority 升序**轮询候选 profile，失败降级下一个，全失败抛「AI 服务暂不可用」。每次调用记录 `ai_usage` 表（task/provider/tokens/latency/status）。当前任务名包括 `wrong_diagnosis`、`vocab_labeling`、`import_assist`、`question_labeling`、`essay_grading`、`article_generate`、`deep_explain`、`speaking_practice`、`rag_qa`、`similar_questions`、`chat_explain`、`connection_test`、`ocr_fallback`、`agent_analyze` 和 `agent_plan`。
- **存量迁移**：wrong_analysis、vocabulary、import_assist、question_labeling、essay、deep-explain、speaking、RAG、文章、相似题、聊天和连接测试均走 `chat_with_routing`；新增 AI 任务不得绕过任务路由。

### 诊断服务（P0）

- `services/diagnostic_report.py`（新增）：
  - `assess_level()`：AI 水平评估 1-5（prompt 只给匿名统计，防泄漏）；AI 失败→`_fallback_level()` 本地估算
  - `build_recommendations()`：薄弱 cause → `_CAUSE_TO_UNIT_TYPE` 映射 → SQL 筛同类型未做过的题（`ORDER BY RANDOM()`），carelessness/uncertain 无推荐
  - `compare_snapshots()`：improved/worsened/new
- `routers/diagnostic.py`（新增）：`POST /api/diagnostic/report`、`GET /api/diagnostic/report/{id}`、`GET /api/diagnostic/reports`
- 前端：`DiagnosticView.vue`（/diagnostic 路由，App.vue 导航 + WrongView「🧠 学习诊断」入口）
- 复用（勿重复造）：`wrong_analysis.py` 的 `aggregate_diagnoses`/`write_anonymous_report`（匿名报告防泄漏——聚合后只给白名单建议）/`wrong_analysis_reports` 表

## 🕳️ 关键坑（Codex 直达根因）

1. **导入必挂历史坑**：`upsertKnowledgeItem` SQL 引用 `@sourceType` 参数——**任何调用必须传 sourceType**（sync 传 "github"，import 传 "community"，手写 INSERT 别漏）
2. **ai_profiles.task_tags 是「任务名数组」**（`["wrong_diagnosis","vocab_labeling"]`），不是 cloud/local 组标签——`_task_profiles` 用 `task in tags` 匹配。优先级 = `priority` 列（升序，本地优先调小）
3. **诊断测试要造数据**：`diagnose_wrong_answers` 要求题目有作答记录（practice_answers + practice_sessions 外键链：先建 session 再插 answers + wrong_stats），否则「没有可分析的错题记录」。参考脚本见下
4. **真实 AI 调用慢**：一次诊断 81s（归因 + 水平 + 报告 3 次调用）——测试别频繁跑，用 mock 或本地降级路径
5. **前端 get/post**：`frontend/src/api.ts` 导出 `get(path)`/`post(path, body)`；路由在 `frontend/src/router.ts`；图标从 `lucide-vue-next` import 到 App.vue 才能用
6. **python 直接跑**：`cd backend && python -c "from app.database import connect; conn = connect()"`（get_db 是 generator，迭代后自动关；connect() 手动关）
7. **vite build 被 Hermes 误判为 server**：用 background 跑；vue-tsc 在 frontend/ 下跑 `npx vue-tsc --noEmit`
8. **多用户迁移要覆盖新旧库**：`initialize_database()` 必须在 `SCHEMA` 前后都运行 `_migrate_add_user_id()`；旧库需要补列，fresh schema 也必须直接包含 `practice_sessions.user_id`，否则练习和 Dashboard 查询会在测试/首次启动时崩溃。
9. **发布版本双轨**：程序版本来自 `VERSION`；题库发布版本来自 `CONTENT_VERSION`；Web/Android 离线种子来自 `OFFLINE_CONTENT_VERSION`。不要因为后端扩展库与离线种子 hash 不同就直接覆盖，发布报告必须同时记录两者 hash、schema 和计数。
10. **Android 生成目录**：`frontend/android/` 是 Capacitor 生成且被忽略的目录；原生插件模板在 `frontend/native/android/`，干净 checkout 后必须执行 `npx cap add android`、`npx cap sync android`、`node scripts/sync_android_plugins.mjs` 和 `node scripts/sync_android_version.mjs`。Capacitor 8 的生成/同步环境固定 Node.js 22+，CI 显式安装 Android SDK 36、Build Tools 36.0.0 和 Emulator，再进行 Gradle 构建、APK 资源校验，以及 `node tools/android_runtime_smoke.mjs` 的 Android Keystore round-trip、安装启动和重启检查。
11. **AI 任务路由**：错题分析、词汇翻译、导入辅助、题目标注、作文、精讲、口语、RAG、文章、相似题和学习智能体均使用 `services.ai_router.chat_with_routing()`；新增 AI 功能先登记 `KNOWN_TASKS`，再提供结构化输出和无模型回退。`model_pool`/`ai_router` 内部直接调用 `chat_completion` 属于底层实现，不作为业务入口。
12. **核心流程门禁**：`tests/test_learning_flow.py` 是无私有题库、无 AI 依赖的本地学习闭环冒烟测试；修改练习、错题或词汇接口后必须保留并扩展此类测试。
13. **指标隐私**：`/api/metrics` 默认关闭；只有用户在设置页明确同意后才记录 allow-list 事件，且只保留次数/短元数据，不记录题目正文、答案或 API Key。关闭同意时清空本地指标。
14. **前端 bundle/离线门禁**：Vite 构建必须保留 manifest；CI、Windows Release 和 Android CI 统一用 `node tools/check_frontend_bundle.mjs --max-entry-kb 512 --max-lazy-kb 1024` 检查入口 JS 与按需 chunk，并用 `node tools/check_offline_seed.mjs --db frontend/dist/question_bank.db --migrations frontend/dist/offline_migrations.json` 检查离线核心表和迁移清单；VAD/Whisper/ONNX 等按需资源不得回流首屏，继续拆分时必须保持在 1 MB 移动端门禁内。
15. **题库发布质量门禁**：Release 使用 `tools/release_check.py --strict-quality`（PowerShell 包装器对应 `-StrictQuality`）检查空结构、缺答案、答案不在选项、重复选项标签和重复内容哈希；完形题可不填单题 stem，但必须有整篇 passage。
16. **错题复习调度**：`spaced_repetition_records.fsrs_*` 是题目复习的事实来源，`interval_days/ease_factor/due_date` 仅为旧客户端兼容字段；诊断推荐完成后应进入 `/review/queue`，不要重新实现一套固定间隔算法。
17. **AI 本地缓存**：`services.ai_router.chat_with_routing()` 只缓存确定性任务（精讲、标注、导入辅助等），缓存 key 必须包含任务、输入、模型/格式和 user_id；聊天、口语、作文默认不缓存，缓存命中不应消耗每日 provider 配额。
18. **离线迁移清单**：`frontend/public/offline_migrations.json` 同时包含表、索引和可幂等补列的 `column` 对象；修改离线 schema 后必须运行 `node tools/check_offline_seed.mjs ...` 和 `node tools/check_offline_runtime.mjs ...`，后者覆盖旧库与新库，不能只验证 sqlite_master。
19. **公开发布证据**：正式 Windows release 强制 `--require-publishable-provenance`；`NOASSERTION`、`pending` 或仅有字段没有核验记录的题包不得公开发布。证据填写边界见 `docs/content-release-evidence.md`，不要为了过门禁虚构许可证、来源或人工审核。
20. **诊断练习交接**：`diagnostic_report.build_recommendations()` 返回的 `practice_path.question_ids` 是完整可执行题集，前端优先使用它启动针对性练习；`PracticeCreate(mode="random", question_ids=[...])` 必须只序列化这些题，不得退化成整篇；练习提交后应回到 `/review/queue`，旧报告没有该字段时才回退到 `sample_questions`。
21. **Windows 发布包启动门禁**：后端 exe smoke 不能替代桌面包 smoke；Release 构建 portable 包后必须运行 `scripts/windows_portable_smoke.ps1 -Port 18765`，确认 Electron 实际拉起后端并核对 `/api/health`、程序版本、内容版本和 Schema。Electron 默认端口仍是 8765，smoke 通过 `EPM_PORT` 隔离开发服务；NSIS 安装器在无人值守 CI 中只做产物存在性检查。
22. **AI 配额统一入口**：`chat` 和 `speaking` 路由不要再手动执行 `check_daily_quota` 或 `record_user_usage`；统一交给 `chat_with_routing()`，否则一次用户请求会被重复计数。缓存命中仍不消耗 provider 配额，新增 AI 入口必须保留 `QuotaExceeded` 到 HTTP 429 的映射。
23. **🔴 密钥绝不进库（本项目已踩）**：`epm_app/unpackage/cache/certdata` 含明文 keystore 密码、`cloudcertificate/package.keystore` 是证书文件——**均曾在 commit `5797176`/`42bef08` 进公开仓库**（2026-08-06），历史泄露待清除。当前 HEAD 已移出（`70ec87b`）+ `.gitignore` 覆盖 `epm_app/unpackage/`。提交前必查：`git ls-files | grep -iE "certdata|keystore|\.jks$|\.p12$|\.pem$|\.env$"`。正式发布应轮换 keystore（现走 `EPM_ANDROID_KEYSTORE_PASSWORD` 环境变量，勿回退硬编码）。
24. **构建产物/演示媒体不进库**：`epm_app/unpackage/`（19MB，含 APK+keystore）、`docs/images/moti-website-demo.*`（12MB）、`docs/player.html`、`_keylink_home.png` 均已移出（`70ec87b`/`13f5b82`）。提交前 `git ls-files -z | xargs -0 du -k | awk '$1>2048'` 查大文件。
25. **依赖 lock 必须同步**：`frontend/package.json` 改依赖后**必须**跑 `npm install` 重建 `package-lock.json` 并提交——`npm ci` 是严格模式，版本漂移（如 vue ^3.5.42 vs 锁定 3.5.41）会让 CI 三 job **全部红**（`c85180b` 修复）。改完本地验：`npm ci --dry-run`。
26. **SSRF 白名单必须放行 fake-ip 网段**：FlClash 等代理工具把公网域名解析到 `198.18.0.0/15`（RFC2544），SSRF 防护若不放行会拦截合法 API（`api.deepseek.com` → `198.18.0.79`）→ 测试误报。`ai_client.py` 已放行该网段 + loopback（`c85180b`）。
27. **发布版本三轨同步**：`VERSION`（程序）/ `CONTENT_VERSION`（题库）/ `OFFLINE_CONTENT_VERSION`（离线种子）——漏一个 `tests/test_release_check.py` 就红。manifest 的 `content_version`/`offline_seed_version` 必须同步（曾落后 6 天，`c85180b` 修复）。改内容后跑：`python -m pytest tests/test_release_check.py tests/test_rebuild_public_content.py -q`。
28. **CI 触发条件必须匹配依赖输入**：`android.yml` 曾因两处必败长期红——①`setup-java cache: gradle` 在 `frontend/android/`（CI 生成、被 gitignore）不存在时失败（`f0f97a2`）；②`Install or require verified release content inputs` 要求离线种子库，但 `*.db` 被 gitignore（`12e1a2f` 改为 tag/手动触发）。依赖受控内容的构建不要挂在每次 push 上。
29. **测试数据必须来自真实常量**：`test_rebuild_public_content.py` 曾用不存在的 `cn.kaoyan2.simulated`（不在 `UNPUBLISHABLE_PACKAGE_IDS` 名单）→ 断言失败。写名单类测试前先 `python -c "from tools.rebuild_public_content import UNPUBLISHABLE_PACKAGE_IDS; print(...)"` 确认真值。
30. **git 路径遍历必须 `-z` + `quotePath=false`**：`git ls-files` 默认对非 ASCII 路径输出加引号转义形式，Windows git-bash 正常但 Linux CI 直接 `cp` 失败（本项目 219 个中文路径）。统一用：`git -c core.quotePath=false ls-files -z | while IFS= read -r -d '' f; do ...`

## 参考脚本

### 造错题 + 跑诊断（backend 目录）

```python
from app.database import connect, initialize_database
initialize_database()
conn = connect()
conn.execute("INSERT OR IGNORE INTO practice_sessions (id, mode, unit_ids, status, started_at, submitted_at) VALUES (999901, 'practice', '[1]', 'completed', datetime('now','-3 days'), datetime('now','-3 days'))")
for qid in [1, 2, 3]:
    conn.execute("INSERT OR IGNORE INTO practice_answers (session_id, question_id, user_answer, option_order, is_correct, answered_at) VALUES (999901, ?, 'B', '[]', 0, datetime('now','-3 days'))", (qid,))
    conn.execute("INSERT OR IGNORE INTO wrong_stats (question_id, attempt_count, wrong_count, recent_results, consecutive_correct, manually_frequent, last_wrong_at, last_attempt_at) VALUES (?, 3, 2, '[1,0,0]', 0, 0, datetime('now','-3 days'), datetime('now'))", (qid,))
conn.commit()
from app.services.diagnostic_report import generate_diagnostic_report
print(generate_diagnostic_report(conn, [1, 2, 3]))  # 真实 AI，~80s
# 清理：
conn.execute("DELETE FROM practice_answers WHERE session_id = 999901")
conn.execute("DELETE FROM practice_sessions WHERE id = 999901")
conn.execute("DELETE FROM wrong_stats WHERE question_id IN (1,2,3)")
conn.commit(); conn.close()
```

### AI 路由降级验证（mock，快）

```python
from unittest.mock import patch
from app.database import connect
conn = connect()
from app.services.ai_router import chat_with_routing
with patch("app.services.ai_router.chat_completion") as mock_chat:
    mock_chat.side_effect = [ValueError("模型服务暂时不可用，请稍后重试或切换 API 配置"), "ok"]
    print(chat_with_routing(conn, "wrong_diagnosis", [{"role": "user", "content": "hi"}]))  # ok（降级成功）
    print("usage 记录:", conn.execute("SELECT task, status FROM ai_usage ORDER BY id DESC LIMIT 2").fetchall())
conn.close()
```

## 后续路线

- [x] 存量调用迁移：vocabulary/import_assist/question_labeling 改走 `chat_with_routing`
- [ ] 本地 Qwen 接入：加 profile（base_url=http://127.0.0.1:8080/v1, task_tags 按任务, priority 调小做本地优先）——注意 8K 上下文不适合长文归因
- [x] ai_usage 用量统计 UI（设置页展示每月 token/失败率/任务分布；配额由统一路由执行）
- [ ] 诊断报告导出/分享（现在是页面内展示）
- [x] 推荐练习闭环：DiagnosticView 推荐题一键进入 PracticeView；Dashboard 同步承接最近诊断焦点

## 验证命令

```bash
cd backend && python -c "from app.main import app; print([r.path for r in app.routes if 'diagnostic' in getattr(r,'path','')])"  # 路由注册
cd frontend && npx vue-tsc --noEmit   # TS 类型
cd frontend && npx vite build          # 构建（用 background 跑）
```

---

## v9.26 更新（2026-08-20）——AI 三件套 + 性能 + 安全

### AI 三件套（Gemini 方案落地，全部走现有 AI 配置零新增依赖）

| 功能 | 后端 | 前端 | 成本 |
|:---|:---|:---|:---|
| **P0 真题精讲** | `POST /api/questions/{id}/deep-explain`（`backend/app/routers/explanations.py`）| `DeepExplainDrawer.vue`（练习页 ✨AI 精讲按钮）| 单题 ¥0.0034，缓存后 95% 零成本 |
| **P1 作文批改** | `POST /api/essays/evaluate` + `GET /api/essays[/{id}]`（`routers/essays.py`）| `EssayView.vue`（导航「作文精批」）| 单篇 ¥0.004 |
| **P2 口语陪练** | `POST /api/speaking/sessions[/{id}/turns|/finish]`（`routers/speaking.py`）| `SpeakingView.vue`（导航「口语陪练」，Web Speech API 浏览器原生语音）| 单轮 ¥0.001 |

**提示词位置**：`backend/prompts/explain_prompt.py`（DEEP_EXPLAIN_SYSTEM_PROMPT）/ `essay_prompt.py` / `speaking_prompt.py`——均为严格 JSON 输出 + response_format=json_object。

**关键坑**：
- 新表 `essay_submissions` / `speaking_sessions` / `speaking_turns` 在 `database.py` SCHEMA——**旧后端进程不会自动建表，重启（墨题启动.bat）后自动执行**；若手工测试先 `initialize_database()`
- `explanations.py` 的 `from prompts.explain_prompt import` 是**顶层导入**（prompts 是 backend 根的包，不是 app 子包）——`..prompts` 会 ModuleNotFoundError
- deep-explain 缓存命中条件：`content` 是 dict 且含 `options_analysis`（深度结构）；旧简单版解析不会命中深度缓存（会重新生成）

### 性能优化（2026-08-20）

- **路由全量懒加载**：`frontend/src/router.ts` 全部 `() => import(...)`——主 bundle 509KB→140KB（-72%，gzip 164→52KB）
- services 层：`local_similar_matches` 全表+Levenshtein → SQL 前缀候选池（LIMIT 200）；`translate_queued_vocabulary` 去掉 BEGIN IMMEDIATE 改原子 UPDATE 认领 + translating 10 分钟超时自愈；`label_next_unit` 失败熔断防毒丸死循环

### Gemini 审查已修（2026-08-20，安全）

- **P0 严重**：`question_labeling.py` 毒丸死循环（AI 失败 unit 永远重复选）→ 异常标记跳过
- **services 严重**：translating 僵尸状态（异常崩溃永久锁定）→ 超时自愈认领
- **Sims4 联机**（不同仓库）：lobby.py 路径穿越 RCE（filename 网络可控 → `_safe_save_filename` 白名单）、travel_ack 路由缺失（每次旅行 10s 超时）已修

### 后续路线补充

- [ ] UI 第四轮审查：Dashboard/单词本三页/登录/导入/题库库（问题包在桌面 gemini-moti-ui4.md，等 Gemini 方案）
- [ ] Sims4 架构级 4 项（主机迁移/存档竞态/多线程锁/离线级联——问题包在桌面 gemini-sims4-architecture.md）
- [ ] deep-explain 前端划词联动（点击解析中的单词弹词库释义）
- [ ] 作文批改多用户隔离（user_id 目前 NULL）


## 参考脚本

### 造错题 + 跑诊断（backend 目录）

```python
from app.database import connect, initialize_database
initialize_database()
conn = connect()
conn.execute("INSERT OR IGNORE INTO practice_sessions (id, mode, unit_ids, status, started_at, submitted_at) VALUES (999901, 'practice', '[1]', 'completed', datetime('now','-3 days'), datetime('now','-3 days'))")
for qid in [1, 2, 3]:
    conn.execute("INSERT OR IGNORE INTO practice_answers (session_id, question_id, user_answer, option_order, is_correct, answered_at) VALUES (999901, ?, 'B', '[]', 0, datetime('now','-3 days'))", (qid,))
    conn.execute("INSERT OR IGNORE INTO wrong_stats (question_id, attempt_count, wrong_count, recent_results, consecutive_correct, manually_frequent, last_wrong_at, last_attempt_at) VALUES (?, 3, 2, '[1,0,0]', 0, 0, datetime('now','-3 days'), datetime('now'))", (qid,))
conn.commit()
from app.services.diagnostic_report import generate_diagnostic_report
print(generate_diagnostic_report(conn, [1, 2, 3]))  # 真实 AI，~80s
# 清理：
conn.execute("DELETE FROM practice_answers WHERE session_id = 999901")
conn.execute("DELETE FROM practice_sessions WHERE id = 999901")
conn.execute("DELETE FROM wrong_stats WHERE question_id IN (1,2,3)")
conn.commit(); conn.close()
```

### AI 路由降级验证（mock，快）

```python
from unittest.mock import patch
from app.database import connect
conn = connect()
from app.services.ai_router import chat_with_routing
with patch("app.services.ai_router.chat_completion") as mock_chat:
    mock_chat.side_effect = [ValueError("模型服务暂时不可用，请稍后重试或切换 API 配置"), "ok"]
    print(chat_with_routing(conn, "wrong_diagnosis", [{"role": "user", "content": "hi"}]))  # ok（降级成功）
    print("usage 记录:", conn.execute("SELECT task, status FROM ai_usage ORDER BY id DESC LIMIT 2").fetchall())
conn.close()
```

## 后续路线

- [x] 存量调用迁移：vocabulary/import_assist/question_labeling 改走 `chat_with_routing`
- [ ] 本地 Qwen 接入：加 profile（base_url=http://127.0.0.1:8080/v1, task_tags 按任务, priority 调小做本地优先）——注意 8K 上下文不适合长文归因
- [x] ai_usage 用量统计 UI（设置页展示每月 token/失败率/任务分布；配额由统一路由执行）
- [ ] 诊断报告导出/分享（现在是页面内展示）
- [x] 推荐练习闭环：DiagnosticView 推荐题一键进入 PracticeView；Dashboard 同步承接最近诊断焦点

## 验证命令

```bash
cd backend && python -c "from app.main import app; print([r.path for r in app.routes if 'diagnostic' in getattr(r,'path','')])"  # 路由注册
cd frontend && npx vue-tsc --noEmit   # TS 类型
cd frontend && npx vite build          # 构建（用 background 跑）
```

---

## v9.26 更新（2026-08-20）——AI 三件套 + 性能 + 安全

### AI 三件套（Gemini 方案落地，全部走现有 AI 配置零新增依赖）

| 功能 | 后端 | 前端 | 成本 |
|:---|:---|:---|:---|
| **P0 真题精讲** | `POST /api/questions/{id}/deep-explain`（`backend/app/routers/explanations.py`）| `DeepExplainDrawer.vue`（练习页 ✨AI 精讲按钮）| 单题 ¥0.0034，缓存后 95% 零成本 |
| **P1 作文批改** | `POST /api/essays/evaluate` + `GET /api/essays[/{id}]`（`routers/essays.py`）| `EssayView.vue`（导航「作文精批」）| 单篇 ¥0.004 |
| **P2 口语陪练** | `POST /api/speaking/sessions[/{id}/turns|/finish]`（`routers/speaking.py`）| `SpeakingView.vue`（导航「口语陪练」，Web Speech API 浏览器原生语音）| 单轮 ¥0.001 |

**提示词位置**：`backend/prompts/explain_prompt.py`（DEEP_EXPLAIN_SYSTEM_PROMPT）/ `essay_prompt.py` / `speaking_prompt.py`——均为严格 JSON 输出 + response_format=json_object。

**关键坑**：
- 新表 `essay_submissions` / `speaking_sessions` / `speaking_turns` 在 `database.py` SCHEMA——**旧后端进程不会自动建表，重启（墨题启动.bat）后自动执行**；若手工测试先 `initialize_database()`
- `explanations.py` 的 `from prompts.explain_prompt import` 是**顶层导入**（prompts 是 backend 根的包，不是 app 子包）——`..prompts` 会 ModuleNotFoundError
- deep-explain 缓存命中条件：`content` 是 dict 且含 `options_analysis`（深度结构）；旧简单版解析不会命中深度缓存（会重新生成）

### 性能优化（2026-08-20）

- **路由全量懒加载**：`frontend/src/router.ts` 全部 `() => import(...)`——主 bundle 509KB→140KB（-72%，gzip 164→52KB）
- services 层：`local_similar_matches` 全表+Levenshtein → SQL 前缀候选池（LIMIT 200）；`translate_queued_vocabulary` 去掉 BEGIN IMMEDIATE 改原子 UPDATE 认领 + translating 10 分钟超时自愈；`label_next_unit` 失败熔断防毒丸死循环

### Gemini 审查已修（2026-08-20，安全）

- **P0 严重**：`question_labeling.py` 毒丸死循环（AI 失败 unit 永远重复选）→ 异常标记跳过
- **services 严重**：translating 僵尸状态（异常崩溃永久锁定）→ 超时自愈认领
- **Sims4 联机**（不同仓库）：lobby.py 路径穿越 RCE（filename 网络可控 → `_safe_save_filename` 白名单）、travel_ack 路由缺失（每次旅行 10s 超时）已修

### 后续路线补充

- [ ] UI 第四轮审查：Dashboard/单词本三页/登录/导入/题库库（问题包在桌面 gemini-moti-ui4.md，等 Gemini 方案）
- [ ] Sims4 架构级 4 项（主机迁移/存档竞态/多线程锁/离线级联——问题包在桌面 gemini-sims4-architecture.md）
- [ ] deep-explain 前端划词联动（点击解析中的单词弹词库释义）
- [ ] 作文批改多用户隔离（user_id 目前 NULL）
