from __future__ import annotations

import sqlite3
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .config import DATABASE_PATH, ensure_directories


SCHEMA = """
PRAGMA foreign_keys = ON;

-- v9.24: 多用户支持（多人部署时启用）
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    token TEXT,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_users_token ON users(token);

CREATE TABLE IF NOT EXISTS question_bank_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT '#486d5c',
    icon TEXT NOT NULL DEFAULT 'book',
    is_default INTEGER NOT NULL DEFAULT 0,
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_question_bank_profiles_name
    ON question_bank_profiles(name COLLATE NOCASE)
    WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL DEFAULT 1,
    year INTEGER NOT NULL,
    subject TEXT NOT NULL DEFAULT '英语一',
    title TEXT NOT NULL,
    source_file TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES question_bank_profiles(id)
);

CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL,
    unit_type TEXT NOT NULL,
    subtype TEXT,
    title TEXT NOT NULL,
    external_key TEXT,
    sequence INTEGER NOT NULL,
    passage TEXT NOT NULL DEFAULT '',
    shared_data TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    UNIQUE (paper_id, sequence)
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    number INTEGER NOT NULL,
    stem TEXT NOT NULL DEFAULT '',
    question_type TEXT NOT NULL DEFAULT 'single_choice',
    answer TEXT NOT NULL,
    score REAL NOT NULL,
    sequence INTEGER NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    external_key TEXT,
    content_hash TEXT,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE,
    UNIQUE (unit_id, number)
);

CREATE TABLE IF NOT EXISTS options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL,
    stable_key TEXT NOT NULL,
    original_label TEXT NOT NULL,
    content TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    UNIQUE (question_id, stable_key)
);

CREATE TABLE IF NOT EXISTS practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT NOT NULL,
    paper_id INTEGER,
    unit_ids TEXT NOT NULL,
    shuffle_options INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TEXT,
    score REAL,
    max_score REAL,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS practice_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    user_answer TEXT NOT NULL,
    option_order TEXT NOT NULL DEFAULT '[]',
    is_correct INTEGER,
    answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    UNIQUE (session_id, question_id)
);

CREATE TABLE IF NOT EXISTS practice_answer_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    user_answer TEXT NOT NULL,
    option_order TEXT NOT NULL DEFAULT '[]',
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS practice_unit_submissions (
    session_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    score REAL NOT NULL DEFAULT 0,
    max_score REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, unit_id),
    FOREIGN KEY (session_id) REFERENCES practice_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wrong_stats (
    user_id INTEGER DEFAULT NULL,
    question_id INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    wrong_count INTEGER NOT NULL DEFAULT 0,
    recent_results TEXT NOT NULL DEFAULT '[]',
    consecutive_correct INTEGER NOT NULL DEFAULT 0,
    manually_frequent INTEGER NOT NULL DEFAULT 0,
    last_wrong_at TEXT,
    last_attempt_at TEXT,
    PRIMARY KEY (user_id, question_id),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

-- v9.28: Gemini batch5 任务3——错题间隔重复（SM-2 简化版）
CREATE TABLE IF NOT EXISTS spaced_repetition_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    question_id INTEGER NOT NULL,
    interval_days INTEGER NOT NULL DEFAULT 1,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    review_date TEXT,
    due_date TEXT NOT NULL,
    UNIQUE (user_id, question_id),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS vocabulary_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    term TEXT NOT NULL,
    normalized_term TEXT NOT NULL,
    lemma TEXT NOT NULL DEFAULT '',
    phonetic TEXT NOT NULL DEFAULT '',
    part_of_speech TEXT NOT NULL DEFAULT '',
    contextual_meaning TEXT NOT NULL DEFAULT '',
    common_meaning TEXT NOT NULL DEFAULT '',
    synonyms TEXT NOT NULL DEFAULT '[]',
    antonyms TEXT NOT NULL DEFAULT '[]',
    similar_forms TEXT NOT NULL DEFAULT '[]',
    memory_hint TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    translation_status TEXT NOT NULL DEFAULT 'pending',
    translation_error TEXT NOT NULL DEFAULT '',
    encounter_count INTEGER NOT NULL DEFAULT 1,
    study_status TEXT NOT NULL DEFAULT 'learning',
    manually_frequent INTEGER NOT NULL DEFAULT 0,
    user_edited INTEGER NOT NULL DEFAULT 0,
    next_review_at TEXT,
    last_reviewed_at TEXT,
    -- FSRS 间隔复习字段 (v9.19: 替代固定间隔算法)
    fsrs_due TEXT,
    fsrs_stability REAL,
    fsrs_difficulty REAL,
    fsrs_state INTEGER DEFAULT 0,
    fsrs_step INTEGER DEFAULT 0,
    fsrs_last_review TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vocabulary_occurrences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    surface_form TEXT NOT NULL,
    context_sentence TEXT NOT NULL DEFAULT '',
    context_before TEXT NOT NULL DEFAULT '',
    context_after TEXT NOT NULL DEFAULT '',
    unit_id INTEGER,
    question_id INTEGER,
    year INTEGER,
    unit_title TEXT NOT NULL DEFAULT '',
    unit_type TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entry_id) REFERENCES vocabulary_entries(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE SET NULL,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS vocabulary_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    rating TEXT NOT NULL,
    reviewed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    next_review_at TEXT,
    FOREIGN KEY (entry_id) REFERENCES vocabulary_entries(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL DEFAULT 1,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    answer_stored_path TEXT NOT NULL DEFAULT '',
    detected_year INTEGER,
    detected_format TEXT,
    status TEXT NOT NULL DEFAULT 'analyzing',
    draft_data TEXT NOT NULL DEFAULT '{}',
    warnings TEXT NOT NULL DEFAULT '[]',
    parse_context TEXT NOT NULL DEFAULT '{}',
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (profile_id) REFERENCES question_bank_profiles(id)
);

CREATE TABLE IF NOT EXISTS trash_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deletion_batch_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id INTEGER NOT NULL,
    resource_name TEXT NOT NULL DEFAULT '',
    profile_id INTEGER,
    metadata TEXT NOT NULL DEFAULT '{}',
    deleted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    purge_after TEXT NOT NULL,
    restored_at TEXT,
    FOREIGN KEY (profile_id) REFERENCES question_bank_profiles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS revision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_job_id INTEGER,
    entity_type TEXT NOT NULL,
    entity_ref TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source TEXT NOT NULL,
    model_name TEXT,
    approved INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (import_job_id) REFERENCES import_jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL DEFAULT 'DeepSeek V4-Flash',
    base_url TEXT NOT NULL DEFAULT 'https://api.deepseek.com/v1',
    api_key_encrypted TEXT,
    model TEXT NOT NULL DEFAULT 'deepseek-v4-flash',
    temperature REAL NOT NULL DEFAULT 0.2,
    max_tokens INTEGER NOT NULL DEFAULT 1200,
    system_prompt TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO ai_settings (id) VALUES (1);

CREATE TABLE IF NOT EXISTS ai_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    api_key_encrypted TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    is_default INTEGER NOT NULL DEFAULT 0,
    default_model TEXT NOT NULL DEFAULT '',
    temperature REAL NOT NULL DEFAULT 0.2,
    max_tokens INTEGER NOT NULL DEFAULT 1200,
    system_prompt TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_profile_models (
    profile_id INTEGER NOT NULL,
    model_id TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    owned_by TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL DEFAULT '',
    is_visible INTEGER NOT NULL DEFAULT 1,
    is_available INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, model_id),
    FOREIGN KEY (profile_id) REFERENCES ai_profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ai_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '新对话',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    profile_id INTEGER,
    model_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES ai_profiles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS learning_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    day TEXT NOT NULL,
    activity_type TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, day, activity_type)
);

CREATE INDEX IF NOT EXISTS idx_learning_days_day
    ON learning_days(day);

CREATE TABLE IF NOT EXISTS question_ai_labels (
    question_id INTEGER PRIMARY KEY,
    primary_skill TEXT NOT NULL DEFAULT '',
    secondary_skills TEXT NOT NULL DEFAULT '[]',
    trap_types TEXT NOT NULL DEFAULT '[]',
    attention_points TEXT NOT NULL DEFAULT '[]',
    vocabulary_demand TEXT NOT NULL DEFAULT 'medium',
    context_dependency TEXT NOT NULL DEFAULT 'medium',
    grammar_dependency TEXT NOT NULL DEFAULT 'medium',
    confidence REAL NOT NULL DEFAULT 0,
    locked INTEGER NOT NULL DEFAULT 0,
    user_edited INTEGER NOT NULL DEFAULT 0,
    model_name TEXT NOT NULL DEFAULT '',
    label_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_label_run_items (
    run_id TEXT NOT NULL,
    question_id INTEGER NOT NULL,
    processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, question_id),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS wrong_analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope_key TEXT NOT NULL DEFAULT '',
    unit_ids TEXT NOT NULL DEFAULT '[]',
    input_snapshot TEXT NOT NULL DEFAULT '{}',
    scope_title TEXT NOT NULL DEFAULT '',
    question_count INTEGER NOT NULL DEFAULT 0,
    aggregate_data TEXT NOT NULL DEFAULT '{}',
    report TEXT NOT NULL,
    model_name TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wrong_analysis_states (
    unit_id INTEGER PRIMARY KEY,
    report_id INTEGER NOT NULL,
    analyzed_session_id INTEGER NOT NULL DEFAULT 0,
    analyzed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES units(id) ON DELETE CASCADE,
    FOREIGN KEY (report_id) REFERENCES wrong_analysis_reports(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS question_bank_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    content_version TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    publisher TEXT NOT NULL DEFAULT '',
    manifest_data TEXT NOT NULL DEFAULT '{}',
    source_file TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (package_id, content_version)
);

CREATE TABLE IF NOT EXISTS question_bank_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    content_version TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    media_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (package_id, content_version, asset_id)
);

CREATE TABLE IF NOT EXISTS question_bank_revisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id TEXT NOT NULL,
    content_version TEXT NOT NULL,
    paper_external_key TEXT NOT NULL,
    action TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- v9.19: 模拟考试模式
CREATE TABLE IF NOT EXISTS exam_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    question_ids TEXT NOT NULL,
    total_questions INTEGER NOT NULL,
    duration_minutes INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    submitted_at TEXT,
    score REAL,
    max_score REAL,
    correct_count INTEGER DEFAULT 0,
    wrong_count INTEGER DEFAULT 0,
    unanswered_count INTEGER DEFAULT 0,
    FOREIGN KEY (profile_id) REFERENCES question_bank_profiles(id)
);
CREATE TABLE IF NOT EXISTS exam_answers (
    exam_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    user_answer TEXT NOT NULL DEFAULT '',
    option_order TEXT NOT NULL DEFAULT '[]',
    answered_at TEXT,
    PRIMARY KEY (exam_id, question_id),
    FOREIGN KEY (exam_id) REFERENCES exam_sessions(id) ON DELETE CASCADE
);

-- v3.0: 做题标注（关键词高亮 + 笔记持久化）
CREATE TABLE IF NOT EXISTS annotations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    unit_id INTEGER NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    text TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    color TEXT NOT NULL DEFAULT 'amber',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_annotations_unit ON annotations(unit_id);

-- v9.26: P1 作文批改（考研大小作文多维精批）
CREATE TABLE IF NOT EXISTS essay_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    essay_type TEXT NOT NULL,
    subject TEXT NOT NULL DEFAULT '英语一',
    prompt_title TEXT NOT NULL DEFAULT '',
    user_content TEXT NOT NULL,
    word_count INTEGER NOT NULL DEFAULT 0,
    score REAL NOT NULL DEFAULT 0,
    max_score REAL NOT NULL DEFAULT 20,
    band_name TEXT NOT NULL DEFAULT '',
    dimensions TEXT NOT NULL DEFAULT '{}',
    overall_comment TEXT NOT NULL DEFAULT '',
    markups TEXT NOT NULL DEFAULT '[]',
    lexical_upgrades TEXT NOT NULL DEFAULT '[]',
    model_essay TEXT NOT NULL DEFAULT '',
    essay_highlights TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_essay_user ON essay_submissions(user_id, created_at DESC);

-- v9.26: P2 口语陪练（考研复试仿真/日常流利度/发音纠偏）
CREATE TABLE IF NOT EXISTS speaking_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    scenario TEXT NOT NULL DEFAULT 'graduate_interview',
    topic TEXT NOT NULL DEFAULT '',
    ai_role TEXT NOT NULL DEFAULT 'Examiner',
    score_fluency REAL DEFAULT 0,
    score_grammar REAL DEFAULT 0,
    score_vocabulary REAL DEFAULT 0,
    score_coherence REAL DEFAULT 0,
    summary_report TEXT DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS speaking_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    turn_index INTEGER NOT NULL DEFAULT 0,
    user_text TEXT NOT NULL DEFAULT '',
    ai_reply TEXT NOT NULL DEFAULT '',
    grammar_corrections TEXT NOT NULL DEFAULT '[]',
    native_upgrade TEXT NOT NULL DEFAULT '',
    audio_duration_ms INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_speaking_turns_session ON speaking_turns(session_id, turn_index);

-- 任务E: 题目解析（AI 批量生成，content 为结构化 JSON，见 backend/prompts/explain_prompt.py）
CREATE TABLE IF NOT EXISTS question_explanations (
    question_id INTEGER PRIMARY KEY,
    content TEXT NOT NULL,
    source_model TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_question_explanations_updated
    ON question_explanations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_question_explanations_model
    ON question_explanations(source_model);

 INSERT INTO ai_profiles
    (name, base_url, api_key_encrypted, enabled, is_default, default_model,
     temperature, max_tokens, system_prompt)
SELECT
    name, base_url, api_key_encrypted, 1, 1, model,
    temperature, max_tokens, system_prompt
FROM ai_settings
WHERE NOT EXISTS (SELECT 1 FROM ai_profiles);

INSERT OR IGNORE INTO ai_profile_models
    (profile_id, model_id, display_name, is_visible, is_available)
SELECT id, default_model, default_model, 1, 1
FROM ai_profiles
WHERE default_model <> '';

CREATE INDEX IF NOT EXISTS idx_units_paper ON units(paper_id);
CREATE INDEX IF NOT EXISTS idx_questions_unit ON questions(unit_id);
CREATE INDEX IF NOT EXISTS idx_answers_session ON practice_answers(session_id);
CREATE INDEX IF NOT EXISTS idx_answer_events_question
    ON practice_answer_events(question_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_unit_submissions_session
    ON practice_unit_submissions(session_id);
CREATE INDEX IF NOT EXISTS idx_wrong_count ON wrong_stats(wrong_count DESC);
CREATE INDEX IF NOT EXISTS idx_vocab_priority
    ON vocabulary_entries(encounter_count DESC, next_review_at, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_vocab_occurrences_entry
    ON vocabulary_occurrences(entry_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_vocab_translation_queue
    ON vocabulary_entries(translation_status, user_edited, updated_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ai_profiles_single_default
    ON ai_profiles(is_default) WHERE is_default = 1;
CREATE INDEX IF NOT EXISTS idx_ai_profile_models_selector
    ON ai_profile_models(profile_id, is_visible, is_available);
CREATE INDEX IF NOT EXISTS idx_ai_conversations_updated
    ON ai_conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_messages_conversation
    ON ai_messages(conversation_id, id);
CREATE INDEX IF NOT EXISTS idx_question_ai_labels_locked
    ON question_ai_labels(locked, updated_at);
CREATE INDEX IF NOT EXISTS idx_question_label_run_items_question
    ON question_label_run_items(question_id, run_id);
CREATE INDEX IF NOT EXISTS idx_wrong_analysis_created
    ON wrong_analysis_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_question_bank_assets_lookup
    ON question_bank_assets(package_id, content_version, asset_id);
CREATE INDEX IF NOT EXISTS idx_question_bank_revisions_paper
    ON question_bank_revisions(paper_external_key, created_at DESC);
"""


