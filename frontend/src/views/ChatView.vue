<script setup lang="ts">
// v10.1: 学习陪伴聊天室（Phase 3 前端）——REST 拉历史 + WebSocket 实时收发 + @阿墨 流式回复
import { Bot, LoaderCircle, Send, UserRound } from 'lucide-vue-next'
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { get, getToken } from '../api'

// ── 消息类型（REST 历史是 snake_case，WS 广播是 camelCase，统一成内部结构）──
type ChatMessage = {
  key: string            // 列表渲染 key（历史用 id，乐观/流式消息用 clientId/requestId）
  id?: number
  senderType: 'user' | 'ai'
  senderName: string
  content: string
  createdAt?: string
  clientId?: string      // 乐观消息去重用
  streaming?: boolean    // 阿墨流式输出中
  error?: boolean        // ai_error 标记
}

// ── WS 地址推导（与 api.ts 的 API_ROOT 取值逻辑保持一致；api.ts 未导出故在此复刻）──
// 构建时注入 VITE_API_ROOT（手机 APK 指向 PC 局域网 IP）时，WS 也必须走同一台主机
const API_ROOT = (import.meta.env.VITE_API_ROOT as string | undefined) || '/api'
function buildWsUrl(): string {
  let httpRoot: string
  if (API_ROOT.startsWith('http://') || API_ROOT.startsWith('https://')) {
    httpRoot = API_ROOT
  } else {
    // 相对路径（默认 /api）→ 用当前页面源推导
    httpRoot = `${location.protocol}//${location.host}${API_ROOT}`
  }
  const wsRoot = httpRoot.replace(/^http/, 'ws')
  const token = getToken()
  // 后端启用 EPM_AUTH 时从 query token 鉴权（浏览器 WS 无法自定义 Header）
  return `${wsRoot}/chat/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`
}

const messages = ref<ChatMessage[]>([])
const input = ref('')
const online = ref(0)
const connected = ref(false)
const loadingHistory = ref(true)
const loadError = ref('')
const messageList = ref<HTMLElement | null>(null)

let ws: WebSocket | null = null
let pingTimer: number | null = null
let reconnectTimer: number | null = null
let reconnectDelay = 1000
let disposed = false
let optimisticSeq = 0

// ── 滚动到底部（新消息/流式追加时调用）──
async function scrollToBottom() {
  await nextTick()
  const el = messageList.value
  if (el) el.scrollTop = el.scrollHeight
}

function formatTime(iso?: string): string {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

// ── REST 拉取历史消息 ──
async function loadHistory() {
  loadingHistory.value = true
  loadError.value = ''
  try {
    const list = await get<any[]>('/chat/messages')
    messages.value = (list || []).map(item => ({
      key: `h-${item.id}`,
      id: item.id,
      senderType: item.sender_type === 'ai' ? 'ai' : 'user',
      senderName: item.sender_name || (item.sender_type === 'ai' ? '阿墨' : '你'),
      content: item.content || '',
      createdAt: item.created_at,
    }))
    scrollToBottom()
  } catch {
    loadError.value = '聊天记录暂时没有加载成功，请稍后重试。'
  } finally {
    loadingHistory.value = false
  }
}

// ── WS 事件处理 ──
function findStreaming(requestId: string): ChatMessage | undefined {
  return messages.value.find(m => m.key === `ai-${requestId}`)
}

function handleEvent(event: any) {
  switch (event?.type) {
    case 'presence':
      online.value = Number(event.online) || 0
      break
    case 'message': {
      // 自己刚发的消息回显：按 clientId 替换乐观消息，避免重复
      if (event.clientId) {
        const optimistic = messages.value.find(m => m.clientId === event.clientId)
        if (optimistic) {
          optimistic.id = event.id
          optimistic.key = `h-${event.id}`
          optimistic.createdAt = event.createdAt
          optimistic.senderName = event.senderName || optimistic.senderName
          scrollToBottom()
          return
        }
      }
      messages.value.push({
        key: `h-${event.id}`,
        id: event.id,
        senderType: event.senderType === 'ai' ? 'ai' : 'user',
        senderName: event.senderName || '研友',
        content: event.content || '',
        createdAt: event.createdAt,
      })
      scrollToBottom()
      break
    }
    case 'ai_start':
      // 阿墨开始回复：插入流式占位消息（同一 requestId 只插一次）
      if (!findStreaming(event.requestId)) {
        messages.value.push({
          key: `ai-${event.requestId}`,
          senderType: 'ai',
          senderName: event.senderName || '阿墨',
          content: '',
          streaming: true,
        })
        scrollToBottom()
      }
      break
    case 'ai_delta': {
      // 逐段追加到同一条阿墨消息上（打字机效果）
      const target = findStreaming(event.requestId)
      if (target) {
        target.content += event.content || ''
        scrollToBottom()
      }
      break
    }
    case 'ai_done': {
      const target = findStreaming(event.requestId)
      if (target) {
        target.content = event.fullContent || target.content
        target.id = event.messageId
        target.key = `h-${event.messageId}`
        target.createdAt = event.createdAt
        target.streaming = false
      } else {
        // 没收到 start/delta（例如中途进房），直接补一条完整消息
        messages.value.push({
          key: `h-${event.messageId}`,
          id: event.messageId,
          senderType: 'ai',
          senderName: event.senderName || '阿墨',
          content: event.fullContent || '',
          createdAt: event.createdAt,
        })
      }
      scrollToBottom()
      break
    }
    case 'ai_error': {
      const target = findStreaming(event.requestId)
      if (target) {
        target.content = event.error || '阿墨暂时没连上，请稍后再试'
        target.streaming = false
        target.error = true
      } else {
        messages.value.push({
          key: `err-${event.requestId}`,
          senderType: 'ai',
          senderName: '阿墨',
          content: event.error || '阿墨暂时没连上，请稍后再试',
          error: true,
        })
      }
      scrollToBottom()
      break
    }
    case 'pong':
      break
    default:
      break
  }
}

// ── WS 连接（含心跳与自动重连）──
function clearTimers() {
  if (pingTimer !== null) { window.clearInterval(pingTimer); pingTimer = null }
  if (reconnectTimer !== null) { window.clearTimeout(reconnectTimer); reconnectTimer = null }
}

function connect() {
  if (disposed) return
  try {
    ws = new WebSocket(buildWsUrl())
  } catch {
    scheduleReconnect()
    return
  }
  ws.onopen = () => {
    connected.value = true
    reconnectDelay = 1000
    // 每 30s 心跳保活
    if (pingTimer !== null) window.clearInterval(pingTimer)
    pingTimer = window.setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'ping' }))
    }, 30000)
  }
  ws.onmessage = e => {
    try {
      handleEvent(JSON.parse(e.data))
    } catch {
      // 忽略非 JSON 帧
    }
  }
  ws.onclose = () => {
    connected.value = false
    online.value = 0
    if (pingTimer !== null) { window.clearInterval(pingTimer); pingTimer = null }
    scheduleReconnect()
  }
  ws.onerror = () => {
    // onclose 会随后触发，统一在那里重连
  }
}

