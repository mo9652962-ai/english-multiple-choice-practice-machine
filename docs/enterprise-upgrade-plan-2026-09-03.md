# 墨题 English Practice Machine：强化升级执行方案

> 版本：2026-09-03 · 来源：GPT 方案设计（k 已质疑式核验）
> 核验状态：✅ 通过（3 处修正见文末「k 核验意见」）
> 用途：Codex 执行依据。仓库：D:\english-multiple-choice-practice-machine

## 一、执行摘要

墨题当前已经不是从零开始：仓库已有练习、组卷、考试、反作弊、证书、登录、AI 路由、题库导入和部署脚本，前端也已有 27 个视图；真正的商业短板是没有把这些能力接成"组织—成员—班级—任务—结果—订单—权益"的闭环。建议先做单实例、单组织可售 MVP，再按试点结果扩展共享 SaaS 和白标，而不是立即引入 PostgreSQL、Redis、课程直播等大模块。

推荐顺序是：

1. 先补发布基线、数据库迁移和权限边界，确保旧版个人数据不会被破坏。
2. 建立产品、订单、支付事件、订阅和权益模型；正式支付采用适配器，先支持人工收款/沙箱，资质完成后再打开微信通道。
3. 建立组织、成员、角色、班级、作业/考试分发和教师报告，形成可以向培训机构、学校教研组销售的最小闭环。
4. 把现有考试、证书和反作弊 API 做成前端可用页面，补齐管理员的导出和审计能力。
5. 经过至少两个真实试点后，再做共享租户、域名/品牌配置和租户级配额。SQLite 继续保留：企业私有化采用"一客户一实例/一数据库"，共享 SaaS 只承诺低到中等并发。

建议的第一版商业 MVP 为 31–45 人天，包含 P0 基线、P1 订单/支付内核、P2 组织与班级最小能力、P3 证书/报告入口。它可以先通过合同或转账售卖，待商户资质完成后无缝启用微信支付。暂不做课程、直播、录播、复杂 CRM、自动续费和真正的大规模多租户。

## 二、现状与边界

### 已有能力

| 范围 | 当前证据/判断 | 对升级的含义 |
|---|---|---|
| 技术栈 | Vue 3 + Vite + vue-router；FastAPI + 原生 sqlite3；Capacitor Android；Electron/Web | 所有新增功能沿用现有目录、`api.ts`、路由懒加载和 `database.py` 迁移机制 |
| 题库与练习 | `papers`、`units`、`questions`、`practice_sessions`、`practice_answers` 等已有 | 不重写题库；组织能力通过 profile/组织关系包裹现有数据 |
| 商业考试基础 | `generated_papers`、`exam_sessions`、`anti_cheat_logs`、`certificates` 已存在 | 重点是组织分发、权限、前端入口和可审计状态，而不是重做组卷判分 |
| 身份认证 | `users`、Bearer token、`EPM_AUTH`、管理员依赖已存在 | 商业路由必须强制登录；保留桌面单用户兼容模式 |
| AI | `ai_profiles`、任务路由、`ai_usage`、诊断/作文/口语等能力已存在 | 增加配额、成本可见性和降级，不把 AI 作为组织闭环的前置阻塞 |
| 前端入口 | 已有 Dashboard、Library、Practice、Exam、Report、Diagnostic、Settings、Login 等页面 | 新增 billing/org/assignment/certificate 页面，遵循现有组件 registry；不另起 UI 框架 |
| 数据库 | SQLite，多表通过 `CREATE TABLE IF NOT EXISTS` 与 `_ensure_column` 迁移 | 采用可回滚的增量迁移；开启 WAL、busy timeout、索引和幂等，不引入 PostgreSQL/Redis |
| 发布 | 有 `deploy/DEPLOY.md`、Linux systemd/Nginx 和 Windows 脚本 | 商业版验收必须增加环境变量清单、备份恢复和 webhook 公网检查 |

### 已验证事实（k 实测 2026-09-03）

- 工作树干净，最新提交 `b0fe134`。
- **测试基线：91 passed / 13 skipped**（`python -m pytest -q`，实测通过）。
- **前端 build 可跑**：`vue-tsc --noEmit` + `vite build` 已装可用（npm run build 正常）。
- 14 个测试文件（`find tests backend/tests -name "test_*.py" | wc -l` = 14）。
- LICENSE = GPL-3.0-only（README 徽章 + LICENSE 文件确认）。
- 微信支付文档链接全部有效（curl 实测 8 个链接 200；GPT 附件里显示的 404 是抓取渲染问题，非链接失效）。

