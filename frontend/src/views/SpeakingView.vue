<template>
  <div class="page speaking-page">
    <div class="page-head">
      <h2>🎧 AI 口语陪练</h2>
      <p class="muted">考研复试仿真 · 日常流利度 · 发音纠偏 —— 浏览器原生语音（零服务器开销）</p>
    </div>

    <!-- 场景选择 -->
    <div v-if="!session" class="speaking-scenarios">
      <button v-for="s in scenarios" :key="s.id" class="card scenario-card" @click="startSession(s.id)">
        <h3>{{ s.label }}</h3>
        <p>{{ s.desc }}</p>
        <span class="scenario-stamp">{{ s.stamp }}</span>
      </button>
    </div>

    <!-- 对话界面 -->
    <div v-else class="speaking-room">
      <div class="card speaking-orbit-card">
        <div class="orbit-wrap" :class="{ speaking: listening || speaking }">
          <div class="orbit-ring ring-1"></div>
          <div class="orbit-ring ring-2"></div>
          <div class="orbit-core">{{ listening ? '🎙' : '🤝' }}</div>
        </div>
        <div class="orbit-status">
          {{ listening ? '倾听中…' : (speaking ? '考官播报中…' : '点击按钮或按空格说话') }}
        </div>
      </div>

      <!-- 对话流 -->
      <div class="card conversation-card">
        <div v-for="(t, i) in turns" :key="i" class="turn-block">
          <!-- 考官开场/回应 -->
          <div v-if="t.role === 'assistant'" class="bubble examiner">
            <p class="bubble-text">{{ t.content }}</p>
            <button v-if="t.audio" class="bubble-audio" @click="speakText(t.content)">🔊 重听</button>
          </div>
          <!-- 学生回答 -->
          <div v-else class="bubble student">
            <p class="bubble-text">{{ t.content }}</p>
            <div v-if="t.feedback?.grammar_corrections?.length" class="correction-box">
              <div v-for="(c, j) in t.feedback.grammar_corrections" :key="j" class="correction-item">
                <span class="corr-orig"><s>{{ c.original }}</s></span> → <span class="corr-new">{{ c.corrected }}</span>
                <span class="corr-reason">{{ c.reason }}</span>
              </div>
            </div>
            <p v-if="t.feedback?.native_upgrade" class="native-upgrade">✨ {{ t.feedback.native_upgrade }}</p>
          </div>
        </div>

        <!-- 输入区 -->
        <div class="speaking-input">
          <button class="mic-btn" :class="{ active: listening }" @click="toggleListen" :disabled="speaking">
            {{ listening ? '⏹ 完成' : '🎙 按住说话' }}
          </button>
          <input v-model="textInput" class="text-input" placeholder="或直接输入英文回答…" @keyup.enter="sendTurn()" :disabled="listening || speaking" />
          <button class="button send-btn" @click="sendTurn()" :disabled="!textInput.trim() || listening || speaking">发送</button>
        </div>
        <div class="speaking-actions">
          <button class="button ghost compact" @click="finish">📜 结束并评分</button>
          <span class="hint">PC 端按 <kbd>Space</kbd> 开始/停止录音</span>
        </div>
      </div>
    </div>

    <!-- 结课报告 -->
    <div v-if="report" class="card speaking-report">
      <h3>📜 口语诊断报告</h3>
      <div class="report-grid">
        <div v-for="(v, k) in report.dimensions" :key="k" class="report-dim">
          <span class="dim-label">{{ dimLabel(String(k)) }}</span>
          <div class="dim-track ink-progress-track"><div class="dim-fill ink-progress-bar" :style="{ width: v + '%' }"></div></div>
          <span class="dim-score">{{ v }}</span>
        </div>
      </div>
      <p class="report-summary">{{ report.summary }}</p>
      <!-- v9.28: Gemini batch5 任务4——本场亮点表达 -->
      <div v-if="nativeHighlights.length" class="native-highlights">
        <h4>✨ 本场 Native 亮点表达</h4>
        <div v-for="(h, i) in nativeHighlights" :key="i" class="native-highlight-item">{{ h }}</div>
      </div>
      <button class="button ghost" @click="resetAll">再来一场</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { get, post } from '../api'

const scenarios = [
  { id: 'graduate_interview', label: '考研复试仿真', desc: '个人陈述 / 专业问答 / 时事抽题', stamp: '复试' },
  { id: 'daily_fluency', label: '日常流利度', desc: '轻松话题 · 自由表达练习', stamp: '流利' },
  { id: 'pronunciation', label: '发音纠偏', desc: '绕口令跟读 · 音素纠正', stamp: '纠音' },
]

