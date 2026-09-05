<script setup lang="ts">
// 错题知识点归因分析面板（v3.1 移动端增强版）
// 四个视图：归因总览（环形图）/ 知识点（条形榜）/ 学习建议（方案卡）/ 趋势追踪（折线+雷达）
// 数据源：POST /api/wrong/analysis/run + GET trend / knowledge-points / history / report/{id}
//
// 移动端（≤860px）专项增强：
// - 面板以「底部抽屉」呈现：拖拽把手下滑关闭、点遮罩/×/ESC 关闭、打开时锁定背景滚动
// - 标签页支持左右滑动手势切换（纵向滚动干扰已排除）
// - 学习建议卡折叠（默认只展开第一张，点标题展开/收起）
// - 历史记录改为横向滚动 chips 轨道（触控友好，替代下拉框）
// - 趋势追踪分类数改为分段控件（segmented control）
// - 一键分享诊断摘要（navigator.share → 剪贴板降级）
// - 分析中骨架屏 + 完成触觉反馈（navigator.vibrate，Android WebView 支持）
// - 图表 fluid 流式缩放（DonutChart / RadarChart / TrendLineChart viewBox 等比）

import {
  BarChart3,
  Brain,
  ChevronDown,
  History,
  Lightbulb,
  LineChart,
  Radar,
  Share2,
  Sparkles,
  Puzzle,
  Zap,
} from 'lucide-vue-next'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { get, post } from '../api'
import { showToast } from '../services/toast'
import DonutChart from './charts/DonutChart.vue'
import RadarChart from './charts/RadarChart.vue'
import TrendLineChart from './charts/TrendLineChart.vue'

type Category = {
  code: string
  label: string
  count: number
  percentage: number
  average_confidence: number
}

type KnowledgePoint = {
  code: string
  label: string
  cause_code: string
  cause_label: string
  hit_count?: number
  total_hits?: number
  percentage?: number
  report_count?: number
  guidance: string
  last_seen_at?: string
}

type Suggestion = {
  cause_code: string
  label: string
  question_count: number
  percentage: number
  average_confidence: number
  priority_score: number
  immediate_actions: string[]
  knowledge_points: { code: string; label: string; hit_count: number; guidance: string }[]
  weekly_plan: { days: string; task: string }[]
  recommended_unit_types: string[]
  trend: { trend_direction?: string; mastery_score?: number } | null
}

type RunResult = {
  report_id: number
  scope_title: string
  aggregate: { question_count: number; categories: Category[]; uncertain_count: number } | null
  knowledge_points: KnowledgePoint[]
  suggestions: { priority_order: string[]; suggestions: Suggestion[]; overall_summary: string[] } | null
  trend: { has_previous: boolean; improved: any[]; worsened: any[]; new: any[] } | null
  report: string
}

type TrendSeriesItem = {
  report_id: number
  scope_title: string
  captured_at: string
  categories: Record<string, { percentage: number; count: number }>
}

type MasteryRow = {
  cause_code: string
  label: string
  recent_percentage: number
  previous_percentage: number
  trend_direction: string
  mastery_score: number
  total_occurrences: number
  report_count: number
}

type HistoryItem = {
  report_id: number
  scope_title: string
  question_count: number
  detail_count: number
  knowledge_point_count: number
  top_categories: { code: string; label: string; percentage: number }[]
  created_at: string
}

const props = withDefaults(
  defineProps<{
    /** 要分析的错题 ID 列表；空数组时自动从当前错题本拉取 */
    questionIds?: number[]
    /** 面板标题（如「本周错题分析」）*/
    scopeTitle?: string
    /** 限定单元 ID（按单元范围分析时传入）*/
    unitIds?: number[]
    /** 挂载后是否自动发起分析（默认 true）*/
    autoLoad?: boolean
  }>(),
  { questionIds: () => [], scopeTitle: '', unitIds: () => [], autoLoad: true },
)

const emit = defineEmits<{
  analyzed: [reportId: number]
  historyLoaded: [count: number]
}>()

