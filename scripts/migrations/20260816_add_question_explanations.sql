-- =====================================================================
-- 任务 E（第 1 部分）：题目解析表迁移
-- 目标库：frontend/public/question_bank.db（打包分发库）
--        backend/data/question_bank.db（后端运行库）——两库都需执行
-- 执行方式（任选其一）：
--   sqlite3 frontend/public/question_bank.db < scripts/migrations/20260816_add_question_explanations.sql
--   sqlite3 backend/data/question_bank.db   < scripts/migrations/20260816_add_question_explanations.sql
-- 或由 backend/app/database.py 的 initialize_database() 自动建表（幂等，已同步加入 SCHEMA）。
-- 本脚本完全幂等：可重复执行，已存在的对象会被跳过。
-- =====================================================================

-- ── 推荐方案：新建 question_explanations 表（而非给 questions 加 explain 字段）──
-- 理由：
--   1. questions 表由导入管道按内容寻址管理（content_hash/external_key），
--      追加大段解析文本会污染内容哈希与题库同步/去重体系；
--   2. 解析有独立生命周期：AI 生成、可整批重生成、需按 source_model 溯源审计，
--      与题目本体（静态、随试卷导入）生命周期不同；
--   3. 与既有 question_ai_labels 表同构（question_id 主键 + model_name + 时间戳），
--      ON DELETE CASCADE 保证题目删除时解析联动清理，符合回收站机制；
--   4. content 存结构化 JSON（correct_analysis / wrong_options / knowledge_points /
--      study_advice），不存 HTML：前端结构化渲染（正确项绿/错误项红/标签），无 XSS 风险，
--      换皮/改版无需重写数据。
--
-- 索引设计：
--   question_id INTEGER PRIMARY KEY —— rowid 聚簇，服务两种高频查询：
--       ① API 点查 GET /api/questions/{id}/explain；
--       ② 断点续传扫描 LEFT JOIN ... WHERE e.question_id IS NULL。
--   idx_question_explanations_updated —— 管理端「最近生成/覆盖情况」列表。
--   idx_question_explanations_model   —— 按生成模型统计/质量对比。

BEGIN;

CREATE TABLE IF NOT EXISTS question_explanations (
    question_id INTEGER PRIMARY KEY,          -- 一题一条解析；UPSERT 即重生成
    content TEXT NOT NULL,                    -- 结构化 JSON，格式见 backend/prompts/explain_prompt.py
    source_model TEXT NOT NULL DEFAULT '',    -- 生成模型名（如 glm-5.3），便于溯源与对比
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_question_explanations_updated
    ON question_explanations(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_question_explanations_model
    ON question_explanations(source_model);

COMMIT;

-- 验证：
--   sqlite3 frontend/public/question_bank.db "PRAGMA table_info(question_explanations);"
--   sqlite3 frontend/public/question_bank.db "EXPLAIN QUERY PLAN
--     SELECT q.id FROM questions q LEFT JOIN question_explanations e
--     ON e.question_id = q.id WHERE e.question_id IS NULL;"
--   （应显示 SCAN questions + SEARCH question_explanations USING COVERING INDEX ...）
