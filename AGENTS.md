# 墨题（英语刷题机）· Agent 交接文档

> 供 AI Coding Agent（Hermes/Codex 等）接手时直达根因。最后更新：2026-08-15（P0/P1 AI 诊断落地）。

## 项目一句话

本地优先的英语客观题刷题工具（考研/四六级/高考），Windows Web + Android（Capacitor），题库自由导入（Word/ESQ），AI 辅助（错题归因/词汇/标注）但**不依赖 AI 也能刷题**。

## 技术栈与目录

| 层 | 技术 | 位置 |
|:---|:---|:---|
| 前端 | Vue 3 + Vite + vue-router（hash）| `frontend/src/`（views/ 每页一个，api.ts 封装 fetch）|
| 后端 | FastAPI + sqlite3（原生，无 ORM）| `backend/app/`（routers/ + services/）|
| 数据库 | SQLite，多库 | `backend/data/*.db`（app.db 主库）|
| 移动端 | Capacitor 8.5 | `frontend/android/`（APK 构建：cap sync → gradlew assembleDebug，JDK21）|

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
- `services/ai_router.py`（新增）：`chat_with_routing(connection, task, messages)`——按 **task_tags 匹配任务 + priority 升序**轮询候选 profile，失败降级下一个，全失败抛「AI 服务暂不可用」。每次调用记录 `ai_usage` 表（task/provider/tokens/latency/status）。
- **存量迁移**：wrong_analysis 已改走 `chat_with_routing`；vocabulary/import_assist/question_labeling 仍直连 `chat_completion`（可继续迁）。

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

- [ ] 存量调用迁移：vocabulary/import_assist/question_labeling 改走 `chat_with_routing`
- [ ] 本地 Qwen 接入：加 profile（base_url=http://127.0.0.1:8080/v1, task_tags 按任务, priority 调小做本地优先）——注意 8K 上下文不适合长文归因
- [ ] ai_usage 用量统计 UI（设置页展示每月 token/成本/降级率）
- [ ] 诊断报告导出/分享（现在是页面内展示）
- [ ] 推荐练习闭环：DiagnosticView 推荐题一键进入 PracticeView

## 验证命令

```bash
cd backend && python -c "from app.main import app; print([r.path for r in app.routes if 'diagnostic' in getattr(r,'path','')])"  # 路由注册
cd frontend && npx vue-tsc --noEmit   # TS 类型
cd frontend && npx vite build          # 构建（用 background 跑）
```
