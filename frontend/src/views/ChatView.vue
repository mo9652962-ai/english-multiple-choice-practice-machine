<script setup lang="ts">
// REST 历史记录 + WebSocket 实时收发 + @阿墨 流式回复
import { Bot, ChevronDown, LoaderCircle, Send, UserRound } from 'lucide-vue-next'
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { get, getToken, isOffline } from '../api'

type ChatMessage = {
  key: string
  id?: number
  senderType: 'user' | 'ai'
  senderName: string
  content: string
  createdAt?: string
  clientId?: string
  requestId?: string
  streaming?: boolean
  error?: boolean
}

type HistoryMessage = {
  id: number
  sender_type?: string
  sender_name?: string | null
  content?: string | null
  created_at?: string | null
}

type ChatEvent =
  | { type: 'presence'; online: number }
  | { type: 'message'; id: number; senderType: string; senderName?: string; content?: string; createdAt?: string; clientId?: string }
  | { type: 'ai_start'; requestId: string; senderName?: string }
  | { type: 'ai_delta'; requestId: string; content?: string }
  | { type: 'ai_done'; requestId: string; messageId: number; senderName?: string; fullContent?: string; createdAt?: string }
  | { type: 'ai_error'; requestId: string; error?: string }
  | { type: 'error'; error?: string }
  | { type: 'pong' }

const API_ROOT = (import.meta.env.VITE_API_ROOT as string | undefined) || '/api'

function buildWsUrl(): string {
  const httpRoot = /^https?:\/\//.test(API_ROOT)
    ? API_ROOT
    : `${location.protocol}//${location.host}${API_ROOT}`
  const token = getToken()
  return `${httpRoot.replace(/^http/, 'ws')}/chat/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`
}

const messages = ref<ChatMessage[]>([])
const input = ref('')
const online = ref(0)
const connected = ref(false)
const offlineMode = isOffline()
const loadingHistory = ref(true)
const historyLoaded = ref(false)
const loadError = ref('')
const messageList = ref<HTMLElement | null>(null)
const chatPage = ref<HTMLElement | null>(null)
const closeToBottom = ref(true)
const showLatestButton = ref(false)

let ws: WebSocket | null = null
let pingTimer: number | null = null
let reconnectTimer: number | null = null
let reconnectDelay = 1000
let disposed = false
let optimisticSeq = 0
let viewportObserver: ResizeObserver | null = null

function measureChatHeight() {
  const page = chatPage.value
  if (!page) return

  const viewport = window.visualViewport
  const visibleTop = viewport?.offsetTop ?? 0
  const visibleBottom = visibleTop + (viewport?.height ?? window.innerHeight)
  const pageTop = page.getBoundingClientRect().top
  let usableBottom = visibleBottom
  const mobileNav = document.querySelector<HTMLElement>('.mobile-nav')

  if (mobileNav) {
    const nav = mobileNav.getBoundingClientRect()
    if (nav.top < visibleBottom && nav.bottom > visibleTop) {
      usableBottom = Math.min(usableBottom, nav.top)
    }
  }

  page.style.setProperty('--chat-height', `${Math.max(0, usableBottom - pageTop - 12)}px`)
}

function onViewportChange() {
  measureChatHeight()
}

function onListScroll() {
  const list = messageList.value
  if (!list) return
  closeToBottom.value = list.scrollHeight - list.scrollTop - list.clientHeight < 88
  showLatestButton.value = !closeToBottom.value && messages.value.length > 0
}

async function scrollToBottom(force = false) {
  await nextTick()
  const list = messageList.value
  if (list && (force || closeToBottom.value)) {
    list.scrollTop = list.scrollHeight
    closeToBottom.value = true
    showLatestButton.value = false
  }
}

