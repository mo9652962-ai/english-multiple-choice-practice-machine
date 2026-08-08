<script setup lang="ts">
import {
  BookOpenText,
  Brain,
  ChevronDown,
  FileText,
  Play,
  Sparkles,
  Zap,
} from 'lucide-vue-next'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { get, post, put } from '../api'
import { showToast } from '../services/toast'

type WrongRow = {
  question_id: number
  number: number
  unit_id: number
  unit_title: string
  unit_type: string
  year: number
  wrong_count: number
  is_frequent: boolean
}

type UnitGroup = {
  unitId: number
  title: string
  unitType: string
  questionIds: number[]
  questionCount: number
  wrongAttempts: number
  frequentCount: number
}

type YearGroup = {
  year: number
  units: UnitGroup[]
  questionIds: number[]
  questionCount: number
  wrongAttempts: number
  frequentCount: number
}

type AnalysisCategory = {
  code: string
  label: string
  count: number
  percentage: number
  average_confidence: number
}

type AnalysisAggregate = {
  question_count: number
  categories: AnalysisCategory[]
  recommended_actions: string[]
  uncertain_count: number
}

type AnalysisStatus = {
  unit_id: number
  report_id: number
  scope_title: string
  scope_key: string
  locked: boolean
  can_reanalyze: boolean
  report: string
  aggregate: AnalysisAggregate | null
}

const router = useRouter()
const rows = ref<WrongRow[]>([])
const frequentOnly = ref(false)
const error = ref('')
const analysis = ref('')
const analysisTitle = ref('')
const analysisAggregate = ref<AnalysisAggregate | null>(null)
const analysisNote = ref('')
const analyzingKey = ref('')
const startingKey = ref('')
const openYears = ref(new Set<number>())
const analysisReport = ref<HTMLElement | null>(null)
const analysisStatuses = ref<Record<number, AnalysisStatus>>({})
const exporting = ref(false)

async function exportWrong() {
  if (exporting.value) return
  exporting.value = true
  try {
    const result: any = await get('/wrong/export')
    const markdown: string = result.markdown || ''
    if (!markdown) {
      showToast('没有可导出的错题。', 'info')
      return
    }
    // 复制到剪贴板 + 下载 .md 文件
    try {
      await navigator.clipboard.writeText(markdown)
    } catch {
      // 剪贴板不可用时忽略，仍提供下载
    }
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `错题导出-${new Date().toISOString().slice(0, 10)}.md`
    a.click()
    URL.revokeObjectURL(url)
    showToast(`已导出 ${result.count} 道错题（已复制到剪贴板）`, 'success')
  } catch (e) {
    showToast(`导出失败：${e}`, 'error')
  } finally {
    exporting.value = false
  }
}

// v2.37: 导出可打印错题卷 (粉笔式出卷, HTML 打印版)
const paperExporting = ref(false)
async function exportWrongPaper() {
  if (paperExporting.value) return
  paperExporting.value = true
  try {
    const res = await fetch('/api/wrong/export/html')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const html = await res.text()
    if (!html.includes('paper-item')) {
      showToast('没有可导出的错题。', 'info')
      return
    }
    const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `错题卷-${new Date().toISOString().slice(0, 10)}.html`
    a.click()
    URL.revokeObjectURL(url)
    showToast('错题卷已导出，可用浏览器打开后打印', 'success')
  } catch (e) {
    showToast(`导出失败：${e}`, 'error')
  } finally {
    paperExporting.value = false
  }
}

const visible = computed(() =>
  frequentOnly.value ? rows.value.filter(row => row.is_frequent) : rows.value,
)

