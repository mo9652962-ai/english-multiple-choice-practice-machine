<script setup lang="ts">
import { BookOpen, Check, FileText, RefreshCw, Search, Settings, Star, Trash2, Headphones } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { del, get, post, put } from '../api'
import { sanitizeHtml } from '../services/sanitize'  // v9.24: XSS 防护
import TtsButton from '../components/TtsButton.vue'
import DictationMode from '../components/DictationMode.vue'
import { showToast } from '../services/toast'

const route = useRoute()
const router = useRouter()
const showWordBank = ref(false)
const items = ref<any[]>([])
// v3.4: 首页推荐 20 词（随机——每次刷新变化）
const recommended = computed(() => {
  const all = items.value.filter((w: any) => w.translation_status === 'ready')
  const shuffled = [...all].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, 20)
})
const counts = ref<any>({ total:0, frequent:0, mastered:0, pending:0, review:0 })
const plans = ref<any[]>([])
const activePlan = ref<any>(null)
const planWords = ref<any[]>([])
const planLoading = ref(false)
const selected = ref<any>(null)
const wordContexts = ref<any[]>([])
const wordContextsLoading = ref(false)
const filter = ref('all')
const category = ref('')
const catType = ref('')  // v2.15: 高频/热点 子分类
const search = ref('')
const error = ref('')
const notice = ref('')
const editing = ref(false)
const editForm = reactive<any>({})
const reviewMode = ref(false)
const dictationMode = ref(false)
const dictationWords = ref<any[]>([])
const reveal = ref(false)
const reviewIndex = ref(0)
const reviewItems = computed(() => items.value.filter(item => item.translation_status === 'ready' && item.study_status !== 'mastered'))
const reviewWord = computed(() => reviewItems.value[reviewIndex.value])
const DISPLAY_DEFAULTS: Record<string, boolean> = {
  common_meaning: true,
  contextual: true,
  sentence: true,
  memory_hint: false,
  synonyms: false,
  antonyms: false,
  similar_forms: false,
}
const displayOptions: Record<string, string> = {
  common_meaning: '常用释义',
  contextual: '语境释义',
  sentence: '真题例句',
  memory_hint: '记忆提示',
  synonyms: '同义词辨析',
  antonyms: '反义词辨析',
  similar_forms: '形近词辨析',
}
function loadDisplayConfig(): Record<string, boolean> {
  try {
    const saved = JSON.parse(localStorage.getItem('vocab-display-config') || '{}')
    return { ...DISPLAY_DEFAULTS, ...(saved && typeof saved === 'object' ? saved : {}) }
  } catch {
    return { ...DISPLAY_DEFAULTS }
  }
}
const displayConfig = ref<Record<string, boolean>>(loadDisplayConfig())
const showDisplayDialog = ref(false)
const expandedAll = ref(false)
function saveDisplayConfig() {
  localStorage.setItem('vocab-display-config', JSON.stringify(displayConfig.value))
}

function translationStatusText(status: string, detail = false) {
  if (status === 'translating') return detail ? '模型正在后台翻译' : '正在后台翻译…'
  if (status === 'failed') return detail ? '翻译暂未完成' : '等待重新翻译'
  return detail ? '等待练习提交或退出后翻译' : '等待练习结束后翻译'
}

// v3.3: 学习三态（墨墨认识/模糊/忘记）——已掌握保留为第四态
function vocabStatusText(status: string) {
  if (status === 'mastered') return '已掌握'
  if (status === 'familiar') return '认识'
  if (status === 'learning') return '模糊'
  return '忘记'
}

async function load() {
  try {
    const catParam = category.value || catType.value ? `&category=${encodeURIComponent(category.value + catType.value)}` : ''
    const result: any = await get(`/vocabulary?status=${filter.value}&search=${encodeURIComponent(search.value)}${catParam}`)
    error.value = ''
    items.value = result.items || []
    counts.value = result.counts || counts.value
    const requested = Number(route.query.word)
    const target = items.value.find(item => item.id === requested) || items.value[0]
    if (target) await select(target.id)
    else selected.value = null
  } catch (e) { error.value = String(e) }
}

