<script setup lang="ts">
// TTS 朗读按钮 — 浏览器原生 Web Speech API（零依赖）
// 参考: Edge 沉浸式阅读器"朗读"、TTSReader
// 用法: <TtsButton :text="'Hello world'" :speed="0.9" />

import { onBeforeUnmount, ref } from 'vue'

const props = withDefaults(defineProps<{
  text: string
  speed?: number
  size?: number
}>(), {
  speed: 0.9,
  size: 16,
})

const speaking = ref(false)
const supported = typeof window !== 'undefined' && 'speechSynthesis' in window

let utterance: SpeechSynthesisUtterance | null = null

function stop() {
  if (!supported) return
  window.speechSynthesis.cancel()
  speaking.value = false
}

function toggle() {
  if (!supported) return
  if (speaking.value) {
    stop()
    return
  }
  const clean = props.text
    .replace(/<[^>]+>/g, ' ')       // 去 HTML 标签
    .replace(/\s+/g, ' ')
    .trim()
  if (!clean) return

  window.speechSynthesis.cancel()   // 清除排队
  utterance = new SpeechSynthesisUtterance(clean)
  utterance.lang = 'en-US'
  utterance.rate = props.speed

  // 优先选美音
  const voices = window.speechSynthesis.getVoices()
  const en = voices.find(v => /en[-_]US/i.test(v.lang) && /female|samantha|zira|google us/i.test(v.name))
    || voices.find(v => /en[-_]US/i.test(v.lang))
  if (en) utterance.voice = en

  utterance.onend = () => { speaking.value = false }
  utterance.onerror = () => { speaking.value = false }

  window.speechSynthesis.speak(utterance)
  speaking.value = true
}

// 某些浏览器 voices 异步加载
if (supported) {
  window.speechSynthesis.onvoiceschanged = () => {
    if (utterance) {
      const voices = window.speechSynthesis.getVoices()
      const en = voices.find(v => /en[-_]US/i.test(v.lang))
      if (en) utterance.voice = en
    }
  }
}

onBeforeUnmount(stop)
</script>

<template>
  <button
    v-if="supported"
    class="tts-btn"
    :class="{ speaking }"
    type="button"
    :title="speaking ? '停止朗读' : '朗读'"
    @click="toggle"
  >
    <svg :width="props.size" :height="props.size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <polygon v-if="!speaking" points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" fill="currentColor" stroke="none" />
      <path v-if="!speaking" d="M15.54 8.46a5 5 0 0 1 0 7.07" />
      <path v-if="!speaking" d="M19.07 4.93a10 10 0 0 1 0 14.14" />
      <line v-if="speaking" x1="4" y1="12" x2="8" y2="12" />
      <line v-if="speaking" x1="4" y1="16" x2="10" y2="16" />
    </svg>
  </button>
</template>

<style scoped>
.tts-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--line, #e0e0e0);
  background: var(--surface-2, #f5f5f5);
  color: var(--text-dim, #666);
  cursor: pointer;
  transition: all .15s ease;
  padding: 0;
  flex-shrink: 0;
}
.tts-btn:hover {
  border-color: var(--accent, #2d8a3a);
  color: var(--accent, #2d8a3a);
}
.tts-btn.speaking {
  color: #fff;
  background: var(--accent, #2d8a3a);
  border-color: var(--accent, #2d8a3a);
  animation: tts-pulse 1.2s ease-in-out infinite;
}
@keyframes tts-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(45, 138, 58, .3); }
  50% { box-shadow: 0 0 0 6px rgba(45, 138, 58, 0); }
}
</style>
