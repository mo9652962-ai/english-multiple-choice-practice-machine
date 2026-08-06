<script setup lang="ts">
import { ArrowRight, BookOpen, Flame, Sparkles, Star } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get, post } from '../api'
import QuestionBankSwitcher from '../components/QuestionBankSwitcher.vue'
import StudyHeatmap from '../components/StudyHeatmap.vue'
import CountUp from '../components/CountUp.vue'

const router = useRouter()
const data = ref<any>(null)
const error = ref('')
const vocabulary = ref<any[]>([])
const tickerPaused = ref(false)
const vocabularyPage = ref(0)
const wordsPerPage = 4
let vocabularyTimer: number | null = null
// v9.19: streak 数据
const streak = ref<any>(null)
const dueToday = ref<any[]>([])
const vocabularyPages = computed(() => {
  const pages: any[][] = []
  for (let index = 0; index < vocabulary.value.length; index += wordsPerPage) {
    pages.push(vocabulary.value.slice(index, index + wordsPerPage))
  }
  return pages
})
const visibleWords = computed(() =>
  vocabularyPages.value[vocabularyPage.value] || vocabularyPages.value[0] || [],
)

function wordMeaning(word: any) {
  return word.common_meaning || word.contextual_meaning || '释义整理中'
}

function advanceVocabulary() {
  if (tickerPaused.value || vocabularyPages.value.length <= 1) return
  vocabularyPage.value = (vocabularyPage.value + 1) % vocabularyPages.value.length
}

function startVocabularyRotation() {
  if (vocabularyTimer !== null) window.clearInterval(vocabularyTimer)
  vocabularyTimer = window.setInterval(advanceVocabulary, 5000)
}

function wait(milliseconds: number) {
  return new Promise(resolve => window.setTimeout(resolve, milliseconds))
}

async function loadHome() {
  error.value = ''
  const embedded = (window as any).__LINJIAN_STARTUP__
  if (embedded) {
    data.value = embedded
    try {
      const words: any = await get('/vocabulary/home?limit=20')
      vocabulary.value = words.items || []
    } catch {
      vocabulary.value = []
    }
    return
  }
  let dashboardResult: PromiseSettledResult<any> | null = null
  let wordsResult: PromiseSettledResult<any> | null = null
  let streakResult: PromiseSettledResult<any> | null = null
  let dueResult: PromiseSettledResult<any> | null = null

  for (let attempt = 0; attempt < 2; attempt++) {
    [dashboardResult, wordsResult, streakResult, dueResult] = await Promise.allSettled([
      get('/startup'),
      get('/vocabulary/home?limit=20'),
      get('/dashboard/streak'),
      get('/vocabulary/due-today'),
    ])
    if (dashboardResult.status === 'fulfilled') break
    if (attempt === 0) await wait(500)
  }

  if (dashboardResult?.status === 'fulfilled') {
    data.value = dashboardResult.value
  } else {
    error.value = '主页数据暂时没有加载成功，请刷新页面重试。'
  }
  if (wordsResult?.status === 'fulfilled') {
    const words: any = wordsResult.value
    vocabulary.value = words.items || []
  }
  // v9.19: streak + 待复习
  if (streakResult?.status === 'fulfilled') {
    streak.value = streakResult.value
  }
  if (dueResult?.status === 'fulfilled') {
    const due: any = dueResult.value
    dueToday.value = due.entries || []
  }
}

onMounted(async () => {
  await loadHome()
  startVocabularyRotation()
})
onBeforeUnmount(() => {
  if (vocabularyTimer !== null) window.clearInterval(vocabularyTimer)
})

async function randomPractice(type: string) {
  try {
    const session: any = await post('/practice/sessions', {
      mode: 'random', unit_type: type, count: 1, shuffle_options: true,
    })
    router.push(`/practice/${session.id}`)
  } catch (e) { error.value = String(e) }
}
</script>