async function select(id: number) {
  try {
    selected.value = await get(`/vocabulary/${id}`)
    error.value = ''
    Object.assign(editForm, selected.value)
    editing.value = false
    expandedAll.value = false
    // v2.23: 词文串学 — 加载真题语境
    wordContexts.value = []
    wordContextsLoading.value = true
    try {
      const ctx: any = await get(`/vocabulary/${id}/context`)
      wordContexts.value = ctx.contexts || []
    } catch { wordContexts.value = [] }
    wordContextsLoading.value = false
  } catch (e) {
    error.value = String(e)
  }
}

async function saveEdit() {
  selected.value = await put(`/vocabulary/${selected.value.id}`, {
    contextual_meaning: editForm.contextual_meaning,
    common_meaning: editForm.common_meaning,
    phonetic: editForm.phonetic,
    part_of_speech: editForm.part_of_speech,
    note: editForm.note,
    study_status: editForm.study_status,
    manually_frequent: Boolean(editForm.manually_frequent),
  })
  editing.value = false
  notice.value = '词条已保存'
  await load()
}

async function removeEntry() {
  if (!selected.value || !confirm(`删除 ${selected.value.term} 吗？`)) return
  await del(`/vocabulary/${selected.value.id}`)
  selected.value = null
  await load()
}

async function retryTranslation() {
  await post(`/vocabulary/${selected.value.id}/retry`)
  notice.value = '已重新提交翻译，请稍后刷新'
  await load()
}

async function exportAnki() {
  try {
    const result: any = await get('/vocabulary/export/anki')
    if (result.error) {
      showToast(result.error, 'error')
      return
    }
    // 下载 .apkg 文件
    const resp = await fetch(`/api/vocabulary/export/anki/download?filename=${encodeURIComponent(result.filename)}`)
    if (!resp.ok) {
      showToast('文件下载失败，请到 exports/ 目录查看', 'error')
      return
    }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = result.filename
    a.click()
    URL.revokeObjectURL(url)
    showToast(`已导出 ${result.count} 个单词到 Anki 牌组`, 'success')
  } catch (e) {
    showToast(`导出失败：${e}`, 'error')
  }
}

async function rate(rating: string) {
  if (!reviewWord.value) return
  await post(`/vocabulary/${reviewWord.value.id}/review`, { rating })
  reveal.value = false
  await load()
  if (reviewIndex.value >= reviewItems.value.length) reviewIndex.value = 0
}

function startReview() {
  filter.value = 'review'
  reviewMode.value = true
  reveal.value = false
  reviewIndex.value = 0
  load()
}

function startDictation() {
  // 从当前列表随机取 10 个已就绪词
  const ready = items.value.filter((w: any) => w.translation_status === 'ready')
  const pool = ready.length ? ready : items.value
  const shuffled = [...pool].sort(() => Math.random() - 0.5)
  // v3.3: 生成 4 选项（听音选词）——正确词 + 3 干扰词
  const picked = shuffled.slice(0, 10)
  dictationWords.value = picked.map((w: any, i: number) => {
    const distractors = shuffled.filter((x: any) => x.id !== w.id).slice(i, i + 3).map((x: any) => x.term)
    while (distractors.length < 3) {
      const extra = items.value.find((x: any) => !distractors.includes(x.term) && x.term !== w.term)
      if (!extra) break
      distractors.push(extra.term)
    }
    return { ...w, options: [w.term, ...distractors].sort(() => Math.random() - 0.5) }
  })
  dictationMode.value = true
}

// v2.32: 短文填词 (扇贝式) — 真题句挖空选词
const clozeItems = ref<any[]>([])
const clozeMode = ref(false)
const clozeIndex = ref(0)
const clozePicked = ref('')
const clozeScore = ref(0)
const clozeDone = ref(false)
const clozeLoading = ref(false)
const clozeWrong = ref<string[]>([])

async function loadCloze() {
  clozeLoading.value = true
  try {
    const r: any = await get('/vocab/cloze?count=5')
    clozeItems.value = r.items || []
    clozeIndex.value = 0
    clozePicked.value = ''
    clozeScore.value = 0
    clozeDone.value = false
    clozeWrong.value = []
    clozeMode.value = true
  } catch (e) {
    showToast('生成填词失败，请稍后再试', 'error')
  } finally {
    clozeLoading.value = false
  }
}

const clozeCurrent = computed(() => clozeItems.value[clozeIndex.value])

