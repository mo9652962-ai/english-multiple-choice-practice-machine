<script setup lang="ts">
// v3.0-enhance: 笔记管理增强 — 标签分类 + Markdown 导出 + 复习模式 + 统计
// v3.2: 合并入口 — 错题本 / 单词本 / 我的笔记 三合一（移动端底部导航"笔记"）
import { onMounted, ref, computed } from 'vue'
import { get, put, del } from '../api'
import { BookMarked, PenLine, RefreshCw, Search, Download, Tag, Trash2 } from 'lucide-vue-next'
import WrongView from './WrongView.vue'
import VocabularyView from './VocabularyView.vue'

const activeTab = ref<'wrong' | 'vocabulary' | 'notes'>('notes')

const TAGS = ['生词', '短语', '语法', '长难句', '易错', '其他'] as const

const notes = ref<any[]>([])
const loading = ref(true)
const keyword = ref('')
const activeTag = ref('')
const error = ref('')
const editing = ref<{ id: number; note: string; tag: string } | null>(null)
const stats = ref<{ total: number; week: number; today: number; tags: { tag: string; count: number }[] } | null>(null)

// 复习模式
const reviewMode = ref(false)
const reviewItems = ref<any[]>([])
const reviewIndex = ref(0)
const reviewRevealed = ref(false)

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  return notes.value.filter(n => {
    const tagOk = !activeTag.value || (n.tag || '') === activeTag.value
    if (!tagOk) return false
    if (!k) return true
    return (n.text || '').toLowerCase().includes(k) ||
      (n.note || '').toLowerCase().includes(k) ||
      (n.unit_title || '').toLowerCase().includes(k)
  })
})

onMounted(async () => {
  try {
    const [r, s]: any = await Promise.all([get('/annotations'), get('/annotations/stats')])
    notes.value = Array.isArray(r) ? r : []
    stats.value = s || null
  } catch (e) {
    error.value = String(e)
  }
  loading.value = false
})

async function saveEdit() {
  if (!editing.value) return
  try {
    const r: any = await put(`/annotations/${editing.value.id}`, {
      note: editing.value.note, tag: editing.value.tag,
    })
    const found = notes.value.find(n => n.id === r.id)
    if (found) { found.note = r.note; found.tag = r.tag }
    editing.value = null
    await refreshStats()
  } catch (e) {
    error.value = String(e)
  }
}

async function removeNote(id: number) {
  if (!window.confirm('确定删除这条标注笔记？')) return
  try {
    await del(`/annotations/${id}`)
    notes.value = notes.value.filter(n => n.id !== id)
    await refreshStats()
  } catch (e) {
    error.value = String(e)
  }
}

function colorClass(color: string) {
  return `ann ann-${color || 'amber'}`
}

