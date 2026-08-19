<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { get, post } from '../api'
import { useRoute } from 'vue-router'

const route = useRoute()
const loading = ref(false)
const error = ref('')
const report = ref<any>(null)
const history = ref<any[]>([])
const selecting = ref(false)
const questionIds = ref<number[]>([])
const wrongItems = ref<any[]>([])

const causeColor: Record<string, string> = {
  vocabulary: '#a0522d',
  collocation: '#8b5e3c',
  grammar: '#7d7a5a',
  context: '#4a7c59',
  discourse: '#3a7d7a',
  detail: '#4a6a8a',
  inference: '#6a5a8a',
  main_idea: '#3a7a6a',
  attitude: '#7a4a6a',
  trap: '#6a6a6a',
  carelessness: '#7a7a7a',
  uncertain: '#8a8a8a',
}

const causeLabel = (code: string) => report.value?.aggregate?.categories?.find((c: any) => c.code === code)?.label || code

// v9.24: 能力维度转译（脏 key → 人类可读）
const DIM_LABELS: Record<string, string> = {
  detail: '细节定位题', uncertain: '主旨/推断题', vocabulary: '词汇理解',
  grammar: '语法结构', context: '语境推断', discourse: '篇章逻辑',
  inference: '推理判断', main_idea: '主旨大意', attitude: '态度观点',
  trap: '干扰项识别', carelessness: '粗心失误', collocation: '搭配运用',
}
const dimLabel = (key: string) => DIM_LABELS[key] || key.replace(/_/g, ' ')

const levelBars = computed(() => {
  const dims = report.value?.level?.by_dimension || {}
  return Object.entries(dims).map(([key, value]) => ({ key, value: value as number }))
})

onMounted(async () => {
  // 历史报告列表
  try { history.value = await get('/diagnostic/reports?limit=8') } catch { /* ignore */ }
  const id = route.query.report
  if (id) { loadReport(Number(id)) }
  else if (history.value.length) { loadReport(history.value[0].id) }  // 刷新后自动展示最新报告
})

async function loadReport(id: number) {
  loading.value = true
  error.value = ''
  try { report.value = await get(`/diagnostic/report/${id}`) }
  catch (e) { error.value = String(e) }
  loading.value = false
}

async function loadWrongForSelect() {
  selecting.value = true
  try {
    wrongItems.value = await get('/wrong')
  } catch (e) { error.value = String(e) }
}

const loadingStep = ref('正在诊断…')
let stepTimers: number[] = []

async function generate() {
  if (!questionIds.value.length) { error.value = '请先勾选要诊断的错题'; return }
  loading.value = true
  error.value = ''
  stepTimers = []
  loadingStep.value = '正在逐题归因…（约 40 秒）'
  stepTimers.push(window.setTimeout(() => { loadingStep.value = '正在评估水平…' }, 40000))
  stepTimers.push(window.setTimeout(() => { loadingStep.value = '正在生成报告…' }, 55000))
  try {
    const prev = history.value[0]?.id
    report.value = await post('/diagnostic/report', {
      question_ids: questionIds.value,
      previous_report_id: prev || null,
    })
    history.value = await get('/diagnostic/reports?limit=8')
    questionIds.value = []
    selecting.value = false
  } catch (e) { error.value = String(e) }
  finally { stepTimers.forEach((t) => clearTimeout(t)); stepTimers = [] }
  loading.value = false
}

function toggleQuestion(id: number) {
  const idx = questionIds.value.indexOf(id)
  if (idx >= 0) questionIds.value.splice(idx, 1)
  else questionIds.value.push(id)
}

