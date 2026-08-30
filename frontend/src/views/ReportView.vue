<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { get } from '../api'
import CountUp from '../components/CountUp.vue'

const report = ref<any>(null)
const loading = ref(true)
const error = ref('')
const heatmap = ref<any>(null)

onMounted(async () => {
  try {
    report.value = await get('/report')
  } catch (e) { error.value = String(e) }
  loading.value = false
  // v2.35: 学习热力图 (GitHub 风格)
  try {
    heatmap.value = await get('/report/heatmap')
  } catch { heatmap.value = null }
})

// v2.35: 热力图按周分组 (7 行 × 16 列, GitHub 风格)
const heatmapWeeks = (): any[][] => {
  if (!heatmap.value?.cells) return []
  const cells = heatmap.value.cells
  const weeks: any[][] = []
  for (let w = 0; w < cells.length / 7; w++) {
    const col: any[] = []
    for (let d = 0; d < 7; d++) {
      const c = cells[w * 7 + d]
      if (c) col.push(c)
    }
    weeks.push(col)
  }
  return weeks
}

function heatClass(level: number) {
  return `heat-l${Math.min(4, level)}`
}

// v2.38: 词汇掌握进度 (环)
const vocabPct = computed(() => {
  const total = report.value?.vocab?.total || 0
  const learned = report.value?.vocab?.learned || 0
  return total ? Math.round((learned / total) * 100) : 0
})

// v2.38: 练习量趋势最大值 (归一化柱高)
const answeredTrendMax = computed(() => {
  const arr = report.value?.answered_trend || []
  return Math.max(...arr.map((t: any) => t.count || 0), 1)
})

function rateClass(rate: number) {
  if (rate >= 80) return 'rate-good'
  if (rate >= 60) return 'rate-mid'
  return 'rate-bad'
}

function radarPoints(): string {
  const stats = report.value?.by_type || []
  if (!stats.length) return ''
  const cx = 60, cy = 60, r = 48
  const n = stats.length
  return stats.map((s: any, i: number) => {
    const ang = -Math.PI / 2 + (2 * Math.PI * i) / n
    const len = Math.min(1, (s.rate || 0) / 100) * r
    return `${cx + len * Math.cos(ang)},${cy + len * Math.sin(ang)}`
  }).join(' ')
}
// v3.3: 记忆曲线折线点（墨墨式）
const memoryCurvePoints = computed(() => {
  const t = report.value?.vocabulary_trend || []
  return t.map((p: any, i: number) => `${12 + i * 24},${108 - (p.rate / 100) * 96}`).join(' ')
})
</script>

