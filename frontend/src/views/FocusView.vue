<script setup lang="ts">
// v2.49: 专注计时 (番茄钟, 借鉴专注清单/Forest)
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

const MODES = [
  { key: 'focus', label: '专注', minutes: 25, color: '#c97b4a' },
  { key: 'short', label: '短休', minutes: 5, color: '#5c7a52' },
  { key: 'long', label: '长休', minutes: 15, color: '#4a6fa5' },
]
const mode = ref('focus')
const running = ref(false)
const remainSec = ref(25 * 60)
const totalSec = ref(25 * 60)
const todayPomodoros = ref(0)
const todayFocusMin = ref(0)
let timer: number | null = null

const remainText = computed(() => {
  const m = Math.floor(remainSec.value / 60)
  const s = remainSec.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})
const progress = computed(() => {
  if (!totalSec.value) return 0
  return Math.round(((totalSec.value - remainSec.value) / totalSec.value) * 100)
})
const currentMode = computed(() => MODES.find((m) => m.key === mode.value) || MODES[0])

function loadStats() {
  const today = new Date().toISOString().slice(0, 10)
  const raw = localStorage.getItem('epm_focus_stats') || '{}'
  const stats = JSON.parse(raw)
  todayPomodoros.value = stats[today]?.pomodoros || 0
  todayFocusMin.value = stats[today]?.minutes || 0
}
function switchMode(key: string) {
  mode.value = key
  running.value = false
  const m = MODES.find((x) => x.key === key) || MODES[0]
  remainSec.value = m.minutes * 60
  totalSec.value = m.minutes * 60
}
function toggle() {
  if (running.value) { running.value = false; return }
  running.value = true
}
function reset() {
  running.value = false
  const m = MODES.find((x) => x.key === mode.value) || MODES[0]
  remainSec.value = m.minutes * 60
  totalSec.value = m.minutes * 60
}
function recordDone() {
  const today = new Date().toISOString().slice(0, 10)
  const raw = localStorage.getItem('epm_focus_stats') || '{}'
  const stats = JSON.parse(raw)
  const day = stats[today] || { pomodoros: 0, minutes: 0 }
  day.pomodoros += 1
  day.minutes += totalSec.value / 60
  stats[today] = day
  localStorage.setItem('epm_focus_stats', JSON.stringify(stats))
  loadStats()
}
onMounted(() => {
  loadStats()
  timer = window.setInterval(() => {
    if (!running.value) return
    remainSec.value -= 1
    if (remainSec.value <= 0) {
      running.value = false
      recordDone()
      // 自动进入休息
      const next = mode.value === 'focus' ? 'short' : 'focus'
      switchMode(next)
    }
  }, 1000)
})
onBeforeUnmount(() => { if (timer !== null) window.clearInterval(timer) })
</script>

<template>
  <div class="page page-focus">
    <div class="page-head">
      <div>
        <span class="eyebrow">FOCUS</span>
        <h1>专注计时</h1>
        <p class="lead">番茄工作法 · 25 分钟专注，5 分钟休息，让学习进入心流。</p>
      </div>
      <div class="focus-today">
        <span class="focus-today-item">🍅 今日 {{ todayPomodoros }} 个番茄</span>
        <span class="focus-today-item">⏱ {{ Math.round(todayFocusMin) }} 分钟</span>
      </div>
    </div>

    <div class="card focus-card">
      <!-- 模式切换 -->
      <div class="focus-modes">
        <button
          v-for="m in MODES" :key="m.key"
          class="focus-mode" :class="{ active: mode === m.key }"
          :style="mode === m.key ? { borderColor: m.color, color: m.color } : {}"
          type="button" @click="switchMode(m.key)"
        >{{ m.label }} {{ m.minutes }}′</button>
      </div>

      <!-- 环形计时 -->
      <div class="focus-ring" :style="{ '--pct': progress, '--color': currentMode.color }">
        <svg class="focus-ring-svg" viewBox="0 0 120 120">
          <circle class="ring-bg" cx="60" cy="60" r="52"></circle>
          <circle class="ring-fg" cx="60" cy="60" r="52"></circle>
        </svg>
        <div class="focus-time">{{ remainText }}</div>
        <div class="focus-mode-label">{{ currentMode.label }}</div>
      </div>

      <!-- 控制 -->
      <div class="focus-controls">
        <button class="button" :class="running ? 'secondary' : ''" @click="toggle">
          {{ running ? '暂停' : '开始' }}
        </button>
        <button class="button ghost" @click="reset">重置</button>
      </div>
      <p class="focus-tip">专注时保持安静，完成后自动进入休息 🍃</p>
    </div>

    <div class="card report-panel">
      <h3>📊 今日专注</h3>
      <div class="grid grid-2">
        <div class="stat-card ink-dot"><span class="stat-label">完成番茄</span><div class="stat-value"><b class="rank-num">{{ todayPomodoros }}</b></div><small class="stat-sub">个 25 分钟专注块</small></div>
        <div class="stat-card ink-dot"><span class="stat-label">专注时长</span><div class="stat-value"><b class="rank-num">{{ Math.round(todayFocusMin) }}</b><span class="stat-unit">分</span></div><small class="stat-sub">今日累计专注</small></div>
      </div>
    </div>
  </div>
</template>