### 待复核事项

- `question_bank_profiles` 是题库配置隔离，不等于租户；`users.is_admin` 也不等于组织角色。不能仅把 profile_id 改名为 tenant_id。
- 现有 `certificates` 和反作弊路由已经能被调用，但用户端没有完整的证书列表/详情/验证流程，组卷和考试也没有组织任务分发闭环。
- 题库内容不自动继承代码许可证，以 ESQ `manifest.json` 的 `license`/`source` 声明为准。

### 硬约束

- 保持 Vue 3 + FastAPI + SQLite；不引入 PostgreSQL、Redis，也不以新基础设施替代现有部署方式。
- 所有密钥、私钥、APIv3 密钥、商户号等只从环境变量或受保护的部署配置读取；前端包、日志、提交记录和错误响应不得出现密钥。
- 支付只接入官方允许的普通商户/服务商流程，不模拟、绕过或伪造资质；资质未完成时使用人工收款或沙箱适配器。
- 所有组织级读写由后端校验成员身份和角色；前端隐藏按钮不算权限控制。
- 保持现有组件 registry、路由懒加载、`frontend/src/api.ts` 封装和 `database.py` 迁移风格。

## 三、分阶段路线图

| 阶段 | 目标 | 主要产出 | 工程人天 | 售价/收入影响 |
|---|---|---|---:|---|
| P0 发布基线与权限地基 | 让旧版数据可迁移、可备份、可审计 | 迁移脚本、组织上下文依赖、角色矩阵、CI/冒烟基线 | 3–5 | 不单独收费；提升私有化交付可信度，避免低级故障侵蚀报价 |
| P1 商业订单与支付内核 | 形成产品—订单—支付—权益闭环 | 商品/计划、订单、交易、支付事件、人工收款、微信适配器、退款状态 | 10–14 | 从"只能演示/转账"升级为可售订阅；先支撑 5,000–20,000 元/年试点包，正式支付不以审核完成为前置 |
| P2 组织、成员、班级、任务 | 让教师/机构可以运营学生 | 组织、成员、邀请、班级、任务、学生结果、教师报告 | 14–20 | 推荐首个可售团队包 5,980–12,800 元/年；私有化基础报价 2.98–5.98 万元/套 |
| P3 证书、考试运营与交付 | 把已有考试能力变成可交付产品 | 证书中心、验证页、考试监考记录、导出、审计、运营看板 | 10–14 | 可作为"测评/证书"增值包加价 1–3 万元；支持学校/培训机构验收 |
| P4 共享租户与白标 | 在真实试点后扩展 SaaS | 租户配置、域名/品牌、配额、租户管理员、备份恢复、数据导出 | 14–20 | 可形成 1.28–2.98 万元/年机构 SaaS 或 8–15 万元企业项目；受 SQLite 并发上限约束 |
| P5 AI 成本与企业加固 | 保护毛利并提高续费 | AI 配额、成本中心、任务队列、SLA 指标、审计/隐私工具 | 8–12 | AI 作为 1,000–5,000 元/年增值包或按量计费；主要作用是保护利润，不应承诺无限 AI |

### 阶段门禁

- P0 完成后才允许写业务表：旧库备份可恢复、迁移重复执行无破坏、个人模式与登录模式测试通过。
- P1 完成后才允许试收款：人工收款流程、订单状态机、重复回调、金额校验和退款状态先通过；微信正式按钮必须受 feature flag 控制。
- P2 完成后才允许卖团队包：A 组织不能读 B 组织的成员、题库、考试、报告、证书和订单；教师与学生权限必须通过 API 测试。
- P3 完成后才允许以"证书/测评系统"对外报价：证书验证、导出、反作弊证据、撤销/更正策略必须有明确记录。
- P4 只有在至少两个试点、备份恢复演练和并发试验通过后才上线共享 SaaS。

## 四、核心功能的数据模型、API 与前端入口

### 4.1 组织与成员

新增或迁移以下表（字段可按现有命名风格落地，时间统一使用 UTC/ISO 字符串）：

