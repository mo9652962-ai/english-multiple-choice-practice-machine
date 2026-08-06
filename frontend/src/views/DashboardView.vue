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

async function loadHome(force = false) {
  error.value = ''
  const embedded = (window as any).__LINJIAN_STARTUP__
  // v2.11: 切换题库级别时 force=true → 跳过首屏缓存, 重新请求该级别推荐
  if (embedded && !force) {
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

const UNIT_TYPE_NAMES: Record<string, string> = {
  cloze: '完形填空', reading: '阅读理解', paragraph_matching: '阅读 Part B', part_b: '阅读 Part B',
  translation: '翻译', writing: '写作', listening: '听力',
}
const UNIT_TYPE_PARAMS: Record<string, string> = {
  cloze: 'cloze', reading: 'reading', paragraph_matching: 'part_b',
}
function typeName(type: string) { return UNIT_TYPE_NAMES[type] || type }
function typeParam(type: string) { return UNIT_TYPE_PARAMS[type] || type }
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
    <QuestionBankSwitcher @changed="() => loadHome(true)" />
    <!-- v2.9: 按当前级别针对性推荐 -->
    <section v-if="data?.recommendations" class="recommend-section">
      <div class="section-title"><h2><span class="hero-seal recommend-seal" aria-hidden="true">荐</span>{{ data.active_profile?.name || '本级别' }} · 为你推荐</h2></div>
      <!-- 继续练习 -->
      <RouterLink v-if="data.recommendations.continue_paper" :to="'/library'" class="card recommend-continue">
        <span class="feature-icon sage" style="width:48px;height:48px;font-size:22px;margin-bottom:0">继</span>
        <span class="action-copy">
          <small>上次未完</small>
          <h3>继续练习 {{ data.recommendations.continue_paper.year }} 年{{ data.recommendations.continue_paper.subject ? ' · ' + data.recommendations.continue_paper.subject : '' }}</h3>
          <p>{{ data.recommendations.continue_paper.title }}</p>
        </span>
        <ArrowRight class="action-arrow" :size="19" />
      </RouterLink>
      <!-- 本级别真题卷 -->
      <div v-if="data.recommendations.papers?.length" class="grid grid-4 recommend-papers">
        <RouterLink v-for="p in data.recommendations.papers.slice(0, 4)" :key="p.id" :to="'/library'" class="card recommend-paper">
          <span class="seal-badge" aria-hidden="true">卷</span>
          <strong>{{ p.year }} 年{{ p.subject ? ' · ' + p.subject : '' }}</strong>
          <small>{{ p.title }}</small>
          <span class="stat-link">去练习 <ArrowRight :size="14" /></span>
        </RouterLink>
      </div>
      <!-- 高频错题 + 薄弱单元 -->
      <div v-if="data.recommendations.top_wrong?.length" class="grid grid-2 recommend-wrong-grid">
        <div class="card recommend-wrong">
          <h3>本级别高频错题</h3>
          <RouterLink v-for="w in data.recommendations.top_wrong" :key="w.id" :to="'/wrong'" class="recommend-wrong-item">
            <span class="wrong-badge">{{ w.wrong_count }} 次错</span>
            <span>{{ w.prompt }}</span>
          </RouterLink>
        </div>
        <div v-if="data.recommendations.weak_units?.length" class="card recommend-wrong">
          <h3>薄弱单元</h3>
          <RouterLink v-for="u in data.recommendations.weak_units" :key="u.id" :to="'/wrong'" class="recommend-wrong-item">
            <span class="wrong-badge">{{ u.wrong_n }} 题错</span>
            <span>{{ u.title }}</span>
          </RouterLink>
        </div>
      </div>
      <!-- 能力雷达: 各题型正确率 + 薄弱一键专项 -->
      <div v-if="data.recommendations.ability_radar?.length" class="card recommend-radar">
        <h3>能力雷达 · 本级别各题型正确率</h3>
        <div class="radar-bars">
          <div v-for="a in data.recommendations.ability_radar" :key="a.type" class="radar-item" :class="{ weak: a.rate !== null && a.rate < 60 }">
            <span class="radar-label">{{ typeName(a.type) }}</span>
            <span class="radar-bar"><span class="radar-fill" :style="{ width: (a.rate ?? 0) + '%' }"></span></span>
            <span class="radar-rate">{{ a.rate ?? '—' }}%</span>
            <span v-if="a.rate !== null && a.rate < 60" class="radar-weak-tag">薄弱</span>
            <button v-if="a.rate !== null" class="button ghost radar-go" type="button" @click="randomPractice(typeParam(a.type))">练一练</button>
          </div>
        </div>
      </div>
    </section>
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
