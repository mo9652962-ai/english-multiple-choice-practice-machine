<script setup lang="ts">
import { BookOpen, CheckSquare, MoveRight, Play, Search, Trash2, X } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { del, get, post } from '../api'
import { sound } from '../services/sound'
import QuestionBankSwitcher from '../components/QuestionBankSwitcher.vue'
import { loadQuestionBankProfiles, questionBankProfilesState } from '../services/questionBankProfiles'

const router = useRouter()
const papers = ref<any[]>([])
const error = ref('')
const batchMode = ref(false)
const selectedIds = ref<Set<number>>(new Set())
const showDeleteConfirm = ref(false)  // v9.27: 宣纸确认弹层
let holdTimer: number | null = null

// v55: Phase 4 藏书阁年份时光轴与关键词即时检索
const selectedYear = ref<number | 'all'>('all')
const searchQuery = ref('')

function paperSet(title: string): string {
  if (!title) return ''
  const m = title.match(/(新高考[ⅠI一二]?卷|全国[甲乙]卷|全国I?I?卷|新课标[ⅠI一二]?卷|[甲乙]卷)/)
  return m ? m[1] : ''
}
function paperKind(title: string): string {
  if (!title) return ''
  return title
    .replace(/^\d{4}年/, '')
    .replace(/(新高考[ⅠI一二]?卷|全国[甲乙]卷|全国I?I?卷|新课标[ⅠI一二]?卷|[甲乙]卷)/, '')
    .replace(/^高考英语/, '')
    .trim()
}
function setClass(title: string): string {
  const s = paperSet(title)
  if (s.includes('甲')) return 'set-jia'
  if (s.includes('乙')) return 'set-yi'
  if (s.includes('新')) return 'set-new'
  return 'set-default'
}

const availableYears = computed(() => {
  const set = new Set<number>()
  for (const p of papers.value) {
    if (p.year) set.add(Number(p.year))
  }
  return Array.from(set).sort((a, b) => b - a)
})

const filteredPapers = computed(() => {
  let list = papers.value
  if (selectedYear.value !== 'all') {
    list = list.filter(p => Number(p.year) === selectedYear.value)
  }
  const q = searchQuery.value.trim().toLowerCase()
  if (q) {
    list = list.filter(p =>
      String(p.title || '').toLowerCase().includes(q) ||
      String(p.year || '').includes(q) ||
      String(p.subject || '').toLowerCase().includes(q)
    )
  }
  return list
})

const totalUnits = computed(() => papers.value.reduce((acc, p) => acc + (Number(p.unit_count) || 0), 0))
const totalQuestions = computed(() => papers.value.reduce((acc, p) => acc + (Number(p.question_count) || 0), 0))

async function loadPapers() {
  selectedIds.value = new Set()
  const pid = questionBankProfilesState.activeId
  try { papers.value = await get(`/papers?profile_id=${pid}`) } catch (e) { error.value = String(e) }
}

onMounted(async () => {
  await Promise.all([loadPapers(), loadQuestionBankProfiles()])
})

async function startPaper(id: number) {
  sound.tap()
  try {
    const session: any = await post('/practice/sessions', {
      mode: 'paper', paper_id: id, shuffle_options: true,
    })
    router.push(`/practice/${session.id}`)
  } catch (e) { error.value = String(e) }
}