| 表 | 关键字段 | 说明 |
|---|---|---|
| `organizations` | `id`, `name`, `slug`, `status`, `plan_id`, `owner_user_id`, `settings`, `created_at` | 一个客户组织；个人旧数据迁移为默认"个人组织" |
| `organization_members` | `organization_id`, `user_id`, `role`, `status`, `joined_at` | `owner/admin/teacher/student/viewer`；唯一键为组织+用户 |
| `organization_invitations` | `organization_id`, `email_or_username`, `role`, `token_hash`, `expires_at`, `accepted_at` | 只保存 token hash；支持撤销和过期 |
| `classes` | `organization_id`, `name`, `teacher_user_id`, `status` | 班级属于组织，教师必须是组织成员 |
| `class_members` | `class_id`, `user_id`, `status`, `joined_at` | 防重复加入；删除采用状态变更而非物理删除 |
| `audit_logs` | `organization_id`, `actor_user_id`, `action`, `resource_type`, `resource_id`, `metadata`, `created_at` | 记录角色变化、导出、退款、证书撤销等高风险操作 |

后端依赖建议：

- `get_current_user` 继续兼容 `EPM_AUTH=0` 的本地单用户模式；billing/org/assignment 路由始终使用 `require_user`。
- 新增 `get_current_organization`：从登录用户的 active organization context 解析组织，并校验成员关系；不信任前端直接提交的 `organization_id`。
- 新增 `require_org_role(*roles)`，统一返回 401/403；所有 SQL 查询都通过 `organization_id`、成员关系或可证明的 profile 归属过滤。
- 用户可以加入多个组织，但一次请求只有一个明确的 active organization；切换组织要写入 session/token 配置或显式请求头并再次校验。

API：

```text
GET    /api/organizations
POST   /api/organizations
GET    /api/organizations/{org_id}
PATCH  /api/organizations/{org_id}
POST   /api/organizations/{org_id}/switch
GET    /api/organizations/{org_id}/members
POST   /api/organizations/{org_id}/invitations
PATCH  /api/organizations/{org_id}/members/{user_id}
DELETE /api/organizations/{org_id}/members/{user_id}
GET    /api/organizations/{org_id}/classes
POST   /api/organizations/{org_id}/classes
PATCH  /api/classes/{class_id}
POST   /api/classes/{class_id}/members
DELETE /api/classes/{class_id}/members/{user_id}
```

前端入口：

- `/organizations`：组织切换与组织列表。
- `/organization/settings`：组织名称、品牌色、默认题库、数据导出。
- `/organization/members`：邀请、角色、停用、重新发送邀请。
- `/classes`、`/classes/:id`：班级和成员。
- App 侧边栏只给有组织权限的用户显示"组织管理"；学生端只显示"我的班级/任务"。

### 4.2 产品、订单、支付与权益

新增：

| 表 | 关键字段 | 说明 |
|---|---|---|
| `products` | `id`, `code`, `name`, `kind`, `active`, `metadata` | 如 `team_100_yearly`、`private_deploy_base`；产品定义不等于订单 |
| `plans` | `id`, `product_id`, `billing_period`, `amount_cents`, `currency`, `seat_limit`, `ai_quota`, `features` | 金额用整数分，不能用浮点金额 |
| `orders` | `id`, `order_no`, `organization_id`, `buyer_user_id`, `plan_id`, `amount_cents`, `status`, `expires_at`, `paid_at` | `pending/paid/cancelled/refunding/refunded/failed` |
| `payment_transactions` | `id`, `order_id`, `channel`, `provider_trade_no`, `amount_cents`, `status`, `raw_summary`, `paid_at` | 不保存不必要的完整敏感报文 |
| `payment_events` | `event_id`, `channel`, `event_type`, `payload_hash`, `received_at`, `processed_at`, `status` | `event_id` 唯一，解决回调重试和幂等 |
| `subscriptions` | `organization_id`, `plan_id`, `order_id`, `status`, `start_at`, `end_at`, `auto_renew` | MVP 可先关闭自动续费，仅做到期日 |
| `entitlements` | `organization_id`, `feature_code`, `quantity`, `source_order_id`, `start_at`, `end_at` | 所有功能开关/席位/AI额度由权益计算 |
| `refunds` | `id`, `order_id`, `refund_no`, `amount_cents`, `status`, `reason`, `requested_by` | 退款与原订单一对多，状态可追踪 |

支付适配器接口保持可替换：

```text
PaymentProvider.create_payment(order, context) -> PaymentIntent
PaymentProvider.query_payment(order_no) -> PaymentResult
PaymentProvider.refund(order, amount_cents, reason) -> RefundResult
PaymentProvider.verify_callback(headers, body) -> VerifiedEvent
```

