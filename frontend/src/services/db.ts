// AI 英语刷题机 — 离线数据库 (sql.js + IndexedDB 持久化)
// 参考: sql.js + IndexedDB: Building an Offline-First Web App (2026)
// 替代后端 Python SQLite，浏览器端直接运行

import initSqlJs, { type Database, type SqlJsStatic } from 'sql.js'

const DB_NAME = 'english-machine'
const DB_KEY = 'sqlite-db'

let SQL: SqlJsStatic | null = null
let db: Database | null = null

// ── 初始化 ──

export async function initDatabase(): Promise<Database> {
  if (db) return db

  // v3.3: 用 wasmBinary（fetch buffer）而非 instantiateStreaming——
  // Capacitor WebView 对 https://localhost 的 streaming 支持不稳定（曾返回 HTML 导致加载失败）
  let SQL: SqlJsStatic
  try {
    const wasmResp = await fetch('/sql-wasm.wasm', { signal: AbortSignal.timeout(15000) })
    if (!wasmResp.ok) throw new Error(`wasm 加载失败: ${wasmResp.status}`)
    const wasmBinary = new Uint8Array(await wasmResp.arrayBuffer())
    SQL = await initSqlJs({ wasmBinary: wasmBinary.buffer as ArrayBuffer })
  } catch (e) {
    console.error('[offline] sql.js wasm 加载失败:', e)
    throw e
  }

  // 尝试从 IndexedDB 恢复（异常不阻塞——走 seed）
  let saved: Uint8Array | null = null
  try {
    saved = await loadFromIndexedDB()
  } catch (e) {
    console.error('[offline] IndexedDB 恢复失败，走 seed:', e)
    saved = null
  }
  if (saved) {
    db = new SQL.Database(saved)
  } else {
    // v9.20: 优先加载打包的预置题库（question_bank.db 随构建发布，
    // App/离线场景直接使用完整题库——无需后端即可刷题，也减少网络攻击面）
    const seed = await fetchSeedDatabase()
    if (seed) {
      db = new SQL.Database(seed)
    } else {
      db = new SQL.Database()
      createSchema()
    }
    try {
      await saveToIndexedDB()
    } catch (e) {
      console.error('[offline] IndexedDB 保存失败（忽略）:', e)
    }
  }

  return db
}

// v9.20: 加载预置题库（public/question_bank.db，sql.js 可直接读取 SQLite 格式）
async function fetchSeedDatabase(): Promise<Uint8Array | null> {
  try {
    // v3.3: 绝对路径——相对路径在路由页会 404
    const resp = await fetch('/question_bank.db', { signal: AbortSignal.timeout(8000) })
    if (!resp.ok) return null
    const buf = await resp.arrayBuffer()
    return new Uint8Array(buf)
  } catch {
    return null
  }
}