// 12 分类固定配色（环形图 / 折线图 / 建议卡徽章共用，保证跨视图一致）
const CAUSE_COLORS: Record<string, string> = {
  vocabulary: '#c73e3a',
  collocation: '#e67e22',
  grammar: '#b05cd6',
  context: '#e6a23c',
  discourse: '#3b7d8c',
  detail: '#4c6ef5',
  inference: '#7c5cd6',
  main_idea: '#3e6b52',
  attitude: '#d65c9a',
  trap: '#8a9a3b',
  carelessness: '#8d6e63',
  uncertain: '#9aa0a6',
}

const TABS = [
  { key: 'overview', label: '总览', icon: Brain },
  { key: 'knowledge', label: '知识点', icon: BarChart3 },
  { key: 'suggestions', label: '建议', icon: Lightbulb },
  { key: 'trend', label: '趋势', icon: LineChart },
] as const
type TabKey = (typeof TABS)[number]['key']

const activeTab = ref<TabKey>('overview')
const running = ref(false)
const loadingMeta = ref(false)
const result = ref<RunResult | null>(null)
const cumulativeKp = ref<KnowledgePoint[]>([])
const history = ref<HistoryItem[]>([])
const trendSeries = ref<TrendSeriesItem[]>([])
const masteryRows = ref<MasteryRow[]>([])
const trendHighlights = ref<{ code: string; label: string; delta: number; direction: string }[]>([])
const trendSeriesLimit = ref(5) // 折线图最多同时追踪的分类数

// ── 移动端状态 ──
const MOBILE_QUERY = '(max-width: 860px)'
const isMobile = ref(false)
const sheetOpen = ref(false)
const sheetDragY = ref(0)
const collapsedCards = ref<Set<string>>(new Set())
const rootEl = ref<HTMLElement | null>(null)
let grabStartY = 0
let grabLastY = 0
let grabLastT = 0
let grabReleaseV = 0 // px/s 释放速度（apple-design 规范：速度交接）
let swipeStartX = 0
let swipeStartY = 0
let mediaQuery: MediaQueryList | null = null

const sheetActive = computed(() => isMobile.value && sheetOpen.value)

function onMediaChange(event: MediaQueryListEvent) {
  isMobile.value = event.matches
  if (!isMobile.value) sheetOpen.value = false
}

// 抽屉打开时锁定背景滚动（iOS 橡皮筋 + 安卓穿透滚动都会破坏抽屉体验）
watch(sheetActive, (open) => {
  if (typeof document === 'undefined') return
  document.body.style.overflow = open ? 'hidden' : ''
})

async function openSheet() {
  if (!isMobile.value) return
  sheetOpen.value = true
  // 查看入口：没有当前结果时自动补载最近一份报告，避免用户看到空态
  if (!result.value && history.value.length) {
    await openHistoryReport(history.value[0].report_id)
  }
}

function closeSheet() {
  sheetOpen.value = false
  sheetDragY.value = 0
}

function onBackdropClick(event: MouseEvent) {
  if (sheetActive.value && event.target === rootEl.value) closeSheet()
}

// 抽屉把手：下滑拖拽关闭
function onGrabStart(event: TouchEvent) {
  if (event.touches.length !== 1) return
  grabStartY = event.touches[0].clientY
  grabLastY = event.touches[0].clientY
  grabLastT = performance.now()
  grabReleaseV = 0
  sheetDragY.value = 0
}

function onGrabMove(event: TouchEvent) {
  const y = event.touches[0].clientY
  const now = performance.now()
  const dt = now - grabLastT
  if (dt > 0) grabReleaseV = ((y - grabLastY) / dt) * 1000 // px/s
  grabLastY = y
  grabLastT = now
  const dy = y - grabStartY
  sheetDragY.value = Math.max(0, dy)
}

function onGrabEnd() {
  // apple-design 规范：用速度符号/大小决策，非仅位置；快甩即关（速度交接）
  if (sheetDragY.value > 90 || grabReleaseV > 700) {
    closeSheet()
  } else {
    // 平滑回弹：加过渡让 CSS 处理（模板端仅在有位移时用 transform）
    sheetDragY.value = 0
  }
}

