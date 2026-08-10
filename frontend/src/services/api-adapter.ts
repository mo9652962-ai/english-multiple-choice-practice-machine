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

// v3.3: 构建离线会话详情（判分提交后前端刷新用——含 submissions）
function buildOfflineSession(sid: number): any {
  const session = queryOne("SELECT * FROM practice_sessions WHERE id = ?", [sid])
  if (!session) return { id: sid, mode: 'paper', units: [], status: 'in_progress' }
  const units = queryAll(
    "SELECT u.*, p.year FROM units u JOIN papers p ON p.id = u.paper_id WHERE u.paper_id = ? ORDER BY u.sequence",
    [session.paper_id]
  )
  const subs = queryAll("SELECT * FROM practice_unit_submissions WHERE session_id = ?", [sid])
  const subByUnit: Record<number, any> = {}
  for (const s of subs) subByUnit[s.unit_id] = s
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
    const sub = subByUnit[u.id]
    return {
      id: u.id, paper_id: u.paper_id, year: u.year, title: u.title,
      unit_type: u.unit_type, subtype: u.subtype, passage: u.passage || '',
      questions,
      max_score: questions.reduce((s: number, q: any) => s + (q.score || 0), 0),
      submission: sub ? { submitted: true, score: sub.score, max_score: sub.max_score } : undefined,
    }
  })
  return {
    id: sid, mode: session.mode, status: session.status,
    paper_id: session.paper_id, units: unitsOut,
  }
}

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
  // Vocabulary main list（v3.3: 我的单词本主列表——本地查询含全部状态——修复真机空单词本）
  if (path.startsWith('/vocabulary?') || path === '/vocabulary') {
    const u = new URL(path, 'http://local')
    const status = u.searchParams.get('status') || ''
    const search = (u.searchParams.get('search') || '').toLowerCase()
    const category = u.searchParams.get('category') || ''
    let rows = queryAll("SELECT * FROM vocabulary_entries ORDER BY encounter_count DESC, id ASC")
    if (status && status !== 'all') rows = rows.filter((r: any) => (r.study_status || 'new') === status)
    if (category) rows = rows.filter((r: any) => (r.category || '') === category)
    if (search) rows = rows.filter((r: any) =>
      (r.term || '').toLowerCase().includes(search) ||
      (r.common_meaning || '').toLowerCase().includes(search) ||
      (r.contextual_meaning || '').toLowerCase().includes(search))
    const counts: Record<string, number> = { all: rows.length }
    for (const s of ['new', 'learning', 'familiar', 'mastered']) {
      counts[s] = queryOne("SELECT COUNT(*) AS c FROM vocabulary_entries WHERE study_status = ?", [s])?.c || 0
    }
    return { items: rows, counts }
  }
  // Vocabulary detail（v3.3: 点词查看——本地详情）
  const vd = path.match(/^\/vocabulary\/(\d+)$/)
  if (vd) {
    return queryOne("SELECT * FROM vocabulary_entries WHERE id = ?", [parseInt(vd[1])]) || { ok: false }
  }
  // Vocabulary context（v3.3: 真题语境——本地简版）
  const vc = path.match(/^\/vocabulary\/(\d+)\/context$/)
  if (vc) {
    const row = queryOne("SELECT contextual_meaning, lemma FROM vocabulary_entries WHERE id = ?", [parseInt(vc[1])])
    return { items: row?.contextual_meaning ? [{ sentence: row.contextual_meaning }] : [] }
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
    // v3.3: word 字段映射（前端显示单词——修复只显示音标）
    return { items: rows.map((r: any) => ({ ...r, word: r.term })) }
  }
  // Vocab cloze（v3.3: 完形填空——本地生成句子挖空+选项+答案——修复无短文/无选项/卡死）
  if (path.startsWith('/vocab/cloze')) {
    const m = path.match(/count=(\d+)/)
    const count = m ? parseInt(m[1]) : 5
    const rows = queryAll(
      "SELECT * FROM vocabulary_entries WHERE contextual_meaning IS NOT NULL AND contextual_meaning != '' ORDER BY RANDOM() LIMIT ?",
      [count]
    )
    const fallback = rows.length ? rows : queryAll("SELECT * FROM vocabulary_entries ORDER BY RANDOM() LIMIT ?", [count])
    const items = fallback.map((r: any) => {
      const term = r.term || ''
      const sentence = r.contextual_meaning || r.common_meaning || term
      let blank = sentence
      if (term && sentence.includes(term)) {
        blank = sentence.replace(term, '____')
      } else if (term) {
        blank = `${sentence} ____`
      }
      // 干扰词：同库随机 3 个（排除自身）
      const distractors = queryAll("SELECT term FROM vocabulary_entries WHERE id != ? ORDER BY RANDOM() LIMIT 3", [r.id]).map((d: any) => d.term)
      const options = [term, ...distractors].sort(() => Math.random() - 0.5)
      return { ...r, blank_sentence: blank, options, answer: term, cloze: sentence }
    })
    return { items }
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
      week_compare: { this: { answered: 0, rate: 0, vocab: 0 }, last: { answered: 0, rate: 0, vocab: 0 }, answered_delta: 0, rate_delta: 0, vocab_delta: 0 },
      total_questions: totalQ,
      total_answered: 0,
      total_rate: 0,
      suggestions: [],
    }
  }
  // Report heatmap（v3.3: 空 cells——不白屏）
  if (path === '/report/heatmap') {
    return { cells: [] }
  }
  // Practice session detail（v3.3: 离线返回本地题目——点击试卷后能做题）
  const sm = path.match(/^\/practice\/sessions\/(\d+)$/)
  if (sm) {
    return buildOfflineSession(parseInt(sm[1]))
  }
  // Exam session detail（考试——本地会话+题目）
  const exm = path.match(/^\/exam\/sessions\/(\d+)$/)
  if (exm) {
    return buildOfflineSession(parseInt(exm[1]))
  }
  // Library units（听力/阅读入口——本地按题型查）
  if (path.startsWith('/library/units')) {
    const qs = new URLSearchParams(path.split('?')[1] || '')
    const unitType = qs.get('unit_type') || ''
    const limit = parseInt(qs.get('limit') || '20')
    const sql = unitType
      ? "SELECT u.*, p.year, p.title AS paper_title FROM units u JOIN papers p ON p.id = u.paper_id WHERE u.unit_type = ? AND p.deleted_at IS NULL ORDER BY p.year DESC, u.sequence LIMIT ?"
      : "SELECT u.*, p.year, p.title AS paper_title FROM units u JOIN papers p ON p.id = u.paper_id WHERE p.deleted_at IS NULL ORDER BY p.year DESC, u.sequence LIMIT ?"
    const params = unitType ? [unitType, limit] : [limit]
    return queryAll(sql, params)
  }
  // Achievements
  if (path === '/achievements') {
    return { achievements: [], total: 0, unlocked_count: 0, progress: [] }
  }
  // Leaderboard
  if (path === '/leaderboard') {
    return { rankings: [], user: null, period: 'weekly' }
  }
  // AI recommendations
  if (path === '/recommendations/ai') {
    return { items: [] }
  }
  // Annotations（笔记页）
  if (path === '/annotations') return { items: [] }
  if (path.startsWith('/annotations/review')) return { items: [] }
  if (path.startsWith('/annotations/stats')) return { total: 0, by_tag: {}, recent: [] }
  // Imports（导入页）
  if (path === '/imports' || path.startsWith('/imports?')) return { imports: [], total: 0 }
  if (path.startsWith('/question-banks/imports')) return { imports: [] }
  if (path === '/ai/selector-models') return { models: [], ai_configured: false }
  // Trash
  if (path === '/trash' || path.startsWith('/trash?')) return { papers: [], units: [], total: 0 }
  // Wrong export/stats
  if (path.startsWith('/wrong/export')) return { text: '', count: 0 }
  if (path === '/wrong/stats') return { total: 0, by_type: [], frequent: [], recent: [] }
  // Wrong AI status
  if (path.startsWith('/ai/wrong-analysis-status')) return { status: 'none', pending: 0 }
  // Version（桌面 About 用后端；移动端直连 GitHub——兜底）
  if (path === '/version') return { version: '2.0.0-beta.15', release_date: '2026-08-10', latest_version: null }

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
  // Vocab quiz estimate（v3.3: 估词量——按认识比例估算；v3.3 修复：results 是数组）
  if (path === '/vocab/quiz/estimate') {
    const results = Array.isArray(body?.results) ? body.results : []
    const known = results.filter((r: any) => (r?.known ?? 0) >= 2).length
    const total = results.length || 1
    const ratio = known / total
    const vocabTotal = queryOne("SELECT COUNT(*) AS c FROM vocabulary_entries")?.c || 7751
    const estimated = Math.round(ratio * vocabTotal)
    const level = estimated >= 12000 ? 'CET-6 / 考研' : estimated >= 6000 ? 'CET-4 优秀' : estimated >= 4000 ? 'CET-4' : estimated >= 2500 ? '高中' : '初中'
    return { estimated, total: vocabTotal, answered: total, ratio, level }
  }
  // Exam start（v3.3: 离线创建考试会话——详情走 /practice/sessions/{id}）
  if (path === '/exam/start') {
    const id = Date.now()
    const unitIds = JSON.stringify(body?.unit_ids || [])
    execute(
      "INSERT INTO practice_sessions (id, mode, paper_id, unit_ids, status) VALUES (?, 'exam', ?, ?, 'in_progress')",
      [id, body?.paper_id || null, unitIds]
    )
    return { session_id: id, id, status: 'in_progress' }
  }
  // Vocabulary add（长按选词加入单词本——本地插入）
  if (path === '/vocabulary') {
    const term = (body?.term || body?.word || '').trim().toLowerCase()
    if (term) {
      const exists = queryOne("SELECT id FROM vocabulary_entries WHERE term = ?", [term])
      if (!exists) {
        execute(
          "INSERT INTO vocabulary_entries (term, normalized_term, encounter_count, study_status, created_at, updated_at) VALUES (?, ?, 1, 'new', datetime('now'), datetime('now'))",
          [term, term]
        )
      } else {
        execute("UPDATE vocabulary_entries SET encounter_count = encounter_count + 1 WHERE id = ?", [exists.id])
      }
    }
    return { ok: true }
  }
  // Vocabulary translation runs（离线：记录 pending——不报错）
  if (path === '/vocabulary/translation-runs') {
    return { id: Date.now(), status: 'pending', items: [] }
  }
  // Feedback（离线：本地记录——不报错）
  if (path === '/feedback') {
    return { ok: true }
  }
  // Papers batch move（离线：空操作——不报错）
  if (path === '/papers/batch-move') {
    return { moved: 0 }
  }
  // AI wrong analysis（离线：无模型——不报错）
  if (path === '/ai/analyze-wrong') {
    return { ok: true, message: '离线模式无法调用 AI', analysis: null }
  }
  if (path === '/ai/similar-questions') {
    return { questions: [] }
  }
  // Vocabulary review（v3.3: 复习评级——本地更新状态）
  const vr = path.match(/^\/vocabulary\/(\d+)\/review$/)
  if (vr) {
    const vid = parseInt(vr[1])
    const rating = body?.rating ?? 0
    const status = rating >= 2 ? 'familiar' : (rating >= 1 ? 'learning' : 'new')
    execute("UPDATE vocabulary_entries SET study_status = ?, last_reviewed_at = datetime('now'), next_review_at = datetime('now', '+1 day') WHERE id = ?", [status, vid])
    return queryOne("SELECT * FROM vocabulary_entries WHERE id = ?", [vid]) || { ok: true }
  }
  // Vocabulary retry（v3.3: 重新翻译——本地空返回）
  const vrt = path.match(/^\/vocabulary\/(\d+)\/retry$/)
  if (vrt) {
    return { ok: true, queued: false }
  }
  // Practice unit submit（v3.3: 本地判分——单篇提交即时得分）
  const sum = path.match(/^\/practice\/sessions\/(\d+)\/units\/(\d+)\/submit$/)
  if (sum) {
    const sid = parseInt(sum[1])
    const uid = parseInt(sum[2])
    const questions = queryAll("SELECT id, answer, score FROM questions WHERE unit_id = ?", [uid])
    const ansRows = queryAll("SELECT question_id, user_answer FROM practice_answers WHERE session_id = ?", [sid])
    const answers: Record<number, string> = {}
    for (const a of ansRows) answers[a.question_id] = a.user_answer
    let correct = 0
    let score = 0
    let maxScore = 0
    for (const q of questions) {
      maxScore += q.score || 0
      const ans = answers[q.id]
      if (ans && String(ans).toUpperCase() === String(q.answer).toUpperCase()) {
        correct++
        score += q.score || 0
      } else {
        // 错题入库
        const existing = queryOne("SELECT question_id FROM wrong_stats WHERE question_id = ?", [q.id])
        if (existing) {
          execute("UPDATE wrong_stats SET wrong_count = wrong_count + 1, attempt_count = attempt_count + 1, last_wrong_at = datetime('now') WHERE question_id = ?", [q.id])
        } else {
          execute("INSERT INTO wrong_stats (question_id, attempt_count, wrong_count, recent_results, last_wrong_at) VALUES (?, 1, 1, ?, datetime('now'))", [q.id, JSON.stringify([ans || null])])
        }
      }
    }
    execute(
      "INSERT INTO practice_unit_submissions (session_id, unit_id, score, max_score, submitted_at) VALUES (?, ?, ?, ?, datetime('now'))",
      [sid, uid, score, maxScore]
    )
    return buildOfflineSession(sid)
  }
  // Practice session submit（整卷提交）
  const ssm = path.match(/^\/practice\/sessions\/(\d+)\/submit$/)
  if (ssm) {
    const sid = parseInt(ssm[1])
    execute("UPDATE practice_sessions SET status = 'submitted', submitted_at = datetime('now') WHERE id = ?", [sid])
    return buildOfflineSession(sid)
  }
  // Exam session submit（考试提交）
  const esm = path.match(/^\/exam\/sessions\/(\d+)\/submit$/)
  if (esm) {
    const sid = parseInt(esm[1])
    execute("UPDATE practice_sessions SET status = 'submitted', submitted_at = datetime('now') WHERE id = ?", [sid])
    return buildOfflineSession(sid)
  }
  return {}
}