function createSchema() {
  if (!db) return
  db.run(`
    CREATE TABLE IF NOT EXISTS question_bank_profiles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      description TEXT NOT NULL DEFAULT '',
      color TEXT NOT NULL DEFAULT '#486d5c',
      icon TEXT NOT NULL DEFAULT 'book',
      is_default INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    INSERT OR IGNORE INTO question_bank_profiles (id, name, description, color, icon, is_default) VALUES (1, '考研英语一', '完形 · 阅读 · 新题型 · 翻译 · 写作', '#486d5c', 'book', 1);
    INSERT OR IGNORE INTO question_bank_profiles (id, name, description, color, icon) VALUES (2, '高中英语', '阅读理解 · 完形 · 七选五 · 语法填空 · 写作', '#e67e22', 'graduation-cap');
    INSERT OR IGNORE INTO question_bank_profiles (id, name, description, color, icon) VALUES (3, '大学英语四级', '听力 · 阅读 · 翻译 · 写作', '#3498db', 'book-open');
    INSERT OR IGNORE INTO question_bank_profiles (id, name, description, color, icon) VALUES (4, '大学英语六级', '听力 · 阅读 · 翻译 · 写作', '#8e44ad', 'book-open');
    INSERT OR IGNORE INTO question_bank_profiles (id, name, description, color, icon) VALUES (5, '考研英语二', '完形 · 阅读 · 新题型 · 翻译 · 写作', '#2ecc71', 'book');

    CREATE TABLE IF NOT EXISTS papers (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      year INTEGER NOT NULL,
      profile_id INTEGER NOT NULL DEFAULT 1,
      status TEXT NOT NULL DEFAULT 'draft',
      deleted_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS units (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      paper_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      unit_type TEXT NOT NULL,
      passage TEXT NOT NULL DEFAULT '',
      sequence INTEGER NOT NULL DEFAULT 0,
      shared_data TEXT DEFAULT '{}',
      FOREIGN KEY (paper_id) REFERENCES papers(id)
    );

    CREATE TABLE IF NOT EXISTS questions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      unit_id INTEGER NOT NULL,
      number INTEGER NOT NULL,
      stem TEXT NOT NULL,
      question_type TEXT NOT NULL DEFAULT 'single_choice',
      answer TEXT NOT NULL DEFAULT '',
      score REAL NOT NULL DEFAULT 2,
      sequence INTEGER NOT NULL DEFAULT 0,
      metadata TEXT DEFAULT '{}',
      FOREIGN KEY (unit_id) REFERENCES units(id)
    );

    CREATE TABLE IF NOT EXISTS vocabulary_entries (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      term TEXT NOT NULL,
      normalized_term TEXT NOT NULL UNIQUE,
      category TEXT NOT NULL DEFAULT '',
      lemma TEXT NOT NULL DEFAULT '',
      phonetic TEXT NOT NULL DEFAULT '',
      common_meaning TEXT NOT NULL DEFAULT '',
      contextual_meaning TEXT NOT NULL DEFAULT '',
      translation_status TEXT NOT NULL DEFAULT 'pending',
      encounter_count INTEGER NOT NULL DEFAULT 1,
      study_status TEXT NOT NULL DEFAULT 'learning',
      fsrs_due TEXT,
      fsrs_stability REAL,
      fsrs_difficulty REAL,
      fsrs_state INTEGER DEFAULT 0,
      fsrs_step INTEGER DEFAULT 0,
      fsrs_last_review TEXT,
      next_review_at TEXT,
      last_reviewed_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS vocabulary_occurrences (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      entry_id INTEGER NOT NULL,
      surface_form TEXT NOT NULL,
      context_sentence TEXT NOT NULL DEFAULT '',
      unit_id INTEGER,
      FOREIGN KEY (entry_id) REFERENCES vocabulary_entries(id)
    );

    CREATE TABLE IF NOT EXISTS vocabulary_reviews (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      entry_id INTEGER NOT NULL,
      rating TEXT NOT NULL,
      next_review_at TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (entry_id) REFERENCES vocabulary_entries(id)
    );

    CREATE TABLE IF NOT EXISTS wrong_stats (
      question_id INTEGER PRIMARY KEY,
      attempt_count INTEGER NOT NULL DEFAULT 0,
      wrong_count INTEGER NOT NULL DEFAULT 0,
      recent_results TEXT DEFAULT '[]',
      manually_frequent INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (question_id) REFERENCES questions(id)
    );

    CREATE TABLE IF NOT EXISTS practice_sessions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      mode TEXT NOT NULL DEFAULT 'random',
      status TEXT NOT NULL DEFAULT 'in_progress',
      paper_id INTEGER,
      score REAL,
      max_score REAL,
      started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      submitted_at TEXT
    );

    CREATE TABLE IF NOT EXISTS learning_days (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      day TEXT NOT NULL,
      activity_type TEXT NOT NULL,
      detail TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(day, activity_type)
    );

    CREATE TABLE IF NOT EXISTS ai_profiles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      base_url TEXT NOT NULL DEFAULT 'https://api.deepseek.com/v1',
      api_key_encrypted TEXT,
      default_model TEXT NOT NULL DEFAULT 'deepseek-v4-flash',
      enabled INTEGER NOT NULL DEFAULT 1,
      is_default INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    INSERT OR IGNORE INTO ai_profiles (id, name, base_url, default_model, enabled, is_default)
      VALUES (1, 'DeepSeek V4-Flash', 'https://api.deepseek.com/v1', 'deepseek-v4-flash', 1, 1);
  `)
}

// ── IndexedDB 持久化 ──

function openStore(): Promise<IDBObjectStore> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore('data')
    }
    req.onsuccess = () => {
      const tx = req.result.transaction('data', 'readwrite')
      resolve(tx.objectStore('data'))
    }
    req.onerror = () => reject(req.error)
  })
}

async function saveToIndexedDB(): Promise<void> {
  if (!db) return
  const data = db.export()
  const store = await openStore()
  return new Promise((resolve, reject) => {
    const req = store.put(data, DB_KEY)
    req.onsuccess = () => resolve()
    req.onerror = () => reject(req.error)
  })
}

async function loadFromIndexedDB(): Promise<Uint8Array | null> {
  const store = await openStore()
  return new Promise((resolve, reject) => {
    const req = store.get(DB_KEY)
    req.onsuccess = () => resolve(req.result || null)
    req.onerror = () => reject(req.error)
  })
}

// ── 便捷 API ──

export function getDb(): Database {
  if (!db) throw new Error('数据库未初始化，请先调用 initDatabase()')
  return db
}

/** 执行查询，返回行数组 */
export function queryAll(sql: string, params: any[] = []): Record<string, any>[] {
  const d = getDb()
  const stmt = d.prepare(sql)
  if (params.length) stmt.bind(params)
  const rows: Record<string, any>[] = []
  while (stmt.step()) {
    rows.push(stmt.getAsObject())
  }
  stmt.free()
  return rows
}

/** 执行查询，返回第一行 */
export function queryOne(sql: string, params: any[] = []): Record<string, any> | null {
  const rows = queryAll(sql, params)
  return rows[0] || null
}

/** 执行写操作（INSERT/UPDATE/DELETE），自动持久化 */
export function execute(sql: string, params: any[] = []) {
  const d = getDb()
  d.run(sql, params)
  // 自动保存到 IndexedDB
  saveToIndexedDB().catch(console.error)
}

/** 获取最后插入的 rowid */
export function lastInsertRowId(): number {
  const d = getDb()
  const r = d.exec('SELECT last_insert_rowid() AS id')
  return r[0]?.values[0][0] as number || 0
}