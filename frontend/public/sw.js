// AI 英语刷题机 — Service Worker (PWA 离线缓存)
// v2.94: 缓存版本化 v3 — 图片/字体缓存优先(加速启动) + HTML/JS网络优先(防白屏)
const CACHE = 'english-machine-v3'
const ASSET_CACHE = 'english-machine-assets-v3'

// 安装时缓存核心资源
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) =>
      cache.addAll(['./', './index.html', './manifest.json'])
    )
  )
  self.skipWaiting()
})

// 激活时清理旧缓存（版本号变化 → 删除旧版缓存）
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE && k !== ASSET_CACHE).map((k) => caches.delete(k)))
    )
  )
  self.clients.claim()
})

// 请求拦截
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url)
  // 跳过 API / 非同源 / websocket
  if (url.origin !== self.location.origin) return
  if (url.pathname.includes('/api/')) return

  // 图片/字体/静态资产: 缓存优先 (不变内容, 加速启动)
  if (/(\.png|\.jpe?g|\.webp|\.svg|\.woff2?|\.ttf|\.wasm|\.db)$/i.test(url.pathname)) {
    e.respondWith(
      caches.match(e.request).then((cached) => {
        if (cached) return cached
        return fetch(e.request).then((resp) => {
          if (resp.ok) {
            const clone = resp.clone()
            caches.open(ASSET_CACHE).then((cache) => cache.put(e.request, clone))
          }
          return resp
        })
      })
    )
    return
  }

  // HTML/JS/CSS: 网络优先 (发布后用户拿到最新版), 失败回退缓存 (离线可用)
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        if (resp.ok && resp.type === 'basic') {
          const clone = resp.clone()
          caches.open(CACHE).then((cache) => cache.put(e.request, clone))
        }
        return resp
      })
      .catch(() => caches.match(e.request).then((cached) => cached))
  )
})