function pickCloze(opt: string) {
  if (clozePicked.value) return
  clozePicked.value = opt
  if (opt === clozeCurrent.value?.answer) {
    clozeScore.value++
  } else {
    clozeWrong.value.push(clozeCurrent.value?.word || opt)
  }
}

function nextCloze() {
  if (clozeIndex.value < clozeItems.value.length - 1) {
    clozeIndex.value++
    clozePicked.value = ''
  } else {
    clozeDone.value = true
  }
}

function closeCloze() {
  clozeMode.value = false
}

// v2.33: 词汇量自测 (百词斩式)
const quizMode = ref(false)
const quizItems = ref<any[]>([])
const quizIndex = ref(0)
const quizResults = ref<Record<string, number>>({})
const quizResult = ref<any>(null)
const quizLoading = ref(false)

async function loadQuiz() {
  quizLoading.value = true
  try {
    const r: any = await get('/vocab/quiz?count=10')
    quizItems.value = r.items || []
    quizIndex.value = 0
    quizResults.value = {}
    quizResult.value = null
    quizMode.value = true
  } catch (e) {
    showToast('词汇量自测加载失败', 'error')
  } finally {
    quizLoading.value = false
  }
}

const quizCurrent = computed(() => quizItems.value[quizIndex.value])
const quizRevealed = ref(false)

function rateQuiz(known: number) {
  if (!quizCurrent.value) return
  quizResults.value[quizCurrent.value.id] = known
  quizRevealed.value = false
  if (quizIndex.value < quizItems.value.length - 1) {
    quizIndex.value++
  } else {
    finishQuiz()
  }
}

async function finishQuiz() {
  const results = quizItems.value.map((w: any) => ({
    word: w.word,
    known: quizResults.value[w.id] ?? 0,
  }))
  try {
    const r: any = await post('/vocab/quiz/estimate', { results })
    quizResult.value = r
  } catch (e) {
    showToast('估算失败', 'error')
  }
}

// v2.43: 闪卡翻面 (点击卡片/空格键)
function toggleReveal() {
  if (reviewMode.value) reveal.value = !reveal.value
}

function closeQuiz() {
  quizMode.value = false
}

// v3.4: AI 文章练词（借锐满分 6.0「AI 文章练词」——按弱词生成专属短文）
const articleMode = ref(false)
const articleData = ref<any>(null)
const articleLoading = ref(false)
const articleTopic = ref('随机')

async function loadArticle() {
  articleLoading.value = true
  articleMode.value = true
  articleData.value = null
  try {
    const r: any = await get(`/vocabulary/article?topic=${encodeURIComponent(articleTopic.value)}&word_count=8`)
    articleData.value = r
  } catch (e) {
    articleData.value = { error: String(e) }
  }
  articleLoading.value = false
}
function closeArticle() { articleMode.value = false; articleData.value = null }

// v3.4: 划词→生词本（借真题全刷「点击查词」+ 冲刺营「划词加生词本」）
async function quickAddVocab(term: string) {
  if (!term) return
  const found = items.value.find((w: any) => w.term === term || w.lemma === term)
  if (found) {
    await put(`/vocabulary/${found.id}`, { study_status: found.study_status === 'mastered' ? 'mastered' : 'learning' })
    showToast(`已加入生词复习：${term}`, 'success')
  } else {
    showToast('该词暂不在单词本，做题后自动收录', 'info')
  }
}

// v2.64: 快答挑战 (百词斩 PK 式 — 限时 4 选 1)
const quickMode = ref(false)
const quickItems = ref<any[]>([])
const quickIndex = ref(0)
const quickScore = ref(0)
const quickRemain = ref(10)
const quickOptions = ref<string[]>([])
const quickPicked = ref<string | null>(null)
const quickDone = ref(false)
const quickBest = ref(Number(localStorage.getItem('epm_quick_best') || 0))
let quickTimer: number | null = null

