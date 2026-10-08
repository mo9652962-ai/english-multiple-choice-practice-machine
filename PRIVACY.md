# 隐私政策与数据主权声明 (Privacy Policy)

**生效日期：** 2026年10月

墨题（MOTI / english-multiple-choice-practice-machine）是一款**本地优先（Local-First）、离线可用**的英语客观题刷题工作台。我们坚守「数据归用户所有 · 工业级确定性 · 零无谓外流」的隐私底线。

## 1. 100% 本地存储与计算
- 您的刷题记录、做题统计、错题本、FSRS 记忆算法参数与自定义题库均保存在本地 SQLite 数据库（`question_bank.db`）或浏览器的 `IndexedDB / LocalStorage` 中。
- 本应用无需联网即可完整运行全部刷题、复习与错题本功能。

## 2. 外部接口与网络边界
- **AI 题目精讲 / 辅助批改（可选）：** 仅当您在设置中主动配置 API Key 并点击“AI 精讲”时，题目文本才会发送至您指定的模型端点。我们不部署中转中间件，不保留您的对话或 Prompt 记录。
- **在线查词 / 词库增强（可选）：** 查词仅请求公开词典释义接口，绝不上传您的个人身份或做题行为数据。
- **自动更新：** Windows 客户端通过 GitHub Releases 检查版本清单，不附带任何设备指纹或遥测标识。

## 3. 零遥测 (Zero Telemetry)
- 墨题代码库中**零第三方统计 SDK、零广告跟踪代码、零用户行为上报**。

## 4. 安全政策与漏洞反馈
若发现安全漏洞，请参阅 [SECURITY.md](SECURITY.md) 或联系 `mo9652962-ai@users.noreply.github.com`。