const session = ref<any>(null)
const turns = ref<any[]>([])
const textInput = ref('')
const listening = ref(false)
const speaking = ref(false)
const report = ref<any>(null)
const nativeHighlights = ref<string[]>([])

const dimLabel = (k: string) => ({ fluency: '流畅度', grammar: '语法', vocabulary: '词汇', coherence: '连贯' }[k] || k)

// ── Web Speech API（浏览器原生，零服务器开销）──
const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
let recognition: any = null
if (SpeechRecognition) {
  recognition = new SpeechRecognition()
  recognition.lang = 'en-US'
  recognition.interimResults = false
  recognition.maxAlternatives = 1
  recognition.onresult = (e: any) => {
    const text = e.results?.[0]?.[0]?.transcript || ''
    listening.value = false
    if (text.trim()) {
      textInput.value = text
      sendTurn(text)
    }
  }
  recognition.onerror = () => { listening.value = false }
  recognition.onend = () => { listening.value = false }
}

function toggleListen() {
  if (!recognition) { alert('当前浏览器不支持语音识别，请使用文字输入（Chrome/Edge 支持）'); return }
  if (listening.value) { recognition.stop(); listening.value = false; return }
  recognition.start()
  listening.value = true
}

function speakText(text: string) {
  if (!('speechSynthesis' in window)) return
  speaking.value = true
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'en-US'
  u.rate = 0.95
  u.onend = () => { speaking.value = false }
  u.onerror = () => { speaking.value = false }
  window.speechSynthesis.speak(u)
}

// ── 会话 ──
async function startSession(scenarioId: string) {
  const s = await post<{ session_id: number; opening_message: { content: string } }>('/speaking/sessions', { scenario: scenarioId })
  session.value = s
  turns.value = [{ role: 'assistant', content: s.opening_message.content }]
  speakText(s.opening_message.content)
}

async function sendTurn(text?: string) {
  const content = (text ?? textInput.value).trim()
  if (!content || !session.value) return
  turns.value.push({ role: 'user', content, feedback: null })
  textInput.value = ''
  try {
    const r = await post<{ ai_reply: string; feedback: any }>(`/speaking/sessions/${session.value.session_id}/turns`, {
      user_text: content,
      duration_ms: 0,
    })
    // 更新最后一轮学生气泡的反馈
    turns.value[turns.value.length - 1].feedback = r.feedback
    turns.value.push({ role: 'assistant', content: r.ai_reply })
    speakText(r.ai_reply)
  } catch (e) {
    alert(String(e))
  }
}

async function finish() {
  if (!session.value) return
  report.value = await post(`/speaking/sessions/${session.value.session_id}/finish`)
  // v9.28: Gemini batch5 任务4——口语局后报告：汇总本场 Native 亮点表达
  nativeHighlights.value = turns.value
    .filter((t: any) => t.feedback?.native_upgrade)
    .map((t: any) => t.feedback.native_upgrade)
    .slice(-3)
}

function resetAll() {
  session.value = null
  turns.value = []
  report.value = null
  textInput.value = ''
}

