-- ═══════════════════════════════════════════════════════════════════════════
-- 错题知识点归因分析 · 数据库 Schema 变更（v3.0）
-- ═══════════════════════════════════════════════════════════════════════════
-- 适用：english-multiple-choice-practice-machine（SQLite）
--
-- 说明：
-- 1. 本文件是完整的手工迁移脚本（幂等，可重复执行）。
-- 2. 应用启动时的自动迁移已内置于 backend/app/database.py：
--    - SCHEMA 字符串内的 CREATE TABLE IF NOT EXISTS（新库直接建全）
--    - _run_migrations() 末尾调用 seed_knowledge_points()（播种知识点字典）
--    → 正常使用无需手工执行本文件；它用于：
--      a) 审阅 / 评审 schema 变更
--      b) 对旧库手工补表（如自动迁移被跳过的特殊环境）
--      c) 其他工具（如 sql.js 离线端）核对表结构
--
-- 依赖：wrong_analysis_reports 表（v2.x 已存在，归因报告主表）
-- ═══════════════════════════════════════════════════════════════════════════

PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. wrong_knowledge_points —— 知识点字典（白名单目录）
--    每个错误原因（cause_code）下的细粒度知识点。内容由应用层
--    seed_knowledge_points() 从 KNOWLEDGE_POINT_CATALOG 常量幂等写入
--    （44 条：vocabulary 5 / collocation 4 / grammar 7 / context 4 /
--     discourse 4 / detail 4 / inference 3 / main_idea 3 / attitude 3 /
--     trap 4 / carelessness 3 / uncertain 0）。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wrong_knowledge_points (
    code        TEXT PRIMARY KEY,                 -- 如 'vocab_synonym'、'gram_tense'
    cause_code  TEXT NOT NULL,                    -- 归属 12 分类之一
    label       TEXT NOT NULL,                    -- 展示名，如 '近义词边界不清'
    description TEXT NOT NULL DEFAULT '',         -- 一句话说明错在哪
    guidance    TEXT NOT NULL DEFAULT '',         -- 本地白名单学习建议
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wrong_kp_cause
    ON wrong_knowledge_points(cause_code);

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. wrong_cause_diagnoses —— 逐题归因明细
--    每次分析（report）对每道题存一行；JSON 数组字段存 code 列表。
--    UNIQUE(report_id, question_id)：同一报告重跑时先 DELETE 再 INSERT。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wrong_cause_diagnoses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id           INTEGER NOT NULL,
    question_id         INTEGER NOT NULL,
    primary_cause       TEXT    NOT NULL DEFAULT 'uncertain',  -- 12 分类 code
    secondary_causes    TEXT    NOT NULL DEFAULT '[]',         -- JSON: [code, ...] ≤3
    knowledge_points    TEXT    NOT NULL DEFAULT '[]',         -- JSON: [kp_code, ...] ≤3
    confidence          REAL    NOT NULL DEFAULT 0,            -- 0.0-1.0 AI 置信度
    reason_codes        TEXT    NOT NULL DEFAULT '[]',         -- JSON: 抽象错因码 ≤4
    recommended_actions TEXT    NOT NULL DEFAULT '[]',         -- JSON: 建议动作 ≤4
    diagnosed_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id)   REFERENCES wrong_analysis_reports(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id)          ON DELETE CASCADE,
    UNIQUE (report_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_wrong_cause_diagnoses_question
    ON wrong_cause_diagnoses(question_id, diagnosed_at DESC);
CREATE INDEX IF NOT EXISTS idx_wrong_cause_diagnoses_cause
    ON wrong_cause_diagnoses(primary_cause);

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. wrong_cause_snapshots —— 12 分类快照（趋势追踪数据源）
--    每次分析为【全部 12 分类】各存一行（本次未出现的分类计 0），
--    保证折线序列完整、且彻底消失的薄弱点能被判为「改善」。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wrong_cause_snapshots (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id          INTEGER NOT NULL,
    cause_code         TEXT    NOT NULL,
    question_count     INTEGER NOT NULL DEFAULT 0,   -- 本报告参与归因的总题数
    wrong_count        INTEGER NOT NULL DEFAULT 0,   -- 该分类的错题数
    percentage         REAL    NOT NULL DEFAULT 0,   -- 占比 0-100
    average_confidence REAL    NOT NULL DEFAULT 0,
    captured_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES wrong_analysis_reports(id) ON DELETE CASCADE,
    UNIQUE (report_id, cause_code)
);

CREATE INDEX IF NOT EXISTS idx_wrong_cause_snapshots_series
    ON wrong_cause_snapshots(cause_code, report_id DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. wrong_kp_snapshots —— 知识点快照
--    每次分析按命中次数存 top 知识点行；跨报告 SUM(total_hits) 即累计榜。
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wrong_kp_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id   INTEGER NOT NULL,
    kp_code     TEXT    NOT NULL,
    hit_count   INTEGER NOT NULL DEFAULT 0,
    percentage  REAL    NOT NULL DEFAULT 0,      -- 占本报告知识点总命中数比例
    captured_at TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (report_id) REFERENCES wrong_analysis_reports(id) ON DELETE CASCADE,
    UNIQUE (report_id, kp_code)
);

CREATE INDEX IF NOT EXISTS idx_wrong_kp_snapshots_code
    ON wrong_kp_snapshots(kp_code, report_id DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. wrong_cause_mastery —— 12 分类掌握度档案（跨报告聚合视图表）
--    每次分析后由 _update_mastery_rows() 全量重算（12 行）。
--    mastery_score = 100 - 近 8 次快照平均占比（uncertain 固定 50）
--    trend_direction: 最近两次快照占比差 ≥3pt 判 improving / worsening，否则 stable
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wrong_cause_mastery (
    cause_code          TEXT PRIMARY KEY,
    first_seen_at       TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at        TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    total_occurrences   INTEGER NOT NULL DEFAULT 0,  -- 历史累计错误题次
    report_count        INTEGER NOT NULL DEFAULT 0,  -- 出现过的报告数
    recent_percentage   REAL    NOT NULL DEFAULT 0,  -- 最近一次快照占比
    previous_percentage REAL    NOT NULL DEFAULT 0,  -- 上一次快照占比
    trend_direction     TEXT    NOT NULL DEFAULT 'stable',
    mastery_score       INTEGER NOT NULL DEFAULT 50, -- 0-100，越低越薄弱
    updated_at          TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ═══════════════════════════════════════════════════════════════════════════
-- 验证（手工执行后）
-- ═══════════════════════════════════════════════════════════════════════════
-- SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'wrong_%';
-- 预期 8 张：wrong_stats, wrong_analysis_reports, wrong_analysis_states,
--           wrong_knowledge_points, wrong_cause_diagnoses,
--           wrong_cause_snapshots, wrong_kp_snapshots, wrong_cause_mastery
--
-- PRAGMA foreign_key_check;  -- 应返回空
-- ═══════════════════════════════════════════════════════════════════════════
