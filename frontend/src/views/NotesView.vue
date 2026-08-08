<script setup lang="ts">
// v3.0: 笔记管理 — 集中查看做题时的标注记录（关键词高亮 + 笔记）
import { onMounted, ref, computed } from 'vue'
import { get, put, del } from '../api'
import { BookMarked, Search } from 'lucide-vue-next'

const notes = ref<any[]>([])
const loading = ref(true)
const keyword = ref('')
const error = ref('')
const editing = ref<{ id: number; note: string } | null>(null)

const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  if (!k) return notes.value
  return notes.value.filter(n =>
    (n.text || '').toLowerCase().includes(k) ||
    (n.note || '').toLowerCase().includes(k) ||
    (n.unit_title || '').toLowerCase().includes(k)
  )
})

onMounted(async () => {
  try {
    const r: any = await get('/annotations')
    notes.value = Array.isArray(r) ? r : []
  } catch (e) {
    error.value = String(e)
  }
  loading.value = false
})

async function saveEdit() {
  if (!editing.value) return
  try {
    const r: any = await put(`/annotations/${editing.value.id}`, { note: editing.value.note })
    const found = notes.value.find(n => n.id === r.id)
    if (found) found.note = r.note
    editing.value = null
  } catch (e) {
    error.value = String(e)
  }
}

async function removeNote(id: number) {
  if (!window.confirm('确定删除这条标注笔记？')) return
  try {
    await del(`/annotations/${id}`)
    notes.value = notes.value.filter(n => n.id !== id)
  } catch (e) {
    error.value = String(e)
  }
}

function colorClass(color: string) {
  return `ann ann-${color || 'amber'}`
}
</script>

<template>
  <div class="page page-notes">
    <div class="page-head">
      <div>
        <span class="eyebrow">NOTES</span>
        <h1>我的笔记</h1>
        <p class="lead">做题时标记的记录都在这里，随时回顾你的重点和思考。</p>
      </div>
      <div class="notes-search">
        <Search :size="15" class="notes-search-icon" aria-hidden="true" />
        <input v-model="keyword" type="search" placeholder="搜索关键词 / 笔记内容 / 单元…" />
      </div>
    </div>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="!filtered.length" class="card empty illustrated-empty">
      <div><BookMarked :size="25" /><strong>{{ keyword ? '没有匹配的笔记' : '还没有笔记' }}</strong></div>
      <p>{{ keyword ? '换个关键词试试' : '做题时选中文章中的词句，点「高亮」或「高亮+笔记」即可记录。' }}</p>
    </div>
    <div v-else class="notes-list">
      <article v-for="n in filtered" :key="n.id" class="card note-item">
        <div class="note-item-head">
          <span class="note-item-meta">
            <span class="note-item-unit">{{ n.paper_year ? n.paper_year + '年 · ' : '' }}{{ n.unit_title }}</span>
            <time class="note-item-time">{{ n.created_at }}</time>
          </span>
          <div class="note-item-actions">
            <button type="button" class="note-action-btn" title="编辑笔记" @click="editing = { id: n.id, note: n.note || '' }">✏️</button>
            <button type="button" class="note-action-btn danger" title="删除" @click="removeNote(n.id)">🗑</button>
          </div>
        </div>
        <blockquote class="note-item-quote"><mark :class="colorClass(n.color)">{{ n.text }}</mark></blockquote>
        <p v-if="n.note" class="note-item-body">{{ n.note }}</p>
        <p v-else class="note-item-body empty">（无笔记内容）</p>
      </article>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="editing" class="ann-note-overlay" @click.self="editing = null">
      <div class="ann-note-card">
        <div class="ann-note-head">
          <span class="ann-note-title">✏️ 编辑笔记</span>
          <button type="button" class="ann-note-close" @click="editing = null">✕</button>
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
  </div>
</template>