function scheduleReconnect() {
  if (disposed || reconnectTimer !== null) return
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    connect()
  }, reconnectDelay)
  reconnectDelay = Math.min(reconnectDelay * 2, 15000)
}

// ── 发送消息 ──
function send() {
  const content = input.value.trim()
  if (!content) return
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    loadError.value = '聊天室连接中，请稍候再发送。'
    return
  }
  loadError.value = ''
  const clientId = `c-${Date.now()}-${++optimisticSeq}`
  // 乐观上屏：立即显示自己的消息，收到广播回显后替换
  messages.value.push({
    key: clientId,
    clientId,
    senderType: 'user',
    senderName: '你',
    content,
    createdAt: new Date().toISOString(),
  })
  ws.send(JSON.stringify({ type: 'message', clientId, content }))
  input.value = ''
  scrollToBottom()
}

function onKeydown(e: KeyboardEvent) {
  // 回车发送，Shift+Enter 换行；输入法组合中不触发
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    send()
  }
}

onMounted(() => {
  void loadHistory()
  connect()
})

onBeforeUnmount(() => {
  disposed = true
  clearTimers()
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
})
</script>

<template>
  <div class="page chat-page">
    <!-- 顶部：标题 + 在线人数/连接状态 -->
    <header class="chat-header">
      <div class="chat-title">
        <span class="chat-seal" aria-hidden="true">聊</span>
        <div>
          <h1>学习聊天室</h1>
          <p class="chat-sub">
            <template v-if="connected">🟢 {{ online }} 人在线</template>
            <template v-else>⚪ 连接中…</template>
          </p>
        </div>
      </div>
      <p class="chat-tip">输入 @阿墨 可召唤阿墨解答问题</p>
    </header>

    <!-- 消息列表 -->
    <div ref="messageList" class="chat-list">
      <div v-if="loadingHistory" class="chat-state">
        <LoaderCircle :size="20" class="spin" aria-hidden="true" /> 正在翻开聊天记录…
      </div>
      <div v-else-if="loadError && !messages.length" class="chat-state error">{{ loadError }}</div>
      <div v-else-if="!messages.length" class="chat-state">
        还没有消息，来第一句吧 —— @阿墨 可以召唤阿墨陪你学习。
      </div>

      <div
        v-for="msg in messages"
        :key="msg.key"
        class="chat-row"
        :class="msg.senderType === 'user' ? 'row-user' : 'row-ai'"
      >
        <span class="chat-avatar" :class="msg.senderType" aria-hidden="true">
          <Bot v-if="msg.senderType === 'ai'" :size="16" />
          <UserRound v-else :size="16" />
        </span>
        <div class="chat-bubble-wrap">
          <span class="chat-meta">
            {{ msg.senderName }}<template v-if="msg.createdAt"> · {{ formatTime(msg.createdAt) }}</template>
          </span>
          <div class="chat-bubble" :class="{ streaming: msg.streaming, error: msg.error }">
            <span v-if="msg.streaming && !msg.content" class="typing">
              <LoaderCircle :size="14" class="spin" aria-hidden="true" /> 阿墨正在输入…
            </span>
            <span class="bubble-text">{{ msg.content }}</span><span v-if="msg.streaming && msg.content" class="cursor">▍</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <footer class="chat-input-bar">
      <textarea
        v-model="input"
        class="chat-input"
        rows="1"
        placeholder="说点什么… 输入 @阿墨 可召唤阿墨"
        @keydown="onKeydown"
      ></textarea>
      <button
        class="chat-send"
        type="button"
        :disabled="!input.trim()"
        aria-label="发送"
        @click="send"
      >
        <Send :size="17" aria-hidden="true" />
      </button>
    </footer>
    <p v-if="loadError && messages.length" class="chat-inline-error">{{ loadError }}</p>
  </div>
