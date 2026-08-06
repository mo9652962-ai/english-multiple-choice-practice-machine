// AI 英语刷题机 — Service Worker (PWA 离线缓存)
// v9.20.1: 缓存版本化 (v2) + 网络优先策略——修复"旧缓存引用已删除资源导致白屏"
const CACHE = 'english-machine-v2'

// 安装时缓存核心资源
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) =>
      cache.addAll([
        './',
        './index.html',
        './manifest.json',
      ])
    )
  )
  self.skipWaiting()
})

// 激活时清理旧缓存（版本号变化 → 删除旧版缓存）
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

// 请求拦截：网络优先（保证发布后用户拿到最新版），失败回退缓存（离线可用）
self.addEventListener('fetch', (e) => {
  // 跳过 API 请求（不缓存）
  if (e.request.url.includes('/api/')) return

  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        // 网络成功 → 缓存副本（同源响应）
        if (resp.ok && resp.type === 'basic') {
          const clone = resp.clone()
          caches.open(CACHE).then((cache) => cache.put(e.request, clone))
        }
        return resp
      })
      .catch(() => caches.match(e.request).then((cached) => cached))
  )
})
