# 任务 E：墨题题库批量生成解析（复制进 ZCode）

项目 D:\english-multiple-choice-practice-machine（Vue + FastAPI + SQLite）。
后端已有 backend/app/services/ai_client.py，提供 chat_completion() 函数（支持多 profile、重试、JSON 解析），复用它们。

任务：实现「题目解析批量生成」功能（让每道题有详解，提升付费价值）

【第 1 部分：数据库 schema】
输出 SQL 迁移方案：给 questions 表加 explain 字段（TEXT，存解析 HTML/Markdown）？
还是新建 question_explanations 表（question_id, content, source_model, created_at, updated_at）？
给出推荐方案 + 完整 SQL（含索引设计）。

【第 2 部分：生成脚本】
输出完整 Python 脚本 batch_generate_explanations.py：
- 从 frontend/public/question_bank.db 读取未生成解析的题目（分批，每批 20 题）
- 每批调用一次 ai_client.chat_completion（一次请求生成 20 题解析，JSON 格式返回）
- 解析格式：{"id": 123, "correct_analysis": "...", "wrong_options": [{"key": "B", "reason": "..."}, ...], "knowledge_points": ["..."], "study_advice": "..."}
- 写入数据库（事务批量提交）
- 断点续传：跳过已有解析的题
- 限速：每次调用间隔 1 秒
- 输出进度日志：当前批/总批数、成功/失败数、剩余时间估算
- 失败重试：单批失败重试 2 次，仍失败记录到 failed.log 继续下一批

【第 3 部分：50 道样例解析】
从题库抽 50 道真实题目（选不同 question_type），用 GLM-5.3 逐题写出高质量解析（正确项分析、错误项原因、知识点、复习建议），完整输出到这 50 题应有的最终格式。

【第 4 部分：前端展示】
输出 Vue 组件 QuestionExplain.vue：点击题目卡片 → 展开解析面板（正确项分析绿色、错误项红色、知识点标签、复习建议），与现有 PracticeView 风格一致。附 API endpoint 设计（GET /api/questions/:id/explain）。

【第 5 部分：prompt 模板】
输出生成解析用的系统提示词模板（要求模型按 JSON 严格输出、分析要专业且面向学生），放 backend/prompts/explain_prompt.py。

要求：代码完整可运行，Python 3.11 兼容后端环境，复用现有 ai_client 的 profile/重试机制，不引入新依赖。