const grouped = computed<YearGroup[]>(() => {
  const yearMap = new Map<number, Map<number, UnitGroup>>()
  for (const row of visible.value) {
    if (!yearMap.has(row.year)) yearMap.set(row.year, new Map())
    const unitMap = yearMap.get(row.year)!
    if (!unitMap.has(row.unit_id)) {
      unitMap.set(row.unit_id, {
        unitId: row.unit_id,
        title: row.unit_title,
        unitType: row.unit_type,
        questionIds: [],
        questionCount: 0,
        wrongAttempts: 0,
        frequentCount: 0,
      })
    }
    const unit = unitMap.get(row.unit_id)!
    unit.questionIds.push(row.question_id)
    unit.questionCount++
    unit.wrongAttempts += row.wrong_count
    if (row.is_frequent) unit.frequentCount++
  }

  return [...yearMap.entries()]
    .sort(([left], [right]) => right - left)
    .map(([year, unitMap]) => {
      const units = [...unitMap.values()]
      return {
        year,
        units,
        questionIds: units.flatMap(unit => unit.questionIds),
        questionCount: units.reduce((sum, unit) => sum + unit.questionCount, 0),
        wrongAttempts: units.reduce((sum, unit) => sum + unit.wrongAttempts, 0),
        frequentCount: units.reduce((sum, unit) => sum + unit.frequentCount, 0),
      }
    })
})

const totalWrongAttempts = computed(() =>
  visible.value.reduce((sum, row) => sum + row.wrong_count, 0),
)
const totalFrequent = computed(() =>
  visible.value.filter(row => row.is_frequent).length,
)

function ensureDefaultOpen() {
  if (!openYears.value.size && grouped.value[0]) {
    openYears.value = new Set([grouped.value[0].year])
  }
}

watch(grouped, ensureDefaultOpen)

async function load() {
  try {
    rows.value = await get<WrongRow[]>('/wrong')
    try {
      const statusResult: any = await get('/ai/wrong-analysis-status')
      const map: Record<number, AnalysisStatus> = {}
      for (const item of statusResult?.units || []) {
        map[item.unit_id] = item
      }
      analysisStatuses.value = map
    } catch {
      // 状态接口不可用时仍可正常分析，后端会自行判断缓存与锁定。
    }
    ensureDefaultOpen()
  } catch (e) {
    error.value = String(e)
  }
}

onMounted(load)

// v2.42: 高频错题 TOP + 错因分布
const wrongStats = ref<any>(null)
async function loadWrongStats() {
  try { wrongStats.value = await get('/wrong/stats') } catch { /* 非阻塞 */ }
}
// v2.46: 我的分析笔记 (粉笔式)
const noteEditing = ref<number | null>(null)
const noteDraft = ref('')
function toggleNote(item: any) {
  if (noteEditing.value === item.id) { noteEditing.value = null; return }
  noteEditing.value = item.id
  noteDraft.value = item.note || ''
}
async function saveNote(item: any) {
  try {
    const r: any = await put(`/wrong/${item.id}/note`, { note: noteDraft.value })
    item.note = r.note
    noteEditing.value = null
    showToast('分析笔记已保存', 'success')
  } catch (e) { showToast(`保存失败：${e}`, 'error') }
}
async function redoQuestion(questionId: number) {
  try {
    const session: any = await post('/practice/sessions', {
      mode: 'random', question_ids: [questionId], count: 1, shuffle_options: true,
    })
    router.push(`/practice/${session.id}`)
  } catch (e) { showToast(`重做失败：${e}`, 'error') }
}
onMounted(loadWrongStats)

function toggleYear(year: number) {
  const next = new Set(openYears.value)
  next.has(year) ? next.delete(year) : next.add(year)
  openYears.value = next
}

async function retryScope(
  key: string,
  unitIds: number[],
  questionIds: number[],
  title: string,
) {
  startingKey.value = key
  error.value = ''
  try {
    const session: any = await post('/practice/sessions', {
      mode: 'wrong',
      unit_ids: unitIds,
      question_ids: questionIds,
      count: unitIds.length,
      shuffle_options: true,
    })
    router.push(`/practice/${session.id}`)
  } catch (e) {
    error.value = `${title}重做启动失败：${String(e)}`
  } finally {
    startingKey.value = ''
  }
}

