<script setup lang="ts">
import { ArrowRight, BookOpen, Flame, Sparkles, Star } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get, post } from '../api'
import { showToast } from '../services/toast'
import QuestionBankSwitcher from '../components/QuestionBankSwitcher.vue'
import StudyHeatmap from '../components/StudyHeatmap.vue'
import CountUp from '../components/CountUp.vue'

const router = useRouter()
const data = ref<any>(null)
const aiPicks = ref<any>(null)
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
  try { aiPicks.value = await get('/recommendations/ai') } catch { /* 推题失败不阻塞 */ }
  loadGoalAndWord()
})
onBeforeUnmount(() => {
  if (vocabularyTimer !== null) window.clearInterval(vocabularyTimer)
})

// v2.40: 打卡里程碑庆祝 (3/7/14/30 天火焰, localStorage 防重复)
import CelebrateOverlay from '../components/CelebrateOverlay.vue'
const streakCelebrate = ref<{ show: boolean; kind: 'confetti' | 'flame'; title: string; subtitle: string }>({
  show: false, kind: 'flame', title: '', subtitle: '',
})
const STREAK_MILESTONES = [3, 7, 14, 30, 60, 100]
function maybeStreakCelebrate(streak: number) {
  if (streak < 3) return
  const milestone = STREAK_MILESTONES.filter((m) => streak >= m).pop()
  if (!milestone) return
  const key = `epm_streak_celebrated_${milestone}`
  if (localStorage.getItem(key)) return
  localStorage.setItem(key, '1')
  streakCelebrate.value = {
    show: true, kind: 'flame',
    title: `🔥 连续打卡 ${streak} 天！`,
    subtitle: `达成 ${milestone} 天里程碑 · 坚持就是胜利`,
  }
}

// v2.39: 今日目标 (localStorage) + 今日答题数 (leaderboard API) + 每日一词
const dailyGoal = ref(Number(localStorage.getItem('epm_daily_goal') || 50))
const todayAnswered = ref(0)
const wordOfDay = ref<any>(null)
const goalPct = computed(() => {
  if (!dailyGoal.value) return 0
  return Math.min(100, Math.round((todayAnswered.value / dailyGoal.value) * 100))
})
function saveGoal() {
  localStorage.setItem('epm_daily_goal', String(dailyGoal.value))
  showToast(`今日目标设为 ${dailyGoal.value || '未设定'} 题`, 'success')
}
function quickGoal(n: number) {
  dailyGoal.value = n
  saveGoal()
}
async function loadGoalAndWord() {
  try {
    const lb: any = await get('/leaderboard')
    const days = lb.days || []
    todayAnswered.value = days.length ? days[days.length - 1].count : 0
    maybeStreakCelebrate(lb.streak || 0) // v2.40: 打卡里程碑火焰
  } catch { /* 排行不可用忽略 */ }
  // 每日一词: 按日期从已加载词汇里取 (固定种子, 当天稳定)
  try {
    const pool = vocabulary.value?.length ? vocabulary.value : []
    if (pool.length) {
      const daySeed = new Date().toISOString().slice(0, 10)
      let h = 0
      for (const ch of daySeed) h = (h * 31 + ch.charCodeAt(0)) % 997
      wordOfDay.value = pool[h % pool.length]
    }
  } catch { /* 忽略 */ }
}

async function randomPractice(type: string) {
  try {
    const session: any = await post('/practice/sessions', {
      mode: 'random', unit_type: type, count: 1, shuffle_options: true,
    })
    router.push(`/practice/${session.id}`)
  } catch (e) { error.value = String(e) }
}

// v2.18: 今日计划任务跳转
function runPlanTask(task: any) {
  if (task.action === 'words') { router.push('/vocabulary') }
  else if (task.action === 'wrong') { router.push('/wrong') }
  else { randomPractice(task.action) }
}

const UNIT_TYPE_NAMES: Record<string, string> = {
  cloze: '完形填空', reading: '阅读理解', paragraph_matching: '阅读 Part B', part_b: '阅读 Part B',
  translation: '翻译', writing: '写作', listening: '听力理解',
}
const UNIT_TYPE_PARAMS: Record<string, string> = {
  cloze: 'cloze', reading: 'reading', paragraph_matching: 'part_b', listening: 'listening',
}
function typeName(type: string) { return UNIT_TYPE_NAMES[type] || type }
function typeParam(type: string) { return UNIT_TYPE_PARAMS[type] || type }