// ── 导出 Markdown ──
function exportMarkdown() {
  const items = filtered.value
  if (!items.length) return
  const lines: string[] = ['# 墨题 · 我的笔记', '', `> 共 ${items.length} 条 · 导出时间 ${new Date().toLocaleString('zh-CN')}`, '']
  for (const n of items) {
    lines.push(`## ${n.text}`)
    if (n.tag) lines.push(`> 标签：${n.tag}`)
    if (n.paper_year || n.unit_title) lines.push(`> 来源：${n.paper_year ? n.paper_year + '年 · ' : ''}${n.unit_title}`)
    lines.push(`> 时间：${n.created_at}`)
    lines.push('')
    lines.push(n.note || '_（无笔记内容）_')
    lines.push('')
    lines.push('---', '')
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `墨题笔记-${new Date().toISOString().slice(0, 10)}.md`
  a.click()
  URL.revokeObjectURL(url)
}

// ── 复习模式 ──
async function startReview() {
  try {
    const r: any = await get('/annotations/review?limit=20')
    reviewItems.value = r?.items || []
    reviewIndex.value = 0
    reviewRevealed.value = false
    reviewMode.value = reviewItems.value.length > 0
  } catch (e) {
    error.value = String(e)
  }
}

function nextReview() {
  if (reviewIndex.value < reviewItems.value.length - 1) {
    reviewIndex.value += 1
    reviewRevealed.value = false
  } else {
    reviewMode.value = false
  }
}

// ── 统计 ──
async function refreshStats() {
  try {
    const s: any = await get('/annotations/stats')
    stats.value = s || null
  } catch { /* 忽略 */ }
}
</script>

<template>
  <div class="page page-notes">
    <!-- v3.2: 合并入口 tabs（错题本/单词本/我的笔记） -->
    <div class="notes-tabs" role="tablist">
      <button type="button" :class="{ active: activeTab === 'wrong' }" role="tab" @click="activeTab = 'wrong'">错题本</button>
      <button type="button" :class="{ active: activeTab === 'vocabulary' }" role="tab" @click="activeTab = 'vocabulary'">单词本</button>
      <button type="button" :class="{ active: activeTab === 'notes' }" role="tab" @click="activeTab = 'notes'">我的笔记</button>
    </div>

    <WrongView v-if="activeTab === 'wrong'" />
    <VocabularyView v-else-if="activeTab === 'vocabulary'" />

    <template v-else>
    <div class="page-head">
      <div>
        <span class="eyebrow">研习笔记</span>
        <h1>我的笔记</h1>
        <p class="lead">做题时标记的记录都在这里，随时回顾你的重点和思考。</p>
      </div>
      <div class="notes-actions">
        <div class="notes-search">
          <Search :size="15" class="notes-search-icon" aria-hidden="true" />
          <input v-model="keyword" type="search" placeholder="搜索关键词 / 笔记内容 / 单元…" />
        </div>
        <button type="button" class="button ghost" title="导出 Markdown" @click="exportMarkdown">
          <Download :size="15" /> 导出
        </button>
        <button type="button" class="button" title="复习模式" @click="startReview">
          <RefreshCw :size="15" /> 复习
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div v-if="stats" class="notes-stats">
      <div class="notes-stat"><span class="notes-stat-num">{{ stats.total }}</span><span class="notes-stat-label">全部笔记</span></div>
      <div class="notes-stat"><span class="notes-stat-num">{{ stats.week }}</span><span class="notes-stat-label">近 7 天</span></div>
      <div class="notes-stat"><span class="notes-stat-num">{{ stats.today }}</span><span class="notes-stat-label">今天</span></div>
    </div>

    <!-- 标签筛选 -->
    <div class="notes-tags">
      <button type="button" class="notes-tag" :class="{ active: !activeTag }" @click="activeTag = ''">全部</button>
      <button v-for="t in TAGS" :key="t" type="button" class="notes-tag" :class="{ active: activeTag === t }" @click="activeTag = activeTag === t ? '' : t">
        <Tag :size="12" /> {{ t }}
      </button>
    </div>

    <div v-if="loading" class="card skeleton-card"><span class="skeleton-line"></span><span class="skeleton-line" style="width:72%"></span><span class="skeleton-line" style="width:46%"></span></div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="!filtered.length" class="card empty illustrated-empty">
      <div><BookMarked :size="25" /><strong>{{ keyword || activeTag ? '没有匹配的笔记' : '还没有笔记' }}</strong></div>
      <p>{{ keyword || activeTag ? '换个条件试试' : '做题时选中文章中的词句，点「高亮」或「高亮+笔记」即可记录。' }}</p>
    </div>
    <div v-else class="notes-list">
      <article v-for="n in filtered" :key="n.id" class="card note-item">
        <div class="note-item-head">
          <span class="note-item-meta">
            <span class="note-item-unit">{{ n.paper_year ? n.paper_year + '年 · ' : '' }}{{ n.unit_title }}</span>
            <span v-if="n.tag" class="note-item-tag">{{ n.tag }}</span>
            <time class="note-item-time">{{ n.created_at }}</time>
          </span>
          <div class="note-item-actions">
            <button type="button" class="note-action-btn" title="编辑笔记" aria-label="编辑笔记" @click="editing = { id: n.id, note: n.note || '', tag: n.tag || '' }"><PenLine :size="14" aria-hidden="true" /></button>
            <button type="button" class="note-action-btn danger" title="删除" aria-label="删除笔记" @click="removeNote(n.id)"><Trash2 :size="14" aria-hidden="true" /></button>
          </div>
        </div>
        <blockquote class="note-item-quote"><mark :class="colorClass(n.color)">{{ n.text }}</mark></blockquote>
        <p v-if="n.note" class="note-item-body">{{ n.note }}</p>
        <p v-else class="note-item-body empty">（无笔记内容）</p>
      </article>
    </div>

    <!-- 复习模式 -->
    <div v-if="reviewMode" class="ann-note-overlay" @click.self="reviewMode = false">
      <div class="ann-note-card review-card-note">
        <div class="ann-note-head">
          <span class="ann-note-title"><RefreshCw :size="13" aria-hidden="true" />复习笔记 · {{ reviewIndex + 1 }}/{{ reviewItems.length }}</span>
          <button type="button" class="ann-note-close" aria-label="关闭复习" @click="reviewMode = false">✕</button>
        </div>
        <template v-if="reviewItems[reviewIndex]">
          <div class="review-prompt" @click="reviewRevealed = !reviewRevealed">
            <mark :class="colorClass(reviewItems[reviewIndex].color)">{{ reviewItems[reviewIndex].text }}</mark>
            <p class="review-hint">{{ reviewRevealed ? '点击隐藏答案' : '点击显示你的笔记' }}</p>
          </div>
          <div v-if="reviewRevealed" class="review-answer-box">
            <p v-if="reviewItems[reviewIndex].note" class="review-answer-text">{{ reviewItems[reviewIndex].note }}</p>
            <p v-else class="review-answer-text empty">（这条没有笔记内容）</p>
            <p class="review-source">{{ reviewItems[reviewIndex].paper_year ? reviewItems[reviewIndex].paper_year + '年 · ' : '' }}{{ reviewItems[reviewIndex].unit_title }} · {{ reviewItems[reviewIndex].created_at }}</p>
          </div>
          <div class="ann-note-actions">
            <button type="button" class="button ghost" @click="reviewMode = false">退出复习</button>
            <button type="button" class="button" @click="nextReview">{{ reviewIndex < reviewItems.length - 1 ? '下一条 →' : '完成复习 ✓' }}</button>
          </div>
        </template>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="editing" class="ann-note-overlay" @click.self="editing = null">
      <div class="ann-note-card">
        <div class="ann-note-head">
          <span class="ann-note-title"><PenLine :size="13" aria-hidden="true" />编辑笔记</span>
          <button type="button" class="ann-note-close" aria-label="关闭编辑" @click="editing = null">✕</button>
        </div>
        <div class="edit-tag-row">
          <span class="edit-tag-label">标签：</span>
          <button v-for="t in TAGS" :key="t" type="button" class="notes-tag small" :class="{ active: editing.tag === t }" @click="editing.tag = editing.tag === t ? '' : t">{{ t }}</button>
        </div>
        <textarea
          v-model="editing.note"
          class="ann-note-input"
          rows="4"
          placeholder="写下你的理解、翻译或记忆技巧…"
        ></textarea>
        <div class="ann-note-actions">
          <button type="button" class="button ghost" @click="editing = null">取消</button>
          <button type="button" class="button" @click="saveEdit">保存</button>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>