API：

```text
GET    /api/catalog
GET    /api/me/entitlements
POST   /api/orders
GET    /api/orders
GET    /api/orders/{order_id}
POST   /api/orders/{order_id}/manual-confirm       # 仅 owner/admin 或人工运营
POST   /api/payments/wechat/native/{order_id}
POST   /api/payments/wechat/jsapi/{order_id}
POST   /api/payments/wechat/notify
GET    /api/payments/{order_id}/status
POST   /api/orders/{order_id}/refund
POST   /api/payments/{order_id}/reconcile
```

前端入口：

- `/pricing`：展示可售计划、人数上限、AI 配额、数据部署方式和退款说明。
- `/checkout/:orderId`：订单确认、人工收款/微信按钮、支付状态轮询。
- `/account/orders`：订单、发票/合同信息入口、退款申请状态。
- `/organization/billing`：组织管理员查看订阅、席位、到期日、AI 用量。
- 任何支付方式不可用时显示"联系管理员/人工转账"，不能伪造支付成功。

### 4.3 任务分发、考试与结果

复用 `generated_papers`、`exam_sessions`、`certificates`、`anti_cheat_logs`，新增：

| 表 | 关键字段 | 说明 |
|---|---|---|
| `assignments` | `id`, `organization_id`, `class_id`, `generated_paper_id`, `title`, `kind`, `start_at`, `due_at`, `pass_score`, `status`, `created_by` | 作业/模拟考试统一入口 |
| `assignment_targets` | `assignment_id`, `user_id`, `status`, `started_at`, `submitted_at`, `score` | 支持班级快照；成员后续退出不改变历史任务 |
| `certificate_templates` | `organization_id`, `name`, `title_template`, `brand_config`, `active` | P3 再做，默认模板先复用现有证书字段 |
| `certificate_revocations` | `certificate_id`, `reason`, `revoked_by`, `revoked_at` | 证书不能靠删除实现撤销 |

迁移规则：

- 为 `question_bank_profiles` 增加 `organization_id`，已有 profile 归到默认个人组织；不要把现有 `profile_id` 直接当组织 ID。
- 为 `generated_papers`、`exam_sessions`、`certificates`、`anti_cheat_logs` 增加组织归属或可追溯的 profile 关联，并为历史行使用明确的默认组织回填。
- 先覆盖商业核心路径，不要一次性给所有词汇/AI/个人学习表强加组织列；对个人表通过 `user_id` 隔离，对题库表通过 profile→organization 隔离。
- 每个迁移都先备份，执行后检查行数、外键、唯一约束和历史登录迁移。

API：

```text
GET    /api/organizations/{org_id}/assignments
POST   /api/organizations/{org_id}/assignments
GET    /api/assignments/{assignment_id}
POST   /api/assignments/{assignment_id}/start
POST   /api/assignments/{assignment_id}/submit
GET    /api/assignments/{assignment_id}/results
GET    /api/organizations/{org_id}/reports/overview
GET    /api/organizations/{org_id}/reports/students/{user_id}
GET    /api/certificates
GET    /api/certificates/{cert_no}
GET    /api/certificates/verify/{cert_no}
POST   /api/certificates/{cert_no}/revoke
GET    /api/exams/{exam_id}/anti-cheat
```

前端入口：

- `/assignments`：教师发布、学生待办、截止时间和状态。
- `/assignments/:id`：任务详情与开始/继续/查看结果。
- `/organization/reports`：班级正确率、完成率、薄弱题型、异常事件概览。
- `/certificates`、`/certificates/:certNo`、`/verify/:certNo`：列表、详情、公开验证。
- 复用 `PracticeView.vue`、`ExamView.vue` 的作答组件，不新建第二套判分逻辑。

### 4.4 租户、白标与部署

P4 不做"看起来多租户、实际串数据"的半成品。建议采用两种明确模式：

1. **私有化模式（推荐先卖）**：每个机构一个部署目录和 SQLite 数据库，组织表仍保留，便于未来迁移；客户数据天然隔离，适合学校/培训机构。
2. **共享 SaaS 模式（试点后）**：单实例单 SQLite 文件，以 `organization_id` 做强制行级过滤，开启 WAL、`busy_timeout`、合理索引和 SQLite 备份；只承诺低/中等并发，并提供容量阈值和升级到独立实例的路径。

