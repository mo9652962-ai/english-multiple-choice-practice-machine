<template>
  <teleport to="body">
    <transition name="fts-fade">
      <div class="fts-modal-backdrop" v-if="visible" @click.self="close">
        <div class="fts-dialog">
          <!-- 搜索输入框 -->
          <div class="fts-input-header">
            <span class="fts-icon">🔍</span>
            <input
              ref="inputRef"
              type="text"
              v-model="query"
              placeholder="全局搜索真题长难句、选项、核心考点... (按 Esc 关闭)"
              @input="onSearchInput"
              @keydown.esc="close"
            />
            <button class="fts-esc-tag" @click="close">ESC</button>
          </div>

          <!-- 搜索结果列表 -->
          <div class="fts-body">
            <div v-if="loading" class="fts-loading">
              <span class="fts-spinner"></span> 正在遍历 2,760 道真题全集...
            </div>
            
            <div v-else-if="results.length > 0" class="fts-results-list">
              <div
                v-for="item in results"
                :key="item.question_id"
                class="fts-result-card"
                @click="goToQuestion(item)"
              >
                <div class="card-meta">
                  <span class="paper-badge">{{ item.paper_title }}</span>
                  <span class="qid">题号 #{{ item.question_id }}</span>
                </div>
                <div class="card-stem" v-html="item.stem_highlight || item.stem"></div>
                <div class="card-passage" v-if="item.passage_highlight" v-html="item.passage_highlight"></div>
              </div>
            </div>

            <div v-else-if="searched && results.length === 0" class="fts-empty">
              未搜得包含“{{ query }}”的真题考点
            </div>

            <div v-else class="fts-hot-hints">
              <div class="hint-title">✦ 热门真题研习关键词：</div>
              <div class="hint-chips">
                <span class="chip" @click="quickSearch('climate change')">climate change</span>
                <span class="chip" @click="quickSearch('psychologist')">psychologist</span>
                <span class="chip" @click="quickSearch('artificial intelligence')">artificial intelligence</span>
                <span class="chip" @click="quickSearch('coffee')">coffee</span>
                <span class="chip" @click="quickSearch('industrial revolution')">industrial revolution</span>
              </div>
            </div>
          </div>

          <!-- 底部提示 -->
          <div class="fts-footer">
            <span>Powered by SQLite FTS5 毫秒级全文检索引擎</span>
            <span class="shortcut-tip">支持快捷键 Ctrl / ⌘ + K 快速唤起</span>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'

interface FtsItem {
  question_id: number
  paper_title: string
  stem: string
  passage?: string
  stem_highlight?: string
  passage_highlight?: string
}

const visible = ref(false)
const query = ref('')
const results = ref<FtsItem[]>([])
const loading = ref(false)
const searched = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)
const router = useRouter()

let debounceTimer: any = null

const open = () => {
  visible.value = true
  nextTick(() => {
    inputRef.value?.focus()
  })
}

const close = () => {
  visible.value = false
  query.value = ''
  results.value = []
  searched.value = false
}

const quickSearch = (kw: string) => {
  query.value = kw
  executeSearch()
}

const onSearchInput = () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    executeSearch()
  }, 250)
}

const executeSearch = async () => {
  const kw = query.value.trim()
  if (!kw) {
    results.value = []
    searched.value = false
    return
  }

  loading.value = true
  searched.value = true

  try {
    const res = await fetch(`/api/search/fts?q=${encodeURIComponent(kw)}&limit=30`)
    if (res.ok) {
      const data = await res.json()
      results.value = data.results || []
    }
  } catch (err) {
    console.error('FTS 搜索出错', err)
  } finally {
    loading.value = false
  }
}

const goToQuestion = (item: FtsItem) => {
  close()
  router.push({
    name: 'practice',
    query: { question_id: item.question_id },
  })
}

const handleGlobalKeydown = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (visible.value) {
      close()
    } else {
      open()
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})

defineExpose({
  open,
  close,
})
</script>

<style scoped>
.fts-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(26, 24, 20, 0.65);
  backdrop-filter: blur(10px);
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 80px;
}

.fts-dialog {
  width: 90%;
  max-width: 680px;
  background: var(--surface, #fdfaf3);
  border: 1px solid var(--line-strong, #cfc7b6);
  border-radius: var(--radius-lg, 20px);
  box-shadow: 0 20px 60px rgba(46, 42, 35, 0.25);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: 80vh;
}

.fts-input-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--line, #e4ded1);
  background: rgba(253, 250, 243, 0.9);
}

.fts-icon {
  font-size: 18px;
}

.fts-input-header input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 16px;
  color: var(--ink, #2e2a23);
  outline: none;
  font-family: inherit;
}

.fts-esc-tag {
  background: rgba(46, 42, 35, 0.08);
  border: 1px solid var(--line, #e4ded1);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11px;
  color: var(--muted, #6b665c);
  cursor: pointer;
}

.fts-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.fts-loading {
  text-align: center;
  color: var(--muted, #6b665c);
  padding: 30px;
  font-size: 14px;
}

.fts-results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.fts-result-card {
  padding: 14px;
  border: 1px solid var(--line, #e4ded1);
  border-radius: var(--radius-md, 14px);
  background: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  transition: all 0.2s ease;
}

.fts-result-card:hover {
  background: #fff;
  border-color: var(--accent-bamboo, #4a5f4e);
  transform: translateY(-1px);
  box-shadow: 0 4px 16px rgba(46, 42, 35, 0.06);
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.paper-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-bamboo, #4a5f4e);
  background: rgba(92, 122, 82, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.qid {
  font-size: 11px;
  color: var(--muted, #6b665c);
}

.card-stem {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink, #2e2a23);
  line-height: 1.4;
  margin-bottom: 6px;
}

:deep(b) {
  color: var(--accent-vermilion, #b84a39);
  background: rgba(184, 74, 57, 0.08);
  padding: 0 2px;
  border-radius: 2px;
}

.card-passage {
  font-size: 12px;
  color: var(--muted, #6b665c);
  line-height: 1.4;
  font-style: italic;
  background: rgba(46, 42, 35, 0.03);
  padding: 6px 10px;
  border-radius: 6px;
}

.fts-empty {
  text-align: center;
  color: var(--muted, #6b665c);
  padding: 40px;
  font-size: 14px;
}

.fts-hot-hints {
  padding: 20px 0;
}

.hint-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted, #6b665c);
  margin-bottom: 10px;
}

.hint-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  padding: 4px 12px;
  background: rgba(46, 42, 35, 0.05);
  border-radius: 9999px;
  font-size: 12px;
  color: var(--ink, #2e2a23);
  cursor: pointer;
  transition: all 0.2s ease;
}

.chip:hover {
  background: var(--primary-soft, #eae6dc);
  color: var(--accent-vermilion, #b84a39);
}

.fts-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  background: rgba(46, 42, 35, 0.03);
  border-top: 1px solid var(--line, #e4ded1);
  font-size: 11px;
  color: var(--muted, #6b665c);
}

.fts-fade-enter-active,
.fts-fade-leave-active {
  transition: all 0.2s ease;
}

.fts-fade-enter-from,
.fts-fade-leave-to {
  opacity: 0;
  transform: scale(0.98);
}
</style>
