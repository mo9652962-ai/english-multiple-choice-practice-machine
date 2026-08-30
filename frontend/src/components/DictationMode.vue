<script setup lang="ts">
// 单词听写模式 — 听发音 → 拼写 → 判分
// 参考: 不背单词"随身听" + 墨墨听写 (研究 2026-08)
import { Check, RefreshCw, Volume2, X } from 'lucide-vue-next'
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { speak, stop as stopTts } from '../services/tts'

const props = defineProps<{ /** 要听写的单词列表（每项含 word/en/phonetic 等字段）*/ words: any[] }>()
const emit = defineEmits<{ close: [] }>()

const idx = ref(0)
const input = ref('')
const mode = ref<'choice' | 'spell'>('choice') // v3.3: 默认选择题（听音选词）——可切拼写
const result = ref<'correct' | 'wrong' | null>(null)
const correctCount = ref(0)
const wrongCount = ref(0)
const skipped = ref(0)
const finished = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

const words = computed(() => props.words || [])
const current = computed(() => words.value[idx.value] || null)

// v3.4: 统一 TTS 服务（原生 Capacitor 优先，修复 Android WebView 无声）
async function playWordSound(text: string) {
  try {
    await speak(text, 0.85)
  } catch { /* ignore */ }
}

function playWord() {
  if (current.value) playWordSound(current.value.term)
}

function playSentence() {
  if (current.value?.latest_sentence) playWordSound(current.value.latest_sentence)
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

// v3.3: 选择题模式——听音选词
function choose(opt: string) {
  if (result.value || !current.value) return
  if (opt === current.value.term) {
    result.value = 'correct'
    correctCount.value++
  } else {
    result.value = 'wrong'
    wrongCount.value++
  }
}

function switchMode(m: 'choice' | 'spell') {
  if (mode.value === m) return
  mode.value = m
  result.value = null
  input.value = ''
  nextTick(() => { if (m === 'spell') inputRef.value?.focus() })
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

onUnmounted(() => { stopTts() })

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
        <div class="dictation-mode-switch">
          <button class="button ghost compact" :class="{ active: mode === 'choice' }" @click="switchMode('choice')">选择题</button>
          <button class="button ghost compact" :class="{ active: mode === 'spell' }" @click="switchMode('spell')">拼写</button>
          <button class="button ghost compact" @click="emit('close')"><X :size="16" />退出</button>
        </div>
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
            v-if="mode === 'spell'"
            ref="inputRef"
            v-model="input"
            class="dictation-input"
            :class="result ? (result === 'correct' ? 'ok' : 'bad') : ''"
            :disabled="!!result"
            placeholder="输入你听到的单词…"
            @keyup="onKey"
          />

          <!-- v3.3: 选择题模式——听音选词 -->
          <div v-if="mode === 'choice'" class="dictation-options">
            <button
              v-for="opt in current.options || []"
              :key="opt"
              class="dictation-option"
              :class="{ picked: result && opt === current.term, wrong: result && opt !== current.term && result === 'wrong' }"
              :disabled="!!result"
              @click="choose(opt)"
            >{{ opt }}</button>
            <p v-if="!current.options?.length" class="muted">选项生成中…</p>
          </div>

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
