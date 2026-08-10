<script setup lang="ts">
import { BookOpen, Check, RefreshCw, Search, Settings, Star, Trash2, Headphones } from 'lucide-vue-next'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { del, get, post, put } from '../api'
import TtsButton from '../components/TtsButton.vue'
import DictationMode from '../components/DictationMode.vue'
import { showToast } from '../services/toast'

const route = useRoute()
const items = ref<any[]>([])
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
    <div v-if="notice" class="card vocab-notice">{{ notice }}</div>
    <div class="vocab-categories">
      <button class="vocab-cat-chip" :class="{ active: category === '' }" @click="category=''">全部</button>
      <button class="vocab-cat-chip" :class="{ active: category === '高中' }" @click="category='高中'">🏫 高中</button>
      <button class="vocab-cat-chip" :class="{ active: category === '四级' }" @click="category='四级'">📘 四级</button>
      <button class="vocab-cat-chip" :class="{ active: category === '六级' }" @click="category='六级'">📙 六级</button>
      <button class="vocab-cat-chip" :class="{ active: category === '考研' }" @click="category='考研'">🎓 考研</button>
    </div>
    <div class="vocab-categories vocab-cat-types">
      <button class="vocab-cat-chip" :class="{ active: catType === '' }" @click="catType=''">全部类型</button>
      <button class="vocab-cat-chip" :class="{ active: catType === '·高频' }" @click="catType='·高频'">⭐ 高频词</button>
      <button class="vocab-cat-chip" :class="{ active: catType === '·热点' }" @click="catType='·热点'">🔥 热点词</button>
      <button class="vocab-cat-chip" :class="{ active: catType === '·' }" @click="catType='·'">📚 基础词</button>
    </div>
    <div class="vocab-stats">
      <button class="card" @click="filter='all'"><span>全部单词</span><strong>{{ counts.total || 0 }}</strong></button>
      <button class="card amber" @click="filter='frequent'"><span>🌟 高频生词</span><strong>{{ counts.frequent || 0 }}</strong></button>
      <button class="card" @click="filter='review'"><span>今日待复习</span><strong>{{ counts.review || 0 }}</strong></button>
      <button class="card" @click="filter='mastered'"><span>已掌握</span><strong>{{ counts.mastered || 0 }}</strong></button>
      <button class="card" @click="filter='pending'"><span>等待翻译</span><strong>{{ counts.pending || 0 }}</strong></button>
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

    <div v-else class="vocabulary-layout">
      <aside class="vocab-filters card">
        <div class="search-field"><Search :size="16" /><input v-model="search" placeholder="搜索单词或释义"></div>
        <button v-for="item in [
          ['all','全部单词'],['review','今日复习'],['frequent','🌟 高频词'],
          ['familiar','认识'],['learning','模糊'],['mastered','已掌握'],['pending','等待翻译']
        ]" :key="item[0]" :class="{active:filter===item[0]}" @click="filter=item[0]">{{ item[1] }}</button>
      </aside>

      <section class="vocab-list card">
        <button v-for="word in items" :key="word.id" class="vocab-list-item" :class="{active:selected?.id===word.id}" @click="select(word.id)">
          <div class="vocab-list-head"><strong><span v-if="word.is_frequent">🌟 </span>{{ word.lemma || word.term }}</strong><small>遇到 {{ word.encounter_count }} 次</small></div>
          <p v-if="word.translation_status==='ready'">{{ word.common_meaning || word.contextual_meaning }}</p>
          <p v-else class="pending-text">{{ translationStatusText(word.translation_status) }}</p>
          <div class="vocab-list-meta"><span>{{ word.part_of_speech }}</span><span class="study-badge" :class="word.study_status || 'new'">{{ vocabStatusText(word.study_status) }}</span></div>
        </button>
        <div v-if="!items.length" class="empty">这里还没有符合条件的单词。</div>
      </section>

      <section class="vocab-detail card" v-if="selected">
        <div class="vocab-detail-head">
          <div><span class="eyebrow">{{ selected.is_frequent ? '🌟 HIGH FREQUENCY' : 'VOCABULARY' }}</span><h2>{{ selected.lemma || selected.term }}<TtsButton :text="selected.term" :speed="0.8" /></h2><p>{{ selected.phonetic }} <span v-if="selected.part_of_speech">· {{ selected.part_of_speech }}</span></p></div>
          <div class="vocab-tools"><button class="button ghost" @click="expandedAll=!expandedAll">{{ expandedAll ? '收起全部' : '展开全部' }}</button><button class="button ghost" @click="exportAnki">导出 Anki</button><button class="button ghost" @click="editing=!editing">编辑</button><button class="button ghost danger-text" @click="removeEntry"><Trash2 :size="17" /></button></div>
        </div>
        <div v-if="selected.translation_status!=='ready'" class="vocab-pending-panel">
          <RefreshCw :size="22" /><strong>{{ translationStatusText(selected.translation_status, true) }}</strong>
          <p>单词和真题原句已经安全保存。</p>
          <button v-if="selected.translation_status==='failed'" class="button secondary" @click="retryTranslation">重新翻译</button>
        </div>
        <template v-else-if="!editing">
          <div v-if="displayConfig.common_meaning || expandedAll" class="detail-section"><label>常用释义</label><strong>{{ selected.common_meaning || selected.contextual_meaning }}</strong></div>
          <div v-if="selected.synonyms?.length && (displayConfig.synonyms || expandedAll)" class="detail-section discrimination-section">
            <label>同义词辨析</label>
            <ul class="discrimination-list">
              <li v-for="item in selected.synonyms" :key="`s-${item.word}`"><strong>{{ item.word }}</strong><span>{{ item.note }}</span></li>
            </ul>
          </div>
          <div v-if="selected.antonyms?.length && (displayConfig.antonyms || expandedAll)" class="detail-section discrimination-section">
            <label>反义词辨析</label>
            <ul class="discrimination-list">
              <li v-for="item in selected.antonyms" :key="`a-${item.word}`"><strong>{{ item.word }}</strong><span>{{ item.note }}</span></li>
            </ul>
          </div>
          <div v-if="(selected.local_similar?.length || selected.similar_forms?.length) && (displayConfig.similar_forms || expandedAll)" class="detail-section discrimination-section">
            <label>形近词辨析</label>
            <ul class="discrimination-list">
              <li v-for="item in selected.local_similar" :key="`l-${item.word}`"><strong>{{ item.word }}</strong><span>{{ item.note }}<em class="source-tag">本地</em></span></li>
              <li v-for="item in selected.similar_forms" :key="`m-${item.word}`"><strong>{{ item.word }}</strong><span>{{ item.note }}</span></li>
            </ul>
          </div>
          <div v-if="selected.memory_hint && (displayConfig.memory_hint || expandedAll)" class="detail-section memory-hint"><label>记忆提示</label><p>{{ selected.memory_hint }}</p></div>
          <div v-if="selected.note" class="detail-section"><label>我的笔记</label><p>{{ selected.note }}</p></div>
          <div v-if="(displayConfig.contextual || expandedAll) || (displayConfig.sentence || expandedAll)" class="detail-section"><label>真题中的遇见</label>
            <div v-if="selected.contextual_meaning && (displayConfig.contextual || expandedAll)" class="occurrence-context-meaning">
              <small>语境释义</small>
              <strong>{{ selected.contextual_meaning }}</strong>
            </div>
            <template v-if="displayConfig.sentence || expandedAll">
              <article v-for="occurrence in selected.occurrences" :key="occurrence.id" class="occurrence">
                <p>{{ occurrence.context_sentence }}</p>
                <small>{{ occurrence.year || '未知年份' }} · {{ occurrence.unit_title || occurrence.unit_type }}</small>
              </article>
            </template>
          </div>
          <!-- v2.23: 词文串学 — 全局真题语境扩展 -->
          <div class="detail-section vocab-context-section">
            <label>词文串学 · 真题语境</label>
            <p class="vocab-context-hint">在真题文章中巩固记忆，背一个词，见真语境</p>
            <div v-if="wordContextsLoading" class="muted">检索真题语境…</div>
            <div v-else-if="wordContexts.length">
              <article v-for="(c, i) in wordContexts" :key="i" class="occurrence">
                <p v-html="highlightContext(c)"></p>
                <small>{{ c.source }} <span v-if="c.style" class="style-badge" :class="`style-${c.style}`">{{ styleLabel(c.style) }}</span></small>
              </article>
            </div>
            <div v-else class="muted">题库中暂无该词的真题例句。</div>
          </div>
          <div class="detail-actions">
            <button class="button secondary" @click="put(`/vocabulary/${selected.id}`,{manually_frequent:!selected.manually_frequent}).then(()=>load())"><Star :size="16" />{{ selected.manually_frequent ? '取消重点' : '标记重点' }}</button>
            <button class="button" @click="put(`/vocabulary/${selected.id}`,{study_status:selected.study_status==='mastered'?'learning':'mastered'}).then(()=>load())"><Check :size="16" />{{ selected.study_status === 'mastered' ? '恢复学习' : '标记已掌握' }}</button>
          </div>
        </template>
        <div v-else class="vocab-edit">
          <label>音标<input v-model="editForm.phonetic"></label>
          <label>词性<input v-model="editForm.part_of_speech"></label>
          <label>当前语境释义<textarea rows="3" v-model="editForm.contextual_meaning"></textarea></label>
          <label>常用释义<textarea rows="3" v-model="editForm.common_meaning"></textarea></label>
          <label>我的笔记<textarea rows="4" v-model="editForm.note"></textarea></label>
          <div><button class="button" @click="saveEdit">保存修改</button><button class="button ghost" @click="editing=false">取消</button></div>
        </div>
      </section>
      <section v-else class="vocab-detail card empty">选择一个单词查看详细释义与真题语境。</section>
    </div>
    <!-- v2.32: 短文填词弹层 -->
    <div v-if="clozeMode" class="review-overlay" role="dialog" aria-modal="true" aria-label="短文填词">
      <div class="review-card cloze-card">
        <h3 style="margin-bottom:8px">✏️ 短文填词</h3>
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
        <h3 style="margin-bottom:8px">📊 词汇量自测</h3>
        <p class="lead" style="font-size:12px;line-height:1.7;margin-bottom:14px">10 个词 · 认识 / 模糊 / 不认识，快速定位词汇等级</p>
        <template v-if="!quizResult && quizCurrent">
          <div class="cloze-progress">{{ quizIndex + 1 }} / {{ quizItems.length }}</div>
          <p class="quiz-word">{{ quizCurrent.word }}</p>
          <p class="quiz-phonetic">{{ quizCurrent.phonetic }}</p>
          <button v-if="!quizRevealed" class="button ghost" style="margin-bottom:16px" @click="toggleQuizReveal">显示释义</button>
          <p v-else class="quiz-meaning" style="margin-bottom:16px">{{ quizCurrent.meaning }}</p>
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
