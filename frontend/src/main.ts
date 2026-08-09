import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles.css'
import { initOfflineMode } from './api'

// v3.1: 前端自动更新检测 — 每 60s 对比首页 JS 哈希，变化则自动刷新
// 解决：旧标签页/窗口不自动加载新版本的问题（配合后端 no-store + 哈希资源）
function setupAutoReload() {
  const current = document.querySelector('script[src*="index-"]')?.getAttribute('src') || ''
  if (!current) return
  setInterval(async () => {
    try {
      const html = await fetch('/', { cache: 'no-store', headers: { 'Accept': 'text/html' } }).then(r => r.text())
      const m = html.match(/src="\.?\/?assets\/(index-[A-Za-z0-9_-]+\.js)/)
      if (m && m[1] !== current) {
        console.log('[update] 检测到新版本，自动刷新')
        location.reload()
      }
    } catch { /* 离线时跳过 */ }
  }, 60000)
}

// v9.19: PWA 离线检测 — 后端不可用时自动切换到 sql.js
// v3.3: Capacitor 原生平台（手机）跳过 health 检查直接离线（无后端）——先初始化再挂载
async function bootstrap() {
  const isNative = !!(window as any).Capacitor?.isNativePlatform
  const offline = await initOfflineMode(isNative)
  if (!offline) setupAutoReload()
  if (offline) {
    (window as any).__LINJIAN_STARTUP__ = {
      active_profile: { id: 1, name: '考研英语一' },
      paper_count: 0, unit_count: 0, question_count: 0,
      wrong_count: 0, frequent_count: 0, recent_sessions: [],
    }
  }
  createApp(App).use(router).mount('#app')
}

bootstrap()