</template>

<style scoped>
/* 水墨文人书房主题——只用全局 CSS 变量，深浅色模式自动适配 */
.chat-page {
  display: flex;
  flex-direction: column;
  /* 撑满可视高度（扣除页面自身 padding），消息区内部滚动 */
  height: calc(100vh - 114px);
  max-width: 860px;
}

.chat-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  flex-shrink: 0;
}

.chat-title { display: flex; align-items: center; gap: 12px; }

.chat-seal {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--accent);
  color: #f8f5ef;
  font-family: "Kaiti SC", "STKaiti", "楷体", serif;
  font-size: 20px;
  font-weight: 700;
  flex-shrink: 0;
}

.chat-title h1 { font-size: 24px; margin: 0; }

.chat-sub { margin: 2px 0 0; font-size: 12px; color: var(--muted); }

.chat-tip { margin: 0; font-size: 12px; color: var(--muted); }

/* 消息列表 */
.chat-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  background: var(--primary-faint);
  border: 1px solid var(--primary-soft);
  border-radius: 14px;
}

.chat-state {
  margin: auto;
  color: var(--muted);
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: center;
  padding: 24px 12px;
}

.chat-state.error { color: var(--accent); }

.chat-row { display: flex; gap: 8px; max-width: 100%; }

.row-user { flex-direction: row-reverse; }

.chat-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  margin-top: 2px;
}

.chat-avatar.ai { background: var(--primary-soft); color: var(--primary); }
.chat-avatar.user { background: var(--primary); color: var(--primary-faint); }

.chat-bubble-wrap {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: min(78%, 560px);
}

.row-user .chat-bubble-wrap { align-items: flex-end; }
.row-ai .chat-bubble-wrap { align-items: flex-start; }

.chat-meta { font-size: 11px; color: var(--muted); }

.chat-bubble {
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
}

.row-ai .chat-bubble {
  background: var(--primary-soft);
  color: var(--ink);
  border-top-left-radius: 4px;
}

.row-user .chat-bubble {
  background: var(--primary);
  color: var(--primary-faint);
  border-top-right-radius: 4px;
}

.chat-bubble.error { background: var(--accent-soft); color: var(--accent); }

.bubble-text:empty { display: none; }

.typing { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 13px; }

.cursor {
  display: inline-block;
  margin-left: 1px;
  animation: blink 0.9s steps(2) infinite;
  color: var(--muted);
}

@keyframes blink { 50% { opacity: 0; } }

.spin { animation: rotate 1s linear infinite; }
@keyframes rotate { to { transform: rotate(360deg); } }

/* 输入区 */
.chat-input-bar {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  margin-top: 12px;
  padding: 10px 12px;
  background: var(--primary-faint);
  border: 1px solid var(--primary-soft);
  border-radius: 14px;
  flex-shrink: 0;
}

.chat-input {
  flex: 1;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--ink);
  font-size: 14px;
  line-height: 1.6;
  max-height: 120px;
  font-family: inherit;
}

.chat-input::placeholder { color: var(--muted); }

.chat-send {
  width: 38px;
  height: 38px;
  border: none;
  border-radius: 10px;
  background: var(--accent);
  color: #f8f5ef;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.15s;
  flex-shrink: 0;
}

.chat-send:hover:not(:disabled) { transform: translateY(-1px); }
.chat-send:disabled { opacity: 0.45; cursor: not-allowed; }

.chat-inline-error { margin: 8px 2px 0; font-size: 12px; color: var(--accent); flex-shrink: 0; }

/* 移动端适配：矮窗口收紧边距，底部留出移动导航高度 */
@media (max-width: 980px) {
  .chat-page { height: calc(100vh - 190px); }
  .chat-tip { display: none; }
  .chat-title h1 { font-size: 20px; }
}

@media (max-width: 560px) {
  .chat-bubble-wrap { max-width: 86%; }
  .chat-list { padding: 12px; }
}
</style>