function togglePaper(id: number) {
  if (!batchMode.value) return
  const next = new Set(selectedIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  selectedIds.value = next
}

function beginHold(id: number) {
  if (holdTimer !== null) window.clearTimeout(holdTimer)
  holdTimer = window.setTimeout(() => {
    batchMode.value = true
    togglePaper(id)
  }, 520)
}

function cancelHold() {
  if (holdTimer !== null) window.clearTimeout(holdTimer)
  holdTimer = null
}

function leaveBatch() {
  batchMode.value = false
  selectedIds.value = new Set()
}

async function moveSelected() {
  const targets = questionBankProfilesState.items.filter(
    item => Number(item.id) !== questionBankProfilesState.activeId,
  )
  if (!targets.length) {
    error.value = '请先新建另一个题库配置'
    return
  }
  const answer = window.prompt(
    `输入目标题库配置编号：\n${targets.map(item => `${item.id}：${item.name}`).join('\n')}`,
    String(targets[0].id),
  )
  const targetId = Number(answer)
  if (!targets.some(item => Number(item.id) === targetId)) return
  try {
    await post('/papers/batch-move', {
      paper_ids: [...selectedIds.value],
      target_profile_id: targetId,
    })
    leaveBatch()
    await loadPapers()
  } catch (cause) {
    error.value = String(cause)
  }
}

async function deleteSelected() {
  if (!selectedIds.value.size) return
  showDeleteConfirm.value = true
}
async function confirmDelete() {
  showDeleteConfirm.value = false
  if (!selectedIds.value.size) return
  try {
    for (const id of selectedIds.value) await del(`/papers/${id}`)
    leaveBatch()
    await loadPapers()
  } catch (cause) {
    error.value = String(cause)
  }
}
</script>

<template>
  <div class="page page-library">
    <div class="page-head">
      <div>
        <span class="eyebrow">真题文库 · 藏书阁</span>
        <h1>卷宗文库</h1>
        <p class="lead">于墨香中抚卷，历年真题整卷全景研习，中途自动保存作答记录。</p>
      </div>
    </div>
    <QuestionBankSwitcher @changed="loadPapers" />

    <!-- v55: 藏书阁案头统计条 -->
    <div v-if="papers.length" class="library-stats-strip">
      <div class="library-stats-items">
        <span>藏卷 <strong>{{ papers.length }}</strong> 套</span>
        <span>精编 <strong>{{ totalUnits }}</strong> 篇语篇</span>
        <span>客观题 <strong>{{ totalQuestions }}</strong> 道</span>
      </div>
      <div class="lead" style="font-size:12px;margin:0">
        真题全真还原 · 自动打乱选项防死记 · 随时提笔开卷
      </div>
    </div>

    <!-- v55: 年份时光轴与搜索栏 -->
    <div v-if="papers.length" class="library-filter-bar">
      <div class="year-pills-wrap" role="tablist" aria-label="年份筛选">
        <button
          class="year-pill"
          :class="{ active: selectedYear === 'all' }"
          type="button"
          @click="selectedYear = 'all'; sound.tap()"
        >
          全部年份 ({{ papers.length }})
        </button>
        <button
          v-for="yr in availableYears"
          :key="yr"
          class="year-pill"
          :class="{ active: selectedYear === yr }"
          type="button"
          @click="selectedYear = yr; sound.tap()"
        >
          {{ yr }} 年
        </button>
      </div>
      <div class="library-search-box">
        <Search class="library-search-icon" :size="15" />
        <input
          v-model="searchQuery"
          type="search"
          class="library-search-input"
          placeholder="按卷名/年份搜索…"
          aria-label="搜索试卷"
        />
      </div>
    </div>

    <div class="batch-toolbar">
      <span class="lead">{{ batchMode ? `已选择 ${selectedIds.size} 套试卷` : '长按试卷或点击“批量管理”可移动、删除多套试卷。' }}</span>
      <span style="display:flex;gap:8px;flex-wrap:wrap">
        <button v-if="!batchMode" class="button secondary compact" type="button" @click="batchMode=true"><CheckSquare :size="16" />批量管理</button>
        <template v-else>
          <button class="button secondary compact" type="button" :disabled="!selectedIds.size" @click="moveSelected"><MoveRight :size="16" />移动</button>
          <button class="button ghost danger compact" type="button" :disabled="!selectedIds.size" @click="deleteSelected"><Trash2 :size="16" />移入回收站</button>
          <button class="button ghost compact" type="button" @click="leaveBatch"><X :size="16" />取消</button>
        </template>
      </span>
    </div>

    <div v-if="error" class="warning">{{ error }}</div>

    <!-- 试卷卡片网格 (Scholar Edition) -->
    <div v-if="filteredPapers.length" class="grid grid-3">
      <article
        class="card paper-card scholar-edition selectable"
        :class="{ selected: selectedIds.has(paper.id) }"
        v-for="paper in filteredPapers"
        :key="paper.id"
        @pointerdown="beginHold(paper.id)"
        @pointerup="cancelHold"
        @pointerleave="cancelHold"
        @click="togglePaper(paper.id)"
      >
        <!-- 大字古典年份水印 -->
        <div class="paper-watermark-year" aria-hidden="true">{{ paper.year }}</div>

        <div class="paper-card-body">
          <div class="paper-card-top">
            <span class="scholar-seal-tag">真题卷</span>
            <span class="pill" :class="{ 'pill-published': paper.status === 'published' }">
              {{ paper.status === 'published' ? '已收录' : '未刊布' }}
            </span>
          </div>

          <div class="paper-headline">
            <span v-if="paperSet(paper.title)" class="paper-set-tag" :class="setClass(paper.title)" style="margin-bottom:6px;display:inline-block">
              {{ paperSet(paper.title) }}
            </span>
            <h3>{{ paper.title }}</h3>
          </div>

          <div class="paper-meta-pills">
            <span class="paper-meta-pill">{{ paper.subject || '英语' }}</span>
            <span class="paper-meta-pill">{{ paper.unit_count }} 篇语篇</span>
            <span class="paper-meta-pill">{{ paper.question_count }} 道小题</span>
          </div>
        </div>

        <button
          class="button"
          style="width:100%;margin-top:22px;position:relative;z-index:2"
          :disabled="paper.status !== 'published' || batchMode"
          @click.stop="startPaper(paper.id)"
        >
          <Play :size="16" />开卷研习
        </button>
      </article>
    </div>
    <div v-else-if="papers.length" class="card empty" style="text-align:center;padding:42px 20px">
      <p style="color:var(--muted);margin-bottom:12px">未找到符合当前年份或搜索条件的试卷</p>
      <button class="button ghost compact" type="button" @click="selectedYear='all'; searchQuery=''">重置筛选</button>
    </div>
    <div v-else class="card empty illustrated-empty">
      <img loading="lazy" decoding="async" src="/assets/quiet-study-empty.webp" alt="" />
      <strong>题库还是空的</strong>
      <p>请先到“导入题库”上传 Word 真题。</p>
    </div>
  </div>

  <!-- v9.27: 宣纸确认弹层（替换原生 confirm） -->
  <Teleport to="body">
    <div v-if="showDeleteConfirm" class="modal-overlay" @click.self="showDeleteConfirm = false">
      <div class="modal-xuanzhi-confirm">
        <h3 class="icon-h3"><Trash2 :size="15" aria-hidden="true" />移入回收站</h3>
        <p>销毁卷宗将无法复原练习记录。<b>确认将选中的 {{ selectedIds.size }} 套试卷移入回收站？</b></p>
        <div class="modal-actions">
          <button class="button ghost" @click="showDeleteConfirm = false">再想想</button>
          <button class="button danger" @click="confirmDelete">确认移入</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