// 标签页左右滑动切换（仅移动端；纵向滚动与横向滚动容器内不触发）
function onSwipeStart(event: TouchEvent) {
  if (event.touches.length !== 1) return
  swipeStartX = event.touches[0].clientX
  swipeStartY = event.touches[0].clientY
}

function onSwipeEnd(event: TouchEvent) {
  if (!isMobile.value) return
  const touch = event.changedTouches[0]
  const dx = touch.clientX - swipeStartX
  const dy = touch.clientY - swipeStartY
  if (Math.abs(dx) < 64 || Math.abs(dy) > 48) return
  const target = event.target as HTMLElement
  if (target.closest('.wa-trend-chart-wrap, .wa-history-rail, .wa-weekly-plan')) return
  const index = TABS.findIndex(tab => tab.key === activeTab.value)
  const next = dx < 0 ? index + 1 : index - 1
  if (next >= 0 && next < TABS.length) {
    activeTab.value = TABS[next].key
    vibrate(12)
  }
}

function vibrate(pattern: number | number[]) {
  try {
    navigator.vibrate?.(pattern)
  } catch {
    // 不支持触觉反馈的设备静默忽略
  }
}

// 学习建议卡折叠（移动端）：新结果默认只展开第一张
function resetCollapse() {
  collapsedCards.value = new Set(
    (result.value?.suggestions?.suggestions || [])
      .slice(1)
      .map(item => item.cause_code),
  )
}

function toggleCard(code: string) {
  const next = new Set(collapsedCards.value)
  next.has(code) ? next.delete(code) : next.add(code)
  collapsedCards.value = next
}

function isCardExpanded(code: string): boolean {
  if (!isMobile.value) return true
  return !collapsedCards.value.has(code)
}

function causeColor(code: string): string {
  return CAUSE_COLORS[code] || '#9aa0a6'
}

// ── 归因总览：环形图数据 ──
const donutItems = computed(() =>
  (result.value?.aggregate?.categories || []).map(category => ({
    label: category.label,
    value: category.count,
    percentage: category.percentage,
    color: causeColor(category.code),
  })),
)

// ── 顶部速览（移动端首屏摘要） ──
const heroStats = computed(() => {
  const aggregate = result.value?.aggregate
  if (!aggregate) return []
  const first = aggregate.categories.find(item => item.code !== 'uncertain')
  const trend = result.value?.trend
  let direction = '保持平稳'
  let directionClass = 'is-stable'
  if (trend?.has_previous) {
    if (trend.improved.length && !trend.worsened.length) {
      direction = '整体改善 ↓'
      directionClass = 'is-improving'
    } else if (trend.worsened.length && !trend.improved.length) {
      direction = '需警惕 ↑'
      directionClass = 'is-worsening'
    } else if (trend.improved.length || trend.worsened.length) {
      direction = '有升有降'
    }
  }
  return [
    { value: String(aggregate.question_count), label: '参与归因', unit: '道' },
    {
      value: first ? `${first.percentage}%` : '—',
      label: first ? `首要薄弱 · ${first.label}` : '暂无明确薄弱点',
      unit: '',
    },
    { value: direction, label: '对比上次分析', unit: '', class: directionClass },
  ]
})

// ── 知识点榜：横向条形（纯 CSS，按命中次数） ──
const knowledgeRanking = computed(() => {
  const items = cumulativeKp.value.length
    ? cumulativeKp.value.map(item => ({
        ...item,
        hits: item.total_hits || item.hit_count || 0,
      }))
    : (result.value?.knowledge_points || []).map(item => ({
        ...item,
        hits: item.hit_count || 0,
      }))
  const max = Math.max(1, ...items.map(item => item.hits))
  return items.slice(0, 12).map(item => ({ ...item, width: Math.round((item.hits / max) * 100) }))
})

// ── 趋势折线：近 N 次报告的占比序列 ──
const trendLabels = computed(() =>
  trendSeries.value.map(item => {
    const date = (item.captured_at || '').slice(5, 10).replace('-', '/')
    return date || `#${item.report_id}`
  }),
)