白标只做配置，不复制代码：`brand_name`、logo 路径、主色、证书模板、邮件/站内文案、登录页标识。域名绑定、HTTPS、备份和日志保留在部署文档中，不能由前端配置绕过服务端访问控制。

## 五、Codex 子任务清单

每个子任务都必须在 `D:\english-multiple-choice-practice-machine` 执行，先读根目录 `AGENTS.md`，只做增量迁移；完成后回报修改文件、迁移说明、测试命令、测试结果和未决风险。每个任务均包含后端、前端和验证三部分，避免只改接口不落入口。

### P0：基线与地基

- [ ] **P0-01 盘点与备份**：后端确认现有表、外键、用户迁移、profile 归属；前端盘点 registry、路由和 API 错误处理；验证生成 SQLite 备份并能恢复，建立迁移前后行数报告。
- [ ] **P0-02 组织上下文依赖**：后端新增 `organizations`、`organization_members`、active org 解析、角色依赖和审计写入；前端新增最小组织选择状态；验证未登录/跨组织/越权返回 401/403/404，旧版本地模式仍可启动。
- [ ] **P0-03 商业数据迁移框架**：后端新增迁移版本记录、默认个人组织回填、profile→organization 关联和索引；前端增加版本/维护提示；验证重复运行幂等、断点失败可恢复、旧库样本不丢数据。
- [ ] **P0-04 发布门禁**：后端整理健康检查、备份恢复、环境变量示例和敏感字段脱敏；前端检查生产构建不包含 secret；验证 Python 测试、`vue-tsc`、Vite build、启动冒烟。

### P1：订单与支付

- [ ] **P1-01 产品/计划/权益模型**：后端新增 catalog、plan、entitlement 表和服务；前端新增 `/pricing`、`/organization/billing`；验证金额用分、计划过期、席位与 AI quota 计算正确。
- [ ] **P1-02 订单状态机**：后端实现订单创建、查询、过期、人工确认、审计和幂等键；前端新增 checkout 和订单列表；验证重复下单、重复确认、金额篡改、越权查询和过期订单。
- [ ] **P1-03 微信支付适配器**：后端实现 Native 优先、JSAPI/H5 受资质 feature flag 控制、APIv3 签名/验签/解密接口、通知幂等；前端只拿支付意图或 code_url，不接触私钥；验证 mock 回调、伪造签名、重复通知、金额不一致、网络超时、查询补偿。
- [ ] **P1-04 退款与对账**：后端实现退款申请、退款回调/查询、人工重试、交易对账摘要；前端显示退款状态和运营入口；验证部分退款、重复退款、失败重试、订单与权益回收规则。

### P2：组织运营闭环

- [ ] **P2-01 成员邀请与角色**：后端邀请 token hash、过期、接受、停用、角色变更；前端成员管理和邀请反馈；验证 owner/admin/teacher/student/viewer 权限矩阵和审计记录。
- [ ] **P2-02 班级管理**：后端班级、成员、教师关系和快照；前端 `/classes`、`/classes/:id`；验证重复加入、退班、教师不能管理外组织班级、历史任务不随成员变更漂移。
- [ ] **P2-03 任务分发**：后端把 generated paper 绑定 assignment，支持班级/个人目标、开始/提交/结果；前端复用 Practice/Exam 作答入口；验证题目归属、截止时间、重复提交、学生看不到他人成绩。
- [ ] **P2-04 教师报告**：后端聚合完成率、正确率、题型弱项和反作弊计数；前端报告筛选、空状态、导出按钮；验证空班级、分页、时区、组织隔离和大数据量查询索引。

### P3：证书与可交付验收

- [ ] **P3-01 证书中心**：后端补列表/详情/验证/撤销和模板最小字段；前端 `/certificates`、`/certificates/:id`、`/verify/:certNo`；验证签发、重复签发、撤销后验证结果、公开验证不泄露隐私。
- [ ] **P3-02 考试运营台**：后端补考试列表、状态、anti-cheat 统计、导出；前端管理员/教师考试台；验证仅授权角色可看监考记录，事件不可由学生伪造为"已确认违规"。
- [ ] **P3-03 商业验收包**：补部署文档、管理员手册、退款/证书/数据导出 SOP；前端增加帮助与联系人；验证新客户从创建组织到发布任务、完成考试、验真证书、导出报告的全链路。

