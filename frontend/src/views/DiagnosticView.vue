<script setup lang="ts">
import {
  Award,
  BookMarked,
  Brain,
  CheckCircle2,
  FileText,
  History,
  Play,
  RefreshCw,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, post } from '../api'
import { sound } from '../services/sound'
import { showToast } from '../services/toast'

const route = useRoute()
const router = useRouter()
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

const causeLabel = (code: string) =>
  report.value?.aggregate?.categories?.find((c: any) => c.code === code)?.label || code

// v9.24: 能力维度转译（脏 key → 人类可读）
const DIM_LABELS: Record<string, string> = {
  detail: '细节定位题',
  uncertain: '主旨/推断题',
  vocabulary: '词汇理解',
  grammar: '语法结构',
  context: '语境推断',
  discourse: '篇章逻辑',
  inference: '推理判断',
  main_idea: '主旨大意',
  attitude: '态度观点',
  trap: '干扰项识别',
  carelessness: '粗心失误',
  collocation: '搭配运用',
}
const dimLabel = (key: string) => DIM_LABELS[key] || key.replace(/_/g, ' ')

const LEVEL_TITLES: Record<number, string> = {
  1: '初窥门径',
  2: '略有小成',
  3: '驾轻就熟',
  4: '炉火纯青',
  5: '登峰造极',
}
function levelTitle(score: number | string | undefined): string {
  const num = Math.round(Number(score) || 0)
  return LEVEL_TITLES[num] || '学海泛舟'
}

const levelBars = computed(() => {
  const dims = report.value?.level?.by_dimension || {}
  return Object.entries(dims).map(([key, value]) => ({ key, value: value as number }))
})

onMounted(async () => {
  // 历史报告列表
  try {
    history.value = await get('/diagnostic/reports?limit=8')
  } catch {
    /* ignore */
  }
  const id = route.query.report
  if (id) {
    loadReport(Number(id))
  } else if (history.value.length) {
    loadReport(history.value[0].id) // 刷新后自动展示最新报告
  }
})

async function loadReport(id: number) {
  loading.value = true
  error.value = ''
  try {
    report.value = await get(`/diagnostic/report/${id}`)
  } catch (e) {
    error.value = String(e)
  }
  loading.value = false
}

async function loadWrongForSelect() {
  sound.tap()
  selecting.value = true
  report.value = null
  try {
    wrongItems.value = await get('/wrong')
  } catch (e) {
    error.value = String(e)
  }
}

const loadingStep = ref('正在诊断…')
let stepTimers: number[] = []

async function generate() {
  if (!questionIds.value.length) {
    error.value = '请先勾选要诊断的错题'
    return
  }
  sound.tap()
  loading.value = true
  error.value = ''
  stepTimers = []
  loadingStep.value = '正在逐题归因…（约 40 秒）'
  stepTimers.push(
    window.setTimeout(() => {
      loadingStep.value = '正在评估水平…'
    }, 40000),
  )
  stepTimers.push(
    window.setTimeout(() => {
      loadingStep.value = '正在生成报告…'
    }, 55000),
  )
  try {
    const prev = history.value[0]?.id
    report.value = await post('/diagnostic/report', {
      question_ids: questionIds.value,
      previous_report_id: prev || null,
    })
    history.value = await get('/diagnostic/reports?limit=8')
    questionIds.value = []
    selecting.value = false
    sound.fanfare()
    showToast('学情诊断报告已生成', 'success')
  } catch (e) {
    error.value = String(e)
    sound.wrong()
  } finally {
    stepTimers.forEach(t => clearTimeout(t))
    stepTimers = []
    loading.value = false
  }
}

function toggleQuestion(id: number) {
  sound.tap()
  const idx = questionIds.value.indexOf(id)
  if (idx >= 0) questionIds.value.splice(idx, 1)
  else questionIds.value.push(id)
}

function useHistory(id: number) {
  sound.tap()
  loadReport(id)
}