// v2.34: 同类题强化 (粉笔/错题plus式) — 按该范围错题最薄弱题型, 生成同类专项练习
async function strengthenScope(key: string, questionIds: number[], title: string) {
  startingKey.value = key
  error.value = ''
  try {
    const scopeRows = rows.value.filter(r => questionIds.includes(r.question_id))
    const typeCount: Record<string, number> = {}
    for (const row of scopeRows) {
      typeCount[row.unit_type] = (typeCount[row.unit_type] || 0) + row.wrong_count
    }
    const top = Object.entries(typeCount).sort((a, b) => b[1] - a[1])[0]
    if (!top) {
      error.value = '没有可强化的题型'
      return
    }
    const session: any = await post('/practice/sessions', {
      mode: 'random', unit_type: top[0], count: 1, shuffle_options: true,
    })
    showToast(`已生成 ${top[0]} 同类专项（薄弱题型 ${top[1]} 次错）`, 'success')
    router.push(`/practice/${session.id}`)
  } catch (e) {
    error.value = `${title}同类强化启动失败：${String(e)}`
  } finally {
    startingKey.value = ''
  }
}

// v2.96: AI 变体题 (竞品借鉴: 粉笔举一反三/类似题推荐)
const aiVariantKey = ref('')
const aiVariantOpen = ref(false)
const aiVariantLoading = ref(false)
const aiVariantError = ref('')
const aiVariantsList = ref<any[]>([])

async function aiVariants(key: string, questionIds: number[]) {
  aiVariantKey.value = key
  aiVariantError.value = ''
  aiVariantLoading.value = true
  aiVariantOpen.value = true
  try {
    const result: any = await post('/ai/similar-questions', { question_ids: questionIds.slice(0, 5) })
    aiVariantsList.value = result.questions || []
    if (!aiVariantsList.value.length) {
      aiVariantError.value = result.error || 'AI 未生成变体题，请稍后再试'
    }
  } catch (e) {
    aiVariantError.value = `生成失败：${String(e)}`
  } finally {
    aiVariantLoading.value = false
    aiVariantKey.value = ''
  }
}

async function analyzeScope(
  key: string,
  questionIds: number[],
  title: string,
  unitIds: number[] = [],
) {
  const scopeStatuses = unitIds
    .map(unitId => analysisStatuses.value[unitId])
    .filter(Boolean)
  const lockedStatus = scopeStatuses.find(status => status?.locked)
  if (lockedStatus) {
    analysisTitle.value = title
    analysis.value = lockedStatus.report
    analysisAggregate.value = lockedStatus.aggregate || null
    analysisNote.value = '以上是上次分析结果的本地缓存。完成这篇错题的下一次练习后，才能重新分析。'
    await nextTick()
    analysisReport.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    analysisReport.value?.focus({ preventScroll: true })
    return
  }
  analyzingKey.value = key
  error.value = ''
  analysis.value = ''
  analysisAggregate.value = null
  analysisNote.value = ''
  analysisTitle.value = title
  try {
    const result: any = await post('/ai/analyze-wrong', {
      question_ids: questionIds,
      focus: `只分析${title}范围内的错题，概括薄弱能力、干扰项倾向和下一步练习建议。`,
      scope_title: title,
    })
    const content = typeof result?.analysis === 'string'
      ? result.analysis.trim()
      : ''
    if (!content) throw new Error('模型没有返回可显示的分析内容')
    analysis.value = content
    analysisAggregate.value = result.aggregate || null
    if (result?.cached) {
      analysisNote.value = '以上是上次分析结果的本地缓存。完成这篇错题的下一次练习后，才能重新分析。'
    } else {
      analysisNote.value = '分析结果已缓存到本地；完成这篇错题的下一次练习后，可再次分析并对比两次作答。'
    }
    for (const unitId of unitIds) {
      analysisStatuses.value = {
        ...analysisStatuses.value,
        [unitId]: {
          unit_id: unitId,
          report_id: Number(result?.report_id || 0),
          scope_title: title,
          scope_key: '',
          locked: true,
          can_reanalyze: false,
          report: content,
          aggregate: result?.aggregate || null,
        },
      }
    }
    await nextTick()
    analysisReport.value?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
    })
    analysisReport.value?.focus({ preventScroll: true })
  } catch (e) {
    error.value = `${title}分析失败：${String(e)}`
  } finally {
    analyzingKey.value = ''
  }
}