const trendChartSeries = computed(() => {
  // 选最近一次占比最高的 N 类作为追踪对象
  const latest = trendSeries.value[trendSeries.value.length - 1]
  if (!latest) return []
  const ranked = Object.entries(latest.categories)
    .filter(([code]) => code !== 'uncertain')
    .sort((a, b) => b[1].percentage - a[1].percentage)
    .slice(0, trendSeriesLimit.value)
  return ranked.map(([code, stat]) => ({
    name: masteryRows.value.find(row => row.cause_code === code)?.label || code,
    color: causeColor(code),
    points: trendSeries.value.map(item => item.categories[code]?.percentage || 0),
    latest: stat.percentage,
  }))
})

// ── 雷达图：12 分类掌握度 ──
const radarAxes = computed(() =>
  masteryRows.value
    .filter(row => row.cause_code !== 'uncertain')
    .slice(0, 11)
    .map(row => ({ label: row.label, value: row.mastery_score })),
)

async function runAnalysis() {
  if (running.value) return
  running.value = true
  try {
    const payload: Record<string, unknown> = {
      scope_title: props.scopeTitle || '错题本整体',
      with_ai_report: true,
    }
    if (props.questionIds.length) {
      payload.question_ids = props.questionIds
    }
    if (props.unitIds.length) {
      payload.unit_ids = props.unitIds
    }
    const res = await post<RunResult>('/wrong/analysis/run', payload)
    result.value = res
    activeTab.value = 'overview'
    resetCollapse()
    emit('analyzed', res.report_id)
    showToast(`归因分析完成：${res.aggregate?.question_count || 0} 道错题`, 'success')
    vibrate([30, 40, 30])
    await Promise.all([loadTrend(), loadKnowledgePoints(), loadHistory()])
    if (isMobile.value) {
      sheetOpen.value = true
    } else {
      await nextTick()
      rootEl.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  } catch (e) {
    showToast(`归因分析失败：${e}`, 'error')
    vibrate(60)
  } finally {
    running.value = false
  }
}

async function loadTrend() {
  try {
    const res = await get<{ series: TrendSeriesItem[]; mastery: MasteryRow[]; highlights: typeof trendHighlights.value }>(
      '/wrong/analysis/trend',
    )
    trendSeries.value = res.series || []
    masteryRows.value = res.mastery || []
    trendHighlights.value = res.highlights || []
  } catch {
    // 趋势接口不可用时面板仍可运行分析
  }
}

async function loadKnowledgePoints() {
  try {
    const res = await get<{ items: KnowledgePoint[] }>('/wrong/analysis/knowledge-points')
    cumulativeKp.value = res.items || []
  } catch {
    // 非阻塞
  }
}

async function loadHistory() {
  try {
    const res = await get<{ items: HistoryItem[] }>('/wrong/analysis/history')
    history.value = res.items || []
    emit('historyLoaded', history.value.length)
  } catch {
    // 非阻塞
  }
}

async function openHistoryReport(reportId: number) {
  loadingMeta.value = true
  try {
    const res = await get<RunResult>(`/wrong/analysis/report/${reportId}`)
    result.value = { ...res, suggestions: res.suggestions || null, knowledge_points: res.knowledge_points || [] }
    resetCollapse()
    activeTab.value = 'overview'
    if (isMobile.value) sheetOpen.value = true
  } catch (e) {
    showToast(`读取历史报告失败：${e}`, 'error')
  } finally {
    loadingMeta.value = false
  }
}

function directionLabel(direction: string): string {
  if (direction === 'improving') return '改善中 ↓'
  if (direction === 'worsening') return '需警惕 ↑'
  return '保持平稳'
}

function directionClass(direction: string): string {
  if (direction === 'improving') return 'is-improving'
  if (direction === 'worsening') return 'is-worsening'
  return 'is-stable'
}

// ── 一键分享诊断摘要（navigator.share → 剪贴板降级） ──
function buildShareText(): string {
  const aggregate = result.value?.aggregate
  if (!aggregate) return ''
  const lines = [
    '错题归因分析摘要',
    `范围：${result.value?.scope_title || '错题本整体'}`,
    `参与归因：${aggregate.question_count} 道错题`,
    '',
    '薄弱点分布：',
    ...aggregate.categories
      .filter(item => item.code !== 'uncertain')
      .slice(0, 5)
      .map(item => `· ${item.label} ${item.percentage}%（${item.count} 道）`),
  ]
  if (aggregate.uncertain_count) {
    lines.push(`· 另有 ${aggregate.uncertain_count} 道证据不足，暂不归因`)
  }
  const top = result.value?.suggestions?.suggestions?.[0]
  if (top && top.cause_code !== 'uncertain') {
    lines.push('', `优先行动（${top.label}）：`, ...top.immediate_actions.map(action => `· ${action}`))
  }
  if (result.value?.report) {
    lines.push('', result.value.report.slice(0, 400))
  }
  return lines.join('\n')
}

async function shareAnalysis() {
  const text = buildShareText()
  if (!text) {
    showToast('还没有分析结果，先运行一次归因分析', 'info')
    return
  }
  vibrate(12)
  try {
    if (navigator.share) {
      await navigator.share({ title: '错题归因分析摘要', text })
      return
    }
    await navigator.clipboard.writeText(text)
    showToast('诊断摘要已复制到剪贴板', 'success')
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') return // 用户取消分享
    showToast('分享失败，可长按文本复制', 'error')
  }
}

async function refresh() {
  await Promise.all([loadTrend(), loadKnowledgePoints(), loadHistory()])
}

defineExpose({ runAnalysis, refresh, openSheet, closeSheet })

onMounted(() => {
  mediaQuery = window.matchMedia(MOBILE_QUERY)
  isMobile.value = mediaQuery.matches
  mediaQuery.addEventListener('change', onMediaChange)
  if (props.autoLoad) {
    void refresh()
  }
})

onBeforeUnmount(() => {
  mediaQuery?.removeEventListener('change', onMediaChange)
  if (typeof document !== 'undefined') document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body" :disabled="!sheetActive">
    <Transition name="sheet-rise" appear>
      <section
        v-show="!isMobile || sheetOpen"
        ref="rootEl"
        class="card wa-panel"
        :class="{ 'as-sheet': sheetActive }"
        :role="sheetActive ? 'dialog' : undefined"
        :aria-modal="sheetActive ? 'true' : undefined"
        aria-label="错题知识点归因分析"
        tabindex="-1"
        @click="onBackdropClick"
        @keydown.esc="closeSheet"
      >
        <!-- 移动端抽屉装饰层：拖拽把手 + 关闭按钮 -->
        <div v-if="sheetActive" class="wa-sheet-top">
          <div
            class="sheet-grabber"
            @touchstart.passive="onGrabStart"
            @touchmove="onGrabMove"
            @touchend="onGrabEnd"
          >
            <span />
          </div>
          <button class="sheet-close" type="button" aria-label="关闭归因分析" @click="closeSheet">×</button>
        </div>

        <div
          class="wa-panel-scroll"
          :style="sheetActive && sheetDragY ? { transform: `translateY(${sheetDragY}px)`, transition: 'none' } : { transition: 'transform .3s cubic-bezier(.22, 1, .36, 1)' }"
        >
          <div class="wa-panel-head">
            <div>
              <span class="eyebrow">错因归因</span>
              <h3><Puzzle :size="15" aria-hidden="true" />知识点归因分析</h3>
              <p class="wa-panel-sub">
                12 分类错误原因 → 细粒度知识点 → 分层学习建议 → 跨报告趋势追踪
              </p>
            </div>
            <div class="wa-panel-actions">
              <button
                class="button ghost compact wa-share-btn"
                type="button"
                :disabled="!result"
                aria-label="分享诊断摘要"
                @click="shareAnalysis"
              >
                <Share2 :size="15" />
                <span class="wa-share-label">分享</span>
              </button>
              <button class="button primary compact" type="button" :disabled="running" @click="runAnalysis">
                <Sparkles :size="15" />
                {{ running ? '归因中…' : (result ? '重新归因' : '运行归因分析') }}
              </button>
            </div>
          </div>

          <!-- 历史记录：横向滚动 chips 轨道（触控友好） -->
          <div v-if="history.length" class="wa-history-rail" role="list" aria-label="历史归因分析">
            <button
              v-for="item in history"
              :key="item.report_id"
              class="wa-history-chip"
              type="button"
              role="listitem"
              :disabled="loadingMeta"
              @click="openHistoryReport(item.report_id)"
            >
              <History :size="12" />
              <span class="wa-history-title">{{ item.scope_title || `报告 #${item.report_id}` }}</span>
              <span class="wa-history-date">{{ (item.created_at || '').slice(5, 10) }}</span>
              <span class="wa-history-count">{{ item.question_count }} 题</span>
            </button>
          </div>

          <div class="wa-tabs" role="tablist">
            <button
              v-for="tab in TABS"
              :key="tab.key"
              class="wa-tab"
              type="button"
              role="tab"
              :class="{ active: activeTab === tab.key }"
              :aria-selected="activeTab === tab.key"
              @click="activeTab = tab.key"
            >
              <component :is="tab.icon" :size="14" />
              {{ tab.label }}
            </button>
          </div>

          <div
            class="wa-tab-body"
            @touchstart.passive="onSwipeStart"
            @touchend.passive="onSwipeEnd"
          >
            <!-- 归因总览：速览 + 环形图 + 分类明细 -->
            <div v-if="activeTab === 'overview'" class="wa-tab-pane" role="tabpanel">
              <!-- 骨架屏：分析中且尚无结果 -->
              <div v-if="running && !result" class="wa-skeleton" aria-label="分析中">
                <div class="wa-skeleton-ring" />
                <div class="wa-skeleton-lines">
                  <div v-for="i in 4" :key="i" class="wa-skeleton-line" :style="{ width: `${88 - i * 12}%` }" />
                </div>
              </div>
              <template v-else-if="result?.aggregate">
                <div class="wa-hero" aria-label="本次分析速览">
                  <div v-for="(stat, i) in heroStats" :key="i" class="wa-hero-item" :class="stat.class">
                    <b>{{ stat.value }}<small v-if="stat.unit">{{ stat.unit }}</small></b>
                    <span>{{ stat.label }}</span>
                  </div>
                </div>
                <div class="wa-overview-grid">
                  <div class="wa-donut-wrap">
                    <DonutChart
                      :items="donutItems"
                      :size="210"
                      :thickness="28"
                      :center-value="result.aggregate.question_count"
                      center-label="道错题归因"
                      fluid
                    />
                  </div>
                  <div class="wa-category-list">
                    <div v-for="category in result.aggregate.categories" :key="category.code" class="wa-category-row">
                      <div class="wa-category-meta">
                        <span class="wa-cause-dot" :style="{ background: causeColor(category.code) }" />
                        <strong>{{ category.label }}</strong>
                        <span class="wa-category-count">{{ category.count }} 道 · {{ category.percentage }}%</span>
                        <span class="wa-category-confidence" :title="`平均置信度 ${category.average_confidence}`">
                          置信 {{ Math.round(category.average_confidence * 100) }}%
                        </span>
                      </div>
                      <div class="wa-category-bar">
                        <span :style="{ width: `${category.percentage}%`, background: causeColor(category.code) }" />
                      </div>
                    </div>
                    <p v-if="result.aggregate.uncertain_count" class="wa-uncertain-note">
                      其中 {{ result.aggregate.uncertain_count }} 道证据不足，保留为「不确定」，不强行归因。
                    </p>
                  </div>
                </div>
                <div v-if="result.trend?.has_previous" class="wa-trend-brief">
                  <template v-if="result.trend.improved.length || result.trend.worsened.length">
                    <span v-for="item in result.trend.improved" :key="item.code" class="wa-trend-chip is-improving">
                      ↓ {{ item.label }} {{ item.previous_percentage }}% → {{ item.percentage }}%
                    </span>
                    <span v-for="item in result.trend.worsened" :key="item.code" class="wa-trend-chip is-worsening">
                      ↑ {{ item.label }} {{ item.previous_percentage }}% → {{ item.percentage }}%
                    </span>
                  </template>
                  <span v-else class="wa-trend-chip is-stable">与上次分析相比无明显变化</span>
                </div>
                <div v-if="result.report" class="wa-ai-report">
                  <span class="eyebrow">AI 智能总结</span>
                  <div class="wa-ai-report-text">{{ result.report }}</div>
                </div>
              </template>
              <div v-else class="wa-empty">
                <Radar :size="28" />
                <p>{{ running ? '正在逐题归因，可能需要 1-2 分钟…' : '点击「运行归因分析」开始。留空范围时自动分析当前高频错题。' }}</p>
              </div>
            </div>

            <!-- 知识点：命中频次榜 -->
            <div v-else-if="activeTab === 'knowledge'" class="wa-tab-pane" role="tabpanel">
              <template v-if="knowledgeRanking.length">
                <p class="wa-tab-hint">按命中次数排序 · 跨全部历史分析累计</p>
                <div v-for="item in knowledgeRanking" :key="item.code" class="wa-kp-row">
                  <div class="wa-kp-meta">
                    <strong>{{ item.label }}</strong>
                    <span class="wa-kp-cause" :style="{ color: causeColor(item.cause_code) }">{{ item.cause_label }}</span>
                    <span class="wa-kp-hits">{{ item.hits }} 次</span>
                  </div>
                  <div class="wa-kp-bar"><span :style="{ width: `${item.width}%`, background: causeColor(item.cause_code) }" /></div>
                  <p v-if="item.guidance" class="wa-kp-guidance"><Lightbulb :size="12" aria-hidden="true" /> {{ item.guidance }}</p>
                </div>
              </template>
              <div v-else class="wa-empty">
                <BarChart3 :size="28" />
                <p>还没有知识点统计数据，先运行一次归因分析。</p>
              </div>
            </div>

            <!-- 学习建议：优先级方案卡（移动端可折叠） -->
            <div v-else-if="activeTab === 'suggestions'" class="wa-tab-pane" role="tabpanel">
              <template v-if="result?.suggestions?.suggestions?.length">
                <ul v-if="result.suggestions.overall_summary.length" class="wa-summary-list">
                  <li v-for="(line, i) in result.suggestions.overall_summary" :key="i">{{ line }}</li>
                </ul>
                <article
                  v-for="(suggestion, index) in result.suggestions.suggestions"
                  :key="suggestion.cause_code"
                  class="wa-suggestion-card"
                  :class="{ 'is-uncertain': suggestion.cause_code === 'uncertain', 'is-collapsed': !isCardExpanded(suggestion.cause_code) }"
                >
                  <header
                    class="wa-suggestion-head"
                    :role="isMobile ? 'button' : undefined"
                    :aria-expanded="isMobile ? isCardExpanded(suggestion.cause_code) : undefined"
                    @click="isMobile && toggleCard(suggestion.cause_code)"
                  >
                    <span class="wa-suggestion-rank" :style="{ background: causeColor(suggestion.cause_code) }">#{{ index + 1 }}</span>
                    <div class="wa-suggestion-title">
                      <strong>{{ suggestion.label }}</strong>
                      <span>{{ suggestion.percentage }}% · {{ suggestion.question_count }} 道 · 优先分 {{ suggestion.priority_score }}</span>
                    </div>
                    <span
                      v-if="suggestion.trend?.trend_direction"
                      class="wa-trend-chip"
                      :class="directionClass(suggestion.trend.trend_direction)"
                    >{{ directionLabel(suggestion.trend.trend_direction) }}</span>
                    <ChevronDown v-if="isMobile" :size="17" class="wa-card-chevron" />
                  </header>
                  <div class="wa-suggestion-body">
                    <div v-for="(action, i) in suggestion.immediate_actions" :key="'a' + i" class="wa-action-line">
                      <Zap :size="12" aria-hidden="true" /> {{ action }}
                    </div>
                    <div v-if="suggestion.knowledge_points.length" class="wa-suggestion-kps">
                      <span v-for="kp in suggestion.knowledge_points" :key="kp.code" class="wa-kp-chip" :title="kp.guidance">
                        {{ kp.label }} ×{{ kp.hit_count }}
                      </span>
                    </div>
                    <ol v-if="suggestion.weekly_plan.length" class="wa-weekly-plan">
                      <li v-for="(step, i) in suggestion.weekly_plan" :key="i">
                        <b>{{ step.days }}</b>{{ step.task }}
                      </li>
                    </ol>
                    <div v-if="suggestion.recommended_unit_types.length" class="wa-unit-types">
                      推荐题型：<span v-for="t in suggestion.recommended_unit_types" :key="t" class="wa-unit-chip">{{ t }}</span>
                    </div>
                  </div>
                </article>
              </template>
              <div v-else class="wa-empty">
                <Lightbulb :size="28" />
                <p>运行归因分析后，这里会生成分层学习方案。</p>
              </div>
            </div>

            <!-- 趋势追踪：折线 + 雷达 + 掌握度表 -->
            <div v-else class="wa-tab-pane" role="tabpanel">
              <template v-if="trendSeries.length">
                <div class="wa-trend-controls">
                  <div class="wa-seg" role="radiogroup" aria-label="追踪分类数">
                    <button
                      v-for="n in [3, 5, 8]"
                      :key="n"
                      class="wa-seg-btn"
                      type="button"
                      role="radio"
                      :aria-checked="trendSeriesLimit === n"
                      :class="{ active: trendSeriesLimit === n }"
                      @click="trendSeriesLimit = n"
                    >
                      {{ n }} 类
                    </button>
                  </div>
                  <div v-if="trendHighlights.length" class="wa-highlights">
                    <span
                      v-for="item in trendHighlights"
                      :key="item.code"
                      class="wa-trend-chip"
                      :class="directionClass(item.direction)"
                    >
                      {{ item.direction === 'improving' ? '↓' : '↑' }} {{ item.label }} {{ item.delta > 0 ? '+' : '' }}{{ item.delta }}pt
                    </span>
                  </div>
                </div>
                <div class="wa-trend-grid">
                  <div class="wa-trend-chart-wrap">
                    <TrendLineChart :labels="trendLabels" :series="trendChartSeries" :width="620" :height="240" fluid />
                    <p class="wa-swipe-hint">← 左右滑动切换标签 · 图例可对照折线颜色</p>
                  </div>
                  <div class="wa-radar-wrap">
                    <RadarChart v-if="radarAxes.length >= 3" :axes="radarAxes" :size="270" fluid />
                    <p v-else class="wa-radar-hint">掌握度档案不足 3 项，多运行几次分析后展示雷达图。</p>
                  </div>
                </div>
                <div class="wa-mastery-table">
                  <div class="wa-mastery-row wa-mastery-head">
                    <span>错误原因</span><span>掌握度</span><span>最近占比</span><span>方向</span><span>累计出现</span>
                  </div>
                  <div v-for="row in masteryRows" :key="row.cause_code" class="wa-mastery-row">
                    <span class="wa-mastery-label">
                      <i class="wa-cause-dot" :style="{ background: causeColor(row.cause_code) }" />{{ row.label }}
                    </span>
                    <span class="wa-mastery-score">
                      <b>{{ row.mastery_score }}</b>
                      <i class="wa-mastery-bar"><em :style="{ width: `${row.mastery_score}%`, background: causeColor(row.cause_code) }" /></i>
                    </span>
                    <span>{{ row.recent_percentage }}%</span>
                    <span class="wa-trend-chip" :class="directionClass(row.trend_direction)">{{ directionLabel(row.trend_direction) }}</span>
                    <span>{{ row.total_occurrences }} 题 · {{ row.report_count }} 次报告</span>
                  </div>
                </div>
              </template>
              <div v-else class="wa-empty">
                <LineChart :size="28" />
                <p>还没有趋势数据。每次运行归因分析都会保存一张快照，两次以上即可对比变化。</p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </Transition>
  </Teleport>
</template>