// v2.12: 练习卡随级别动态切换 (标题/描述/可用性 按当前题库级别)
const practiceCards = computed(() => {
  const profile = data.value?.active_profile?.name || ''
  const counts = data.value?.recommendations?.unit_type_counts || {}
  const clozeN = counts.cloze || 0
  const readN = counts.reading || 0
  const partBN = counts.paragraph_matching || 0
  const isGaoKao = profile.includes('高中')
  const isCet4 = profile.includes('四级')
  const isCet6 = profile.includes('六级')
  const isKaoYan = profile.includes('考研')
  const level = profile || '本级别'
  return [
    {
      key: 'cloze', icon: '/assets/icons/cloze.png', iconClass: 'orange',
      title: isCet4 || isCet6 ? '选词填空' : '完形填空',
      subtitle: clozeN
        ? (isKaoYan ? `${level} · 20 空语篇` : isGaoKao ? `${level} · 15 空语境` : `${level} · 整篇提交`)
        : `${level} 暂无此题型`,
      desc: isCet4 || isCet6
        ? '四六级改革后取消完形，改为选词填空（词汇理解）。'
        : (isKaoYan ? '考研完形：语篇连贯与词汇辨析并重。' : isGaoKao ? '高考完形：语境语义优先于语法。' : '在完整语境中完成填空练习。'),
      enabled: clozeN > 0, type: 'cloze',
    },
    {
      key: 'reading', icon: '/assets/icons/reading.png', iconClass: 'sage',
      title: '阅读理解',
      subtitle: readN ? `${level} · ${readN} 篇` : `${level} 暂无此题型`,
      desc: isKaoYan ? '考研阅读 A：主旨/态度/细节/推理四类题。'
        : isCet6 ? '六级仔细阅读：学术语料，长难句更多。'
        : isCet4 ? '四级仔细阅读：篇章长度与词汇量适中。'
        : isGaoKao ? '高考阅读：传统四篇 + 语篇理解。'
        : '按文章完整练习，专注理解论证与细节。',
      enabled: readN > 0, type: 'reading',
    },
    {
      key: 'part_b', icon: '/assets/icons/part-b.png', iconClass: 'blue',
      title: isKaoYan ? '阅读 Part B' : (isCet4 || isCet6 ? '长篇阅读匹配' : '七选五'),
      subtitle: partBN ? `${level} · ${partBN} 篇` : `${level} 暂无此题型`,
      desc: isKaoYan ? '考研新题型：七选五/排序/段落匹配。'
        : (isCet4 || isCet6) ? '四六级长篇阅读：句子与段落信息匹配。'
        : isGaoKao ? '高考七选五：把握文章结构与句际逻辑。'
        : '在段落关系中辨认结构、衔接与观点。',
      enabled: partBN > 0, type: 'part_b',
    },
  ]
})
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
    <!-- v2.18: 备考倒计时条 (研究: 练题狗/好题库 备考节点) -->
    <div v-if="data?.exam_countdown?.length" class="exam-countdown-bar">
      <span class="countdown-label">⏳ 备考倒计时</span>
      <span v-for="ex in data.exam_countdown" :key="ex.name" class="countdown-item">
        <strong>{{ ex.name }}</strong>
        <b>{{ ex.days_left }}</b> 天
      </span>
    </div>
    <!-- v2.18/19: 今日学习计划 (研究: AI智能推题/艾宾浩斯新学+复习) -->
    <div v-if="data?.today_plan?.plan?.length" class="card today-plan-card">
      <div class="today-plan-head">
        <h3 class="today-plan-title">📌 今日学习计划</h3>
        <span class="today-plan-total">预计 {{ data.today_plan.total_minutes || 0 }} 分钟</span>
      </div>
      <div class="today-plan-list">
        <button
          v-for="(task, i) in data.today_plan.plan" :key="i"
          class="today-plan-item" type="button"
          :class="{ done: task.done }"
          @click="!task.done && runPlanTask(task)"
        >
          <span class="plan-icon">{{ task.icon }}</span>
          <span class="plan-label">{{ task.label }}</span>
          <span class="plan-min">{{ task.minutes }}分</span>
          <span class="plan-status">{{ task.done ? '✓ 已完成' : '开始 →' }}</span>
        </button>
      </div>
    </div>
    <!-- v2.39: 今日目标 + 每日一词 -->
    <div class="grid grid-2 home-goal-row">
      <div class="card today-plan-card">
        <div class="today-plan-head">
          <h3 class="today-plan-title">🎯 今日目标</h3>
          <span class="today-plan-total">{{ todayAnswered }} / {{ dailyGoal }} 题</span>
        </div>
        <div class="goal-bar"><i :style="{ width: goalPct + '%' }"></i></div>
        <div class="goal-actions">
          <button class="button ghost compact" @click="quickGoal(20)">20题</button>
          <button class="button ghost compact" @click="quickGoal(50)">50题</button>
          <button class="button ghost compact" @click="quickGoal(100)">100题</button>
          <button class="button compact" @click="dailyGoal = 0; saveGoal()">重置</button>
        </div>
      </div>
      <div class="card today-plan-card word-of-day" @click="router.push('/vocabulary')">
        <div class="today-plan-head"><h3 class="today-plan-title">📖 每日一词</h3></div>
        <template v-if="wordOfDay">
          <p class="wod-word">{{ wordOfDay.term }}</p>
          <p class="wod-mean">{{ wordOfDay.common_meaning || wordOfDay.contextual_meaning || '' }}</p>
          <span class="wod-hint">去单词本复习 →</span>
        </template>
        <p v-else class="muted">暂无词汇数据</p>
      </div>
    </div>
    <!-- v2.9: 按当前级别针对性推荐 -->
    <section v-if="data?.recommendations" class="recommend-section">
      <div class="section-title"><h2><span class="hero-seal recommend-seal" aria-hidden="true">荐</span>{{ data.active_profile?.name || '本级别' }} · 为你推荐</h2></div>
      <!-- v2.29: AI 智能推题 -->
      <div v-if="aiPicks" class="card ai-picks-card">
        <div class="ai-picks-head">
          <span class="ai-picks-badge">AI 推题</span>
          <span class="ai-picks-sub">基于薄弱分析 · 规则引擎</span>
        </div>
        <div class="ai-picks-body">
          <div v-if="aiPicks.strategy?.length" class="ai-strategy">
            <p v-for="(s, i) in aiPicks.strategy" :key="i">{{ s }}</p>
          </div>
          <div class="ai-picks-row">
            <button v-if="aiPicks.weak_type" class="ai-pick-chip" type="button" @click="randomPractice(aiPicks.weak_type)">
              🎯 强化{{ aiPicks.weak_label }}（薄弱）
            </button>
            <button v-if="aiPicks.redo?.length" class="ai-pick-chip" type="button" @click="router.push('/wrong')">
              🔁 重做 {{ aiPicks.redo.length }} 道高频错题
            </button>
            <button v-if="aiPicks.vocab?.length" class="ai-pick-chip" type="button" @click="router.push('/vocabulary')">
              📖 背 {{ aiPicks.vocab.length }} 个生词
            </button>
            <button class="ai-pick-chip" type="button" @click="router.push('/exam')">
              ✍️ 模拟考试
            </button>
          </div>
        </div>
      </div>
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
      <button
        v-for="card in practiceCards" :key="card.key"
        class="card action-card" type="button"
        :disabled="!card.enabled"
        :class="{ 'practice-card-disabled': !card.enabled }"
        @click="card.enabled && randomPractice(card.type)"
      >
        <span class="feature-icon" :class="card.iconClass"><img :src="card.icon" alt="" /></span>
        <span class="action-copy">
          <small>{{ card.subtitle }}</small>
          <h3>{{ card.title }}</h3>
          <p>{{ card.desc }}</p>
        </span>
        <ArrowRight class="action-arrow" :size="19" />
      </button>
    </div>
    <div class="section-title"><h2>学习概览</h2></div>
    <div v-if="data" class="grid grid-4 bento-stats">
      <div class="card stat-card bento-wide ink-dot"><span class="seal-badge" aria-hidden="true">卷</span><span class="stat-label">已收录年份</span><div class="stat-value"><CountUp :value="data.paper_count" /></div><span class="stat-note">覆盖 {{ data.active_profile?.name || '本级别' }} 真题与模拟</span></div>
      <div class="card stat-card ink-dot"><span class="seal-badge" aria-hidden="true">篇</span><span class="stat-label">练习篇目</span><div class="stat-value"><CountUp :value="data.unit_count" /></div></div>
      <div class="card stat-card ink-dot"><span class="seal-badge" aria-hidden="true">题</span><span class="stat-label">客观题</span><div class="stat-value"><CountUp :value="data.question_count" /></div></div>
      <div class="card stat-card ink-dot"><span class="seal-badge" aria-hidden="true">错</span><span class="stat-label">高频错题</span><div class="stat-value"><CountUp :value="data.frequent_count" /></div></div>
      <RouterLink to="/report" class="card stat-card linked ink-dot bento-wide"><span class="seal-badge" aria-hidden="true">报</span><span class="stat-label">学习报告</span><div class="stat-value"><CountUp :value="data.answered_count || 0" /></div><span class="stat-link">查看趋势与建议 <ArrowRight :size="14" /></span></RouterLink>
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

  <!-- v2.40: 打卡里程碑火焰庆祝 -->
  <CelebrateOverlay
    :show="streakCelebrate.show"
    :kind="streakCelebrate.kind"
    :title="streakCelebrate.title"
    :subtitle="streakCelebrate.subtitle"
    @close="streakCelebrate.show = false"
  />
</template>