### P4/P5：规模与毛利

- [ ] **P4-01 白标配置**：后端组织品牌配置和安全的 logo 文件引用；前端登录页、侧栏、证书使用配置；验证组织 A 的品牌不会出现在组织 B，上传路径不可穿越。
- [ ] **P4-02 共享租户容量**：后端 WAL、busy timeout、索引、租户级配额、SQLite 备份与恢复；前端容量提示和升级独立实例入口；验证并发读写、锁等待、备份恢复和容量阈值。
- [ ] **P5-01 AI 成本中心**：后端把 `ai_usage` 关联 org/user/feature，增加每日/周期额度、超额降级、任务队列表；前端 billing/report 展示 token、调用次数、估算成本；验证无 profile、429、超时、重复任务和成本上限。
- [ ] **P5-02 企业安全加固**：后端敏感日志脱敏、token 轮换、数据导出/删除、审计检索；前端管理员工具；验证 secret 扫描、权限回归、删除确认、审计不可由普通用户删除。

## 六、支付资质与实现建议

### 通道选择

| 场景 | MVP 建议 | 资质/技术前提 |
|---|---|---|
| 合同、对公转账、人工确认 | 首发默认 | 不阻塞开发；必须有订单号、收款凭证、人工确认审计和权益发放记录 |
| PC 管理台扫码 | 微信 Native | 适合管理员在电脑上展示二维码；不等同于移动 H5 支付 |
| 微信内网页 | JSAPI | 需要商户号、已认证公众号/服务号、公众号 AppID 绑定和支付目录/授权域名配置 |
| 手机浏览器 H5 | H5 | 需要公网可访问的支付域名和经营场景；域名主体不一致时要准备集团/品牌/服务商 SaaS 合作材料 |
| Electron/Android 原生直调 | 暂不作为 MVP | 需要另行评估 APP 支付/开放平台主体与签名，不能把 JSAPI/H5 代码直接当原生支付方案 |

微信官方资料（k 已 curl 实测全部 200 有效）：
- JSAPI 准入条件：https://pay.wechatpay.cn/doc/v3/merchant/4012062524
- JSAPI 开发接入准备：https://pay.wechatpay.cn/doc/v3/merchant/4015423216
- H5 支付权限指引：https://pay.wechatpay.cn/doc/v3/merchant/4012791841
- 各主体基础支付权限列表：https://pay.wechatpay.cn/doc/v3/merchant/4015420731

### 不可省略的支付工程要求

- 商户私钥、证书序列号、APIv3 密钥只在 FastAPI 服务端读取；环境变量名写入 `.env.example`，值不进仓库。
- 下单金额、币种、订单号在服务端生成并持久化；前端不能决定最终收款金额。
- APIv3 请求与回调都做签名/验签和回调解密；先检查签名序列号、时间窗，再校验订单号、组织、金额和商品。
- `payment_events.event_id` 唯一；重复通知直接返回成功，不重复发权益。回调只做短事务，失败可由查询/补偿任务继续处理。
- 退款接口的受理结果不等于退款成功；要通过退款回调或查询更新最终状态。人工退款也必须回写订单、交易、权益和审计。
- 未获得资质时，正式环境不显示"微信支付成功"按钮；使用人工收款或沙箱 mock，不能用前端假回调绕过平台限制。

## 七、测试与验收标准

### 后端与数据

- 新建空库、旧版样例库、含 `user_id IS NULL` 的历史库都能初始化；迁移执行两次结果一致。
- 组织 A/B 的用户、题库 profile、generated paper、exam、assignment、报告、证书、订单相互不可见；用 API 直接改 URL/ID 也不能越权。
- 角色矩阵至少覆盖 owner、admin、teacher、student、viewer；所有拒绝场景有明确 401/403/404。
- 金额使用整数分；订单状态只能按允许的状态机迁移；订单创建、确认、回调、退款和权益发放具备幂等测试。
- 支付 mock 覆盖：合法签名、伪造签名、重复回调、金额不一致、订单不存在、过期、重复退款、回调超时、查询补偿。
- 证书覆盖：签发、重复签发、公开验真、撤销、撤销后验真、公开接口隐私最小化。
- 所有新增查询具备组织/用户过滤和必要索引；SQLite 开启 WAL 后做写入锁等待测试。

### 前端