<template>
  <div class="page page-report">
    <div class="page-head">
      <div><span class="eyebrow">研习学情报告</span><h1>学习报告</h1><p class="lead">数据可视化复盘：正确率趋势、薄弱题型、词汇进度与智能建议。</p></div>
    </div>

    <div v-if="loading" class="card empty">报告生成中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="report">
      <!-- 顶部统计卡 -->
      <div class="report-hero grid grid-4">
        <div class="card stat-card">
          <span class="stat-label">练习场次</span>
          <div class="stat-value"><CountUp :value="report.practice.sessions" /></div>
          <small class="stat-sub">{{ report.practice.submitted }} 场已完成</small>
        </div>
        <div class="card stat-card">
          <span class="stat-label">错题总数</span>
          <div class="stat-value"><CountUp :value="report.wrong.total" /></div>
          <small class="stat-sub">{{ report.wrong.repeat }} 道高频重复错</small>
        </div>
        <div class="card stat-card vocab-ring-card">
          <span class="stat-label">词汇掌握</span>
          <!-- v2.38: 进度环 (数据可视化 UI 趋势) -->
          <div class="vocab-ring" :style="{ '--pct': vocabPct + '%' }">
            <svg viewBox="0 0 44 44" class="vocab-ring-svg">
              <circle class="vocab-ring-track" cx="22" cy="22" r="18" />
              <circle class="vocab-ring-bar" cx="22" cy="22" r="18" />
            </svg>
            <div class="vocab-ring-text"><b>{{ vocabPct }}</b><span>%</span></div>
          </div>
          <small class="stat-sub">已学 {{ report.vocab.learned }} / 掌握 {{ report.vocab.mastered }}</small>
        </div>
        <div class="card stat-card">
          <span class="stat-label">近7天活跃</span>
          <div class="stat-value"><CountUp :value="report.activity.active_days" /><span class="stat-unit">天</span></div>
          <small class="stat-sub">{{ report.activity.activities }} 次学习活动</small>
        </div>
      </div>

      <!-- 级别汇总 (全部类别) -->
      <div v-if="report.by_profile?.length" class="report-panel card">
        <h3>🗂️ 全部级别汇总</h3>
        <div class="profile-grid">
          <div v-for="p in report.by_profile" :key="p.profile_id" class="profile-card" :class="{ 'profile-active': p.profile_id === report.active_profile?.id }">
            <div class="profile-head">
              <strong>{{ p.name }}</strong>
              <span v-if="p.profile_id === report.active_profile?.id" class="profile-tag">当前</span>
            </div>
            <div class="profile-stats">
              <div><b>{{ p.sessions }}</b><small>场次</small></div>
              <div><b>{{ p.answered }}</b><small>答题</small></div>
              <div><b :class="rateClass(p.rate)">{{ p.rate }}%</b><small>正确率</small></div>
              <div><b>{{ p.wrong }}</b><small>错题</small></div>
            </div>
          </div>
        </div>
      </div>

      <!-- v2.35: 学习热力图 (GitHub 风格打卡) -->
      <div v-if="heatmap?.cells?.length" class="card report-panel heatmap-panel">
        <h3>🔥 学习热力图（近 16 周）</h3>
        <p class="lead" style="font-size:12px;color:var(--muted);margin-bottom:12px">颜色越深，当天学习越投入 · 共 {{ heatmap.total }} 次活动</p>
        <div class="heatmap-grid">
          <div v-for="(week, wi) in heatmapWeeks()" :key="wi" class="heatmap-week">
            <div v-for="cell in week" :key="cell.date" class="heat-cell" :class="heatClass(cell.level)"
              :title="`${cell.date} · ${cell.count} 次活动`"></div>
          </div>
        </div>
        <div class="heatmap-legend">
          <span>少</span>
          <i class="heat-cell heat-l0"></i>
          <i class="heat-cell heat-l1"></i>
          <i class="heat-cell heat-l2"></i>
          <i class="heat-cell heat-l3"></i>
          <i class="heat-cell heat-l4"></i>
          <span>多</span>
        </div>
      </div>

      <div class="grid grid-2 report-main">
        <!-- 正确率趋势 -->
        <div class="card report-panel">
          <h3>📈 正确率趋势（近30天 · 全级别）</h3>
          <div v-if="report.trend.length" class="trend-chart">
            <div v-for="(t, i) in report.trend" :key="i" class="trend-bar-wrap">
              <div class="trend-bar" :class="rateClass(t.rate)" :style="{ height: Math.max(6, t.rate) + '%' }" :title="`${t.day} 正确率 ${t.rate}% (${t.total}题)`"></div>
              <span class="trend-day">{{ t.day.slice(3) }}</span>
            </div>
          </div>
          <div v-else class="muted">暂无练习数据，去刷一题吧</div>
        </div>

        <!-- v3.3: 词汇记忆曲线（墨墨式——近30天复习认识率） -->
        <div class="card report-panel">
          <h3>🧠 词汇记忆曲线（近30天）</h3>
          <div v-if="report?.vocabulary_trend?.length" class="memory-curve">
            <svg :viewBox="`0 0 ${Math.max(280, report.vocabulary_trend.length * 24)} 120`" preserveAspectRatio="none" class="memory-curve-svg">
              <polyline :points="memoryCurvePoints" fill="none" stroke="#486d5c" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
              <circle v-for="(p, i) in report.vocabulary_trend" :key="i" :cx="12 + i * 24" :cy="108 - (p.rate / 100) * 96" r="3" fill="#a4342a" :title="`${p.date} 认识率 ${p.rate}% (${p.total}次)`" />
            </svg>
            <div class="memory-curve-legend"><span class="dot"></span>认识率（认识/模糊记作认识，忘记不计）</div>
          </div>
          <div v-else class="muted">开始复习单词后，这里会生成你的记忆曲线</div>
        </div>

        <!-- v2.41: 本周战报 (墨墨式数据亮点: 本周 vs 上周) -->
        <div class="card report-panel week-report-card">
          <h3>📈 本周战报</h3>
          <div v-if="report?.week_compare" class="week-report-grid">
            <div class="week-report-item">
              <span class="wr-label">本周答题</span>
              <b class="wr-value">{{ report.week_compare.this.answered }}</b>
              <span class="wr-delta" :class="report.week_compare.answered_delta >= 0 ? 'up' : 'down'">
                {{ report.week_compare.answered_delta >= 0 ? '↑' : '↓' }} {{ Math.abs(report.week_compare.answered_delta) }}
              </span>
              <small>上周 {{ report.week_compare.last.answered }}</small>
            </div>
            <div class="week-report-item">
              <span class="wr-label">正确率</span>
              <b class="wr-value">{{ report.week_compare.this.rate }}%</b>
              <span class="wr-delta" :class="report.week_compare.rate_delta >= 0 ? 'up' : 'down'">
                {{ report.week_compare.rate_delta >= 0 ? '↑' : '↓' }} {{ Math.abs(report.week_compare.rate_delta) }}%
              </span>
              <small>上周 {{ report.week_compare.last.rate }}%</small>
            </div>
            <div class="week-report-item">
              <span class="wr-label">本周新词</span>
              <b class="wr-value">{{ report.week_compare.this.vocab }}</b>
              <span class="wr-delta" :class="report.week_compare.vocab_delta >= 0 ? 'up' : 'down'">
                {{ report.week_compare.vocab_delta >= 0 ? '↑' : '↓' }} {{ Math.abs(report.week_compare.vocab_delta) }}
              </span>
              <small>上周 {{ report.week_compare.last.vocab }}</small>
            </div>
            <div class="week-report-item">
              <span class="wr-label">累计正确率</span>
              <b class="wr-value">{{ report.total_rate }}%</b>
              <small>全周期 {{ report.total_answered }} 题</small>
            </div>
          </div>
        </div>

        <!-- v2.38: 练习量趋势 (近14天) -->
        <div class="card report-panel">
          <h3>📊 练习量趋势（近14天）</h3>
          <div v-if="answeredTrendMax" class="answered-trend">
            <div v-for="(t, i) in report.answered_trend" :key="i" class="answered-bar-wrap" :title="`${t.day} 答题 ${t.count} 题`">
              <div class="answered-bar" :style="{ height: Math.max(4, (t.count / answeredTrendMax) * 100) + '%' }"></div>
              <span class="trend-day">{{ t.day.slice(3) }}</span>
            </div>
          </div>
          <div v-else class="muted">近14天暂无答题记录</div>
        </div>

        <!-- 题型能力雷达 -->
        <div class="card report-panel">
          <h3>🎯 题型能力（全级别汇总）</h3>
          <div v-if="report.by_type.length" class="radar-wrap">
            <svg viewBox="0 0 120 120" class="radar">
              <polygon points="60,12 108,60 60,108 12,60" fill="none" stroke="var(--line)" stroke-width="0.5" />
              <polygon points="60,36 96,60 60,84 24,60" fill="none" stroke="var(--line)" stroke-width="0.5" />
              <polygon :points="radarPoints()" fill="color-mix(in srgb, var(--accent) 25%, transparent)" stroke="var(--accent)" stroke-width="1" />
            </svg>
            <div class="radar-legend">
              <div v-for="s in report.by_type" :key="s.type" class="radar-item">
                <span class="radar-dot" :class="rateClass(s.rate)"></span>
                <span>{{ s.label }}</span>
                <b>{{ s.rate }}%</b>
              </div>
            </div>
          </div>
          <div v-else class="muted">暂无题型数据</div>
        </div>
      </div>

      <!-- 智能建议 -->
      <div v-if="report.suggestions?.length" class="card report-panel">
        <h3>💡 智能建议</h3>
        <ul class="suggest-list">
          <li v-for="(s, i) in report.suggestions" :key="i">{{ s }}</li>
        </ul>
      </div>
    </div>
  </div>
</template>
