# P0-01 数据与前端结构清单

更新时间：2026-09-03

## 范围与边界

本清单对应企业化升级 P0-01～P0-04。P0 只建立组织、成员、审计、迁移版本和健康检查的基础能力；班级、成员邀请、按组织隔离全部业务表和支付/证书等 P1/P2/P3 能力不在本次范围。

## 后端清单

入口：`backend/app/main.py`。应用生命周期依次执行启动备份、数据库初始化、旧数据修复、题库安装和后台恢复任务；API 使用 `/api` 前缀。

### 数据库表

`backend/app/database.py` 的 `SCHEMA` 负责新库建表，`_ensure_column()` 负责兼容旧库追加列，复杂约束变更使用表重建。当前 schema 表为：

| 数据域 | 表 |
| --- | --- |
| 账号与组织 | `users`, `organizations`, `organization_members`, `audit_logs`, `schema_migrations` |
| 题库 | `question_bank_profiles`, `question_bank_packages`, `question_bank_assets`, `question_bank_revisions`, `papers`, `units`, `questions`, `options` |
| 练习与考试 | `practice_sessions`, `practice_answers`, `practice_answer_events`, `practice_unit_submissions`, `exam_sessions`, `exam_answers`, `generated_papers`, `exam_templates`（由相关模块按需创建） |
| 错题与学习 | `wrong_stats`, `wrong_analysis_reports`, `wrong_analysis_states`, `spaced_repetition_records`, `learning_days`, `user_achievements`（由相关模块按需创建） |
| 词汇 | `vocabulary_entries`, `vocabulary_occurrences`, `vocabulary_examples`, `vocabulary_reviews`, `vocab_plans`（由相关模块按需创建） |
| AI 与内容 | `ai_settings`, `ai_profiles`, `ai_profile_models`, `ai_conversations`, `ai_messages`, `chat_messages`, `ai_usage`, `diagnostic_reports`, `question_explanations`, `explain_collections` |
| 导入、回收站与审计辅助 | `import_jobs`, `trash_entries`, `revision_log`, `annotations`, `feedback`（由相关模块按需创建） |
| 写作、口语与知识库 | `essay_submissions`, `speaking_sessions`, `speaking_turns`, `knowledge_docs`, `knowledge_chunks` |
| Agent | `agent_runs`, `agent_steps`, `agent_decisions`, `agent_tool_calls`, `user_memories` |

以 `SCHEMA`/sqlite 实际 schema 为准；带“按需创建”的历史表可能由对应 service 的迁移补齐，初始化不会删除它们。

### P0-02 组织模型

- `organizations`：`id`, `name`, `slug`, `status`, `owner_user_id`, `settings`, `created_at`。
- `organization_members`：组织与用户的复合主键、`role`, `status`, `joined_at`；角色预留 `owner/admin/teacher/student/viewer`。
- `audit_logs`：组织、操作者、动作、资源和 JSON metadata；组织/用户删除不会级联删除审计记录。
- `users.active_organization_id`：当前组织偏好；失效时回退到最早的 active membership。
- `question_bank_profiles.organization_id`：预留字段，P0 不改变现有全局题库查询；真正按组织隔离留给后续阶段。

API：

| 方法 | 路径 | 行为与权限 |
| --- | --- | --- |
| GET | `/api/organizations` | 登录用户的 active memberships；`EPM_AUTH=0` 返回本地兼容空间及本地创建的组织 |
| POST | `/api/organizations` | 创建组织；登录用户自动成为 owner，单用户模式保持兼容 |
| GET | `/api/organizations/{org_id}` | 必须是成员；返回组织与 active 成员列表 |
| POST | `/api/organizations/{org_id}/switch` | 必须是成员；更新 `users.active_organization_id` 并写审计 |

认证开启时：缺少/无效 token 为 401，非成员访问组织为 403，不存在组织为 404。认证关闭时不强制登录，保留既有本地工作流。

## 迁移历史与回滚点

1. 既有版本迁移：题库 profile、user_id、多用户唯一约束和 AI/诊断扩展均保留在历史 `_run_migrations()`、`_migrate_add_user_id()`、`_migrate_multi_user_schema()` 中。
2. schema migration `1`：记录现有 schema 作为基线，不重新复制历史数据。
3. schema migration `2`：补齐组织表、审计表、`users.active_organization_id`、`question_bank_profiles.organization_id`；为已有用户创建一次 owner 组织，并确保 `user_id IS NULL` 的历史数据仍由原有注册迁移逻辑处理。
4. 每个版本使用命名 savepoint；失败会回滚该版本并重新抛出异常。所有迁移均幂等，重复初始化不会重复组织、成员或迁移记录。
5. FastAPI 启动时在迁移前用 SQLite online backup 复制到 `backend/data/backups/question_bank_YYYYMMDD_HHMMSS.db`，最多保留 5 份。迁移失败时原库不被删除，可从该备份恢复。

## 前端清单

- 路由注册：`frontend/src/router.ts`，使用 `createWebHashHistory()`；全部页面使用动态 import，新增 `/organizations` 同样遵循该 registry。
- API 入口：`frontend/src/api.ts`；继续统一处理 token、401 跳转、离线 adapter，并额外发送 `X-Organization-Id`。
- 组织状态：`frontend/src/services/organizations.ts`，负责加载、创建、切换、localStorage 当前组织 ID 和离线本地兼容。
- 组织页面：`frontend/src/views/OrganizationsView.vue`，展示组织列表、创建表单、当前组织和成员。
- 侧栏组件：`frontend/src/components/OrganizationSwitcher.vue`，在已有题库切换器旁展示当前组织并支持切换。
- 应用壳：`frontend/src/App.vue` 增加“组织管理”导航和组织切换器；不改变练习页全屏壳与 Capacitor 离线初始化路径。

## P0-04 健康检查

`GET /api/health` 保持公开访问，执行 `SELECT 1` 并返回应用版本、数据库状态和当前最大 schema migration version；数据库不可用时返回 503。`.env.example` 只包含空配置位，不写入任何 secret。
