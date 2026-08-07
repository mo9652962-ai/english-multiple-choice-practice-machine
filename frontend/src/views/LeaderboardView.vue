<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../api'

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await get('/leaderboard')
  } catch (e) { error.value = String(e) }
  loading.value = false
})

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']
function weekdayLabel(day: string) {
  const d = new Date(day)
  return '周' + WEEKDAYS[d.getDay() === 0 ? 6 : d.getDay() - 1]
}
function maxCount(): number {
  return Math.max(...(data.value?.days || []).map((d: any) => d.count || 0), 1)
}
</script>

<template>
  <div class="page page-leaderboard">
    <div class="page-head">
      <div>
        <span class="eyebrow">LEADERBOARD</span>
        <h1>学习排行</h1>
        <p class="lead">本周学习战报 · 与自己赛跑，每天进步一点点（多邻国式激励）</p>
      </div>
      <div v-if="data?.level" class="rank-level" :style="{ color: data.level.color }">
        <span class="rank-icon">{{ data.level.icon }}</span>
        <b>{{ data.level.name }}</b>
      </div>
    </div>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="data">
      <!-- 本周核心指标 -->
      <div class="grid grid-4 rank-stats">
        <div class="card stat-card ink-dot">
          <span class="stat-label">本周答题</span>
          <div class="stat-value"><b class="rank-num">{{ data.answered }}</b></div>
          <small class="stat-sub">累计 {{ data.total_answered }} 题</small>
        </div>
        <div class="card stat-card ink-dot">
          <span class="stat-label">本周正确率</span>
          <div class="stat-value"><b class="rank-num">{{ data.rate }}%</b></div>
          <small class="stat-sub">答对 {{ data.correct }} 题</small>
        </div>
        <div class="card stat-card ink-dot">
          <span class="stat-label">本周场次</span>
          <div class="stat-value"><b class="rank-num">{{ data.sessions }}</b></div>
          <small class="stat-sub">练习场次</small>
        </div>
        <div class="card stat-card ink-dot">
          <span class="stat-label">连续打卡</span>
          <div class="stat-value"><b class="rank-num">{{ data.streak }}</b><span class="stat-unit">天</span></div>
          <small class="stat-sub">新学词 {{ data.vocab_new }} 个</small>
        </div>
      </div>

      <!-- 本周每日答题柱状 -->
      <div class="card report-panel">
        <h3>📊 本周每日答题</h3>
        <div class="answered-trend">
          <div v-for="(t, i) in data.days" :key="i" class="answered-bar-wrap" :title="`${t.day} 答题 ${t.count} 题`">
            <div class="answered-bar" :style="{ height: Math.max(4, (t.count / maxCount()) * 100) + '%' }"></div>
            <span class="trend-day">{{ weekdayLabel(t.day) }}</span>
          </div>
        </div>
      </div>

      <!-- 段位说明 -->
      <div class="card report-panel">
        <h3>🏅 段位规则</h3>
        <div class="rank-rules">
          <span class="rank-rule"><i>💎</i> 钻石 · 本周 300+ 题</span>
          <span class="rank-rule"><i>🥇</i> 黄金 · 本周 150+ 题</span>
          <span class="rank-rule"><i>🥈</i> 白银 · 本周 60+ 题</span>
          <span class="rank-rule"><i>🥉</i> 青铜 · 本周有练习</span>
          <span class="rank-rule"><i>🌱</i> 未开始</span>
        </div>
      </div>
    </div>
  </div>
</template>