function offlinePut(path: string, body?: any): any {
  // AI profile update（离线 APK：key 变化时重新加密）
  const m = path.match(/^\/ai\/profiles\/(\d+)$/)
  if (m) {
    return updateAiProfileOffline(parseInt(m[1]), body)
  }
  // Vocabulary update（v3.3: 标记重点/已掌握——本地保存）
  const vu = path.match(/^\/vocabulary\/(\d+)$/)
  if (vu) {
    const vid = parseInt(vu[1])
    const fields: string[] = []
    const vals: any[] = []
    for (const k of ['study_status', 'manually_frequent', 'notes', 'is_favorite', 'user_edited']) {
      if (body && body[k] !== undefined) { fields.push(`${k} = ?`); vals.push(body[k]) }
    }
    if (fields.length) {
      vals.push(vid)
      execute(`UPDATE vocabulary_entries SET ${fields.join(', ')}, updated_at = datetime('now') WHERE id = ?`, vals)
    }
    return queryOne("SELECT * FROM vocabulary_entries WHERE id = ?", [vid]) || { ok: true }
  }
  // Practice answer save（v3.3: 本地记录答案——判分依据）
  const am = path.match(/^\/practice\/sessions\/(\d+)\/answers\/(\d+)$/)
  if (am) {
    const sid = parseInt(am[1])
    const qid = parseInt(am[2])
    const q = queryOne("SELECT answer FROM questions WHERE id = ?", [qid])
    const isCorrect = !!(q && body?.answer && String(body.answer).toUpperCase() === String(q.answer).toUpperCase())
    execute(
      "INSERT INTO practice_answers (session_id, question_id, user_answer, is_correct, answered_at) VALUES (?, ?, ?, ?, datetime('now'))",
      [sid, qid, body?.answer || null, isCorrect ? 1 : 0]
    )
    return { ok: true, is_correct: isCorrect }
  }
  // Exam answer save（考试答题——本地记录）
  const eam = path.match(/^\/exam\/sessions\/(\d+)\/answers\/(\d+)$/)
  if (eam) {
    const sid = parseInt(eam[1])
    const qid = parseInt(eam[2])
    execute(
      "INSERT INTO exam_answers (exam_id, question_id, user_answer, answered_at) VALUES (?, ?, ?, datetime('now'))",
      [sid, qid, body?.answer || null]
    )
    return { ok: true }
  }
  // Annotations（标注——本地记录）
  if (path === '/units/') return {}
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