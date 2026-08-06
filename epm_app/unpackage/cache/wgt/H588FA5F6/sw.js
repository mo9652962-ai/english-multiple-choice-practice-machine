// AI 英语刷题机 — Service Worker (PWA 离线缓存)
const CACHE = 'english-machine-v1'

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

// 激活时清理旧缓存
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

// 请求拦截：缓存优先，回退网络
self.addEventListener('fetch', (e) => {
  // 跳过 API 请求（不缓存）
  if (e.request.url.includes('/api/')) return

  e.respondWith(
    caches.match(e.request).then((cached) => {
      // 缓存命中 → 直接返回
      if (cached) return cached
      // 网络请求 → 成功则缓存
      return fetch(e.request).then((resp) => {
        if (resp.ok && resp.type === 'basic') {
          const clone = resp.clone()
          caches.open(CACHE).then((cache) => cache.put(e.request, clone))
        }
        return resp
      })
    })
  )
})