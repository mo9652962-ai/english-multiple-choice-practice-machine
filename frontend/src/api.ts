const API_ROOT = '/api'

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(`${API_ROOT}${path}`, { ...options, headers })
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`
    let detail: unknown = null
    try {
      const data = await response.json()
      detail = data.detail
      message = typeof detail === 'string'
        ? detail
        : (detail as any)?.message || JSON.stringify(detail)
    } catch {
      // Keep status text.
    }
    const error = new Error(message) as Error & { status?: number, detail?: unknown }
    error.status = response.status
    error.detail = detail
    throw error
  }
  return response.json()
}

export const get = async <T>(path: string) => {
  if (isOffline()) {
    const { apiGet } = await import('./services/api-adapter')
    return apiGet(path) as T
  }
  return api<T>(path)
}
export const post = async <T>(path: string, body?: unknown) => {
  if (isOffline()) {
    const { apiPost } = await import('./services/api-adapter')
    return apiPost(path, body as any) as T
  }
  return api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })
}
export const put = async <T>(path: string, body?: unknown) => {
  if (isOffline()) {
    const { apiPut } = await import('./services/api-adapter')
    return apiPut(path, body as any) as T
  }
  return api<T>(path, { method: 'PUT', body: body === undefined ? undefined : JSON.stringify(body) })
}
export const patch = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) })
export const del = <T>(path: string) => api<T>(path, { method: 'DELETE' })

// ── PWA 离线模式 (v9.19) ──
// 检测后端是否可用，不可用则自动切换到 sql.js 本地数据库
let _offlineReady = false
let _offlinePromise: Promise<boolean> | null = null

export async function initOfflineMode(skipHealthCheck = false): Promise<boolean> {
  if (_offlinePromise) return _offlinePromise
  _offlinePromise = (async () => {
    // Capacitor 原生平台（手机）没有本地后端——跳过 health 检查直接切 sql.js
    if (!skipHealthCheck) {
      try {
        const resp = await fetch('/api/health', { signal: AbortSignal.timeout(2000) })
        if (resp.ok) {
          _offlineReady = false
          return false
        }
      } catch {
        // 后端不可用 → 初始化 sql.js
      }
    }
    try {
      const { initDatabase } = await import('./services/db')
      await initDatabase()
      _offlineReady = true
      return true
    } catch {
      _offlineReady = false
      return false
    }
  })()
  return _offlinePromise
}

export function isOffline(): boolean {
  return _offlineReady
}