def connect() -> sqlite3.Connection:
    ensure_directories()
    # FastAPI may enter and resume a synchronous dependency on different
    # worker threads. SQLite's default thread check would then intermittently
    # reject an otherwise valid request with a 500 response.
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    # v9.24: 生产级并发配置（WAL + 忙等待——防多线程/后台任务 database is locked）
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA synchronous = NORMAL")
    except sqlite3.Error:
        pass  # 只读/旧环境不强制
    return connection


def _ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    declaration: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(
            f"ALTER TABLE {table} ADD COLUMN {column} {declaration}"
        )


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row["name"])
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }


def _rebuild_child_tables(
    connection: sqlite3.Connection,
    *,
    create_statements: dict[str, str],
    order: list[str],
) -> None:
    """Rebuild tables that reference the rebuilt parent table.

    Runs inside the papers-table rebuild where foreign keys are already
    disabled. Child rows are preserved by copying every column that exists
    in both the old child table and the new table definition. Tables that do
    not exist are skipped.
    """
    for table in order:
        snapshot_table = f"papers_rebuild_snapshot_{table}"
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (snapshot_table,),
        ).fetchone():
            continue
        old_columns = _table_columns(connection, snapshot_table)
        connection.execute(f"DROP TABLE {table}")
        connection.execute(create_statements[table])
        new_columns = _table_columns(connection, table)
        shared = [column for column in new_columns if column in old_columns]
        if shared:
            columns = ", ".join(f'"{column}"' for column in shared)
            connection.execute(
                f"""
                INSERT INTO {table} ({columns})
                SELECT {columns} FROM {snapshot_table}
                """
            )
        connection.execute(f"DROP TABLE {snapshot_table}")


