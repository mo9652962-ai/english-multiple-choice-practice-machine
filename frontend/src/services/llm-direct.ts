// llm-direct.ts — 离线 APK 直连 AI provider（v9.29 手机端 AI 三件套离线补全）
// 方案：2026-08-20 Gemini 第二意见 → k 落地
// 作用：手机端无后端时，从前端直连用户配置的 AI provider（OpenAI 兼容），
//       让 真题精讲/作文批改/口语陪练 在离线 APK 也可用；结果存 IndexedDB 可断网回看。
import { queryOne } from './db'
import { SecureStorage } from './secure-storage'

// ── IndexedDB KV（离线 AI 结果缓存：key=路径+参数哈希）──
const IDB_NAME = 'epm_ai_cache'
const IDB_STORE = 'kv'

// 单例连接（避免每次 open 新连接——Gemini 审查 2026-08-20）
let _idbPromise: Promise<IDBDatabase> | null = null

function idbOpen(): Promise<IDBDatabase> {
  if (!_idbPromise) {
    _idbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(IDB_NAME, 1)
      req.onupgradeneeded = () => {
        if (!req.result.objectStoreNames.contains(IDB_STORE)) {
          req.result.createObjectStore(IDB_STORE)
        }
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => {
        _idbPromise = null // 失败重置，下次重试
        reject(req.error)
      }
    })
  }
  return _idbPromise
}

// 本地时间戳（对齐后端 SQLite CURRENT_TIMESTAMP 的 "YYYY-MM-DD HH:MM:SS" 格式）
export function localTimestamp(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

// 唯一主键（Date.now() + 随机后缀，避免快速并发碰撞——Gemini 审查 2026-08-20）
export function uniqueId(): number {
  return Date.now() * 1000 + Math.floor(Math.random() * 1000)
}

export async function idbGet(key: string): Promise<any> {
  try {
    const db = await idbOpen()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readonly')
      const req = tx.objectStore(IDB_STORE).get(key)
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => reject(req.error)
    })
  } catch {
    return null
  }
}

export async function idbSet(key: string, value: any): Promise<void> {
  try {
    const db = await idbOpen()
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readwrite')
      tx.objectStore(IDB_STORE).put(value, key)
      tx.oncomplete = () => resolve()
      tx.onerror = () => reject(tx.error)
    })
  } catch {
    // IDB 不可用（隐私模式等）→ 静默降级：不缓存但功能可用
  }
}

export async function idbAll(): Promise<{ key: string; value: any }[]> {
  try {
    const db = await idbOpen()
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(IDB_STORE, 'readonly')
      const req = tx.objectStore(IDB_STORE).openCursor()
      const out: { key: string; value: any }[] = []
      req.onsuccess = () => {
        const cur = req.result
        if (cur) {
          out.push({ key: String(cur.key), value: cur.value })
          cur.continue()
        } else resolve(out)
      }
      req.onerror = () => reject(req.error)
    })
  } catch {
    return []
  }
}

// ── AI Profile 读取（复用 sql.js 的 ai_profiles 表，key 从 SecureStorage 解密）──
interface AiProfile {
  id: number
  name: string
  base_url: string
  default_model: string
  api_key_encrypted: string | null
  temperature: number | null
  max_tokens: number | null
}

export async function getActiveAiProfile(): Promise<AiProfile | null> {
  const row = queryOne(
    'SELECT id, name, base_url, default_model, api_key_encrypted, temperature, max_tokens FROM ai_profiles WHERE enabled = 1 AND is_default = 1 LIMIT 1'
  ) as AiProfile | null
  return row
}

export async function resolveApiKey(profile: AiProfile): Promise<string | null> {
  if (!profile.api_key_encrypted) return null
  try {
    // 手机原生环境：SecureStorage 解密；桌面 dev：明文直用
    const cap = (window as any)?.Capacitor
    if (cap?.isNativePlatform?.()) {
      return await SecureStorage.decrypt(profile.api_key_encrypted)
    }
    return profile.api_key_encrypted
  } catch {
    return profile.api_key_encrypted // 解密失败回退明文（仍是本地值）
  }
}

// ── OpenAI 兼容调用（直连）──
interface LlmOpts {
  responseFormat?: 'json_object' | 'text'
  maxTokens?: number
  temperature?: number
}

