<script setup lang="ts">
// 单词听写模式 — 听发音 → 拼写 → 判分
// 参考: 不背单词"随身听" + 墨墨听写 (研究 2026-08)
import { Check, RefreshCw, Volume2, X } from 'lucide-vue-next'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps<{ words: any[] }>()
const emit = defineEmits<{ close: [] }>()

const idx = ref(0)
const input = ref('')
const result = ref<'correct' | 'wrong' | null>(null)
const correctCount = ref(0)
const wrongCount = ref(0)
const skipped = ref(0)
const finished = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const words = computed(() => props.words || [])
const current = computed(() => words.value[idx.value] || null)

const supported = typeof window !== 'undefined' && 'speechSynthesis' in window

function speak(text: string) {
  if (!supported) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'en-US'
  u.rate = 0.85
  const voices = window.speechSynthesis.getVoices()
  const en = voices.find(v => /en[-_]US/i.test(v.lang))
  if (en) u.voice = en
  window.speechSynthesis.speak(u)
}

function playWord() {
  if (current.value) speak(current.value.term)
}

function playSentence() {
  if (current.value?.latest_sentence) speak(current.value.latest_sentence)
}

function check() {
  if (result.value) return
  const ans = (current.value?.term || '').trim().toLowerCase()
  const guess = input.value.trim().toLowerCase()
  if (!guess) { playWord(); return }
  if (guess === ans) {
    result.value = 'correct'
    correctCount.value++
  } else {
    result.value = 'wrong'
    wrongCount.value++
  }
}

function next() {
  if (idx.value >= words.value.length - 1) {
    finished.value = true
    emit('close')
    return
  }
  idx.value++
  input.value = ''
  result.value = null
  nextTick(() => { inputRef.value?.focus(); playWord() })
}

function skip() {
  skipped.value++
  result.value = 'wrong'
  next()
}

function restart() {
  idx.value = 0
  correctCount.value = 0
  wrongCount.value = 0
  skipped.value = 0
  finished.value = false
  input.value = ''
  result.value = null
  nextTick(() => { inputRef.value?.focus(); playWord() })
}

function onKey(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    if (!result.value) check()
    else next()
  }
}

watch(current, () => {
  input.value = ''
  result.value = null
})

onMounted(() => {
  nextTick(() => {
    inputRef.value?.focus()
    if (words.value.length) playWord()
  })
})

onUnmounted(() => { window.speechSynthesis?.cancel() })

const accuracy = computed(() => {
  const done = correctCount.value + wrongCount.value
  return done ? Math.round(correctCount.value / done * 100) : 0
})
</script>

<template>
  <div class="dictation-overlay">
    <div class="dictation-card">
      <header class="dictation-header">
        <div>
          <h3>🎧 听写模式</h3>
          <span class="muted">{{ idx + 1 }} / {{ words.length }}</span>
        </div>
        <button class="button ghost compact" @click="emit('close')"><X :size="16" />退出</button>
      </header>

      <div class="dictation-body">
        <div class="dictation-progress">
          <div class="progress-bar"><div class="progress-fill" :style="{ width: (idx / words.length * 100) + '%' }"></div></div>
        </div>

        <div v-if="current" class="dictation-question">
          <div class="dictation-sound" @click="playWord">
            <Volume2 :size="48" />
            <span>点击重听发音</span>
          </div>

          <input
            ref="inputRef"
            v-model="input"
            class="dictation-input"
            :class="result ? (result === 'correct' ? 'ok' : 'bad') : ''"
            :disabled="!!result"
            placeholder="输入你听到的单词…"
            @keyup="onKey"
          />

          <div v-if="result" class="dictation-result" :class="result">
            <template v-if="result === 'correct'">
              <Check :size="18" /> 正确！
            </template>
            <template v-else>
              <X :size="18" /> 正确答案：<strong>{{ current.term }}</strong>
              <span class="meaning">{{ current.common_meaning || current.contextual_meaning }}</span>
            </template>
            <button class="dictation-listen" @click="playWord">🔊 再听一遍</button>
          </div>

          <div v-if="current.latest_sentence" class="dictation-sentence">
            <button class="button ghost compact" @click="playSentence">🔊 听例句</button>
            <p>{{ current.latest_sentence }}</p>
          </div>

          <div class="dictation-actions">
            <button v-if="!result" class="button ghost" @click="skip">跳过</button>
            <button v-if="!result" class="button" @click="check">检查拼写</button>
            <button v-else class="button" @click="next">下一词</button>
          </div>
        </div>

        <div v-else class="dictation-empty">没有可听写的单词</div>
      </div>

      <footer class="dictation-footer">
        <span class="ok-count">✅ {{ correctCount }}</span>
        <span class="bad-count">❌ {{ wrongCount }}</span>
        <span class="muted">准确率 {{ accuracy }}%</span>
        <button v-if="finished" class="button compact" @click="restart"><RefreshCw :size="15" />再来一轮</button>
      </footer>
    </div>
  </div>
</template>