// 空格键快捷录音
function onKeydown(e: KeyboardEvent) {
  if (e.code === 'Space' && session.value && !report.value && (e.target as HTMLElement)?.tagName !== 'INPUT' && (e.target as HTMLElement)?.tagName !== 'TEXTAREA') {
    e.preventDefault()
    toggleListen()
  }
}
window.addEventListener('keydown', onKeydown)
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.speaking-scenarios { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.scenario-card { text-align: left; cursor: pointer; transition: all 0.2s; }
.scenario-card:hover { transform: translateY(-3px); border-color: rgba(74, 95, 78, 0.3); box-shadow: var(--shadow-hover); }
.scenario-card h3 { font-family: var(--font-serif); font-size: 17px; color: var(--text-pine); margin-bottom: 8px; }
.scenario-card p { font-size: 13px; color: var(--text-faint); margin-bottom: 12px; }
.scenario-stamp { font-family: var(--font-serif); font-size: 11px; color: var(--accent-ochre); background: rgba(166, 122, 56, 0.08); border: 1px solid rgba(166, 122, 56, 0.2); border-radius: 4px; padding: 2px 8px; }

.speaking-room { display: flex; gap: 16px; flex-wrap: wrap; }
.speaking-orbit-card { flex: 0 0 260px; display: flex; flex-direction: column; align-items: center; padding: 28px 20px; }
.orbit-wrap { position: relative; width: 150px; height: 150px; }
.orbit-ring { position: absolute; inset: 0; border-radius: 50%; border: 1.5px solid rgba(60, 50, 40, 0.12); transition: all 0.4s; }
.ring-1 { animation: breathe 4s ease-in-out infinite; }
.ring-2 { inset: 18px; border-color: rgba(74, 95, 78, 0.25); animation: breathe 3s ease-in-out 0.5s infinite; }
.orbit-core { position: absolute; inset: 40px; border-radius: 50%; background: radial-gradient(circle, rgba(74, 95, 78, 0.18), rgba(74, 95, 78, 0.05)); display: flex; align-items: center; justify-content: center; font-size: 26px; }
.orbit-wrap.speaking .ring-1 { border-color: rgba(184, 74, 57, 0.4); animation-duration: 1.5s; }
.orbit-wrap.speaking .ring-2 { border-color: rgba(184, 74, 57, 0.3); animation-duration: 1s; }
@keyframes breathe { 0%, 100% { transform: scale(1); opacity: 0.8; } 50% { transform: scale(1.05); opacity: 0.4; } }
.orbit-status { margin-top: 16px; font-size: 13px; color: var(--text-faint); }

.conversation-card { flex: 1 1 420px; min-width: 340px; max-height: 70vh; overflow-y: auto; }
.turn-block { margin-bottom: 14px; }
.bubble { border-radius: 12px; padding: 12px 16px; max-width: 85%; }
.bubble.examiner { background: rgba(255, 252, 247, 0.9); border: 1px solid var(--border-paper); margin-right: auto; }
.bubble.student { background: rgba(74, 95, 78, 0.08); border: 1px solid rgba(74, 95, 78, 0.15); margin-left: auto; }
.bubble-text { font-size: 14px; line-height: 1.7; color: var(--text-pine); font-family: var(--font-en-serif), serif; }
.bubble-audio { background: none; border: none; color: var(--accent-bamboo); font-size: 12px; cursor: pointer; padding: 0; margin-top: 6px; }
.correction-box { margin-top: 10px; padding: 8px 12px; background: rgba(184, 74, 57, 0.05); border-left: 3px solid var(--accent-vermilion); border-radius: 0 8px 8px 0; }
.correction-item { font-size: 12px; color: var(--text-pine); margin-bottom: 4px; }
.corr-orig { color: var(--text-faint); }
.corr-new { color: var(--accent-bamboo); font-weight: 600; }
.corr-reason { display: block; color: var(--text-faint); font-size: 11px; }
.native-upgrade { margin-top: 8px; font-size: 12px; color: var(--accent-ochre); background: rgba(166, 122, 56, 0.06); border-radius: 8px; padding: 8px 10px; }

.speaking-input { display: flex; gap: 8px; margin-top: 14px; align-items: center; }
.mic-btn { border-radius: 9999px; padding: 8px 16px; border: 1px solid var(--border-paper); background: var(--bg-card); cursor: pointer; font-size: 13px; transition: all 0.2s; flex-shrink: 0; }
.mic-btn.active { background: var(--accent-vermilion); color: #FFFDF9; border-color: var(--accent-vermilion); }
.text-input { flex: 1; border: 1px solid var(--border-paper); border-radius: 9999px; padding: 8px 16px; font-size: 13px; background: rgba(255, 255, 255, 0.75); }
.text-input:focus { outline: none; border-color: var(--accent-vermilion); }
.send-btn { background: var(--accent-bamboo); color: #FFFDF9; border-radius: 9999px; }
.speaking-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
.hint { font-size: 11px; color: var(--text-muted); }

.speaking-report { margin-top: 20px; }
.report-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.report-dim { display: flex; align-items: center; gap: 10px; }
.dim-label { font-size: 13px; color: var(--text-faint); flex-shrink: 0; width: 44px; }
.dim-track { flex: 1; }
.dim-score { font-family: var(--font-en-serif); color: var(--accent-bamboo); font-weight: 600; }
.report-summary { margin-top: 14px; font-size: 14px; color: var(--text-pine); line-height: 1.7; }
.native-highlights { margin-top: 16px; padding: 12px 16px; background: rgba(166, 122, 56, 0.06); border: 1px solid rgba(166, 122, 56, 0.2); border-radius: 10px; }
.native-highlights h4 { font-family: var(--font-serif); font-size: 14px; color: var(--accent-ochre); margin-bottom: 8px; }
.native-highlight-item { font-size: 13px; color: var(--text-pine); padding: 5px 0; border-bottom: 1px dashed rgba(166, 122, 56, 0.15); }
.native-highlight-item:last-child { border-bottom: none; }
kbd { background: rgba(60, 50, 40, 0.06); border-radius: 4px; padding: 1px 6px; font-size: 11px; }
</style>