export async function callLLM(
  messages: { role: string; content: string }[],
  opts: LlmOpts = {}
): Promise<string> {
  const profile = await getActiveAiProfile()
  if (!profile) throw new Error('未配置 AI 服务，请在设置中添加')
  const apiKey = await resolveApiKey(profile)
  if (!apiKey) throw new Error('AI 服务未配置 API Key，请在设置中添加')

  const base = (profile.base_url || '').replace(/\/+$/, '')
  const url = base.includes('/chat/completions') ? base : `${base}/chat/completions`
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 120000)

  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model: profile.default_model || 'deepseek-chat',
        messages,
        temperature: opts.temperature ?? profile.temperature ?? 0.7,
        max_tokens: opts.maxTokens ?? profile.max_tokens ?? 2048,
        response_format: opts.responseFormat === 'json_object' ? { type: 'json_object' } : undefined,
        stream: false,
      }),
    })
    if (!resp.ok) {
      const text = await resp.text().catch(() => '')
      throw new Error(`AI 服务错误 ${resp.status}: ${text.slice(0, 120)}`)
    }
    const data = await resp.json()
    const content: string = data?.choices?.[0]?.message?.content ?? ''
    if (!content) throw new Error('AI 返回为空')
    return content
  } finally {
    clearTimeout(timer)
  }
}

function tryParseJson(raw: string): any {
  try {
    return JSON.parse(raw)
  } catch {
    // 兼容模型输出被 ```json 包裹的情况
    const m = raw.match(/```(?:json)?\s*([\s\S]*?)```/)
    if (m) {
      try { return JSON.parse(m[1]) } catch { /* fallthrough */ }
    }
    throw new Error('AI 返回解析失败，请重试')
  }
}

// ── 1. 真题精讲（deep-explain）──
const DEEP_EXPLAIN_SYSTEM_PROMPT = `你是资深考研英语老师。根据题目、选项、答案和文章，生成深度精讲。
只输出 JSON，结构：
{
  "question_type_label": "题型名",
  "core_skill": "考查的核心能力",
  "locator_sentence": "定位句（文章原文摘录）",
  "solution_steps": ["解题步骤1", "解题步骤2"],
  "options_analysis": {"A": "为什么对/错", "B": "...", "C": "...", "D": "..."},
  "sentence_grammar": {"core_skeleton": "长难句主干拆解", "grammar_note": "语法点说明"},
  "knowledge_points": ["知识点1", "知识点2"],
  "study_advice": "针对性学习建议"
}`

export interface DeepExplainResult {
  question_id: number
  cached: boolean
  question_type_label: string
  core_skill: string
  locator_sentence: string
  solution_steps: string[]
  options_analysis: Record<string, string>
  sentence_grammar: { core_skeleton?: string; grammar_note?: string }
  knowledge_points: string[]
  study_advice: string
  source_model: string
  updated_at: string
}

export async function offlineDeepExplain(
  questionId: number,
  question: { stem: string; answer: string; options: { key: string; content: string }[]; passage?: string },
  forceRefresh = false
): Promise<DeepExplainResult> {
  const cacheKey = `explain:${questionId}`
  if (!forceRefresh) {
    const hit = await idbGet(cacheKey)
    if (hit) return { ...hit, cached: true }
  }
  const userPrompt = `题目：${question.stem}

选项：${JSON.stringify(question.options, null, 0)}

正确答案：${question.answer}

文章（片段）：
${(question.passage || '').slice(0, 4000)}

请生成深度精讲 JSON。`
  const raw = await callLLM(
    [
      { role: 'system', content: DEEP_EXPLAIN_SYSTEM_PROMPT },
      { role: 'user', content: userPrompt },
    ],
    { responseFormat: 'json_object', maxTokens: 2500 }
  )
  const parsed = tryParseJson(raw)
  const result: DeepExplainResult = {
    question_id: questionId,
    cached: false,
    question_type_label: parsed.question_type_label ?? '',
    core_skill: parsed.core_skill ?? '',
    locator_sentence: parsed.locator_sentence ?? '',
    solution_steps: parsed.solution_steps ?? [],
    options_analysis: parsed.options_analysis ?? {},
    sentence_grammar: parsed.sentence_grammar ?? {},
    knowledge_points: parsed.knowledge_points ?? [],
    study_advice: parsed.study_advice ?? '',
    source_model: '',
    updated_at: localTimestamp(),
  }
  await idbSet(cacheKey, result)
  return result
}

// ── 2. 作文批改（essays/evaluate）──
const ESSAY_SYSTEM_PROMPT = `你是考研英语阅卷老师。批改作文并给出评分、维度分、行内批注、词汇升格和范文。
只输出 JSON，结构：
{
  "score": 数字,
  "max_score": 20,
  "band": "档次描述",
  "dimensions": {"内容": 数字, "结构": 数字, "语言": 数字},
  "overall_comment": "总评",
  "markups": [{"original": "原文片段", "suggestion": "修改建议"}],
  "lexical_upgrades": [{"original": "原词", "upgrade": "升格词", "context": "语境说明"}],
  "model_essay": "满分范文（同题）",
  "essay_highlights": ["亮点1", "亮点2"]
}`