function formatTime(iso?: string): string {
  if (!iso) return ''
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return ''
  return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

function normalizeHistory(item: HistoryMessage): ChatMessage {
  return {
    key: `h-${item.id}`,
    id: item.id,
    senderType: item.sender_type === 'ai' ? 'ai' : 'user',
    senderName: item.sender_name || (item.sender_type === 'ai' ? '阿墨' : '你'),
    content: item.content || '',
    createdAt: item.created_at || undefined,
  }
}

async function loadHistory() {
  loadingHistory.value = true
  loadError.value = ''
  try {
    const list = await get<HistoryMessage[]>('/chat/messages')
    if (!Array.isArray(list)) throw new TypeError('聊天记录格式不正确')

    const history = list.filter(item => Number.isFinite(item?.id)).map(normalizeHistory)
    const historyIds = new Set(history.map(message => message.id))
    // A WebSocket event may arrive while REST is in flight; retain live messages.
    const liveOnly = messages.value.filter(message => !message.id || !historyIds.has(message.id))
    messages.value = [...history, ...liveOnly]
    historyLoaded.value = true
    await scrollToBottom(true)
  } catch {
    loadError.value = '聊天记录暂时没有加载成功，请重试。'
  } finally {
    loadingHistory.value = false
  }
}

function findStreaming(requestId: string) {
  return messages.value.find(message => message.requestId === requestId)
}

function handleEvent(event: ChatEvent) {
  switch (event.type) {
    case 'presence':
      online.value = Math.max(0, Number(event.online) || 0)
      break
    case 'message': {
      const existing = messages.value.find(message =>
        (event.clientId && message.clientId === event.clientId) || message.id === event.id,
      )
      if (existing) {
        existing.id = event.id
        existing.key = `h-${event.id}`
        existing.createdAt = event.createdAt || existing.createdAt
        existing.senderName = event.senderName || existing.senderName
        existing.content = event.content || existing.content
      } else {
        messages.value.push({
          key: `h-${event.id}`,
          id: event.id,
          senderType: event.senderType === 'ai' ? 'ai' : 'user',
          senderName: event.senderName || '研友',
          content: event.content || '',
          createdAt: event.createdAt,
        })
      }
      void scrollToBottom()
      break
    }
    case 'ai_start':
      if (!findStreaming(event.requestId)) {
        messages.value.push({
          key: `ai-${event.requestId}`,
          requestId: event.requestId,
          senderType: 'ai',
          senderName: event.senderName || '阿墨',
          content: '',
          streaming: true,
        })
        void scrollToBottom()
      }
      break
    case 'ai_delta': {
      const target = findStreaming(event.requestId)
      if (target) {
        target.content += event.content || ''
        void scrollToBottom()
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
      } else if (!messages.value.some(message => message.id === event.messageId)) {
        messages.value.push({
          key: `h-${event.messageId}`,
          id: event.messageId,
          senderType: 'ai',
          senderName: event.senderName || '阿墨',
          content: event.fullContent || '',
          createdAt: event.createdAt,
        })
      }
      void scrollToBottom()
      break
    }
    case 'ai_error': {
      const target = findStreaming(event.requestId)
      if (target) {
        target.content = event.error || '阿墨暂时没连上，请稍后再试。'
        target.streaming = false
        target.error = true
      } else {
        messages.value.push({
          key: `err-${event.requestId}`,
          requestId: event.requestId,
          senderType: 'ai',
          senderName: '阿墨',
          content: event.error || '阿墨暂时没连上，请稍后再试。',
          error: true,
        })
      }
      void scrollToBottom()
      break
    }
    case 'error':
      loadError.value = event.error || '消息暂时没有发送成功，请稍后重试。'
      break
    case 'pong':
      break
  }
}

function clearTimers() {
  if (pingTimer !== null) { window.clearInterval(pingTimer); pingTimer = null }
  if (reconnectTimer !== null) { window.clearTimeout(reconnectTimer); reconnectTimer = null }
}

function scheduleReconnect() {
  if (disposed || reconnectTimer !== null) return
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    connect()
  }, reconnectDelay)
  reconnectDelay = Math.min(reconnectDelay * 2, 15000)
}