def _paper_child_create_statements() -> dict[str, str]:
    statements: dict[str, str] = {}
    import re

    for match in re.finditer(
        r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\);",
        SCHEMA,
        re.DOTALL,
    ):
        name = match.group(1)
        body = match.group(2)
        if name in {
            "units",
            "questions",
            "options",
            "practice_sessions",
            "practice_answers",
            "practice_answer_events",
            "practice_unit_submissions",
            "wrong_stats",
            "vocabulary_occurrences",
            "wrong_analysis_states",
        }:
            statements[name] = f"CREATE TABLE {name} ({body})"
    return statements


def _run_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO question_bank_profiles (name, description, color, icon, is_default)
        SELECT '考研英语一', '完形 · 阅读 · 新题型 · 翻译 · 写作', '#486d5c', 'book', 1
        WHERE NOT EXISTS (
            SELECT 1 FROM question_bank_profiles
            WHERE name = '考研英语一' COLLATE NOCASE
        )
        """
    )
    # v9.19: 预置其他四个类别
    for name, desc, color, icon in [
        ('高中英语', '阅读理解 · 完形 · 七选五 · 语法填空 · 写作', '#e67e22', 'graduation-cap'),
        ('大学英语四级', '听力 · 阅读 · 翻译 · 写作', '#3498db', 'book-open'),
        ('大学英语六级', '听力 · 阅读 · 翻译 · 写作', '#8e44ad', 'book-open'),
        ('考研英语二', '完形 · 阅读 · 新题型 · 翻译 · 写作', '#2ecc71', 'book'),
    ]:
        connection.execute(
            """
            INSERT OR IGNORE INTO question_bank_profiles (name, description, color, icon)
            VALUES (?, ?, ?, ?)
            """,
            (name, desc, color, icon),
        )
    default_profile_id = connection.execute(
        "SELECT id FROM question_bank_profiles WHERE name = '考研英语一' COLLATE NOCASE ORDER BY id LIMIT 1"
    ).fetchone()["id"]
    _ensure_column(connection, "papers", "external_key", "TEXT")
    _ensure_column(connection, "papers", "package_id", "TEXT")
    _ensure_column(connection, "papers", "content_version", "TEXT")
    _ensure_column(connection, "papers", "source_metadata", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(connection, "papers", "profile_id", f"INTEGER NOT NULL DEFAULT {int(default_profile_id)}")
    _ensure_column(connection, "papers", "deleted_at", "TEXT")
    _ensure_column(connection, "units", "external_key", "TEXT")
    _ensure_column(connection, "units", "audio_path", "TEXT")
    _ensure_column(connection, "questions", "external_key", "TEXT")
    _ensure_column(connection, "questions", "content_hash", "TEXT")
    _ensure_column(connection, "options", "metadata", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(connection, "wrong_analysis_reports", "scope_key", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "wrong_analysis_reports", "unit_ids", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(connection, "wrong_analysis_reports", "input_snapshot", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(connection, "wrong_analysis_states", "analyzed_session_id", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "import_jobs", "parse_context", "TEXT NOT NULL DEFAULT '{}'")
    _ensure_column(connection, "import_jobs", "profile_id", f"INTEGER NOT NULL DEFAULT {int(default_profile_id)}")
    _ensure_column(connection, "import_jobs", "answer_stored_path", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "import_jobs", "deleted_at", "TEXT")
    _ensure_column(connection, "vocabulary_entries", "synonyms", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(connection, "vocabulary_entries", "antonyms", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(connection, "vocabulary_entries", "similar_forms", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(connection, "vocabulary_entries", "category", "TEXT NOT NULL DEFAULT ''")  # v9.27: 词库分类（前端 category 筛选）
    _ensure_column(connection, "annotations", "tag", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "papers", "exam_type", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "papers", "exam_month", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(connection, "papers", "set_number", "INTEGER NOT NULL DEFAULT 1")
    _ensure_column(connection, "papers", "session_group_key", "TEXT NOT NULL DEFAULT ''")
    _ensure_column(connection, "ai_profiles", "task_tags", "TEXT NOT NULL DEFAULT '[]'")
    _ensure_column(connection, "ai_profiles", "priority", "INTEGER NOT NULL DEFAULT 100")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'ok',
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_ai_usage_task_time ON ai_usage(task, created_at)"
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS diagnostic_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scope_key TEXT NOT NULL DEFAULT '',
            question_ids TEXT NOT NULL DEFAULT '[]',
            input_snapshot TEXT NOT NULL DEFAULT '{}',
            question_count INTEGER NOT NULL DEFAULT 0,
            aggregate_data TEXT NOT NULL DEFAULT '{}',
            level_data TEXT NOT NULL DEFAULT '{}',
            recommendations TEXT NOT NULL DEFAULT '[]',
            trend_data TEXT NOT NULL DEFAULT '{}',
            report TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        UPDATE vocabulary_entries
        SET translation_status = 'queued'
        WHERE translation_status = 'pending'
        """
    )
    connection.execute(
        "UPDATE papers SET profile_id = ? WHERE profile_id IS NULL OR profile_id = 0",
        (default_profile_id,),
    )
    connection.execute(
        "UPDATE import_jobs SET profile_id = ? WHERE profile_id IS NULL OR profile_id = 0",
        (default_profile_id,),
    )
    # Older databases declared papers.year globally UNIQUE. Rebuild only that
    # table so the new invariant can be scoped by profile/external_key while
    # preserving all existing IDs and foreign-key references.
    table_sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'papers'"
    ).fetchone()["sql"] or ""
    if "YEAR INTEGER NOT NULL UNIQUE" in table_sql.upper():
        child_create = _paper_child_create_statements()
        connection.execute("PRAGMA foreign_keys = OFF")
        snapshot_columns: dict[str, list[str]] = {}
        for child in child_create:
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (child,),
            ).fetchone():
                columns = _table_columns(connection, child)
                snapshot_columns[child] = columns
                column_list = ", ".join(f'"{column}"' for column in columns)
                connection.execute(
                    f"""
                    CREATE TABLE papers_rebuild_snapshot_{child} AS
                    SELECT {column_list} FROM {child}
                    """
                )
        connection.execute(
            "ALTER TABLE papers RENAME TO papers_rebuild_tmp_papers"
        )
        connection.execute(
            """
            CREATE TABLE papers_rebuild (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                subject TEXT NOT NULL DEFAULT '英语一',
                title TEXT NOT NULL,
                exam_type TEXT NOT NULL DEFAULT '',
                exam_month INTEGER NOT NULL DEFAULT 0,
                set_number INTEGER NOT NULL DEFAULT 1,
                session_group_key TEXT NOT NULL DEFAULT '',
                source_file TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                external_key TEXT,
                package_id TEXT,
                content_version TEXT,
                source_metadata TEXT NOT NULL DEFAULT '{}',
                deleted_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (profile_id) REFERENCES question_bank_profiles(id)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO papers_rebuild
                (id, profile_id, year, subject, title, source_file, status,
                 exam_type, exam_month, set_number, session_group_key,
                 external_key, package_id, content_version, source_metadata,
                 deleted_at, created_at, updated_at)
            SELECT id, profile_id, year, subject, title, source_file, status, '', 0, 1, '',
                   external_key, package_id, content_version, source_metadata,
                   deleted_at, created_at, updated_at
            FROM papers_rebuild_tmp_papers
            """
        )
        connection.execute("ALTER TABLE papers_rebuild RENAME TO papers")
        connection.execute("DROP TABLE papers_rebuild_tmp_papers")
        _rebuild_child_tables(
            connection,
            create_statements=child_create,
            order=(
                "units",
                "questions",
                "options",
                "practice_sessions",
                "practice_answers",
                "practice_answer_events",
                "practice_unit_submissions",
                "wrong_stats",
                "vocabulary_occurrences",
                "wrong_analysis_states",
            ),
        )
        connection.execute("PRAGMA foreign_keys = ON")
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise RuntimeError(
                f"数据库迁移后外键校验失败：{violations}"
            )
    connection.execute(
        """
        INSERT OR IGNORE INTO app_settings(key, value)
        VALUES ('active_question_bank_profile_id', ?)
        """,
        (str(default_profile_id),),
    )
    connection.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_units_external_key
            ON units(paper_id, external_key)
            WHERE external_key IS NOT NULL AND external_key <> '';
        CREATE UNIQUE INDEX IF NOT EXISTS idx_questions_external_key
            ON questions(unit_id, external_key)
            WHERE external_key IS NOT NULL AND external_key <> '';
        CREATE INDEX IF NOT EXISTS idx_papers_external_key
            ON papers(external_key);
        CREATE INDEX IF NOT EXISTS idx_papers_profile
            ON papers(profile_id, deleted_at, year DESC);
        CREATE INDEX IF NOT EXISTS idx_import_jobs_profile
            ON import_jobs(profile_id, deleted_at, updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_trash_purge
            ON trash_entries(purge_after, restored_at);
        """
    )


def initialize_database() -> None:
    with connect() as connection:
        connection.executescript(SCHEMA)
        _run_migrations(connection)
        _migrate_add_user_id(connection)
        _migrate_multi_user_schema(connection)  # v9.24: 多用户约束重建


# v9.24: 多用户迁移——核心个人数据表加 user_id（幂等：已存在则跳过）
_USER_ID_TABLES = {
    "exam_sessions": "ALTER TABLE exam_sessions ADD COLUMN user_id INTEGER",
    "practice_sessions": "ALTER TABLE practice_sessions ADD COLUMN user_id INTEGER",
    "ai_conversations": "ALTER TABLE ai_conversations ADD COLUMN user_id INTEGER",
    "vocabulary_entries": "ALTER TABLE vocabulary_entries ADD COLUMN user_id INTEGER",
}


def _migrate_add_user_id(connection: sqlite3.Connection) -> None:
    for table, ddl in _USER_ID_TABLES.items():
        try:
            cols = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in cols:
                connection.execute(ddl)
                connection.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_user_id ON {table}(user_id)"
                )
                print(f"[migrate] {table}.user_id added")
        except Exception as exc:
            # v9.24: 不吞异常——迁移失败要暴露（防不一致状态继续服务）
            print(f"[migrate][ERROR] {table}.user_id 迁移失败: {exc}")
    connection.commit()


# v9.24: 多用户 schema 升级——重建唯一约束/主键（SQLite 不支持 ALTER 约束）
def _table_sql(connection: sqlite3.Connection, table: str) -> str:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row[0] if row else ""


def _migrate_multi_user_schema(connection: sqlite3.Connection) -> None:
    try:
        # 1. annotations / learning_days 加 user_id 列（ALTER 可处理）
        for table, ddl in [
            ("annotations", "ALTER TABLE annotations ADD COLUMN user_id INTEGER DEFAULT NULL"),
            ("learning_days", "ALTER TABLE learning_days ADD COLUMN user_id INTEGER DEFAULT NULL"),
        ]:
            cols = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if "user_id" not in cols:
                connection.execute(ddl)
                print(f"[migrate] {table}.user_id added")
        # 2. vocabulary_entries: 全局 UNIQUE → 联合 UNIQUE（重建表）
        v_sql = _table_sql(connection, "vocabulary_entries")
        if v_sql and "normalized_term TEXT NOT NULL UNIQUE" in v_sql:
            _rebuild_vocabulary_entries(connection)
            print("[migrate] vocabulary_entries 联合唯一约束重建")
        # 联合唯一索引（新库/重建后都执行；旧库需 user_id 列存在——重建已保证）
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab_user_term "
            "ON vocabulary_entries(user_id, normalized_term)"
        )
        # 3. wrong_stats: 主键 question_id → (user_id, question_id)（重建表）
        w_sql = _table_sql(connection, "wrong_stats")
        if w_sql and "question_id INTEGER PRIMARY KEY" in w_sql:
            _rebuild_wrong_stats(connection)
            print("[migrate] wrong_stats 复合主键重建")
        # 4. learning_days: 唯一 (day, activity_type) → (user_id, day, activity_type)（重建表）
        l_sql = _table_sql(connection, "learning_days")
        if l_sql and "UNIQUE (day, activity_type)" in l_sql and "UNIQUE (user_id, day" not in l_sql:
            _rebuild_learning_days(connection)
            print("[migrate] learning_days 联合唯一重建")
        # 5. 关键外键索引（级联删除性能）
        for idx, tbl, col in [
            ("idx_practice_answers_question", "practice_answers", "question_id"),
            ("idx_practice_answer_events_session", "practice_answer_events", "session_id"),
            ("idx_vocabulary_reviews_entry", "vocabulary_reviews", "entry_id"),
            ("idx_vocabulary_occurrences_unit", "vocabulary_occurrences", "unit_id"),
        ]:
            connection.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON {tbl}({col})")
        connection.commit()
    except Exception as exc:
        print(f"[migrate][ERROR] 多用户 schema 升级失败: {exc}")
        raise


def _rebuild_vocabulary_entries(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")
        connection.execute("ALTER TABLE vocabulary_entries RENAME TO vocabulary_entries_old")
        connection.execute(
            """CREATE TABLE vocabulary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT NULL,
                term TEXT NOT NULL,
                normalized_term TEXT NOT NULL,
                lemma TEXT NOT NULL DEFAULT '',
                phonetic TEXT NOT NULL DEFAULT '',
                part_of_speech TEXT NOT NULL DEFAULT '',
                contextual_meaning TEXT NOT NULL DEFAULT '',
                common_meaning TEXT NOT NULL DEFAULT '',
                synonyms TEXT NOT NULL DEFAULT '[]',
                antonyms TEXT NOT NULL DEFAULT '[]',
                similar_forms TEXT NOT NULL DEFAULT '[]',
                memory_hint TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                translation_status TEXT NOT NULL DEFAULT 'pending',
                translation_error TEXT NOT NULL DEFAULT '',
                encounter_count INTEGER NOT NULL DEFAULT 1,
                study_status TEXT NOT NULL DEFAULT 'learning',
                manually_frequent INTEGER NOT NULL DEFAULT 0,
                user_edited INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT,
                last_reviewed_at TEXT,
                fsrs_due TEXT,
                fsrs_stability REAL,
                fsrs_difficulty REAL,
                fsrs_state INTEGER DEFAULT 0,
                fsrs_step INTEGER DEFAULT 0,
                fsrs_last_review TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        connection.execute(
            """INSERT INTO vocabulary_entries (
                id, user_id, term, normalized_term, lemma, phonetic, part_of_speech,
                contextual_meaning, common_meaning, synonyms, antonyms, similar_forms,
                memory_hint, note, translation_status, translation_error, encounter_count,
                study_status, manually_frequent, user_edited, next_review_at, last_reviewed_at,
                fsrs_due, fsrs_stability, fsrs_difficulty, fsrs_state, fsrs_step, fsrs_last_review,
                created_at, updated_at, last_seen_at
            ) SELECT id, user_id, term, normalized_term, lemma, phonetic, part_of_speech,
                contextual_meaning, common_meaning, synonyms, antonyms, similar_forms,
                memory_hint, note, translation_status, translation_error, encounter_count,
                study_status, manually_frequent, user_edited, next_review_at, last_reviewed_at,
                fsrs_due, fsrs_stability, fsrs_difficulty, fsrs_state, fsrs_step, fsrs_last_review,
                created_at, updated_at, last_seen_at
            FROM vocabulary_entries_old"""
        )
        connection.execute("DROP TABLE vocabulary_entries_old")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_vocab_user_term ON vocabulary_entries(user_id, normalized_term)"
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _rebuild_wrong_stats(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")
        connection.execute("ALTER TABLE wrong_stats RENAME TO wrong_stats_old")
        connection.execute(
            """CREATE TABLE wrong_stats (
                user_id INTEGER DEFAULT NULL,
                question_id INTEGER NOT NULL,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                wrong_count INTEGER NOT NULL DEFAULT 0,
                recent_results TEXT NOT NULL DEFAULT '[]',
                consecutive_correct INTEGER NOT NULL DEFAULT 0,
                manually_frequent INTEGER NOT NULL DEFAULT 0,
                last_wrong_at TEXT,
                last_attempt_at TEXT,
                PRIMARY KEY (user_id, question_id),
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
            )"""
        )
        connection.execute(
            """INSERT INTO wrong_stats (
                user_id, question_id, attempt_count, wrong_count, recent_results,
                consecutive_correct, manually_frequent, last_wrong_at, last_attempt_at
            ) SELECT NULL, question_id, attempt_count, wrong_count, recent_results,
                consecutive_correct, manually_frequent, last_wrong_at, last_attempt_at
            FROM wrong_stats_old"""
        )
        connection.execute("DROP TABLE wrong_stats_old")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _rebuild_learning_days(connection: sqlite3.Connection) -> None:
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")
        connection.execute("ALTER TABLE learning_days RENAME TO learning_days_old")
        connection.execute(
            """CREATE TABLE learning_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER DEFAULT NULL,
                day TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                detail TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, day, activity_type)
            )"""
        )
        connection.execute(
            """INSERT INTO learning_days (id, user_id, day, activity_type, detail, created_at)
               SELECT id, NULL, day, activity_type, detail, created_at FROM learning_days_old"""
        )
        connection.execute("DROP TABLE learning_days_old")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_learning_days_day ON learning_days(day)"
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def get_default_profile_id(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT id FROM question_bank_profiles WHERE is_default = 1 AND deleted_at IS NULL ORDER BY id LIMIT 1"
    ).fetchone()
    if row:
        return int(row["id"])
    row = connection.execute(
        "SELECT id FROM question_bank_profiles WHERE deleted_at IS NULL ORDER BY id LIMIT 1"
    ).fetchone()
    if not row:
        cursor = connection.execute(
            "INSERT INTO question_bank_profiles(name, is_default) VALUES ('考研英语一', 1)"
        )
        connection.commit()
        return int(cursor.lastrowid)
    return int(row["id"])


def get_active_profile_id(connection: sqlite3.Connection) -> int:
    default_id = get_default_profile_id(connection)
    row = connection.execute(
        "SELECT value FROM app_settings WHERE key = 'active_question_bank_profile_id'"
    ).fetchone()
    try:
        profile_id = int(row["value"]) if row else default_id
    except (TypeError, ValueError):
        profile_id = default_id
    exists = connection.execute(
        "SELECT 1 FROM question_bank_profiles WHERE id = ? AND deleted_at IS NULL",
        (profile_id,),
    ).fetchone()
    if not exists:
        profile_id = default_id
        connection.execute(
            """
            INSERT INTO app_settings(key, value)
            VALUES ('active_question_bank_profile_id', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(profile_id),),
        )
        connection.commit()
    return profile_id


def set_active_profile_id(connection: sqlite3.Connection, profile_id: int) -> None:
    exists = connection.execute(
        "SELECT 1 FROM question_bank_profiles WHERE id = ? AND deleted_at IS NULL",
        (profile_id,),
    ).fetchone()
    if not exists:
        raise ValueError("题库配置不存在或已在回收站")
    connection.execute(
        """
        INSERT INTO app_settings(key, value)
        VALUES ('active_question_bank_profile_id', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(profile_id),),
    )
    connection.commit()


def new_trash_batch() -> tuple[str, str]:
    deleted_at = datetime.now(timezone.utc).replace(microsecond=0)
    purge_after = deleted_at + timedelta(days=7)
    return uuid4().hex, purge_after.strftime("%Y-%m-%d %H:%M:%S")


def get_db() -> Generator[sqlite3.Connection, None, None]:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()