export interface EssayEvaluateResult {
  submission_id: number
  word_count: number
  score: number
  max_score: number
  band: string
  dimensions: Record<string, number>
  overall_comment: string
  markups: { original: string; suggestion: string }[]
  lexical_upgrades: { original: string; upgrade: string; context: string }[]
  model_essay: string
  essay_highlights: string[]
}

export async function offlineEssayEvaluate(req: {
  essay_type: string
  subject?: string
  prompt_title?: string
  user_content: string
}): Promise<EssayEvaluateResult> {
  const wordCount = req.user_content.trim().split(/\s+/).length
  const userPrompt = `作文类型：${req.essay_type}
题目/主题：${req.prompt_title || req.subject || '（无）'}

作文内容：
${req.user_content}

请批改并输出 JSON。`
  const raw = await callLLM(
    [
      { role: 'system', content: ESSAY_SYSTEM_PROMPT },
      { role: 'user', content: userPrompt },
    ],
    { responseFormat: 'json_object', maxTokens: 2500 }
  )
  const parsed = tryParseJson(raw)
  const maxScore = req.essay_type !== 'essay_small' ? 20 : 10
  const result: EssayEvaluateResult = {
    submission_id: uniqueId(),
    word_count: wordCount,
    score: parsed.score ?? 0,
    max_score: parsed.max_score ?? maxScore,
    band: parsed.band ?? '',
    dimensions: parsed.dimensions ?? {},
    overall_comment: parsed.overall_comment ?? '',
    markups: parsed.markups ?? [],
    lexical_upgrades: parsed.lexical_upgrades ?? [],
    model_essay: parsed.model_essay ?? '',
    essay_highlights: parsed.essay_highlights ?? [],
  }
  // 存 IDB（list 按 id 倒序取）
  const listKey = 'essays:list'
  const existing = (await idbGet(listKey)) || []
  await idbSet(listKey, [result, ...existing].slice(0, 50))
  await idbSet(`essay:${result.submission_id}`, result)
  return result
}

// ── 3. 口语陪练（speaking turn 反馈）──
const SPEAKING_SYSTEM_PROMPT = `你是英语口语考官。根据场景和对话历史，回应用户并给出纠错和升格。
只输出 JSON，结构：
{
  "reply": "考官回应（自然口语，2-3句）",
  "grammar_corrections": [{"original": "原句", "corrected": "改后", "note": "说明"}],
  "native_upgrade": "地道表达替换建议",
  "fluency_score": 0-10数字
}`

export interface SpeakingTurnResult {
  reply: string
  grammar_corrections: { original: string; corrected: string; note: string }[]
  native_upgrade: string
  fluency_score: number
}

export async function offlineSpeakingTurn(
  scenario: string,
  topic: string,
  history: { role: string; content: string }[],
  userText: string
): Promise<SpeakingTurnResult> {
  const historyText = history
    .map((m) => `${m.role === 'user' ? '考生' : '考官'}：${m.content}`)
    .join('\n')
  const userPrompt = `场景：${scenario}
话题：${topic}

对话历史：
${historyText || '（无）'}

考生回答：${userText}

请以考官身份回应并输出 JSON。`
  const raw = await callLLM(
    [
      { role: 'system', content: SPEAKING_SYSTEM_PROMPT },
      { role: 'user', content: userPrompt },
    ],
    { responseFormat: 'json_object', maxTokens: 800 }
  )
  const parsed = tryParseJson(raw)
  return {
    reply: String(parsed.reply ?? '').trim(),
    grammar_corrections: parsed.grammar_corrections ?? [],
    native_upgrade: parsed.native_upgrade ?? '',
    fluency_score: Number(parsed.fluency_score ?? 0),
  }
}

// ── 口语会话本地管理（IDB）──
export interface SpeakingSession {
  id: number
  scenario: string
  topic: string
  status: string
  turns: { turn_index: number; user_text: string; ai_reply: string; created_at: string }[]
}

export async function createSpeakingSession(scenario: string, topic: string): Promise<SpeakingSession> {
  const session: SpeakingSession = {
    id: uniqueId(),
    scenario,
    topic,
    status: 'active',
    turns: [],
  }
  await idbSet(`speaking:${session.id}`, session)
  return session
}

export async function getSpeakingSession(id: number): Promise<SpeakingSession | null> {
  return (await idbGet(`speaking:${id}`)) || null
}

export async function appendSpeakingTurn(
  session: SpeakingSession,
  userText: string,
  aiResult: SpeakingTurnResult
): Promise<void> {
  session.turns.push({
    turn_index: session.turns.length + 1,
    user_text: userText,
    ai_reply: aiResult.reply,
    created_at: localTimestamp(),
  })
  await idbSet(`speaking:${session.id}`, session)
}