function connect() {
  if (disposed) return
  try {
    ws = new WebSocket(buildWsUrl())
  } catch {
    scheduleReconnect()
    return
  }
  const socket = ws
  socket.onopen = () => {
    connected.value = true
    reconnectDelay = 1000
    if (pingTimer !== null) window.clearInterval(pingTimer)
    pingTimer = window.setInterval(() => {
      if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'ping' }))
    }, 30000)
  }
  socket.onmessage = frame => {
    try {
      const event = JSON.parse(frame.data) as ChatEvent
      if (event && typeof event === 'object' && 'type' in event) handleEvent(event)
    } catch {
      // Ignore malformed or non-JSON frames.
    }
  }
  socket.onclose = () => {
    if (ws !== socket) return
    connected.value = false
    online.value = 0
    if (pingTimer !== null) { window.clearInterval(pingTimer); pingTimer = null }
    scheduleReconnect()
  }
  socket.onerror = () => {
    // onclose owns reconnection so only one retry timer is created.
  }
}

function send() {
  const content = input.value.trim()
  if (!content) return
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    loadError.value = offlineMode
      ? '当前为离线模式：请让手机与电脑连接同一 Wi-Fi，启动墨题电脑后端后再试。'
      : '聊天室连接中，请稍候再发送。'
    return
  }

  loadError.value = ''
  const clientId = `c-${Date.now()}-${++optimisticSeq}`
  messages.value.push({
    key: clientId,
    clientId,
    senderType: 'user',
    senderName: '你',
    content,
    createdAt: new Date().toISOString(),
  })
  try {
    ws.send(JSON.stringify({ type: 'message', clientId, content }))
    input.value = ''
    void scrollToBottom(true)
  } catch {
    const optimistic = messages.value.find(message => message.clientId === clientId)
    if (optimistic) messages.value = messages.value.filter(message => message !== optimistic)
    loadError.value = '消息没有发送成功，请检查连接后重试。'
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

onMounted(() => {
  void loadHistory()
  connect()
  measureChatHeight()

  window.addEventListener('resize', onViewportChange)
  window.addEventListener('scroll', onViewportChange, { passive: true })
  window.visualViewport?.addEventListener('resize', onViewportChange)
  window.visualViewport?.addEventListener('scroll', onViewportChange)

  const mobileNav = document.querySelector('.mobile-nav')
  if (mobileNav && typeof ResizeObserver !== 'undefined') {
    viewportObserver = new ResizeObserver(onViewportChange)
    viewportObserver.observe(mobileNav)
  }
})

onBeforeUnmount(() => {
  disposed = true
  clearTimers()
  viewportObserver?.disconnect()
  window.removeEventListener('resize', onViewportChange)
  window.removeEventListener('scroll', onViewportChange)
  window.visualViewport?.removeEventListener('resize', onViewportChange)
  window.visualViewport?.removeEventListener('scroll', onViewportChange)
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
})
</script>

<template>
  <section ref="chatPage" class="page chat-page" aria-labelledby="chat-heading">
    <header class="chat-header">
      <div class="chat-title">
        <span class="chat-seal" aria-hidden="true">聊</span>
        <div class="chat-heading-copy">
          <p class="chat-kicker">MOTEI · STUDY ROOM</p>
          <h1 id="chat-heading">学习聊天室</h1>
          <p class="chat-sub" :class="{ offline: !connected }" role="status">
            <span class="status-dot" :class="connected ? 'on' : 'off'" aria-hidden="true"></span>
            <template v-if="connected">{{ online }} 人在线</template>
            <template v-else-if="offlineMode">离线模式 · 等待电脑后端</template>
            <template v-else>正在连接聊天室…</template>
          </p>
        </div>
      </div>
      <p class="chat-tip"><span aria-hidden="true">✳</span> 输入 @阿墨，唤来学习搭子</p>
    </header>

    <div ref="messageList" class="chat-list" aria-label="聊天室消息" role="log" aria-live="polite" aria-relevant="additions">
      <div v-if="loadingHistory && !messages.length" class="chat-state">
        <LoaderCircle :size="19" class="spin" aria-hidden="true" /> 正在翻开聊天记录…
      </div>
      <div v-else-if="!messages.length && !historyLoaded && loadError" class="chat-state error">
        <p>{{ loadError }}</p>
        <button class="chat-retry" type="button" @click="loadHistory">重新加载</button>
      </div>
      <div v-else-if="!messages.length" class="chat-state chat-empty">
        <span class="empty-seal" aria-hidden="true">墨</span>
        <strong>书房刚刚开席</strong>
        <span>写下你的问题，或用 @阿墨 召唤学习搭子。</span>
      </div>

      <article
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
              <span class="typing-dots" aria-hidden="true"><i></i><i></i><i></i></span>阿墨正在提笔…
            </span>
            <span class="bubble-text">{{ msg.content }}</span><span v-if="msg.streaming && msg.content" class="cursor" aria-hidden="true">▍</span>
          </div>
        </div>
      </article>

      <Transition name="latest-fade">
        <button v-if="showLatestButton" class="latest-button" type="button" @click="scrollToBottom(true)">
          <ChevronDown :size="15" aria-hidden="true" /> 回到最新
        </button>
      </Transition>
    </div>

    <footer class="chat-composer-wrap">
      <p v-if="loadError && messages.length" class="chat-inline-error" role="alert">{{ loadError }}</p>
      <div class="chat-input-bar" :class="{ focused: input.length > 0 }">
        <textarea
          v-model="input"
          class="chat-input"
          rows="1"
          maxlength="4000"
          enterkeyhint="send"
          aria-label="输入聊天消息"
          placeholder="写下此刻的想法…"
          @keydown="onKeydown"
        ></textarea>
        <button class="chat-send" type="button" :disabled="!input.trim()" aria-label="发送消息" @click="send">
          <Send :size="17" aria-hidden="true" />
        </button>
      </div>
      <div class="composer-hint">
        <span>Enter 发送 <span aria-hidden="true">·</span> Shift + Enter 换行</span>
        <span>{{ input.length.toLocaleString() }} / 4,000</span>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.chat-page {
  --paper: #f7f3ee;
  --ink-heavy: #141210;
  --ink-deep: #2e2a26;
  --cinnabar: #b84a39;
  --bamboo: #4a5f4e;
  --paper-card: #fffdf9;
  --paper-wash: #f0ebe4;
  --ink-muted: #82786c;
  --paper-line: rgba(46, 42, 38, .12);
  --spring: cubic-bezier(.32, .72, 0, 1);
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: 1080px;
  height: var(--chat-height, min(78dvh, calc(100dvh - 150px)));
  min-height: 0;
  margin-inline: auto;
  padding: 0 2px 12px;
  color: var(--ink-heavy);
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex: 0 0 auto;
  margin-bottom: 12px;
  padding: 2px 2px 8px;
}

.chat-title { display: flex; align-items: center; gap: 13px; min-width: 0; }
.chat-seal {
  position: relative;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: 0 0 44px;
  border: 1px solid rgba(255,255,255,.5);
  border-radius: 12px;
  outline: 1px solid rgba(184,74,57,.2);
  outline-offset: -4px;
  background: var(--cinnabar);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.23), 0 4px 12px rgba(91,43,34,.12);
  color: #fffaf3;
  font-family: var(--font-brand, "Kaiti SC", "STKaiti", "楷体", serif);
  font-size: 21px;
  font-weight: 700;
}

