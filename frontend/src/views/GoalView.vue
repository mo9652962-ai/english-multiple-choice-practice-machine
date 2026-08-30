<script setup lang="ts">
// v2.49: 目标中心 (独立目标页 — 每日答题目标 + 达成历史)
import { computed, onMounted, ref } from 'vue'
import { get } from '../api'
import { showToast } from '../services/toast'

const dailyGoal = ref(Number(localStorage.getItem('epm_daily_goal') || 50))
const todayAnswered = ref(0)
const todayRate = ref(0)
const weekAnswered = ref(0)
const history = ref<{ day: string; count: number; done: boolean }[]>([])

const goalPct = computed(() => {
  if (!dailyGoal.value) return 0
  return Math.min(100, Math.round((todayAnswered.value / dailyGoal.value) * 100))
})
const goalDone = computed(() => dailyGoal.value > 0 && todayAnswered.value >= dailyGoal.value)

function saveGoal() {
  localStorage.setItem('epm_daily_goal', String(dailyGoal.value))
  showToast(`每日目标设为 ${dailyGoal.value || '未设定'} 题`, 'success')
}
function quickGoal(n: number) { dailyGoal.value = n; saveGoal() }

function loadHistory() {
  const days = [...Array(14)].map((_, i) => {
    const d = new Date()
    d.setDate(d.getDate() - (13 - i))
    return d.toISOString().slice(0, 10)
  })
  // 从今日答题的 leaderboard 拉近 7 天, 其余置 0 (localStorage 不存历史, 简化)
  history.value = days.map((day) => ({ day, count: 0, done: false }))
}

onMounted(async () => {
  loadHistory()
  try {
    const lb: any = await get('/leaderboard')
    const days = lb.days || []
    todayAnswered.value = days.length ? days[days.length - 1].count : 0
    todayRate.value = lb.rate || 0
    weekAnswered.value = lb.answered || 0
    // 近 7 天柱
    const start = history.value.length - 7
    days.forEach((d: any, i: number) => {
      const idx = start + i
      if (idx >= 0 && idx < history.value.length) {
        history.value[idx].count = d.count
        history.value[idx].done = dailyGoal.value > 0 && d.count >= dailyGoal.value
      }
    })
  } catch { /* 忽略 */ }
})
</script>

<template>
  <div class="page page-goal">
    <div class="page-head">
      <div>
        <span class="eyebrow">学业目标</span>
        <h1>目标中心</h1>
        <p class="lead">设定每日目标，让进步看得见。</p>
      </div>
    </div>

    <!-- 目标进度环 -->
    <div class="card goal-hero">
      <div class="goal-ring" :style="{ '--pct': goalPct }">
        <svg class="vocab-ring-svg" viewBox="0 0 120 120">
          <circle class="ring-bg" cx="60" cy="60" r="52"></circle>
          <circle class="ring-fg" cx="60" cy="60" r="52"></circle>
        </svg>
        <div class="goal-ring-text">
          <b class="rank-num">{{ goalPct }}%</b>
          <span>{{ goalDone ? '🎉 今日达标' : '今日目标' }}</span>
        </div>
      </div>
      <div class="goal-info">
        <h3>今日进度 {{ todayAnswered }} / {{ dailyGoal }} 题</h3>
        <p class="goal-rate">本周已答 {{ weekAnswered }} 题 · 正确率 {{ todayRate }}%</p>
        <div class="goal-actions">
          <button class="button ghost compact" @click="quickGoal(20)">20题</button>
          <button class="button ghost compact" @click="quickGoal(50)">50题</button>
          <button class="button ghost compact" @click="quickGoal(100)">100题</button>
          <button class="button compact" @click="dailyGoal = 0; saveGoal()">重置</button>
        </div>
        <div class="goal-set">
          <input v-model.number="dailyGoal" type="number" min="0" max="500" placeholder="自定义目标" />
          <button class="button compact" @click="saveGoal">设定</button>
        </div>
      </div>
    </div>

    <!-- 近 14 天达成历史 -->
    <div class="card report-panel">
      <h3>📆 近 14 天达成</h3>
      <div class="goal-history">
        <div v-for="(h, i) in history" :key="i" class="goal-day" :class="{ done: h.done }" :title="`${h.day} · ${h.count} 题${h.done ? ' ✅' : ''}`">
          <span class="goal-day-bar" :style="{ height: Math.max(4, Math.min(100, (h.count / Math.max(dailyGoal, 1)) * 100)) + '%' }"></span>
          <span class="goal-day-label">{{ h.day.slice(5).replace('-', '/') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>