- `npx vue-tsc --noEmit -p tsconfig.app.json` 通过；`npx vite build` 通过；新增路由全部懒加载。
- loading、空状态、错误、401、403、网络重试、支付处理中和回调未到达都有可理解的界面。
- 学生不看到教师入口；按钮隐藏之外，直接访问路由也由后端拒绝。
- 移动端、Web、Electron 三种入口至少完成登录、加入班级、开始任务、提交、查看证书的 smoke test；支付只在相应场景展示。
- 构建产物和日志扫描不到 API key、私钥、APIv3 key、token 或完整支付回调报文。

### 业务验收脚本

1. 管理员注册/登录，创建组织，选择计划并生成订单。
2. 人工确认或沙箱支付，确认订阅和权益已发放且重复回调不重复发放。
3. 邀请教师和学生，创建班级，发布一套已有 generated paper。
4. 学生完成考试，教师看到班级统计和反作弊事件数量。
5. 系统签发证书，学生查看证书，外部访问验证页；撤销后验证失效但审计仍保留。
6. 导出报告和订单记录，备份 SQLite，恢复到新目录并核对组织、成绩、证书和订单。

## 八、风险与依赖

| 风险/依赖 | 影响 | 应对 |
|---|---|---|
| 微信商户/公众号/域名审核 | 正式在线支付延期 | P1 先完成适配器、人工收款和沙箱；审核通过后只切 feature flag |
| H5 异主体或 SaaS 材料 | 可能无法按预期开通 H5 | 首发 Native/人工收款；准备主体、域名、授权函、合作协议和经营截图，不绕过审核 |
| SQLite 写并发 | 共享 SaaS 容量有限 | 私有化一客户一实例；共享模式只面向试点规模，WAL/索引/备份/容量报警先做 |
| 旧数据 user/profile 混用 | 数据串读或历史记录丢失 | P0 备份、迁移报告、默认个人组织回填、回归测试；不做破坏性重建 |
| 现有前端 registry 不一致 | UI 维护成本上升 | 先复用既有组件、`api.ts`、样式 token、路由懒加载；新组件先注册再引用 |
| AI 延迟与费用 | 毛利和用户体验受损 | 任务路由、超时、缓存、SQLite 任务队列、每日配额、降级到本地规则；不承诺无限调用 |
| 证书/反作弊被过度宣传 | 合规与售后风险 | 对外称"考试记录和异常证据"，不宣称绝对防作弊；证书验证页只公开必要字段 |
| GPL-3.0 许可证 | 闭源白标销售受限 | 先核实版权所有者和贡献者；未完成授权前提供 GPL 源码/部署/服务，不把 GPL 代码直接改名成闭源专有产品 |
| 多平台数据不同步 | Web/Android 结果不一致 | 延续现有题库同步清单；所有新增组织/订单/考试 API 以服务端为准，客户端只缓存展示 |

## 九、MVP 取舍

### MVP 必须包含

- 登录、组织、成员角色、班级和邀请。
- 一个已有题库 profile 选择与组织归属。
- generated paper → assignment → exam/practice → result 的最短路径。
- 订单、人工收款确认、权益、到期和退款状态；支付适配器与 sandbox/mock。
- 证书列表、详情、公开验证和撤销记录。
- 教师最小报告、CSV/JSON 导出、审计日志、备份恢复。

### 首版明确不做

- 课程目录、直播、录播、课件、复杂内容商城；墨题的差异化仍然是题库、考试和学习分析。
- 自动续费、分账、优惠券、发票自动开具、复杂 CRM；这些需要稳定订单量、财税流程和更多外部资质。
- 真正大规模的共享多租户；先用私有化或低并发共享实例验证销售。
- 无限 AI、实时语音转写集群、复杂 RAG 知识库运营；先做 AI 配额、降级和成本可视化。
- 过度承诺的反作弊、证书公信力或教育效果；把证据链和结果可追溯做好。

### 可延后的判断标准

- 有 2 个以上付费试点、每个至少 1 个教师和 30 个学生活跃后，再决定是否开始 P4。
- AI 月度成本超过订阅收入的 15% 或 P95 延迟明显影响完成率，再启动 P5 成本中心；不要提前做复杂计费。
- 客户明确要求在线支付且主体资质已完成，再打开微信 JSAPI/H5；否则人工确认的订单链路足够验证商业模式。

## 十、源码授权、SaaS 与混合定价

### 许可证前提