async function startQuick() {
  try {
    const r: any = await get('/vocab/quiz?count=10')
    quickItems.value = (r.items || []).filter((w: any) => w.meaning)
    if (quickItems.value.length < 4) { showToast('可用词汇不足，先学几个词吧', 'info'); return }
    quickIndex.value = 0
    quickScore.value = 0
    quickDone.value = false
    quickPicked.value = null
    quickMode.value = true
    buildQuickOptions()
    startQuickTimer()
  } catch (e) { showToast('快答挑战加载失败', 'error') }
}
function buildQuickOptions() {
  const cur = quickItems.value[quickIndex.value]
  if (!cur) return
  const others = quickItems.value
    .filter((w: any) => w.id !== cur.id && w.meaning !== cur.meaning)
    .map((w: any) => w.meaning)
  const pool = [...new Set([cur.meaning, ...others])].slice(0, 4)
  while (pool.length < 4) pool.push('以上都不是')
  quickOptions.value = pool.sort(() => Math.random() - 0.5)
  quickRemain.value = 10
}
function startQuickTimer() {
  if (quickTimer !== null) window.clearInterval(quickTimer)
  quickTimer = window.setInterval(() => {
    quickRemain.value -= 1
    if (quickRemain.value <= 0) quickAnswer('')
  }, 1000)
}
function quickAnswer(option: string) {
  if (quickPicked.value !== null || quickDone.value) return
  const cur = quickItems.value[quickIndex.value]
  const correct = option === cur.meaning
  quickPicked.value = option
  if (correct) quickScore.value += 1
  window.setTimeout(() => {
    if (quickIndex.value < quickItems.value.length - 1) {
      quickIndex.value++
      quickPicked.value = null
      buildQuickOptions()
    } else {
      quickDone.value = true
      if (quickTimer !== null) window.clearInterval(quickTimer)
      const best = Math.max(quickBest.value, quickScore.value)
      quickBest.value = best
      localStorage.setItem('epm_quick_best', String(best))
    }
  }, 650)
}
function closeQuick() {
  quickMode.value = false
  if (quickTimer !== null) window.clearInterval(quickTimer)
}
const quickLevel = computed(() => {
  const total = quickItems.value.length || 10
  const rate = quickScore.value / total
  if (rate >= 0.9) return { label: '词汇大师', icon: '🏆' }
  if (rate >= 0.7) return { label: '掌握扎实', icon: '🥇' }
  if (rate >= 0.5) return { label: '继续加油', icon: '🥈' }
  return { label: '需要复习', icon: '📚' }
})
const quickCurrent = computed(() => quickItems.value[quickIndex.value])

function toggleQuizReveal() {
  quizRevealed.value = !quizRevealed.value
}

// v2.36: 词文串学风格标签 (薄荷阅读式)
const STYLE_LABELS: Record<string, string> = {
  interview: '🗣 访谈', argument: '📊 论述', news: '📰 新闻', story: '📖 故事', article: '📄 文章',
}
function styleLabel(style: string) {
  return STYLE_LABELS[style] || style
}

let searchTimer = 0
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(load, 250)
})
watch(filter, load)
watch(category, load)
watch(catType, load)
async function loadPlans() {
  try {
    const r: any = await get('/vocabulary/plans')
    plans.value = r.plans || []
  } catch { /* 计划加载失败不阻塞 */ }
}

async function openPlan(plan: any) {
  activePlan.value = plan
  planLoading.value = true
  try {
    const r: any = await get(`/vocabulary/plans/${plan.key}/daily`)
    planWords.value = r.words || []
  } catch { planWords.value = [] }
  planLoading.value = false
}

function closePlan() { activePlan.value = null; planWords.value = [] }

