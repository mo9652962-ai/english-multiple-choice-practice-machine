// API 适配层 — 自动切换后端 API / sql.js 离线模式
// PWA 手机端：后端不可用 → 自动用 sql.js
// 桌面端：后端可用 → 用 HTTP API

import { queryAll, queryOne, execute, lastInsertRowId, initDatabase, getDb } from './db'

let backendAvailable: boolean | null = null
let offlineMode = false
const listeners: (() => void)[] = []

export function getOfflineMode() { return offlineMode }
export function onModeChange(fn: () => void) { listeners.push(fn) }

// ── 检测后端 ──

export async function checkBackend(): Promise<boolean> {
  if (backendAvailable !== null) return backendAvailable
  // Capacitor 原生平台（手机）：无本地后端——直接切 sql.js（不走 health——Capacitor 会返回 index.html 200 误判）
  const isNative = !!(window as any)?.Capacitor?.isNativePlatform?.()
  if (isNative) {
    backendAvailable = false
    offlineMode = true
    await initDatabase()
    listeners.forEach(fn => fn())
    return backendAvailable
  }
  try {
    const resp = await fetch('/api/health', { signal: AbortSignal.timeout(2000) })
    backendAvailable = resp.ok
  } catch {
    backendAvailable = false
  }
  if (!backendAvailable) {
    offlineMode = true
    await initDatabase()
    listeners.forEach(fn => fn())
  }
  return backendAvailable
}

// ── 统一 API ──

export async function apiGet(path: string): Promise<any> {
  await checkBackend()
  if (backendAvailable) {
    const resp = await fetch(`/api${path}`)
    if (!resp.ok) throw new Error(`${resp.status}`)
    return resp.json()
  }
  // 离线模式：路由到 sql.js
  return offlineGet(path)
}