.chat-heading-copy { min-width: 0; }
.chat-kicker { margin: 0 0 2px; color: var(--bamboo); font-size: 9px; font-weight: 700; letter-spacing: .17em; }
.chat-title h1 { margin: 0; color: var(--ink-heavy); font-size: clamp(20px, 1.45rem, 24px); font-weight: 750; letter-spacing: .025em; line-height: 1.2; }
.chat-sub { display: flex; align-items: center; gap: 6px; margin: 5px 0 0; color: var(--bamboo); font-size: 11px; }
.chat-sub.offline { color: var(--ink-muted); }
.status-dot { width: 7px; height: 7px; flex: 0 0 7px; border-radius: 50%; }
.status-dot.on { background: var(--bamboo); box-shadow: 0 0 0 3px rgba(74,95,78,.11); }
.status-dot.off { background: #a39a8f; }
.chat-tip { margin: 0 3px 0 0; color: var(--ink-muted); font-size: 12px; }
.chat-tip span { margin-right: 4px; color: var(--cinnabar); }

.chat-list {
  position: relative;
  display: flex;
  flex: 1 1 auto;
  flex-direction: column;
  gap: 13px;
  min-width: 0;
  min-height: 104px;
  overflow: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
  padding: clamp(12px, 2.1vw, 22px);
  border: 1px solid rgba(46,42,38,.14);
  border-radius: 18px;
  outline: 1px solid rgba(255,255,255,.84);
  outline-offset: -5px;
  background: linear-gradient(155deg, rgba(255,253,249,.95), rgba(248,244,237,.96));
  box-shadow: inset 0 2px 5px rgba(46,42,38,.035), inset 0 1px 0 rgba(255,255,255,.9), 0 7px 22px rgba(46,42,38,.055);
  scroll-behavior: smooth;
  scrollbar-color: rgba(74,95,78,.35) transparent;
  scrollbar-width: thin;
}

.chat-state { display: flex; flex: 1; flex-direction: column; align-items: center; justify-content: center; gap: 9px; margin: auto; padding: 18px 8px; color: var(--ink-muted); font-size: 13px; text-align: center; }
.chat-state.error { color: var(--cinnabar); }
.chat-state.error p { margin: 0; }
.chat-empty strong { color: var(--ink-deep); font-size: 15px; font-weight: 650; }
.chat-empty > span:last-child { max-width: 29ch; line-height: 1.7; }
.empty-seal { display: grid; place-items: center; width: 37px; height: 37px; border: 1px solid rgba(74,95,78,.25); border-radius: 12px; color: var(--bamboo); font-family: var(--font-brand, serif); font-size: 18px; }
.spin { color: var(--bamboo); animation: rotate 1s linear infinite; }
.chat-retry { border: 1px solid rgba(184,74,57,.27); border-radius: 999px; padding: 8px 15px; background: transparent; color: var(--cinnabar); font: inherit; cursor: pointer; }

.chat-row { display: flex; align-items: flex-start; gap: 9px; max-width: 100%; animation: message-enter .32s var(--spring) both; }
.row-user { flex-direction: row-reverse; }
.chat-avatar { display: grid; place-items: center; width: 29px; height: 29px; flex: 0 0 29px; margin-top: 18px; border: 1px solid rgba(74,95,78,.14); border-radius: 10px; background: var(--paper-wash); color: var(--bamboo); }
.chat-avatar.user { border-color: rgba(184,74,57,.2); background: #f2e5df; color: var(--cinnabar); }
.chat-bubble-wrap { display: flex; flex-direction: column; gap: 4px; max-width: min(82%, 760px); min-width: 0; }
.row-user .chat-bubble-wrap { align-items: flex-end; }
.row-ai .chat-bubble-wrap { align-items: flex-start; }
.chat-meta { color: var(--ink-muted); font-size: 10px; line-height: 1.5; }
.chat-bubble { max-width: 100%; padding: 10px 14px; border: 1px solid rgba(74,95,78,.13); border-radius: 14px 14px 14px 5px; background: var(--paper-card); box-shadow: inset 0 1px 0 rgba(255,255,255,.88), 0 2px 5px rgba(46,42,38,.045); color: var(--ink-deep); font-size: 14px; line-height: 1.75; overflow-wrap: anywhere; white-space: pre-wrap; }
.row-user .chat-bubble { border-color: rgba(74,95,78,.22); border-radius: 14px 14px 5px 14px; background: var(--bamboo); color: #fffdf8; box-shadow: inset 0 1px 0 rgba(255,255,255,.12), 0 3px 9px rgba(41,61,46,.13); }
.chat-bubble.error { border-color: rgba(184,74,57,.2); background: #f7ebe6; color: #8c392c; }
.bubble-text:empty { display: none; }
.typing { display: inline-flex; align-items: center; gap: 7px; color: var(--ink-muted); font-size: 12px; }
.typing-dots { display: inline-flex; align-items: center; gap: 3px; }
.typing-dots i { width: 4px; height: 4px; border-radius: 50%; background: var(--bamboo); animation: dot-breathe .9s ease-in-out infinite alternate; }
.typing-dots i:nth-child(2) { animation-delay: .15s; }
.typing-dots i:nth-child(3) { animation-delay: .3s; }
.cursor { display: inline-block; margin-left: 1px; color: var(--bamboo); animation: blink .9s steps(2) infinite; }
.latest-button { position: sticky; bottom: 0; align-self: center; display: inline-flex; align-items: center; gap: 5px; margin-top: auto; border: 1px solid rgba(74,95,78,.2); border-radius: 999px; padding: 6px 11px; background: var(--paper-card); box-shadow: 0 3px 10px rgba(46,42,38,.09); color: var(--bamboo); font-size: 11px; cursor: pointer; transition: transform .22s var(--spring), box-shadow .22s var(--spring); }
.latest-button:hover { transform: translateY(-1px); box-shadow: 0 5px 13px rgba(46,42,38,.12); }

.chat-composer-wrap { flex: 0 0 auto; margin-top: 10px; }
.chat-inline-error { margin: 0 3px 6px; color: var(--cinnabar); font-size: 12px; line-height: 1.5; }
.chat-input-bar { display: flex; align-items: flex-end; gap: 10px; min-width: 0; padding: 8px 9px 8px 15px; border: 1px solid var(--paper-line); border-radius: 16px; outline: 1px solid rgba(255,255,255,.85); outline-offset: -4px; background: var(--paper-card); box-shadow: inset 0 2px 4px rgba(46,42,38,.035), 0 3px 11px rgba(46,42,38,.045); transition: border-color .24s var(--spring), box-shadow .24s var(--spring); }
.chat-input-bar:focus-within { border-color: rgba(74,95,78,.45); box-shadow: inset 0 2px 4px rgba(46,42,38,.025), 0 0 0 3px rgba(74,95,78,.09), 0 4px 12px rgba(46,42,38,.05); }
.chat-input { flex: 1 1 auto; min-width: 0; min-height: 38px; max-height: 104px; resize: none; overflow-y: auto; border: 0; outline: 0; background: transparent; color: var(--ink-heavy); font: inherit; font-size: 14px; line-height: 1.6; }
.chat-input::placeholder { color: #9b9185; }
.chat-input:focus-visible { outline: none; }
.chat-send { display: grid; place-items: center; width: 40px; height: 40px; flex: 0 0 40px; border: 1px solid rgba(255,255,255,.45); border-radius: 12px; outline: 1px solid rgba(184,74,57,.17); outline-offset: -4px; background: var(--cinnabar); box-shadow: inset 0 1px 0 rgba(255,255,255,.2), 0 3px 8px rgba(91,43,34,.12); color: #fffaf3; cursor: pointer; transition: transform .24s var(--spring), filter .24s var(--spring), opacity .2s; }
.chat-send:hover:not(:disabled) { transform: translateY(-2px); filter: brightness(1.04); }
.chat-send:active:not(:disabled) { transform: scale(.95); }
.chat-send:disabled { opacity: .48; cursor: not-allowed; box-shadow: none; }
.chat-send:focus-visible, .chat-retry:focus-visible, .latest-button:focus-visible { outline: 3px solid rgba(184,74,57,.37); outline-offset: 2px; }
.composer-hint { display: flex; justify-content: space-between; gap: 10px; padding: 5px 4px 0; color: var(--ink-muted); font-size: 10px; }
.composer-hint > span:last-child { font-variant-numeric: tabular-nums; }

@keyframes rotate { to { transform: rotate(360deg); } }
@keyframes blink { 50% { opacity: 0; } }
@keyframes dot-breathe { to { opacity: .35; transform: translateY(-2px); } }
@keyframes message-enter { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
.latest-fade-enter-active, .latest-fade-leave-active { transition: opacity .2s var(--spring), transform .2s var(--spring); }
.latest-fade-enter-from, .latest-fade-leave-to { opacity: 0; transform: translateY(5px); }

:global(:root.dark) .chat-page { --paper-card: #25241f; --paper-wash: #302e27; --ink-heavy: #eee9df; --ink-deep: #e4ded2; --ink-muted: #aaa193; --paper-line: rgba(236,228,214,.16); }
:global(:root.dark) .chat-list { border-color: rgba(236,228,214,.13); outline-color: rgba(255,255,255,.025); background: linear-gradient(155deg, #211f1b, #26241f); box-shadow: inset 0 2px 6px rgba(0,0,0,.18), inset 0 1px 0 rgba(255,255,255,.035); }
:global(:root.dark) .chat-bubble { border-color: rgba(180,197,174,.17); background: #2c3029; box-shadow: inset 0 1px 0 rgba(255,255,255,.035), 0 2px 5px rgba(0,0,0,.12); color: #ece8de; }
:global(:root.dark) .row-user .chat-bubble { border-color: rgba(195,211,188,.2); background: #405343; color: #faf8f0; }
:global(:root.dark) .chat-bubble.error { border-color: rgba(213,120,102,.2); background: #3a2824; color: #edb9aa; }
:global(:root.dark) .chat-input-bar { border-color: rgba(236,228,214,.17); outline-color: rgba(255,255,255,.035); background: #25241f; }
:global(:root.dark) .chat-input::placeholder { color: #a79d8e; }
:global(:root.dark) .chat-avatar.user { border-color: rgba(213,120,102,.23); background: #402b26; }
:global(:root.dark) .latest-button { border-color: rgba(180,197,174,.22); background: #292b25; }

@media (max-width: 980px) {
  .chat-page { height: var(--chat-height, min(76dvh, calc(100dvh - 128px))); }
  .chat-header { margin-bottom: 8px; padding-bottom: 5px; }
  .chat-tip { display: none; }
}

@media (max-width: 560px) {
  .chat-page { height: var(--chat-height, min(72dvh, calc(100dvh - 112px))); padding-inline: 0; padding-bottom: 8px; }
  .chat-seal { width: 40px; height: 40px; flex-basis: 40px; }
  .chat-title { gap: 10px; }
  .chat-kicker { font-size: 8px; }
  .chat-title h1 { font-size: 19px; }
  .chat-sub { margin-top: 4px; font-size: 10px; }
  .chat-list { gap: 11px; min-height: 84px; padding: 12px 10px; border-radius: 15px; }
  .chat-bubble-wrap { max-width: calc(100% - 39px); }
  .chat-avatar { width: 26px; height: 26px; flex-basis: 26px; border-radius: 9px; }
  .chat-bubble { padding: 9px 11px; font-size: 13px; }
  .chat-input-bar { gap: 7px; padding: 6px 7px 6px 12px; border-radius: 14px; }
  .chat-input { min-height: 36px; max-height: 84px; font-size: 16px; }
  .chat-send { width: 38px; height: 38px; flex-basis: 38px; }
  .composer-hint { font-size: 9px; }
}

@media (prefers-reduced-motion: reduce) {
  .chat-page *, .chat-page *::before, .chat-page *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; transition-duration: .01ms !important; }
}
</style>