当前项目包含 `GPL-3.0-only` 标识和仓库许可证文件。GPL 代码可以用于交付和提供服务，但如果把修改后的程序作为专有软件分发，需要先解决 GPL 对对应源代码和许可义务的影响。只有在版权所有权、贡献者授权和第三方依赖清单都清楚时，才考虑双许可证；不能因为客户付费就默认拥有闭源授权。

### 推荐报价结构（起始价，不是市场事实）

| 产品形态 | 建议起始报价 | 包含 | 不包含/边界 |
|---|---:|---|---|
| GPL 社区版 | 0 元软件许可 | 公开源码、基础刷题能力 | 不含 SLA、定制、部署和数据迁移 |
| 实施/数据迁移服务 | 0.8–2.0 万元/项目 | 环境部署、题库导入、基础培训、验收 | 不授予闭源专有权 |
| 商业私有化基础包 | 2.98–5.98 万元/套 | 组织、班级、考试、报告、证书、部署文档 | 单客户单实例；定制需求另计 |
| 机构 SaaS 基础包 | 5,980–12,800 元/年 | 1 个组织、约 100–300 席位、基础 AI 配额、备份 | 超席位、独立域名、深度定制另计 |
| 白标/独立实例 | 8–15 万元首年 | 品牌、域名、部署、培训、SLA、数据迁移 | 需单独评估硬件、合规、驻场和支付资质 |
| AI 增值包 | 1,000–5,000 元/年或按量 | 明确 token/次数额度、成本报表、超额降级 | 不承诺无限模型调用 |

### 定价策略

- **首单卖结果，不卖功能数量**：以"一个组织、多少学生、多少场考试、是否需要私有化和证书"为报价变量。
- **软件许可、实施费、年度服务费分开**：便于 GPL 社区版、商业私有部署和 SaaS 共存，也避免一次性交付后没有维护收入。
- **先做年付，不做自动续费**：首版用人工续费/合同续费验证留存；自动扣款和分账等到订单量、资质和财税流程稳定后再做。
- **席位与 AI 分开计量**：席位反映组织规模，AI 反映外部模型成本；把 AI 无限包含在低价套餐会直接损害毛利。
- **源码授权谨慎单列**：如果没有完整的双许可证权利链，优先销售部署、定制、培训和 SaaS，不对外承诺"买断全部源码的闭源权利"。

## 十一、k 核验意见（2026-09-03）

1. **方案整体通过**：数据模型设计合理、P0-P5 阶段门禁清晰、MVP 取舍务实、GPL 与支付资质风险识别到位。
2. **GPT 声称"本环境无 python/pytest/pnpm"不成立**（k 实测：Python 3.11.15、pytest 9.1.1、vue-tsc 全可用，测试基线 91 passed/13 skipped）——Codex 执行时无需担心环境问题，按仓库现有脚本跑。
3. **GPT 附件里微信文档 8 个链接显示 404 是抓取渲染 bug**（k 实测 curl 全部 200）——链接有效，方案引用无误。
4. **测试文件数 14 核对无误**；LICENSE GPL-3.0-only 核对无误。
5. **执行建议**：先跑 P0（4 子任务，3-5 人天），P0 门禁过了再进 P1/P2。Codex 任务包已生成。

## 十二、交付给 Codex 的总提示

```text
请在 D:\english-multiple-choice-practice-machine 执行本方案，按 P0→P1→P2→P3 顺序推进。

每次开始先阅读根目录 AGENTS.md 和当前 git 状态；不要覆盖用户已有改动。保持 Vue3 + FastAPI + SQLite，不引入 PostgreSQL/Redis，不把 secret 写入代码、前端、日志或测试快照。数据库只做可回滚的增量迁移，所有组织路由由后端校验成员和角色，不能只在前端隐藏按钮。遵循现有 frontend/src/api.ts、router.ts、组件 registry 和 backend/app/database.py 的迁移风格。

每个子任务必须同时包含：
1. 后端表/迁移/服务/API；
2. 前端路由/视图/registry/API 调用/loading/error/empty 状态；
3. 后端测试、权限/组织隔离测试、支付或业务状态机测试、前端类型检查和构建验证。

支付只实现官方合规适配器：资质未完成时保留人工收款和 mock/sandbox，正式微信支付必须服务端签名验签、回调解密、金额校验、幂等、退款和查询补偿。完成后回报：修改文件、迁移策略、API 清单、测试命令及结果、未解决风险、是否建议进入下一阶段。
```