function useHistory(id: number) { loadReport(id) }
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>学习诊断</h2>
      <p class="muted">AI 归因 → 水平评估 → 薄弱点推荐练习</p>
    </div>

    <div class="card" v-if="!selecting && !report">
      <button class="btn primary" @click="loadWrongForSelect">生成诊断报告</button>
      <p class="muted" style="margin-top: 10px">从错题中选择一组题目，AI 将逐题归因并聚合为学习诊断。</p>
    </div>

    <div class="card" v-if="selecting && !report">
      <div class="panel-head">
        <h3>选择要诊断的错题（{{ questionIds.length }} 题）</h3>
        <button class="btn" @click="selecting = false">取消</button>
      </div>
      <div class="wrong-list" v-if="wrongItems.length">
        <label v-for="w in wrongItems.slice(0, 40)" :key="w.question_id" class="wrong-item" :class="{ checked: questionIds.includes(w.question_id) }">
          <input type="checkbox" :checked="questionIds.includes(w.question_id)" @change="toggleQuestion(w.question_id)" />
          <span class="wrong-tag">{{ w.year }}·{{ w.unit_type }}</span>
          <span class="wrong-stem">{{ (w.stem || '').slice(0, 40) }}</span>
          <span class="wrong-count">错 {{ w.wrong_count }} 次</span>
        </label>
      </div>
      <p v-else class="muted">暂无错题记录，先去练习吧。</p>
      <button class="btn primary" :disabled="loading || !questionIds.length" @click="generate">
        {{ loading ? '诊断中…' : `诊断这 ${questionIds.length} 题` }}
      </button>
      <p v-if="error" class="error">{{ error }}</p>
    </div>

    <div v-if="loading && !report" class="card"><p class="muted">{{ loadingStep }}</p></div>
    <template v-if="report">
      <button class="btn" @click="report = null; selecting = false" style="margin-bottom: 12px">← 返回</button>
      <div v-if="error" class="error" style="margin-bottom: 12px">{{ error }}</div>

      <!-- 水平评估 -->
      <div class="card">
        <div class="panel-head">
          <h3>当前水平评估</h3>
          <span class="muted">{{ report.created_at }}</span>
        </div>
        <div class="level-row">
          <div class="level-score grade-seal-badge">
            <span class="level-num score-huge">{{ report.level?.overall || '-' }}</span>
            <span class="level-max score-total">/ 5</span>
          </div>
          <div class="level-label">{{ report.level?.label || '' }}</div>
        </div>
        <div v-if="levelBars.length" class="level-dims">
          <div v-for="d in levelBars" :key="d.key" class="dim-row">
            <span class="dim-name">{{ dimLabel(d.key) }}</span>
            <div class="dim-track ink-progress-track"><div class="dim-fill ink-progress-bar" :style="{ width: (d.value / 5 * 100) + '%' }"></div></div>
            <span class="dim-value">{{ d.value }}</span>
          </div>
        </div>
      </div>

      <!-- 归因分布 -->
      <div class="card">
        <h3>错误归因分布（{{ report.question_count }} 题）</h3>
        <div class="cause-list">
          <div v-for="c in report.aggregate?.categories" :key="c.code" class="cause-row">
            <span class="cause-dot" :style="{ background: causeColor[c.code] || '#999' }"></span>
            <span class="cause-label">{{ c.label }}（{{ c.count }} 题 · {{ c.percentage }}%）</span>
            <span class="cause-conf" v-if="c.average_confidence">置信 {{ (c.average_confidence * 100).toFixed(0) }}%</span>
          </div>
        </div>
        <p v-if="report.aggregate?.uncertain_count" class="muted">其中 {{ report.aggregate.uncertain_count }} 题归因不确定，建议继续积累作答记录。</p>
      </div>

      <!-- 趋势对比 -->
      <div class="card" v-if="report.trend?.has_previous">
        <h3>与上次诊断对比</h3>
        <div class="trend-row" v-if="report.trend.improved.length">
          <span class="trend-good">▲ 改善：</span>{{ report.trend.improved.map(causeLabel).join('、') }}
        </div>
        <div class="trend-row" v-if="report.trend.worsened.length">
          <span class="trend-bad">▼ 退步：</span>{{ report.trend.worsened.map(causeLabel).join('、') }}
        </div>
        <div class="trend-row" v-if="report.trend.new.length">
          <span class="trend-new">✦ 新增：</span>{{ report.trend.new.map(causeLabel).join('、') }}
        </div>
      </div>

      <!-- 推荐练习 -->
      <div class="card" v-if="report.recommendations?.length">
        <h3>薄弱点推荐练习</h3>
        <div v-for="r in report.recommendations" :key="r.cause" class="rec-item">
          <div class="rec-head">
            <strong>{{ r.label }}</strong>
            <span class="muted">{{ r.suggestion }}</span>
          </div>
          <div class="rec-questions" v-if="r.sample_questions?.length">
            <span v-for="q in r.sample_questions" :key="q.id" class="rec-chip">{{ q.year }}·{{ q.unit }}</span>
          </div>
        </div>
      </div>

      <!-- 学习建议 -->
      <div class="card" v-if="report.report">
        <h3>学习建议</h3>
        <div class="report-text">{{ report.report }}</div>
      </div>
    </template>

    <!-- 历史报告 -->
    <div class="card" v-if="history.length && !report">
      <h3>历史诊断</h3>
      <button v-for="h in history" :key="h.id" class="history-item" @click="useHistory(h.id)">
        <span class="history-title">{{ h.scope_key }}</span>
        <span class="muted">{{ h.question_count }} 题 · {{ h.created_at }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.card { background: var(--surface-solid); border: 1px solid var(--line); border-radius: var(--radius-lg); padding: 18px; margin-bottom: 14px; box-shadow: var(--shadow-sm); }
.card::before { display: none; }
.panel-head { display: flex; justify-content: space-between; align-items: center; }
.level-row { display: flex; align-items: center; gap: 16px; margin: 14px 0; }
.level-score { display: flex; align-items: baseline; }
.level-num { font-size: 42px; font-weight: 700; color: var(--primary); }
.level-max { color: var(--ink-3); }
.level-label { color: var(--ink-2); }
.level-dims .dim-row { display: flex; align-items: center; gap: 10px; margin: 6px 0; }
.dim-name { width: 90px; font-size: 13px; color: var(--ink-3); }
.dim-track { flex: 1; height: 8px; background: var(--primary-faint); border-radius: 999px; overflow: hidden; }
.dim-fill { height: 100%; background: linear-gradient(90deg, #544E46 0%, #4A5F4E 100%); border-radius: 999px; transition: width .5s; }
.dim-value { width: 24px; text-align: right; font-size: 13px; color: var(--ink-3); }
.cause-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-bottom: 1px dashed var(--line); }
.cause-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.cause-label { flex: 1; font-size: 14px; color: var(--ink); }
.cause-conf { font-size: 12px; color: var(--ink-3); }
.trend-row { padding: 4px 0; font-size: 14px; color: var(--ink-2); }
.trend-good { color: var(--primary); font-weight: 600; }
.trend-bad { color: var(--danger, #b3593c); font-weight: 600; }
.trend-new { color: var(--primary); font-weight: 600; }
.rec-item { padding: 10px 0; border-bottom: 1px dashed var(--line); }
.rec-head { display: flex; flex-direction: column; gap: 4px; margin-bottom: 6px; color: var(--ink); }
.rec-questions { display: flex; flex-wrap: wrap; gap: 6px; }
.rec-chip { background: var(--primary-soft); color: var(--primary); font-size: 12px; padding: 3px 8px; border-radius: 10px; }
.report-text { white-space: pre-wrap; line-height: 1.7; color: var(--ink-2); font-size: 14px; }
.wrong-list { max-height: 320px; overflow-y: auto; margin-bottom: 12px; }
.wrong-item { display: flex; align-items: center; gap: 8px; padding: 6px 4px; border-radius: 6px; cursor: pointer; }
.wrong-item.checked { background: var(--primary-soft); }
.wrong-tag { font-size: 12px; background: var(--line); color: var(--ink-2); padding: 2px 6px; border-radius: 8px; white-space: nowrap; }
.wrong-stem { flex: 1; font-size: 13px; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wrong-count { font-size: 12px; color: var(--danger, #b3593c); white-space: nowrap; }
.history-item { display: flex; justify-content: space-between; width: 100%; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; margin-bottom: 6px; background: var(--surface-solid); cursor: pointer; color: var(--ink); }
.history-title { font-weight: 500; }
.btn { padding: 8px 16px; border-radius: 8px; border: 1px solid var(--line-strong); background: var(--surface-solid); color: var(--ink); cursor: pointer; }
.btn.primary { background: var(--primary); color: var(--surface-solid); border-color: var(--primary); }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.error { color: var(--danger, #b3593c); font-size: 13px; }
.muted { color: var(--ink-3); font-size: 13px; }
</style>