function analysisLabel(unitIds: number[]): string {
  const statuses = unitIds
    .map(unitId => analysisStatuses.value[unitId])
    .filter(Boolean)
  if (statuses.some(status => status.locked)) return '查看分析'
  if (statuses.length) return '重新分析'
  return '分析错题'
}
</script>

<template>
  <div class="page page-wrong wrong-page">
    <div class="page-head">
      <div>
        <span class="eyebrow">WRONG ANSWERS</span>
        <h1>错题本</h1>
        <p class="lead">按年份与篇目整理，可直接对指定范围进行分析或重做。</p>
      </div>
      <div style="display:flex;gap:8px">
        <button class="button ghost" type="button" :disabled="exporting" @click="exportWrong">
          {{ exporting ? '导出中…' : '导出错题' }}
        </button>
        <!-- v2.37: 打印错题卷 (粉笔式出卷) -->
        <button class="button" type="button" :disabled="paperExporting" @click="exportWrongPaper">
          {{ paperExporting ? '生成中…' : '📄 错题卷' }}
        </button>
      </div>
    </div>

    <!-- v2.42: 高频错题 TOP + 错因分布 (猿题库考点归因) -->
    <div v-if="wrongStats?.top?.length" class="card report-panel freq-card">
      <h3>🔁 高频错题 TOP{{ wrongStats.top.length }} <small class="freq-sub">按重复出错次数排序 · 考前优先攻克</small></h3>
      <div class="freq-grid">
        <button
          v-for="(item, i) in wrongStats.top.slice(0, 5)" :key="item.id"
          class="freq-item" type="button" @click="redoQuestion(item.id)"
        >
          <span class="freq-rank">{{ i + 1 }}</span>
          <span class="freq-body">
            <span class="freq-stem">{{ item.stem }}</span>
            <span class="freq-meta">
              <i class="freq-badge" :class="'reason-' + (item.reason === '反复出错' ? 'repeat' : item.reason === '易错点' ? 'weak' : 'ok')">{{ item.reason_icon }} {{ item.reason }}</i>
              <i>错 {{ item.wrong_count }} 次</i>
              <i v-if="item.year">{{ item.year }}</i>
            </span>
            <!-- v2.46: 我的分析笔记 (粉笔式) -->
            <span class="freq-note" :class="{ has: item.note }" @click.stop="toggleNote(item)">
              📝 <span>{{ item.note ? '我的分析' : '记笔记' }}</span>
            </span>
            <span v-if="noteEditing === item.id" class="freq-note-editor" @click.stop>
              <textarea v-model="noteDraft" rows="2" maxlength="500" placeholder="写下你的分析：错因、思路、提醒…"></textarea>
              <span class="freq-note-actions">
                <button class="button compact" @click="saveNote(item)">保存</button>
                <button class="button ghost compact" @click="noteEditing = null">取消</button>
              </span>
            </span>
            <span v-else-if="item.note" class="freq-note-view" @click.stop>{{ item.note }}</span>
          </span>
        </button>
      </div>
      <div v-if="wrongStats.by_type?.length" class="freq-types">
        <span v-for="t in wrongStats.by_type" :key="t.type" class="freq-type-chip">
          {{ t.type || '未分类' }} × {{ t.count }}
        </span>
      </div>
    </div>

    <div v-if="error" class="warning">{{ error }}</div>
    <div
      v-if="analysis"
      ref="analysisReport"
      class="card ai-report"
      tabindex="-1"
      role="region"
      aria-live="polite"
      :aria-label="`${analysisTitle}错题分析结果`"
    >
      <div class="section-title wrong-report-title">
        <div>
          <span class="eyebrow">AI REVIEW</span>
          <h3>{{ analysisTitle }}分析</h3>
        </div>
        <button class="button ghost" @click="analysis='';analysisAggregate=null;analysisNote=''">收起</button>
      </div>
      <div v-if="analysisAggregate" class="wrong-analysis-summary">
        <div class="wrong-analysis-total">
          <strong>{{ analysisAggregate.question_count }}</strong>
          <span>道错题参与本次匿名诊断</span>
        </div>
        <div class="wrong-analysis-categories" aria-label="错误原因占比">
          <div
            v-for="category in analysisAggregate.categories"
            :key="category.code"
            class="wrong-analysis-category"
          >
            <div>
              <strong>{{ category.label }}</strong>
              <span>{{ category.count }} 道 · {{ category.percentage }}%</span>
            </div>
            <div class="wrong-analysis-bar" aria-hidden="true">
              <span :style="{ width: `${category.percentage}%` }" />
            </div>
          </div>
        </div>
        <p v-if="analysisAggregate.uncertain_count" class="wrong-analysis-uncertain">
          其中 {{ analysisAggregate.uncertain_count }} 道暂时证据不足，已保留为“不确定”，不会强行归因。
        </p>
      </div>
      <div>{{ analysis }}</div>
      <p v-if="analysisNote" class="wrong-analysis-cache-note">{{ analysisNote }}</p>
    </div>

    <section v-if="visible.length" class="wrong-overview" aria-label="错题概览">
      <div class="wrong-overview-copy">
        <span class="eyebrow">REVIEW MAP</span>
        <strong>{{ visible.length }} 道错题，分布在 {{ grouped.length }} 个年份</strong>
        <span>累计答错 {{ totalWrongAttempts }} 次，其中 {{ totalFrequent }} 道为高频错题。</span>
      </div>
      <label class="wrong-filter">
        <input v-model="frequentOnly" type="checkbox">
        <span>只看高频错题</span>
      </label>
    </section>

    <div v-if="grouped.length" class="wrong-tree">
      <section
        v-for="yearGroup in grouped"
        :key="yearGroup.year"
        class="wrong-year card"
      >
        <div class="wrong-level-row wrong-year-row">
          <button
            class="wrong-expand-button"
            type="button"
            :aria-expanded="openYears.has(yearGroup.year)"
            :aria-controls="`wrong-year-${yearGroup.year}`"
            @click="toggleYear(yearGroup.year)"
          >
            <span class="wrong-level-icon"><BookOpenText :size="21" /></span>
            <span class="wrong-level-copy">
              <span class="wrong-level-kicker">年份</span>
              <strong>{{ yearGroup.year }} 年</strong>
            </span>
            <span class="wrong-level-stats">
              <span><b>{{ yearGroup.questionCount }}</b> 道错题</span>
              <span>{{ yearGroup.units.length }} 篇</span>
              <span v-if="yearGroup.frequentCount">{{ yearGroup.frequentCount }} 道高频</span>
            </span>
            <ChevronDown
              :size="20"
              class="wrong-chevron"
              :class="{ open: openYears.has(yearGroup.year) }"
            />
          </button>
          <div class="wrong-scope-actions">
            <button
              class="button secondary compact"
              type="button"
              :disabled="Boolean(analyzingKey)"
              @click="analyzeScope(`year-${yearGroup.year}`, yearGroup.questionIds, `${yearGroup.year} 年`, yearGroup.units.map(unit => unit.unitId))"
            >
              <Sparkles :size="15" />
              {{ analyzingKey === `year-${yearGroup.year}` ? '分析中…' : analysisLabel(yearGroup.units.map(unit => unit.unitId)) }}
            </button>
            <button
              class="button compact"
              type="button"
              :disabled="Boolean(startingKey)"
              @click="retryScope(`year-${yearGroup.year}`, yearGroup.units.map(unit => unit.unitId), yearGroup.questionIds, `${yearGroup.year} 年`)"
            >
              <Play :size="15" />
              {{ startingKey === `year-${yearGroup.year}` ? '正在启动…' : '开始重做' }}
            </button>
            <button
              class="button compact"
              type="button"
              :disabled="Boolean(startingKey)"
              @click="strengthenScope(`year-${yearGroup.year}`, yearGroup.questionIds, `${yearGroup.year} 年`)"
            >
              <Zap :size="15" />
              {{ startingKey === `year-${yearGroup.year}` ? '正在启动…' : '同类强化' }}
            </button>
          </div>
        </div>

        <div
          v-show="openYears.has(yearGroup.year)"
          :id="`wrong-year-${yearGroup.year}`"
          class="wrong-units"
        >
          <article
            v-for="unit in yearGroup.units"
            :key="unit.unitId"
            class="wrong-unit-row"
          >
            <span class="wrong-level-icon unit"><FileText :size="18" /></span>
            <span class="wrong-level-copy">
              <span class="wrong-level-kicker">篇目</span>
              <strong>{{ unit.title }}</strong>
            </span>
            <span class="wrong-level-stats">
              <span><b>{{ unit.questionCount }}</b> 道错题</span>
              <span>累计错误 {{ unit.wrongAttempts }} 次</span>
            </span>
            <div class="wrong-scope-actions">
              <button
                class="button secondary compact"
                type="button"
                :disabled="Boolean(analyzingKey)"
                @click="analyzeScope(`unit-${unit.unitId}`, unit.questionIds, `${yearGroup.year} 年${unit.title}`, [unit.unitId])"
              >
                <Sparkles :size="15" />
                {{ analyzingKey === `unit-${unit.unitId}` ? '分析中…' : analysisLabel([unit.unitId]) }}
              </button>
              <button
                class="button compact"
                type="button"
                :disabled="Boolean(startingKey)"
                @click="retryScope(`unit-${unit.unitId}`, [unit.unitId], unit.questionIds, `${yearGroup.year} 年${unit.title}`)"
              >
                <Play :size="15" />
                {{ startingKey === `unit-${unit.unitId}` ? '正在启动…' : '开始重做' }}
              </button>
              <button
                class="button compact"
                type="button"
                :disabled="Boolean(startingKey)"
                @click="strengthenScope(`unit-${unit.unitId}`, unit.questionIds, `${yearGroup.year} 年${unit.title}`)"
              >
                <Zap :size="15" />
                {{ startingKey === `unit-${unit.unitId}` ? '正在启动…' : '同类强化' }}
              </button>
              <button
                class="button compact"
                type="button"
                :disabled="Boolean(aiVariantKey)"
                @click="aiVariants(`unit-${unit.unitId}`, unit.questionIds)"
              >
                <Brain :size="15" />
                {{ aiVariantKey === `unit-${unit.unitId}` ? '生成中…' : 'AI 变体' }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>

    <div v-else class="card empty illustrated-empty">
      <img src="/assets/quiet-study-empty.webp" alt="">
      <div><Brain :size="25" /><strong>这里还没有错题</strong></div>
      <p>{{ frequentOnly ? '当前没有高频错题，可以切换为查看全部错题。' : '保持这个状态很不错，继续按自己的节奏练习。' }}</p>
    </div>
  </div>

  <!-- v2.96: AI 变体题弹窗 (竞品借鉴: 粉笔举一反三/类似题推荐) -->
  <div v-if="aiVariantOpen" class="modal-backdrop" @click.self="aiVariantOpen = false">
    <div class="modal-card ai-variant-modal">
      <div class="modal-header">
        <h3>🧠 AI 变体题</h3>
        <button class="modal-close" type="button" @click="aiVariantOpen = false">×</button>
      </div>
      <p class="ai-variant-note">基于你的错题考点，AI 生成的相似题（举一反三）</p>
      <div v-if="aiVariantLoading" class="ai-variant-loading">AI 生成中，请稍候…</div>
      <div v-else-if="aiVariantError" class="ai-variant-error">{{ aiVariantError }}</div>
      <div v-else class="ai-variant-list">
        <div v-for="(q, qi) in aiVariantsList" :key="qi" class="ai-variant-item">
          <div class="ai-variant-stem">{{ qi + 1 }}. {{ q.stem }}</div>
          <div v-if="q.options?.length" class="ai-variant-options">
            <div v-for="(o, oi) in q.options" :key="oi" class="ai-variant-option">
              <span class="ai-variant-key">{{ ['A','B','C','D'][oi] }}.</span> {{ o }}
            </div>
          </div>
          <div class="ai-variant-answer">✅ 答案：{{ q.answer || '见解析' }}</div>
          <div v-if="q.explain" class="ai-variant-explain">💡 {{ q.explain }}</div>
        </div>
      </div>
    </div>
  </div>
</template>