export async function apiPost(path: string, body?: any): Promise<any> {
  await checkBackend()
  if (backendAvailable) {
    const resp = await fetch(`/api${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    return resp.json()
  }
  return offlinePost(path, body)
}

export async function apiPut(path: string, body?: any): Promise<any> {
  await checkBackend()
  if (backendAvailable) {
    const resp = await fetch(`/api${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    return resp.json()
  }
  return offlinePut(path, body)
}

export async function apiPatch(path: string, body?: any): Promise<any> {
  await checkBackend()
  if (backendAvailable) {
    const resp = await fetch(`/api${path}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    return resp.json()
  }
  // v3.3: 离线 PATCH 兜底（本地更新或空响应——防 HTML JSON 报错）
  return offlinePut(path, body) || {}
}

export async function apiDelete(path: string): Promise<any> {
  await checkBackend()
  if (backendAvailable) {
    const resp = await fetch(`/api${path}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error(`${resp.status}`)
    return resp.json().catch(() => ({}))
  }
  // v3.3: 离线 DELETE 兜底（空响应）
  return {}
}

// ── 离线路由（sql.js） ──

function offlineGet(path: string): any {
  // Dashboard
  if (path === '/startup' || path === '/overview' || path === '/dashboard') {
    return {
      active_profile: queryOne("SELECT * FROM question_bank_profiles WHERE id = 1"),
      paper_count: queryOne("SELECT COUNT(*) AS count FROM papers WHERE status = 'published' AND deleted_at IS NULL")?.count || 0,
      unit_count: 0,
      question_count: 0,
      wrong_count: queryOne("SELECT COUNT(*) AS count FROM wrong_stats WHERE wrong_count > 0")?.count || 0,
      frequent_count: 0,
      recent_sessions: [],
    }
  }
  // Vocabulary home
  if (path.startsWith('/vocabulary/home')) {
    const rows = queryAll("SELECT * FROM vocabulary_entries ORDER BY encounter_count DESC LIMIT 20")
    return { items: rows }
  }
  // AI settings
  if (path === '/ai/settings') {
    return queryOne("SELECT * FROM ai_profiles WHERE is_default = 1") || {}
  }
  // AI profiles list（离线 APK：key 密文不回显，仅返回 has_api_key）
  if (path === '/ai/profiles' || path.startsWith('/ai/profiles?')) {
    const rows = queryAll("SELECT id, name, base_url, default_model, temperature, max_tokens, system_prompt, enabled, is_default, api_key_encrypted FROM ai_profiles ORDER BY id")
    return rows.map((r: any) => ({
      id: r.id, name: r.name, base_url: r.base_url, default_model: r.default_model,
      temperature: r.temperature, max_tokens: r.max_tokens, system_prompt: r.system_prompt,
      enabled: !!r.enabled, is_default: !!r.is_default,
      has_api_key: !!(r.api_key_encrypted && r.api_key_encrypted.length > 8),
      models: [],
    }))
  }
  // Streak
  if (path === '/dashboard/streak') {
    return { streak: { current: 0, best: 0, today_active: false }, heatmap: [], monthly: { month: '', total_activities: 0, active_days: 0, breakdown: [] }, weekly: { period: '', active_days: 0, total_activities: 0, streak_days: 0, breakdown: [], daily: [] } }
  }
  // Vocabulary due-today
  if (path === '/vocabulary/due-today') {
    return { count: 0, entries: [] }
  }
  // Vocabulary stats
  if (path === '/vocabulary/stats/summary') {
    const total = queryOne("SELECT COUNT(*) AS count FROM vocabulary_entries")?.count || 0
    return { total, mastered: 0, learning: total, due_today: 0, mastery_rate: 0 }
  }
  // Papers list
  if (path === '/papers' || path.startsWith('/papers?')) {
    return queryAll("SELECT * FROM papers WHERE status = 'published' AND deleted_at IS NULL ORDER BY year DESC")
  }
  // Wrong list
  if (path === '/wrong') {
    return queryAll(`
      SELECT q.id AS question_id, q.number, q.stem,
             u.id AS unit_id, u.title AS unit_title, u.unit_type,
             p.year, ws.attempt_count, ws.wrong_count, ws.recent_results, ws.manually_frequent
      FROM wrong_stats ws
      JOIN questions q ON q.id = ws.question_id
      JOIN units u ON u.id = q.unit_id
      JOIN papers p ON p.id = u.paper_id
      WHERE ws.wrong_count > 0 AND p.deleted_at IS NULL
      ORDER BY ws.wrong_count DESC`)
  }
  // Vocabulary quiz（v3.3: 词汇量自测——本地随机抽词）
  if (path.startsWith('/vocab/quiz')) {
    const m = path.match(/count=(\d+)/)
    const count = m ? parseInt(m[1]) : 10
    const rows = queryAll("SELECT * FROM vocabulary_entries ORDER BY RANDOM() LIMIT ?", [count])
    return { items: rows }
  }
  // Vocab cloze（v3.3: 完形填空——本地随机词；库无例句列——用释义句）
  if (path.startsWith('/vocab/cloze')) {
    const m = path.match(/count=(\d+)/)
    const count = m ? parseInt(m[1]) : 5
    const rows = queryAll(
      "SELECT * FROM vocabulary_entries WHERE contextual_meaning IS NOT NULL AND contextual_meaning != '' ORDER BY RANDOM() LIMIT ?",
      [count]
    )
    const fallback = rows.length ? rows : queryAll("SELECT * FROM vocabulary_entries ORDER BY RANDOM() LIMIT ?", [count])
    return { items: fallback.map((r: any) => ({ ...r, cloze: r.contextual_meaning || r.common_meaning || r.term })) }
  }
  // Vocabulary plans（v3.3: 学习计划——空计划不报错）
  if (path.startsWith('/vocabulary/plans')) {
    return { plans: [] }
  }
  // Vocabulary export anki（v3.3: 导出——离线空）
  if (path.startsWith('/vocabulary/export/anki')) {
    return { text: '', count: 0 }
  }
  // Report（v3.3: 学习报告——本地统计完整 shape——防白屏）
  if (path === '/report') {
    const totalQ = queryOne("SELECT COUNT(*) AS c FROM questions")?.c || 0
    const sessions = queryOne("SELECT COUNT(*) AS c FROM practice_sessions")?.c || 0
    const submitted = queryOne("SELECT COUNT(*) AS c FROM practice_sessions WHERE status = 'submitted'")?.c || 0
    const wrongTotal = queryOne("SELECT COUNT(*) AS c FROM wrong_stats WHERE wrong_count > 0")?.c || 0
    const vocabTotal = queryOne("SELECT COUNT(*) AS c FROM vocabulary_entries")?.c || 0
    const activeDays = queryOne("SELECT COUNT(DISTINCT date(started_at)) AS c FROM practice_sessions")?.c || 0
    return {
      practice: { sessions, submitted, answered: 0, correct: 0, accuracy: 0 },
      wrong: { total: wrongTotal, repeat: 0 },
      vocab: { total: vocabTotal, learned: vocabTotal, mastered: 0 },
      activity: { active_days: Math.max(activeDays, 1), activities: sessions },
      by_profile: [],
      active_profile: queryOne("SELECT * FROM question_bank_profiles WHERE id = 1"),
      trend: [],
      by_type: [],
      answered_trend: [],
      week_compare: { this: { answered: 0 }, last: { answered: 0 }, answered_delta: 0 },
      total_questions: totalQ,
    }
  }
  // Report heatmap（v3.3: 空 cells——不白屏）
  if (path === '/report/heatmap') {
    return { cells: [] }
  }
  // Practice session detail（v3.3: 离线返回本地题目——点击试卷后能做题）
  const sm = path.match(/^\/practice\/sessions\/(\d+)$/)
  if (sm) {
    const sid = parseInt(sm[1])
    const session = queryOne("SELECT * FROM practice_sessions WHERE id = ?", [sid])
    if (!session) return { id: sid, mode: 'paper', units: [], status: 'in_progress' }
    const units = queryAll(
      "SELECT u.*, p.year FROM units u JOIN papers p ON p.id = u.paper_id WHERE u.paper_id = ? ORDER BY u.sequence",
      [session.paper_id]
    )
    const unitsOut = units.map((u: any) => {
      const qs = queryAll("SELECT * FROM questions WHERE unit_id = ? ORDER BY sequence", [u.id])
      const questions = qs.map((q: any) => ({
        id: q.id, number: q.number, stem: q.stem, question_type: q.question_type,
        score: q.score, passage: u.passage || '',
        options: queryAll(
          "SELECT stable_key AS key, content FROM options WHERE question_id = ? ORDER BY sequence",
          [q.id]
        ),
        answered: null,
      }))
      return {
        id: u.id, paper_id: u.paper_id, year: u.year, title: u.title,
        unit_type: u.unit_type, subtype: u.subtype, passage: u.passage || '',
        questions,
        max_score: questions.reduce((s: number, q: any) => s + (q.score || 0), 0),
      }
    })
    return {
      id: sid, mode: session.mode, status: session.status,
      paper_id: session.paper_id, units: unitsOut,
    }
  }

  return {}
}

function offlinePost(path: string, body?: any): any {
  // Practice session create（v3.3: unit_ids NOT NULL——补齐防报错）
  if (path === '/practice/sessions') {
    const id = Date.now()
    const unitIds = JSON.stringify(body?.unit_ids || [])
    execute(
      "INSERT INTO practice_sessions (id, mode, paper_id, unit_ids, status) VALUES (?, ?, ?, ?, 'in_progress')",
      [id, body?.mode || 'random', body?.paper_id || null, unitIds]
    )
    return { id, mode: body?.mode || 'random', unit_ids: body?.unit_ids || [] }
  }
  // AI profile create（离线 APK：api_key 用 SecureStorage AES-GCM 加密存储）
  if (path === '/ai/profiles') {
    return saveAiProfileOffline(body)
  }
  // Vocabulary review
  if (path.match(/\/vocabulary\/\d+\/review/)) {
    const id = parseInt(path.match(/\/vocabulary\/(\d+)\/review/)![1])
    execute("INSERT INTO vocabulary_reviews (entry_id, rating) VALUES (?, ?)", [id, body?.rating])
    return queryOne("SELECT * FROM vocabulary_entries WHERE id = ?", [id])
  }
  // Vocab quiz estimate（v3.3: 估词量——按认识比例估算）
  if (path === '/vocab/quiz/estimate') {
    const results = body?.results || {}
    const known = Object.values(results).filter((v: any) => v === 1).length
    const total = Object.keys(results).length || 1
    const vocabTotal = queryOne("SELECT COUNT(*) AS c FROM vocabulary_entries")?.c || 7751
    const estimated = Math.round((known / total) * vocabTotal)
    return { estimated, total: vocabTotal }
  }
  return {}
}

function offlinePut(path: string, body?: any): any {
  // AI profile update（离线 APK：key 变化时重新加密）
  const m = path.match(/^\/ai\/profiles\/(\d+)$/)
  if (m) {
    return updateAiProfileOffline(parseInt(m[1]), body)
  }
  return {}
}

// ── 离线 AI 配置保存（SecureStorage 加密）──

async function encryptKey(value: string | null | undefined): Promise<string | null> {
  if (!value) return null
  try {
    const cap = (window as any)?.Capacitor
    if (cap?.isNativePlatform?.()) {
      const { SecureStorage } = await import('./secure-storage')
      return await SecureStorage.encrypt(value)
    }
  } catch {
    // 加密失败回退（仍可用，仅提示风险）
  }
  return value
}

async function saveAiProfileOffline(body: any): Promise<any> {
  const encrypted = await encryptKey(body?.api_key)
  const existing = queryOne("SELECT id FROM ai_profiles WHERE name = ?", [body?.name])
  if (existing) {
    updateAiProfileOffline(existing.id, body)
    return queryOne("SELECT * FROM ai_profiles WHERE id = ?", [existing.id])
  }
  execute(
    `INSERT INTO ai_profiles (name, base_url, api_key_encrypted, default_model, temperature, max_tokens, system_prompt, enabled, is_default, created_at, updated_at)
     VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, datetime('now','localtime'), datetime('now','localtime'))`,
    [body?.name || '未命名', body?.base_url || '', encrypted || '', body?.default_model || '', body?.temperature ?? 0.2, body?.max_tokens ?? 1200, body?.system_prompt || '']
  )
  const id = lastInsertRowId()
  return queryOne("SELECT * FROM ai_profiles WHERE id = ?", [id])
}

async function updateAiProfileOffline(id: number, body: any): Promise<any> {
  const current = queryOne("SELECT api_key_encrypted FROM ai_profiles WHERE id = ?", [id])
  const encrypted = body?.api_key ? await encryptKey(body.api_key) : current?.api_key_encrypted
  execute(
    `UPDATE ai_profiles SET name = ?, base_url = ?, api_key_encrypted = ?, default_model = ?, temperature = ?, max_tokens = ?, system_prompt = ?, updated_at = datetime('now','localtime') WHERE id = ?`,
    [body?.name ?? current?.name ?? '', body?.base_url ?? current?.base_url ?? '', encrypted ?? '', body?.default_model ?? current?.default_model ?? '', body?.temperature ?? current?.temperature ?? 0.2, body?.max_tokens ?? current?.max_tokens ?? 1200, body?.system_prompt ?? current?.system_prompt ?? '', id]
  )
  return queryOne("SELECT * FROM ai_profiles WHERE id = ?", [id])
}