// 推荐专项练习直接启动做题闭环
async function startRecommendedPractice(qIds: number[], title: string) {
  sound.tap()
  if (!qIds?.length) {
    showToast('暂无对应推荐题目', 'info')
    return
  }
  try {
    const session: any = await post('/practice/sessions', {
      mode: 'random',
      question_ids: qIds,
      count: qIds.length,
      shuffle_options: true,
    })
    showToast(`已生成 ${title} 专项突破练习`, 'success')
    router.push(`/practice/${session.id}`)
  } catch (e) {
    showToast(`练习生成失败：${e}`, 'error')
  }
}
</script>

<template>
  <div class="page page-diagnostic">
    <!-- 案头标头 -->
    <div class="page-head">
      <div>
        <span class="eyebrow">AI 深度归因 · 学情手札</span>
        <h1>学情智能诊断</h1>
        <p class="lead">多维考点归因 · 5级学术水平评估 · 动态进退步对比与薄弱定向突破</p>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button v-if="report && !selecting" class="button primary" type="button" @click="loadWrongForSelect">
          <Sparkles :size="15" />重新诊断错题
        </button>
        <button class="button ghost" type="button" @click="sound.tap(); router.push('/wrong')">
          <BookMarked :size="15" />返回错题本
        </button>
      </div>
    </div>

    <!-- 历史卷宗切换胶囊 -->
    <div v-if="history.length" class="diagnostic-history-bar" role="tablist" aria-label="历史诊断记录">
      <span style="font-size:12px;color:var(--muted);display:inline-flex;align-items:center;gap:4px;padding:0 6px">
        <History :size="13" />历史卷宗:
      </span>
      <button
        v-for="h in history"
        :key="h.id"
        class="diagnostic-history-chip"
        :class="{ active: report?.id === h.id }"
        type="button"
        @click="useHistory(h.id)"
      >
        <span>{{ h.created_at?.slice(0, 10) || '历史诊断' }}</span>
        <span style="opacity:0.75">({{ h.question_count }} 题)</span>
      </button>
    </div>

    <!-- 没有报告且未进入选择模式时的空状态引导卡 -->
    <div v-if="!selecting && !report && !loading" class="card empty illustrated-empty" style="padding:48px 24px;text-align:center">
      <Brain :size="48" style="color:var(--primary);margin:0 auto 16px;opacity:0.85" />
      <h3 style="margin-bottom:8px">尚未生成学情诊断报告</h3>
      <p style="max-width:440px;margin:0 auto 20px;color:var(--muted)">
        从错题库中选择题目，AI 将进行逐题深度考点归因，自动评估学术水平与薄弱点。
      </p>
      <button class="button primary" type="button" @click="loadWrongForSelect">
        <Sparkles :size="16" />选择错题生成诊断
      </button>
    </div>

    <!-- 错题选择抽屉面板 -->
    <div v-if="selecting && !report" class="card" style="padding:24px 28px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--line)">
        <div>
          <h3 style="margin:0;display:flex;align-items:center;gap:8px">
            <CheckCircle2 :size="18" style="color:var(--primary)" />
            选择要诊断的错题（已选 {{ questionIds.length }} 题）
          </h3>
          <small class="muted" style="margin-top:4px;display:block">勾选需要 AI 逐题归因的真题错题</small>
        </div>
        <button class="button ghost compact" type="button" @click="sound.tap(); selecting = false; if (history.length) loadReport(history[0].id)">取消</button>
      </div>
      <div class="wrong-list" v-if="wrongItems.length" style="max-height:400px;overflow-y:auto;display:grid;gap:6px;padding-right:4px">
        <label
          v-for="w in wrongItems.slice(0, 50)"
          :key="w.question_id"
          class="wrong-item scholar-edition"
          :class="{ checked: questionIds.includes(w.question_id) }"
          style="display:flex;align-items:center;gap:12px;padding:10px 14px;border:1px solid var(--line);border-radius:10px;cursor:pointer;background:var(--surface-solid);transition:all .15s ease"
        >
          <input
            type="checkbox"
            :checked="questionIds.includes(w.question_id)"
            @change="toggleQuestion(w.question_id)"
            style="width:16px;height:16px;accent-color:var(--primary)"
          />
          <span class="paper-meta-pill" style="font-size:11px">{{ w.year }}·{{ w.unit_type }}</span>
          <span style="flex:1;font-size:13.5px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
            {{ w.stem || '真题语篇段落' }}
          </span>
          <span class="cinnabar-seal-badge" style="font-size:11px">错 {{ w.wrong_count }} 次</span>
        </label>
      </div>
      <p v-else class="muted" style="padding:24px 0;text-align:center">暂无错题记录，请先去练习或导入真题。</p>

      <div style="display:flex;justify-content:space-between;align-items:center;margin-top:20px;padding-top:14px;border-top:1px solid var(--line)">
        <span class="muted" style="font-size:13px">已勾选 {{ questionIds.length }} 道错题</span>
        <button
          class="button primary"
          type="button"
          :disabled="loading || !questionIds.length"
          @click="generate"
        >
          <Sparkles :size="15" />
          {{ loading ? '诊断中…' : `开始智能诊断 (${questionIds.length} 题)` }}
        </button>
      </div>
      <p v-if="error" class="warning" style="margin-top:12px">{{ error }}</p>
    </div>

    <!-- 诊断加载中反馈卡 -->
    <div v-if="loading && !report" class="card empty illustrated-empty" style="padding:56px 24px;text-align:center">
      <RefreshCw :size="36" style="color:var(--primary);margin:0 auto 16px;animation:spin 1.2s linear infinite" />
      <h3>{{ loadingStep }}</h3>
      <p class="muted" style="font-size:13px;max-width:360px;margin:8px auto 0">
        AI 正在进行全量考点特征解构与多维能力建模，请稍候…
      </p>
    </div>

    <!-- 报告主体内容 -->
    <template v-if="report && !selecting && !loading">
      <!-- 5级水平评估玉盘仪表卡 -->
      <div class="card level-gauge-card">
        <div class="level-gauge-header">
          <div>
            <span class="eyebrow">综合学术评估</span>
            <h3 style="margin:2px 0 0">当前水平定级</h3>
          </div>
          <span class="cinnabar-seal-badge" style="font-size:12px">{{ report.created_at?.slice(0, 10) }} 诊断</span>
        </div>
        <div class="level-gauge-body">
          <div class="level-seal-badge">
            <span class="level-score-huge">{{ report.level?.overall ?? '4.0' }}</span>
            <span class="level-score-max">/ 5.0 学术等第</span>
            <div class="level-seal-title">{{ report.level?.label || levelTitle(report.level?.overall) }}</div>
          </div>
          <div class="dim-grid-scholar" v-if="levelBars.length">
            <div v-for="d in levelBars" :key="d.key" class="dim-row-scholar">
              <span class="dim-label-scholar">{{ dimLabel(d.key) }}</span>
              <div class="dim-track-scholar">
                <div class="dim-fill-scholar" :style="{ width: `${(d.value / 5) * 100}%` }"></div>
              </div>
              <span class="dim-val-scholar">{{ d.value }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 错误归因分布 -->
      <div class="card" style="padding:22px 26px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <span class="eyebrow">考点解构</span>
            <h3 style="margin:2px 0 0">错误归因分布图谱（{{ report.question_count }} 题样本）</h3>
          </div>
          <span class="paper-meta-pill">{{ report.aggregate?.categories?.length || 0 }} 维度</span>
        </div>
        <div class="cause-grid-scholar">
          <div v-for="c in report.aggregate?.categories" :key="c.code" class="cause-card-scholar">
            <div class="cause-head-scholar">
              <span class="cause-title-scholar">
                <span class="cause-dot-scholar" :style="{ background: causeColor[c.code] || '#999' }"></span>
                {{ c.label }}
              </span>
              <span class="cause-conf-badge" v-if="c.average_confidence">
                置信 {{ (c.average_confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="cause-bar-track">
              <div class="cause-bar-fill" :style="{ width: `${c.percentage}%`, background: causeColor[c.code] || 'var(--primary)' }"></div>
            </div>
            <div class="cause-meta-scholar">
              <span>{{ c.count }} 道错题</span>
              <strong>{{ c.percentage }}%</strong>
            </div>
          </div>
        </div>
        <p v-if="report.aggregate?.uncertain_count" class="muted" style="margin-top:14px;font-size:12.5px">
          💡 其中 {{ report.aggregate.uncertain_count }} 题因上下文较少归因为“不确定”，已客观保留。
        </p>
      </div>

      <!-- 动态进退步对比手札 -->
      <div class="card" v-if="report.trend?.has_previous" style="padding:22px 26px">
        <span class="eyebrow">学情演进</span>
        <h3 style="margin:2px 0 0">与前次诊断对比</h3>
        <div class="trend-ledger-grid">
          <div class="trend-column-card improved">
            <div class="trend-col-title" style="color:var(--primary)">
              <TrendingUp :size="16" />
              <span>改善考点 ({{ report.trend.improved?.length || 0 }})</span>
            </div>
            <div v-if="report.trend.improved?.length" class="trend-pill-list">
              <span v-for="cause in report.trend.improved" :key="cause" class="trend-pill improved">
                ▲ {{ causeLabel(cause) }}
              </span>
            </div>
            <span v-else class="muted" style="font-size:12px">暂无显著改善</span>
          </div>

          <div class="trend-column-card worsened">
            <div class="trend-col-title" style="color:var(--accent-vermilion, #c73e3a)">
              <TrendingDown :size="16" />
              <span>需警惕退步 ({{ report.trend.worsened?.length || 0 }})</span>
            </div>
            <div v-if="report.trend.worsened?.length" class="trend-pill-list">
              <span v-for="cause in report.trend.worsened" :key="cause" class="trend-pill worsened">
                ▼ {{ causeLabel(cause) }}
              </span>
            </div>
            <span v-else class="muted" style="font-size:12px">保持优良，未现退步</span>
          </div>

          <div class="trend-column-card new-added">
            <div class="trend-col-title" style="color:var(--accent-gold, #c29339)">
              <Sparkles :size="16" />
              <span>新增考因 ({{ report.trend.new?.length || 0 }})</span>
            </div>
            <div v-if="report.trend.new?.length" class="trend-pill-list">
              <span v-for="cause in report.trend.new" :key="cause" class="trend-pill new-added">
                ✦ {{ causeLabel(cause) }}
              </span>
            </div>
            <span v-else class="muted" style="font-size:12px">无新出现错因</span>
          </div>
        </div>
      </div>

      <!-- 薄弱点推荐专项突破 -->
      <div class="card" v-if="report.recommendations?.length" style="padding:22px 26px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <span class="eyebrow">针对性攻坚</span>
            <h3 style="margin:2px 0 0">薄弱点推荐专项突破</h3>
          </div>
          <span class="cinnabar-seal-badge">优先提分项</span>
        </div>
        <div class="rec-list-scholar">
          <div v-for="r in report.recommendations" :key="r.cause" class="rec-card-scholar">
            <div class="rec-info-scholar">
              <div class="rec-title-scholar">
                <Zap :size="16" style="color:var(--accent-gold, #c29339)" />
                <span>{{ r.label }}</span>
              </div>
              <p class="rec-suggestion-scholar">{{ r.suggestion }}</p>
              <div class="rec-chips-scholar" v-if="r.sample_questions?.length">
                <span v-for="q in r.sample_questions" :key="q.id" class="rec-chip-scholar">
                  {{ q.year }} · {{ q.unit }}
                </span>
              </div>
            </div>
            <button
              v-if="r.sample_questions?.length"
              class="button compact primary"
              type="button"
              @click="startRecommendedPractice(r.sample_questions.map((q: any) => q.id), r.label)"
            >
              <Play :size="13" />提笔攻坚
            </button>
          </div>
        </div>
      </div>

      <!-- 学术研习建议手札 -->
      <div class="card" v-if="report.report" style="padding:22px 26px">
        <span class="eyebrow">名师点评</span>
        <h3 style="margin:2px 0 12px">学术研习建议手札</h3>
        <div class="report-text" style="line-height:1.85;font-size:14.5px;color:var(--ink);background:color-mix(in srgb, var(--primary-faint) 60%, var(--surface-solid));padding:18px 22px;border-radius:12px;border-left:3.5px solid var(--primary);white-space:pre-wrap">
          {{ report.report }}
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
