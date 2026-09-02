# 更新日志（Changelog）

本项目遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范。

## [Unreleased] - 2026-08-19

### 🔧 离线链路修复（任务 E 收尾）
- 离线库自动迁移三层机制：构建期迁移（scripts/migrate_frontend_db.py）+ 运行期自迁移（offline_migrations.json + offline-migrations.ts）+ 清单自动生成，存量设备 IndexedDB 旧副本自动升级
- 离线 DELETE 真删除：生词/试卷/错题/笔记/标注本地 SQL 执行，修复假删除
- 离线刷新丢进度修复：buildOfflineSession 预取 practice_answers 回填 answered
- 离线词汇 note 字段映射：notes → note（后端 schema 单数），修复 no such column
- 离线补 /questions/{id}/explain 与 /explanations/coverage 路由

### 🐛 其他修复（2026-08-19）
- API Key 白名单加登录/注册路径（云端 EPM_API_KEY 死锁修复）
- 补齐 /annotations/stats 端点（NotesView 在线模式 404）
- 修复 11 个 router 双重 /api 前缀（学习报告/排行/成就/听力/阅读报错根因）
- 前端 XSS 修复：DOMPurify 消毒全部 v-html

## [2.0.0] - 2026-09-02

### Release close-out
- 词汇新增独立的 `vocabulary_examples` 双语例句表，保留来源、来源链接和核验状态；提供幂等导入与质量校验脚本。
- 题库导入模板注册表新增高考英语、英语专业四级（TEM-4）和英语专业八级（TEM-8），并提供 `/api/exam-templates` 目录接口。
- 公开 CI 增加仓库隐私/高置信度密钥扫描；tag 发布自动构建并校验 Windows NSIS 安装包和 portable 便携版。
- 版本号统一为 `2.0.0`，更新中英文 README 与发布路线图。

## [2.0.0-beta.15] - 2026-08-09

### ✨ 词汇数据大增强
- 音标全量补充：**7,643 词**（98.6%）——有道词典数据源
- 双语例句全量：**7,708 词**（99.4%）——中英对照（有道 API）
- 真题例句提取：从题库 1,737 句提取匹配真题例句
- 修复：词汇 category 统一为"高中"（前端筛选匹配）

### 🎨 UI/UX
- 推荐卡片"去练习"按钮移至右下角
- 推荐卷按年去重 + 卷别标签
- 动态题型入口（无听力不显示听力卡）

### 📱 移动端
- 竖屏上下分区（文章/题目独立滚动 + 可拖分隔条）
- 底部导航合并（笔记 = 错题 + 单词）
- 答题卡抽屉（题目导航网格）

### 🛠️ 工程化
- Issue 模板（Bug/Feature 表单）+ PR 模板（验证清单）
- CONTRIBUTING.md 贡献指南
- CI：前端 build + 后端 import 检查
- README：首行类别声明 + FAQ + 路线图 + 界面展示墙

## [2.0.0-beta.14] - 2026-08-09

- 移动端 P0+P1（竖屏分区/动态首页/笔记合并/答题卡）
- 词汇库 7,751 词全类别导入（高考/四级/六级/考研）
- 前端自动更新检测（60s 轮询）
- 推荐卷去重 + 卷别标签

## [2.0.0-beta.13] - 2026-08-09

- 安全存储加密接线（Windows DPAPI / Android Keystore AES-GCM）
- 竞品功能回收 9 项（听力音频/选项打乱/错题迭代等）
- 2026 高考英语全国 I 卷导入（45 题）

## [2.0.0-beta.12] - 2026-08-08

- 听力音频支持（MP3 播放器 + 计时禁拖）
- ESQ 1.1 题库分享格式
- 错题迭代递减
