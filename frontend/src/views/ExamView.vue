<script setup lang="ts">
// 模拟考试模式 — 全屏限时作答 + 即时评分
import {
  AlarmClock,
  Award,
  BookMarked,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Flag,
  Play,
  RotateCcw,
  Sparkles,
  XCircle,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { haptic } from '../services/haptics'
import { sound } from '../services/sound'
import { useRoute, useRouter } from 'vue-router'
import { get, post, put } from '../api'

const route = useRoute()
const router = useRouter()
const examId = ref<number | null>(null)
const exam = ref<any>(null)
const loading = ref(true)
const error = ref('')
const remaining = ref(0)
const current = ref(0)
const submitting = ref(false)
const confirmSubmit = ref(false)
const ticker: any = ref(null)

const profileId = ref(1)
const startCount = ref(20)
const showStartDialog = ref(false)

const EXAM_PROFILES = [
  { id: 1, name: '考研英语一' },
  { id: 5, name: '考研英语二' },
  { id: 3, name: '英语四级 CET-4' },
  { id: 4, name: '英语六级 CET-6' },
  { id: 2, name: '高中/高考英语' },
]

const QUESTION_COUNTS = [
  { count: 10, label: '10 题 · 快速自测' },
  { count: 20, label: '20 题 · 标准模拟' },
  { count: 40, label: '40 题 · 强化冲刺' },
]

const currentQuestion = computed(() => exam.value?.questions?.[current.value] || null)
const answeredCount = computed(() => (exam.value?.questions || []).filter((q: any) => q.answered).length)

const examSealInfo = computed(() => {
  const acc = exam.value?.accuracy ?? 0
  if (acc >= 85) return { text: '金榜题名 · 状元及第', class: 'top' }
  if (acc >= 70) return { text: '登科及第 · 渐入佳境', class: 'good' }
  if (acc >= 60) return { text: '金榜有声 · 顺利过关', class: 'pass' }
  return { text: '砥砺潜修 · 蓄力再战', class: 'retry' }
})

function fmtTime(s: number) {
  const m = Math.floor(s / 60)
  const ss = s % 60
  return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

async function startExam() {
  sound.tap()
  loading.value = true
  error.value = ''
  try {
    const r: any = await post('/exam/start', { profile_id: profileId.value, count: startCount.value })
    examId.value = r.id
    showStartDialog.value = false
    await loadExam()
  } catch (e: any) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

async function loadExam() {
  if (!examId.value) return
  try {
    exam.value = await get(`/exam/sessions/${examId.value}`)
    remaining.value = exam.value.remaining_seconds || 0
    current.value = 0
  } catch (e: any) {
    error.value = String(e)
  }
}

async function answer(key: string) {
  if (!exam.value || exam.value.status !== 'active') return
  const q = currentQuestion.value
  haptic(10)
  sound.tap()
  q.answered = key
  try {
    await put(`/exam/sessions/${examId.value}/answers/${q.id}`, { answer: key })
  } catch { /* 忽略网络抖动 */ }

  // v9.32: 移动端答题流畅体验——选完自动平滑切换至下一题
  if (current.value < (exam.value.questions?.length || 0) - 1) {
    window.setTimeout(() => {
      current.value++
    }, 240)
  }
}

function go(idx: number) {
  if (idx >= 0 && idx < (exam.value?.questions?.length || 0)) {
    sound.tap()
    current.value = idx
  }
}

async function submit() {
  if (!examId.value || submitting.value) return
  submitting.value = true
  try {
    exam.value = await post(`/exam/sessions/${examId.value}/submit`, {})
    confirmSubmit.value = false
    if (ticker.value) clearInterval(ticker.value)
    const score = exam.value?.score ?? 0
    const maxScore = exam.value?.max_score ?? 1
    const rate = Math.round((score / maxScore) * 100)
    if (rate >= 80) sound.fanfare()
    else if (rate >= 60) sound.correct()
    else sound.wrong()
  } catch (e: any) {
    error.value = String(e)
  } finally {
    submitting.value = false
  }
}

// v49: 键盘优先 (Anki 习惯) — A-D/1-4 作答, ←/→ 翻题; 输入焦点/组合键让路
function handleExamKeydown(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null
  if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return
  if (e.metaKey || e.ctrlKey || e.altKey) return
  if (!exam.value || exam.value.status !== 'active') return
  if (e.key === 'ArrowRight') { go(current.value + 1); e.preventDefault(); return }
  if (e.key === 'ArrowLeft') { go(current.value - 1); e.preventDefault(); return }
  const q = currentQuestion.value
  if (!q || q.answered) return
  // v49b: 按"可见键位章"匹配 (选项即便乱序也与显示一致)
  const pressed = e.key.toLowerCase()
  const opt = q.options?.find((o: any) => String(o.key || o.label || '').toLowerCase() === pressed)
  if (opt) { e.preventDefault(); void answer(opt.key) }
}

onMounted(async () => {
  window.addEventListener('keydown', handleExamKeydown)
  const rid = Number(route.query.id)
  if (rid) {
    examId.value = rid
    await loadExam()
    loading.value = false
    if (exam.value?.status === 'active') {
      ticker.value = setInterval(() => {
        remaining.value = Math.max(0, remaining.value - 1)
        if (remaining.value <= 0 && exam.value?.status === 'active') {
          void submit()
        }
      }, 1000)
    }
  } else {
    loading.value = false
    showStartDialog.value = true
  }
})

onBeforeUnmount(() => {
  if (ticker.value) clearInterval(ticker.value)
  window.removeEventListener('keydown', handleExamKeydown)
})
</script>

<template>
  <div class="exam-page page-exam">
    <!-- 开始设置卡片 (贡院开科) -->
    <div v-if="showStartDialog && !exam" class="exam-start-scholar card">
      <div class="exam-start-header">
        <span class="cinnabar-seal-badge" style="font-size:13px;padding:3px 10px;margin-bottom:10px">
          贡院开考 · 全真模拟
        </span>
        <h2 style="margin:6px 0 8px;font-size:26px">真题模拟考试</h2>
        <p class="muted" style="font-size:13.5px;max-width:380px;margin:0 auto">
          从题库中随机抽取真实语篇真题，限时全真闭卷答题，交卷后即时定级评榜。
        </p>
      </div>

      <div class="exam-picker-section">
        <span class="exam-picker-label">研习考试科目</span>
        <div class="exam-picker-grid">
          <button
            v-for="p in EXAM_PROFILES"
            :key="p.id"
            type="button"
            class="exam-picker-pill"
            :class="{ active: profileId === p.id }"
            @click="sound.tap(); profileId = p.id"
          >
            {{ p.name }}
          </button>
        </div>
      </div>

      <div class="exam-picker-section">
        <span class="exam-picker-label">拟定模考题量</span>
        <div class="exam-picker-grid">
          <button
            v-for="c in QUESTION_COUNTS"
            :key="c.count"
            type="button"
            class="exam-picker-pill"
            :class="{ active: startCount === c.count }"
            @click="sound.tap(); startCount = c.count"
          >
            {{ c.label }}
          </button>
        </div>
      </div>

      <div style="margin-top:28px">
        <button class="button primary" style="width:100%;min-height:46px;font-size:15px" :disabled="loading" @click="startExam">
          <Play :size="16" />开考提笔
        </button>
      </div>
      <p v-if="error" class="warning" style="margin-top:14px">{{ error }}</p>
    </div>

    <!-- 考试中界面 -->
    <template v-else-if="exam && exam.status === 'active'">
      <header class="exam-header">
        <div class="exam-title">
          <span class="paper-meta-pill" style="font-size:11px">全真模考</span>
          <strong>{{ exam.title }}</strong>
          <span>{{ answeredCount }}/{{ exam.total_questions }} 已作答</span>
        </div>
        <div class="exam-timer-scholar" :class="{ urgent: remaining < 300 }">
          <AlarmClock :size="18" /> {{ fmtTime(remaining) }}
        </div>
        <button class="button ghost compact" type="button" @click="sound.tap(); confirmSubmit = true">
          <Flag :size="15" />提前交卷
        </button>
      </header>

      <!-- 答题进度发丝线 -->
      <div class="progress-hairline" role="progressbar" :aria-valuenow="answeredCount" :aria-valuemax="exam.total_questions">
        <i :style="{ width: (exam.total_questions ? (answeredCount / exam.total_questions) * 100 : 0) + '%' }"></i>
      </div>
      <span class="kbd-hint" aria-hidden="true">⌨️ 快捷盲打：A–D 作答 · ← → 快速翻题</span>

      <div v-if="error" class="warning">{{ error }}</div>

      <main class="exam-body" v-if="currentQuestion">
        <div class="exam-question scholar-edition">
          <div class="exam-q-meta">
            <span class="chip">{{ currentQuestion.year || '真题' }} {{ currentQuestion.paper_title || '' }}</span>
            <span class="chip">{{ currentQuestion.score }} 分</span>
          </div>
          <h3 class="exam-stem">
            第 {{ current + 1 }} 题<template v-if="currentQuestion.stem"> · {{ currentQuestion.stem }}</template>
          </h3>
          <!-- 文章上下文 -->
          <div v-if="currentQuestion.passage" class="exam-passage passage">{{ currentQuestion.passage }}</div>
          <div class="exam-options">
            <button
              v-for="opt in currentQuestion.options"
              :key="opt.key"
              class="exam-option scholar-edition"
              :class="{ selected: currentQuestion.answered === opt.key }"
              @click="answer(opt.key)"
            >
              <span class="opt-key">{{ opt.key }}</span>
              <span class="opt-content">{{ opt.content }}</span>
            </button>
          </div>
        </div>

        <div class="exam-nav">
          <button class="button ghost" :disabled="current === 0" @click="go(current - 1)">
            <ChevronLeft :size="16" />上一题
          </button>
          <div class="exam-dots">
            <button
              v-for="(q, i) in exam.questions"
              :key="q.id"
              class="exam-dot scholar-edition"
              :class="{ answered: q.answered, current: i === current }"
              @click="go(i)"
            >
              {{ i + 1 }}
            </button>
          </div>
          <button class="button ghost" :disabled="current >= exam.questions.length - 1" @click="go(current + 1)">
            下一题<ChevronRight :size="16" />
          </button>
        </div>
      </main>

      <!-- 交卷确认抽屉/弹层 -->
      <div v-if="confirmSubmit" class="exam-overlay" @click.self="confirmSubmit = false">
        <div class="exam-confirm card" style="border-radius:18px;padding:32px 28px">
          <h3 style="margin-top:0">确认交卷并揭榜？</h3>
          <p class="muted" style="margin:10px 0 20px">
            已作答 {{ answeredCount }} / {{ exam.total_questions }} 题
            <template v-if="exam.total_questions - answeredCount > 0">
              ，尚有 <b style="color:var(--accent-vermilion)">{{ exam.total_questions - answeredCount }}</b> 题未填涂
            </template>
          </p>
          <div class="exam-confirm-actions">
            <button class="button ghost" type="button" @click="sound.tap(); confirmSubmit = false">继续作答</button>
            <button class="button primary" type="button" :disabled="submitting" @click="sound.tap(); submit()">
              {{ submitting ? '阅卷中…' : '确认交卷' }}
            </button>
          </div>
        </div>
      </div>
    </template>

    <!-- 成绩揭榜页：金榜题名殿 -->
    <template v-else-if="exam">
      <div class="exam-result-hall">
        <div class="exam-seal-banner">
          <span class="cinnabar-seal-badge" style="font-size:13px;padding:3px 12px">
            {{ examSealInfo.text }}
          </span>
        </div>
        <div class="result-score">
          <div class="exam-score-big" :class="exam.accuracy >= 60 ? 'good' : 'warn'">
            {{ exam.accuracy }}<small style="font-size:24px">%</small>
          </div>
          <div class="score-label" style="font-size:13.5px;color:var(--muted);margin-top:4px">全卷综合正确率</div>
        </div>

        <div class="exam-result-grid-scholar">
          <div class="exam-cell-scholar">
            <span class="exam-cell-val" style="color:var(--primary)">{{ exam.correct_count }}</span>
            <span class="exam-cell-label"><CheckCircle2 :size="14" style="color:var(--primary)" /> 答对</span>
          </div>
          <div class="exam-cell-scholar">
            <span class="exam-cell-val" style="color:var(--accent-vermilion)">{{ exam.wrong_count }}</span>
            <span class="exam-cell-label"><XCircle :size="14" style="color:var(--accent-vermilion)" /> 答错</span>
          </div>
          <div class="exam-cell-scholar">
            <span class="exam-cell-val" style="color:var(--muted)">{{ exam.unanswered_count }}</span>
            <span class="exam-cell-label">未答</span>
          </div>
          <div class="exam-cell-scholar">
            <span class="exam-cell-val">{{ exam.used_minutes || 0 }}<small style="font-size:12px">分</small></span>
            <span class="exam-cell-label"><Clock :size="14" /> 用时</span>
          </div>
          <div class="exam-cell-scholar">
            <span class="exam-cell-val" style="color:var(--primary);font-size:16px">{{ exam.level || '合格' }}</span>
            <span class="exam-cell-label"><Award :size="14" /> 等第</span>
          </div>
          <div class="exam-cell-scholar">
            <span class="exam-cell-val">{{ exam.score }}<small style="font-size:12px">/{{ exam.max_score }}</small></span>
            <span class="exam-cell-label">卷面实得</span>
          </div>
        </div>

        <div class="result-actions" style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
          <button class="button primary" type="button" @click="sound.tap(); showStartDialog = true; exam = null">
            <RotateCcw :size="15" />再来一场
          </button>
          <button v-if="exam.wrong_count > 0" class="button" type="button" @click="sound.tap(); router.push('/wrong')">
            <BookMarked :size="15" />错题手札
          </button>
          <button class="button ghost" type="button" @click="sound.tap(); router.push('/')">
            返回案头
          </button>
        </div>
      </div>
    </template>

    <div v-else-if="loading" class="exam-loading" style="padding:80px 20px;text-align:center">
      <div style="font-size:14px;color:var(--muted)">正在准备全真试卷…</div>
    </div>
  </div>
</template>
