<script setup lang="ts">
// 模拟考试模式 — 全屏限时作答 + 即时评分
import { AlarmClock, CheckCircle2, ChevronLeft, ChevronRight, Clock, Flag, XCircle } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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

const currentQuestion = computed(() => exam.value?.questions?.[current.value] || null)
const answeredCount = computed(() => (exam.value?.questions || []).filter((q: any) => q.answered).length)

function fmtTime(s: number) {
  const m = Math.floor(s / 60)
  const ss = s % 60
  return `${String(m).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

async function startExam() {
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
  q.answered = key
  try {
    await put(`/exam/sessions/${examId.value}/answers/${q.id}`, { answer: key })
  } catch { /* 忽略网络抖动 */ }
}

function go(idx: number) {
  if (idx >= 0 && idx < (exam.value?.questions?.length || 0)) current.value = idx
}

async function submit() {
  if (!examId.value || submitting.value) return
  submitting.value = true
  try {
    exam.value = await post(`/exam/sessions/${examId.value}/submit`, {})
    confirmSubmit.value = false
    if (ticker.value) clearInterval(ticker.value)
  } catch (e: any) {
    error.value = String(e)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
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

onBeforeUnmount(() => { if (ticker.value) clearInterval(ticker.value) })
</script>

<template>
  <div class="exam-page page-exam">
    <!-- 开始设置 -->
    <div v-if="showStartDialog && !exam" class="exam-start card">
      <h2><span class="hero-seal exam-seal" aria-hidden="true">榜</span>模拟考试</h2>
      <p class="muted">从当前题库随机抽题，全真限时作答，交卷即时评分</p>
      <label>
        <span>考试类别</span>
        <select v-model.number="profileId">
          <option :value="1">考研英语一</option>
          <option :value="2">高中英语</option>
          <option :value="3">大学英语四级</option>
          <option :value="4">大学英语六级</option>
          <option :value="5">考研英语二</option>
        </select>
      </label>
      <label>
        <span>题目数量</span>
        <select v-model.number="startCount">
          <option :value="10">10 题（快速自测）</option>
          <option :value="20">20 题（标准模拟）</option>
          <option :value="40">40 题（强化模拟）</option>
        </select>
      </label>
      <button class="button" :disabled="loading" @click="startExam">开始考试</button>
      <p v-if="error" class="warning">{{ error }}</p>
    </div>

    <!-- 考试中 -->
    <template v-else-if="exam && exam.status === 'active'">
      <header class="exam-header">
        <div class="exam-title">
          <strong>{{ exam.title }}</strong>
          <span>{{ answeredCount }}/{{ exam.total_questions }} 已答</span>
        </div>
        <div class="exam-timer" :class="{ urgent: remaining < 300 }">
          <AlarmClock :size="18" /> {{ fmtTime(remaining) }}
        </div>
        <button class="button ghost compact" @click="confirmSubmit = true"><Flag :size="15" />交卷</button>
      </header>

      <div v-if="error" class="warning">{{ error }}</div>

      <main class="exam-body" v-if="currentQuestion">
        <div class="exam-question">
          <div class="exam-q-meta">
            <span class="chip">{{ currentQuestion.year || '' }} {{ currentQuestion.paper_title || '' }}</span>
            <span class="chip">{{ currentQuestion.score }} 分</span>
          </div>
          <h3 class="exam-stem">第 {{ current + 1 }} 题 · {{ currentQuestion.stem }}</h3>
          <!-- v3.3: 文章上下文（选词填空/阅读题——否则只有指令无法作答） -->
          <div v-if="currentQuestion.passage" class="exam-passage">{{ currentQuestion.passage }}</div>
          <div class="exam-options">
            <button
              v-for="opt in currentQuestion.options"
              :key="opt.key"
              class="exam-option"
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
              class="exam-dot"
              :class="{ answered: q.answered, current: i === current }"
              @click="go(i)"
            >{{ i + 1 }}</button>
          </div>
          <button class="button ghost" :disabled="current >= exam.questions.length - 1" @click="go(current + 1)">
            下一题<ChevronRight :size="16" />
          </button>
        </div>
      </main>

      <!-- 交卷确认 -->
      <div v-if="confirmSubmit" class="exam-overlay">
        <div class="exam-confirm card">
          <h3>确认交卷？</h3>
          <p>已答 {{ answeredCount }}/{{ exam.total_questions }}，未答 {{ exam.total_questions - answeredCount }} 题</p>
          <div class="exam-confirm-actions">
            <button class="button ghost" @click="confirmSubmit = false">继续作答</button>
            <button class="button danger" :disabled="submitting" @click="submit">确认交卷</button>
          </div>
        </div>
      </div>
    </template>

    <!-- 成绩页 -->
    <template v-else-if="exam">
      <div class="exam-result card">
        <div class="result-score">
          <div class="big-score" :class="exam.accuracy >= 60 ? 'good' : 'warn'">{{ exam.accuracy }}<small>%</small></div>
          <div class="score-label">正确率</div>
        </div>
        <div class="result-grid">
          <div class="result-cell"><CheckCircle2 :size="20" class="ok" /><span>{{ exam.correct_count }} 答对</span></div>
          <div class="result-cell"><XCircle :size="20" class="bad" /><span>{{ exam.wrong_count }} 答错</span></div>
          <div class="result-cell"><span class="muted">{{ exam.unanswered_count }} 未答</span></div>
          <div class="result-cell"><span class="muted">{{ exam.score }} / {{ exam.max_score }} 分</span></div>
          <!-- v2.44: 等级评价 + 答题用时 (粉笔式考试报告) -->
          <div class="result-cell"><span class="exam-level" :class="'level-' + (exam.level === '优秀' ? 'ex' : exam.level === '良好' ? 'good' : exam.level === '合格' ? 'ok' : 'warn')">{{ exam.level }}</span></div>
          <div class="result-cell"><Clock :size="20" class="ok" /><span>用时 {{ exam.used_minutes || 0 }} 分<small v-if="exam.duration_minutes">/ {{ exam.duration_minutes }} 分</small></span></div>
        </div>
        <div class="result-actions">
          <button class="button" @click="showStartDialog = true">再来一场</button>
          <button class="button ghost" @click="router.push('/')">返回首页</button>
        </div>
      </div>
    </template>

    <div v-else-if="loading" class="exam-loading">加载中…</div>
  </div>
</template>