<template>
  <div class="page page-home">
    <div class="page-head study-hero">
      <div class="study-hero-copy">
        <span class="eyebrow">YOUR QUIET STUDY SPACE</span>
        <h1><span class="hero-seal" aria-hidden="true">墨</span>今天想练些什么？</h1>
        <p class="lead">选一篇文章，留一点安静的时间给自己。</p>
        <RouterLink class="button" to="/library"><BookOpen :size="17" />查看全部题库<ArrowRight :size="16" /></RouterLink>
      </div>
    </div>
    <QuestionBankSwitcher @changed="loadHome" />
    <div v-if="error" class="warning">{{ error }}</div>
    <section v-if="vocabulary.length" class="vocabulary-ticker card" @mouseenter="tickerPaused=true" @mouseleave="tickerPaused=false">
      <div class="ticker-heading"><div><span class="eyebrow">VOCABULARY REVIEW</span><h3>词汇回顾</h3></div><RouterLink to="/vocabulary">查看单词本 →</RouterLink></div>
      <div class="ticker-window">
        <Transition name="vocabulary-flip" mode="out-in">
          <div :key="vocabularyPage" class="ticker-group">
          <RouterLink v-for="word in visibleWords" :key="word.id" :to="`/vocabulary?word=${word.id}`" class="ticker-word">
            <Star v-if="word.is_frequent" class="vocab-star" :size="15" fill="currentColor" aria-label="高频词" />
            <span class="ticker-word-copy">
              <strong>{{ word.lemma || word.term }}</strong>
              <small :title="wordMeaning(word)">{{ wordMeaning(word) }}</small>
            </span>
          </RouterLink>
          </div>
        </Transition>
      </div>
    </section>
    <div class="grid grid-3 practice-actions">
      <button class="card action-card" type="button" @click="randomPractice('cloze')">
        <span class="feature-icon orange"><img src="/assets/icons/cloze.png" alt="" /></span>
        <span class="action-copy"><small>20 个空 · 整篇提交</small><h3>完型填空</h3><p>随机抽取一整篇，在完整语境中完成练习。</p></span>
        <ArrowRight class="action-arrow" :size="19" />
      </button>
      <button class="card action-card" type="button" @click="randomPractice('reading')">
        <span class="feature-icon sage"><img src="/assets/icons/reading.png" alt="" /></span>
        <span class="action-copy"><small>1 篇文章 · 5 道题</small><h3>阅读理解</h3><p>按文章完整练习，专注理解论证与细节。</p></span>
        <ArrowRight class="action-arrow" :size="19" />
      </button>
      <button class="card action-card" type="button" @click="randomPractice('part_b')">
        <span class="feature-icon blue"><img src="/assets/icons/part-b.png" alt="" /></span>
        <span class="action-copy"><small>排序 · 填入 · 匹配</small><h3>阅读 Part B</h3><p>在段落关系中辨认结构、衔接与观点。</p></span>
        <ArrowRight class="action-arrow" :size="19" />
      </button>
    </div>
    <div class="section-title"><h2>学习概览</h2></div>
    <div v-if="data" class="grid grid-4">
      <div class="card stat-card ink-dot"><span class="seal-badge" aria-hidden="true">卷</span><span class="stat-label">已收录年份</span><div class="stat-value"><CountUp :value="data.paper_count" /></div></div>
      <div class="card stat-card ink-dot"><span class="seal-badge" aria-hidden="true">篇</span><span class="stat-label">练习篇目</span><div class="stat-value"><CountUp :value="data.unit_count" /></div></div>
      <div class="card stat-card ink-dot"><span class="seal-badge" aria-hidden="true">题</span><span class="stat-label">客观题</span><div class="stat-value"><CountUp :value="data.question_count" /></div></div>
      <RouterLink to="/wrong" class="card stat-card linked ink-dot"><span class="seal-badge" aria-hidden="true">错</span><span class="stat-label">高频错题</span><div class="stat-value"><CountUp :value="data.frequent_count" /></div><span class="stat-link">去复习 <ArrowRight :size="14" /></span></RouterLink>
    </div>
    <div v-else class="loading-grid">
      <div class="skeleton skeleton-lg"></div>
      <div class="skeleton-grid">
        <div class="skeleton"></div>
        <div class="skeleton"></div>
        <div class="skeleton"></div>
        <div class="skeleton"></div>
      </div>
    </div>

    <!-- v9.19: streak 打卡卡片 -->
    <div v-if="streak" class="streak-card card">
      <div class="streak-head">
        <div class="streak-flame" :class="{ lit: streak.streak?.today_active }">
          <Flame :size="28" fill="currentColor" />
        </div>
        <div>
          <span class="eyebrow">STUDY STREAK</span>
          <h3>已连续学习 <strong>{{ streak.streak?.current || 0 }}</strong> 天</h3>
          <p class="lead">历史最佳 {{ streak.streak?.best || 0 }} 天 · 本月 {{ streak.monthly?.active_days || 0 }} 天活跃</p>
        </div>
        <RouterLink v-if="dueToday.length" to="/vocabulary" class="due-link">
          {{ dueToday.length }} 个单词待复习 <ArrowRight :size="14" />
        </RouterLink>
      </div>
      <StudyHeatmap :values="streak.heatmap || []" tooltip-unit="次学习" />
      <div v-if="streak.weekly" class="weekly-strip">
        <span v-for="d in streak.weekly.daily" :key="d.date" class="week-dot" :class="{ active: d.active, today: d.date === streak.weekly.daily[6].date }" :title="`${d.date} · ${d.count} 次学习`" />
        <span class="weekly-text">本周 {{ streak.weekly.active_days }}/7 天活跃 · {{ streak.weekly.total_activities }} 次学习</span>
      </div>
      <div v-if="dueToday.length" class="due-words">
        <span class="due-label">今日待复习：</span>
        <RouterLink v-for="w in dueToday.slice(0, 6)" :key="w.id" :to="`/vocabulary?word=${w.id}`" class="due-chip">{{ w.term }}</RouterLink>
        <RouterLink v-if="dueToday.length > 6" to="/vocabulary" class="due-more">+{{ dueToday.length - 6 }}</RouterLink>
      </div>
    </div>
    <div class="section-title"><h2>温柔提醒</h2></div>
    <div class="card gentle-reminder">
      <span class="icon blue" style="margin:0"><Sparkles /></span>
      <div><h3>理解文章，比记住答案更重要。</h3><p class="lead">选项可以每次打乱，但文章中的逻辑不会改变。</p></div>
    </div>
  </div>
</template>