// v2.23: 词文串学 — 高亮词形
function highlightContext(c: any): string {
  const word = c.highlight || ''
  if (!word) return c.sentence
  const re = new RegExp('(' + word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig')
  return c.sentence.replace(re, '<mark class="vocab-context-mark">$1</mark>')
}

onMounted(() => { load(); loadPlans() })
</script>

<template>
  <div class="page page-vocab vocabulary-page">
    <div class="page-head">
      <div><span class="eyebrow">VOCABULARY BOOK</span><h1>我的单词本</h1><p class="lead">从真题语境中收集、理解并复习真正困扰你的词。</p></div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="button ghost" @click="showDisplayDialog=true"><Settings :size="17" />显示设置</button>
        <button class="button ghost" @click="startDictation" :disabled="!items.length"><Headphones :size="17" />听写模式</button>
        <button class="button ghost" @click="loadArticle"><FileText :size="17" />AI 文章练词</button>
        <button class="button" @click="startReview"><BookOpen :size="17" />开始今日复习</button>
      </div>
    </div>
    <DictationMode
      v-if="dictationMode"
      :words="dictationWords"
      @close="dictationMode=false"
    />
    <!-- v2.22: 分级背诵计划 (墨墨/扇贝式词书) -->
    <div v-if="plans.length" class="card vocab-plans-card">
      <div class="vocab-plans-head">
        <h3>📚 分级背诵计划</h3>
        <span class="vocab-plans-sub">选一本词书，按每日任务背新词 + 复习到期词</span>
      </div>
      <div class="vocab-plans-grid">
        <button v-for="p in plans" :key="p.key" class="vocab-plan-item" type="button" @click="openPlan(p)">
          <span class="plan-book-icon">{{ p.icon }}</span>
          <span class="plan-book-info">
            <strong>{{ p.name }}</strong>
            <small>{{ p.desc }}</small>
            <span class="plan-progress"><i :style="{ width: p.progress + '%' }"></i></span>
          </span>
          <span class="plan-book-stat">{{ p.learned }}/{{ p.target }}</span>
        </button>
      </div>
    </div>
    <!-- 今日任务弹层 -->
    <div v-if="activePlan" class="plan-drawer" @click.self="closePlan">
      <div class="plan-drawer-panel">
        <div class="plan-drawer-head">
          <h3>{{ activePlan.icon }} {{ activePlan.name }} · 今日任务</h3>
          <button class="button ghost" @click="closePlan">关闭</button>
        </div>
        <p class="lead" style="margin-bottom:12px">新词 {{ planWords.filter((w:any) => w.study_status === 'new').length }} 个 + 到期复习 {{ planWords.length - planWords.filter((w:any) => w.study_status === 'new').length }} 个</p>
        <div v-if="planLoading" class="muted">加载中…</div>
        <div v-else class="plan-word-list">
          <div v-for="(w, i) in planWords" :key="w.id" class="plan-word-item" @click="select(w.id)">
            <span class="plan-word-num">{{ i + 1 }}</span>
            <div class="plan-word-main">
              <strong>{{ w.term }}</strong>
              <small>{{ w.phonetic }} {{ w.part_of_speech }} {{ w.common_meaning || w.contextual_meaning }}</small>
            </div>
            <TtsButton :text="w.term" />
          </div>
        </div>
      </div>
    </div>
    <!-- v2.32: 短文填词入口 -->
    <div class="cloze-entry card" @click="loadCloze">
      <div class="cloze-entry-icon">✏️</div>
      <div class="cloze-entry-main">
        <strong>短文填词</strong>
        <small>真题句子挖空 · 在语境里检验单词（扇贝同款）</small>
      </div>
      <button class="button" :disabled="clozeLoading">{{ clozeLoading ? '生成中…' : '开始' }}</button>
    </div>
    <!-- v2.33: 词汇量自测入口 -->
    <div class="cloze-entry card" @click="loadQuiz">
      <div class="cloze-entry-icon">📊</div>
      <div class="cloze-entry-main">
        <strong>词汇量自测</strong>
        <small>10 个词快速定位词汇量等级（百词斩式初测）</small>
      </div>
      <button class="button" :disabled="quizLoading">{{ quizLoading ? '加载中…' : '开始' }}</button>
    </div>
    <!-- v2.64: 快答挑战入口 (百词斩 PK 式) -->
    <div class="cloze-entry card quick-entry" @click="startQuick">
      <div class="cloze-entry-icon">⚡</div>
      <div class="cloze-entry-main">
        <strong>快答挑战</strong>
        <small>10 题限时 4 选 1 · 每题 10 秒 · 最佳 {{ quickBest }}/10</small>
      </div>
      <button class="button secondary">开始</button>
    </div>
    <div v-if="error" class="warning">{{ error }}</div>

        <!-- v3.4: 今日推荐 20 词（紧凑横版卡片——竞品借鉴） -->
        <div v-if="recommended.length" class="card recommended-section">
          <div class="recommended-head">
            <h3>📖 今日推荐</h3>
            <span class="recommended-sub">随机 20 词 · 快速浏览</span>
            <button class="button ghost compact" @click="router.push('/vocab-bank')">
              <Search :size="14" />查看全部单词库
            </button>
          </div>
          <div class="recommended-grid">
            <button v-for="w in recommended" :key="w.id" class="rec-word-card" @click="router.push({ path: '/vocab-bank', query: { word: w.id } })">
              <span class="rec-word-term">{{ w.lemma || w.term }}</span>
              <span class="rec-word-mean">{{ (w.common_meaning || w.contextual_meaning || '').slice(0, 12) }}</span>
              <span class="rec-word-badge" :class="w.study_status || 'new'">{{ vocabStatusText(w.study_status) }}</span>
            </button>
          </div>
        </div>

    <section v-if="reviewMode" class="review-overlay">
      <div class="review-progress"><i :style="{ width: ((reviewIndex) / Math.max(reviewItems.length, 1)) * 100 + '%' }"></i></div>
      <div class="review-card flip-scene" v-if="reviewWord">
        <div class="flip-inner" :class="{ flipped: reveal }" @click="toggleReveal">
          <!-- 正面: 单词 -->
          <div class="flip-face flip-front">
            <button class="button ghost review-close" @click.stop="reviewMode=false">退出复习</button>
            <span class="eyebrow">今日 {{ reviewIndex + 1 }} / {{ reviewItems.length }}</span>
            <div class="review-term"><span v-if="reviewWord.is_frequent">🌟</span>{{ reviewWord.lemma || reviewWord.term }}<TtsButton :text="reviewWord.term" :speed="0.85" /></div>
            <div class="review-phonetic">{{ reviewWord.phonetic }}</div>
            <button class="button secondary reveal-button" @click.stop="reveal=true"><span class="flip-hint">点击翻开</span><RefreshCw :size="15" /></button>
          </div>
          <!-- 背面: 释义 -->
          <div class="flip-face flip-back">
            <span class="eyebrow">今日 {{ reviewIndex + 1 }} / {{ reviewItems.length }}</span>
            <div class="review-answer">
              <strong>{{ reviewWord.common_meaning || reviewWord.contextual_meaning }}</strong>
              <p v-if="reviewWord.contextual_meaning && reviewWord.contextual_meaning !== reviewWord.common_meaning">
                本句语境：{{ reviewWord.contextual_meaning }}
              </p>
              <blockquote>{{ reviewWord.latest_sentence }}</blockquote>
            </div>
            <div class="review-actions">
              <button class="button danger" @click.stop="rate('again')">不认识</button>
              <button class="button secondary" @click.stop="rate('hard')">有点印象</button>
              <button class="button" @click.stop="rate('mastered')">已掌握</button>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="card empty">今天没有待复习的单词。</div>
    </section>

    <!-- v3.4: AI 文章练词弹层（按弱词生成专属短文——锐满分 6.0 借鉴） -->
    <div v-if="articleMode" class="review-overlay" role="dialog" aria-modal="true" aria-label="AI 文章练词">
      <div class="review-card cloze-card" style="max-height:86vh;overflow:auto">
        <div class="cloze-card-head">
          <h3 style="margin-bottom:8px">📄 AI 文章练词</h3>
          <button class="button ghost compact" @click="closeArticle">✕ 关闭</button>
        </div>
        <p class="lead" style="font-size:12px;line-height:1.7;margin-bottom:12px">按你的弱词生成专属短文 · 在语境里巩固（扇贝词文串学 + 锐满分 AI 文章练词）</p>
        <div style="display:flex;gap:8px;margin-bottom:12px;align-items:center">
          <span style="font-size:12px;color:var(--muted)">主题：</span>
          <button v-for="t in ['随机','科技','日常','考研']" :key="t" class="notes-tag small" :class="{active:articleTopic===t}" @click="articleTopic=t">{{ t }}</button>
          <button class="button" :disabled="articleLoading" @click="loadArticle">{{ articleLoading ? '生成中…' : '重新生成' }}</button>
        </div>
        <div v-if="articleLoading" class="muted" style="padding:20px;text-align:center">AI 正在写短文…</div>
        <div v-else-if="articleData?.error" class="warning">{{ articleData.error }}</div>
        <template v-else-if="articleData">
          <div class="vocab-article-words" style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px">
            <span v-for="w in articleData.words" :key="w.term" class="vocab-article-word"
              style="background:var(--primary-soft);color:var(--primary);padding:3px 10px;border-radius:99px;font-size:12px;cursor:pointer"
              @click="quickAddVocab(w.term)">
              {{ w.term }}
              <span v-if="w.meaning" style="color:var(--muted)">· {{ w.meaning }}</span>
            </span>
          </div>
          <div class="vocab-article-body" style="line-height:2;font-size:15px;background:var(--surface-2);border-radius:12px;padding:16px"
               v-html="sanitizeHtml(articleData.article_html || articleData.article || '')"></div>
          <p style="font-size:11px;color:var(--muted);margin-top:8px">点击上方单词可加入生词复习</p>
        </template>
      </div>
    </div>

    <!-- v2.32: 短文填词弹层 -->
    <div v-if="clozeMode" class="review-overlay" role="dialog" aria-modal="true" aria-label="短文填词">
      <div class="review-card cloze-card">
        <div class="cloze-card-head">
          <h3 style="margin-bottom:8px">✏️ 短文填词</h3>
          <button class="button ghost compact" @click="closeCloze">✕ 退出</button>
        </div>
        <p class="lead" style="font-size:12px;line-height:1.7;margin-bottom:14px">真题句子挖空 · 选择最合适的单词（扇贝同款练习）</p>
        <template v-if="!clozeDone && clozeCurrent">
          <div class="cloze-progress">{{ clozeIndex + 1 }} / {{ clozeItems.length }} · 答对 {{ clozeScore }}</div>
          <p class="cloze-sentence">{{ clozeCurrent.blank_sentence }}</p>
          <p class="cloze-meaning">{{ clozeCurrent.phonetic }} {{ clozeCurrent.part_of_speech }} · {{ clozeCurrent.meaning }}</p>
          <div class="cloze-options">
            <button v-for="opt in clozeCurrent.options" :key="opt" class="cloze-option"
              :class="{ picked: clozePicked && opt === clozeCurrent.answer, wrong: clozePicked && opt === clozePicked && opt !== clozeCurrent.answer }"
              :disabled="!!clozePicked" @click="pickCloze(opt)">
              {{ opt }}
              <span v-if="clozePicked && opt === clozeCurrent.answer" class="cloze-mark">✓</span>
            </button>
          </div>
          <div style="display:flex;justify-content:flex-end;margin-top:16px">
            <button class="button" :disabled="!clozePicked" @click="nextCloze">{{ clozeIndex < clozeItems.length - 1 ? '下一题' : '查看结果' }}</button>
          </div>
        </template>
        <template v-else-if="clozeDone">
          <div class="cloze-result">
            <div class="cloze-score">{{ clozeScore }} / {{ clozeItems.length }}</div>
            <p>{{ clozeScore === clozeItems.length ? '🎉 全对！语感很棒' : clozeScore >= 3 ? '👍 不错，继续巩固' : '📖 多看看单词本，再试一次' }}</p>
            <p v-if="clozeWrong.length" class="cloze-wrong">需要巩固：{{ clozeWrong.join('、') }}</p>
          </div>
          <div style="display:flex;justify-content:center;gap:10px;margin-top:18px">
            <button class="button" @click="loadCloze">再练一组</button>
            <button class="button ghost" @click="closeCloze">关闭</button>
          </div>
        </template>
      </div>
    </div>
    <!-- v2.33: 词汇量自测弹层 -->
    <div v-if="quizMode" class="review-overlay" role="dialog" aria-modal="true" aria-label="词汇量自测">
      <div class="review-card cloze-card">
        <div class="cloze-card-head">
          <h3 style="margin-bottom:8px">📊 词汇量自测</h3>
          <button class="button ghost compact" @click="closeQuiz">✕ 退出</button>
        </div>
        <p class="lead" style="font-size:12px;line-height:1.7;margin-bottom:14px">10 个词 · 认识 / 模糊 / 不认识，快速定位词汇等级</p>
        <template v-if="!quizResult && quizCurrent">
          <div class="cloze-progress">{{ quizIndex + 1 }} / {{ quizItems.length }}</div>
          <p class="quiz-word">{{ quizCurrent.word }}</p>
          <p class="quiz-phonetic">{{ quizCurrent.phonetic }}</p>
          <button v-if="!quizRevealed" class="button ghost" style="margin-bottom:16px" @click="toggleQuizReveal">显示释义</button>
          <p v-else class="quiz-meaning" style="margin-bottom:16px" @click="toggleQuizReveal">{{ quizCurrent.meaning || '（暂无释义）' }}</p>
          <div class="cloze-options" style="grid-template-columns:repeat(3,1fr)">
            <button class="cloze-option" @click="rateQuiz(0)">😵 不认识</button>
            <button class="cloze-option" @click="rateQuiz(1)">🤔 模糊</button>
            <button class="cloze-option" @click="rateQuiz(2)">😎 认识</button>
          </div>
        </template>
        <template v-else-if="quizResult">
          <div class="cloze-result">
            <div class="cloze-score">{{ quizResult.estimated }}</div>
            <p>估算词汇量</p>
            <div class="quiz-level">{{ quizResult.level }}</div>
            <p style="margin-top:8px">答题 {{ quizResult.answered }} 词 · 正确率 {{ Math.round((quizResult.ratio || 0) * 100) }}%</p>
          </div>
          <div style="display:flex;justify-content:center;gap:10px;margin-top:18px">
            <button class="button" @click="loadQuiz">再测一次</button>
            <button class="button ghost" @click="closeQuiz">关闭</button>
          </div>
        </template>
      </div>
    </div>
    <div v-if="showDisplayDialog" class="review-overlay" role="dialog" aria-modal="true" aria-label="单词本显示设置">
      <div class="review-card vocab-display-dialog">
        <h3 style="margin-bottom:10px">单词本显示设置</h3>
        <p class="lead" style="font-size:12px;line-height:1.7;margin-bottom:16px">全局默认显示哪些内容，对所有单词一致生效；查看单个单词时仍可点“展开全部”临时查看。</p>
        <div class="vocab-display-options">
          <label v-for="(label, key) in displayOptions" :key="key">
            <input v-model="displayConfig[key]" type="checkbox" @change="saveDisplayConfig">
            <span>{{ label }}</span>
          </label>
        </div>
        <div style="display:flex;justify-content:center;margin-top:22px">
          <button class="button" @click="showDisplayDialog=false">完成</button>
        </div>
      </div>
    </div>
  </div>

  <!-- v2.64: 快答挑战弹层 (百词斩 PK 式) -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div v-if="quickMode" class="quick-overlay" @click.self="closeQuick">
        <div class="quick-panel">
          <div class="quick-head">
            <span class="eyebrow">QUICK CHALLENGE</span>
            <button class="button ghost compact" @click="closeQuick">✕ 退出</button>
          </div>
          <!-- 结果 -->
          <div v-if="quickDone" class="quick-result">
            <span class="quick-result-icon">{{ quickLevel.icon }}</span>
            <h3 class="quick-result-title">{{ quickLevel.label }}</h3>
            <p class="quick-result-score"><b class="rank-num">{{ quickScore }}</b> / {{ quickItems.length }}</p>
            <p class="quick-result-best">最佳成绩 {{ quickBest }}/{{ quickItems.length }}</p>
            <div class="quick-actions">
              <button class="button" @click="startQuick">再来一局</button>
              <button class="button ghost" @click="closeQuick">关闭</button>
            </div>
          </div>
          <!-- 答题 -->
          <template v-else-if="quickCurrent">
            <div class="quick-progress">
              <i :style="{ width: ((quickIndex + 1) / quickItems.length) * 100 + '%' }"></i>
            </div>
            <div class="quick-meta">
              <span>{{ quickIndex + 1 }} / {{ quickItems.length }}</span>
              <span class="quick-timer" :class="{ low: quickRemain <= 3 }">⏱ {{ quickRemain }}s</span>
              <span>得分 {{ quickScore }}</span>
            </div>
            <h3 class="quick-word">{{ quickCurrent.word }}</h3>
            <div class="quick-options">
              <button
                v-for="opt in quickOptions" :key="opt"
                class="quick-option" type="button"
                :class="{
                  picked: quickPicked === opt,
                  correct: quickPicked !== null && opt === quickCurrent.meaning,
                  wrong: quickPicked === opt && opt !== quickCurrent.meaning,
                }"
                @click="quickAnswer(opt)"
              >{{ opt }}</button>
            </div>
          </template>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
