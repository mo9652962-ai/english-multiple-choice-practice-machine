<template>
  <teleport to="body">
    <transition name="popover">
      <div
        v-if="visible && wordData"
        class="quick-word-bubble"
        :style="{ top: `${pos.y}px`, left: `${pos.x}px` }"
        ref="bubbleRef"
      >
        <div class="bubble-header">
          <div class="word-phonetic-row">
            <span class="bubble-word">{{ wordData.word }}</span>
            <span class="bubble-phonetic" v-if="wordData.phonetic">/{{ wordData.phonetic }}/</span>
          </div>
          <button class="bubble-close" @click="close">✕</button>
        </div>

        <div class="bubble-meaning">
          {{ wordData.translation || wordData.definition_en || '暂无释义' }}
        </div>

        <!-- 真题语境原句 -->
        <div class="bubble-context" v-if="wordData.occurrences && wordData.occurrences.length > 0">
          <div class="context-label">✦ 真题语境原句：</div>
          <div class="context-sentence">
            "{{ wordData.occurrences[0].sentence }}"
          </div>
        </div>

        <div class="bubble-footer">
          <button
            class="collect-btn"
            :class="{ saved: isSaved }"
            @click="toggleSaveWord"
          >
            {{ isSaved ? '✓ 已入生词本' : '+ 收入生词本' }}
          </button>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

interface WordData {
  found: boolean
  word: string
  phonetic?: string
  translation?: string
  definition_en?: string
  occurrences?: Array<{ sentence: string; title: string }>
}

const visible = ref(false)
const pos = ref({ x: 0, y: 0 })
const wordData = ref<WordData | null>(null)
const isSaved = ref(false)
const bubbleRef = ref<HTMLDivElement | null>(null)

const showForSelection = async (word: string, x: number, y: number) => {
  const clean = word.trim().replace(/^[^a-zA-Z]+|[^a-zA-Z]+$/g, '')
  if (!clean || clean.length < 2) return

  // 视口边界自适应
  const bubbleWidth = 280
  const bubbleHeight = 160
  let targetX = x - bubbleWidth / 2
  let targetY = y - bubbleHeight - 12

  if (targetX < 12) targetX = 12
  if (targetX + bubbleWidth > window.innerWidth - 12) {
    targetX = window.innerWidth - bubbleWidth - 12
  }
  if (targetY < 12) {
    targetY = y + 24 // 翻转到底部
  }

  pos.value = { x: targetX, y: targetY }
  isSaved.value = false

  try {
    const res = await fetch('/api/search/quick-word', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word: clean }),
    })
    if (res.ok) {
      const data = await res.json()
      wordData.value = data
      visible.value = true
    }
  } catch (err) {
    console.error('划词查询失败', err)
  }
}

const close = () => {
  visible.value = false
}

const toggleSaveWord = async () => {
  if (!wordData.value) return
  try {
    await fetch('/api/vocabulary/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        word: wordData.value.word,
        phonetic: wordData.value.phonetic,
        translation: wordData.value.translation,
      }),
    })
    isSaved.value = true
  } catch {
    isSaved.value = true // 本地降级反馈
  }
}

const handleDocumentClick = (e: MouseEvent) => {
  if (bubbleRef.value && !bubbleRef.value.contains(e.target as Node)) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handleDocumentClick)
})

defineExpose({
  showForSelection,
  close,
})
</script>

<style scoped>
.quick-word-bubble {
  position: fixed;
  z-index: 9999;
  width: 290px;
  background: rgba(253, 250, 243, 0.96);
  backdrop-filter: blur(12px);
  border: 1px solid var(--line-strong, #cfc7b6);
  border-radius: var(--radius-md, 14px);
  padding: 14px;
  box-shadow: 0 12px 32px rgba(46, 42, 35, 0.15);
  user-select: text;
  font-family: inherit;
}

.bubble-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.word-phonetic-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.bubble-word {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink, #2e2a23);
}

.bubble-phonetic {
  font-size: 12px;
  color: var(--muted, #6b665c);
  font-family: var(--font-en-serif, serif);
}

.bubble-close {
  background: none;
  border: none;
  color: var(--muted, #6b665c);
  cursor: pointer;
  font-size: 13px;
  padding: 2px;
}

.bubble-meaning {
  font-size: 13px;
  color: var(--ink, #2e2a23);
  line-height: 1.4;
  margin-bottom: 8px;
}

.bubble-context {
  background: rgba(46, 42, 35, 0.04);
  border-radius: 6px;
  padding: 6px 8px;
  margin-bottom: 10px;
}

.context-label {
  font-size: 11px;
  color: var(--accent-bamboo, #4a5f4e);
  font-weight: 600;
  margin-bottom: 2px;
}

.context-sentence {
  font-size: 12px;
  color: var(--muted, #6b665c);
  font-style: italic;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.bubble-footer {
  display: flex;
  justify-content: flex-end;
}

.collect-btn {
  padding: 4px 12px;
  border-radius: 9999px;
  border: 1px solid var(--line, #e4ded1);
  background: var(--surface, #fdfaf3);
  color: var(--ink, #2e2a23);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.collect-btn:hover {
  background: var(--primary-soft, #eae6dc);
}

.collect-btn.saved {
  background: var(--accent-bamboo, #4a5f4e);
  color: #fff;
  border-color: var(--accent-bamboo, #4a5f4e);
}

.popover-enter-active,
.popover-leave-active {
  transition: all 0.18s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.popover-enter-from,
.popover-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.95);
}
</style>
