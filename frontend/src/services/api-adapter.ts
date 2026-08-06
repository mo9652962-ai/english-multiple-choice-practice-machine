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

  return {}
}

function offlinePost(path: string, body?: any): any {
  // Practice session create
  if (path === '/practice/sessions') {
    const id = Date.now()
    execute("INSERT INTO practice_sessions (id, mode, paper_id, status) VALUES (?, ?, ?, 'in_progress')", [id, body?.mode || 'random', body?.paper_id || null])
    return { id, mode: body?.mode || 'random' }
  }
  // Vocabulary review
  if (path.match(/\/vocabulary\/\d+\/review/)) {
    const id = parseInt(path.match(/\/vocabulary\/(\d+)\/review/)![1])
    execute("INSERT INTO vocabulary_reviews (entry_id, rating) VALUES (?, ?)", [id, body?.rating])
    return queryOne("SELECT * FROM vocabulary_entries WHERE id = ?", [id])
  }
  return {}
}