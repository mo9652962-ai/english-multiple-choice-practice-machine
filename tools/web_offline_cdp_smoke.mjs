#!/usr/bin/env node

const args = new Map()
for (let index = 2; index < process.argv.length; index += 1) {
  const key = process.argv[index]
  const value = process.argv[index + 1]
  if (key?.startsWith('--') && value) args.set(key.slice(2), value)
}

const cdpPort = Number(args.get('cdp-port') || 18769)
const pageUrl = args.get('url') || 'http://127.0.0.1:18768/'

async function waitForPage() {
  const deadline = Date.now() + 30_000
  while (Date.now() < deadline) {
    try {
      const pages = await fetch(`http://127.0.0.1:${cdpPort}/json`).then(response => response.json())
      const page = pages.find(candidate => candidate.type === 'page' && candidate.url.startsWith(pageUrl))
      if (page) return page
    } catch {
      // Chrome is still starting.
    }
    await new Promise(resolve => setTimeout(resolve, 300))
  }
  throw new Error('Chrome DevTools 页面目标启动超时。')
}

function connect(url) {
  return new Promise((resolve, reject) => {
    const socket = new WebSocket(url)
    socket.onerror = () => reject(new Error('Chrome DevTools WebSocket 连接失败。'))
    socket.onopen = () => resolve(socket)
  })
}

function command(socket, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = Math.floor(Math.random() * 2 ** 30)
    const onMessage = event => {
      const message = JSON.parse(event.data)
      if (message.id !== id) return
      socket.removeEventListener('message', onMessage)
      if (message.error) reject(new Error(message.error.message))
      else resolve(message)
    }
    socket.addEventListener('message', onMessage)
    socket.send(JSON.stringify({ id, method, params }))
  })
}

const page = await waitForPage()
const socket = await connect(page.webSocketDebuggerUrl)
await command(socket, 'Runtime.enable')
await new Promise(resolve => setTimeout(resolve, 12_000))
const result = await command(socket, 'Runtime.evaluate', {
  expression: `JSON.stringify({
    offline: window.__EPM_OFFLINE_INIT_ERROR__ || null,
    dashboard: window.__EPM_DASHBOARD_ERROR__ || null,
    body: document.body.innerText,
  })`,
  returnByValue: true,
})
socket.close()

const state = JSON.parse(result.result.result.value)
if (!state.body.includes('墨题')) throw new Error('页面未完成渲染。')
if (state.offline || state.dashboard) throw new Error(`离线页面初始化失败：${state.offline || state.dashboard}`)
if (state.body.includes('主页数据暂时没有加载成功')) throw new Error('离线页面仍显示主页数据加载失败。')
if (!state.body.includes('考研英语一')) throw new Error('离线页面未读到种子题库默认题库。')
console.log('Web offline browser smoke passed: profile=考研英语一')
