// v9.28: Gemini 方案——API 根地址支持构建时注入（打包手机 APK 时必须指向 PC 局域网 IP）
// 用法: VITE_API_ROOT=http://192.168.x.x:8765/api npm run build
const API_ROOT = (import.meta.env.VITE_API_ROOT as string | undefined) || '/api'

// v9.24: 多用户认证——token 存储
const TOKEN_KEY = 'epm_auth_token'
const ORGANIZATION_KEY = 'epm_active_organization_id'
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}
export function getOrganizationId(): number | null {
  const value = Number(localStorage.getItem(ORGANIZATION_KEY))
  return Number.isInteger(value) && value > 0 ? value : null
}
export function setOrganizationId(organizationId: number | null): void {
  if (organizationId && organizationId > 0) {
    localStorage.setItem(ORGANIZATION_KEY, String(organizationId))
  } else {
    localStorage.removeItem(ORGANIZATION_KEY)
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  // v9.24: 自动携带 token
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const organizationId = getOrganizationId()
  if (organizationId) headers.set('X-Organization-Id', String(organizationId))
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
    // v9.24: 401 未登录 → 跳登录页
    if (response.status === 401 && !path.startsWith('/auth/')) {
      setToken(null)
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
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
export const patch = async <T>(path: string, body?: unknown) => {
  if (isOffline()) {
    const { apiPatch } = await import('./services/api-adapter')
    return apiPatch(path, body as any) as T
  }
  return api<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) })
}
export const del = async <T>(path: string) => {
  if (isOffline()) {
    const { apiDelete } = await import('./services/api-adapter')
    return apiDelete(path) as T
  }
  return api<T>(path, { method: 'DELETE' })
}

// ── v9.24: 多用户认证 API ──
export interface AuthUser {
  id: number
  username: string
  is_admin: boolean
  active_organization_id?: number | null
}
export interface AuthResponse { token: string; user: AuthUser }

export const authApi = {
  register: (username: string, password: string) =>
    api<AuthResponse>('/auth/register', { method: 'POST', body: JSON.stringify({ username, password }) }),
  login: (username: string, password: string) =>
    api<AuthResponse>('/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  me: () => api<AuthUser>('/auth/me'),
}

// ── PWA 离线模式 (v9.19) ──
// 检测后端是否可用，不可用则自动切换到 sql.js 本地数据库
let _offlineReady = false
let _offlinePromise: Promise<boolean> | null = null

export async function initOfflineMode(skipHealthCheck = false): Promise<boolean> {
  if (_offlinePromise) return _offlinePromise
  _offlinePromise = (async () => {
    // v10.4: 手机 APK 构建时注入了 VITE_API_ROOT（指向 PC 局域网后端）→ 先探测后端是否可达
    // 可达则走在线模式（聊天室/设置/AI 精讲可用）；不可达再降级 sql.js 内置离线库
    // 注意必须校验响应是 JSON 的 {status:"ok"}——Capacitor 本地服务器对任意路径都回 200 index.html，会被误判
    if (skipHealthCheck && API_ROOT.startsWith('http')) {
      try {
        const resp = await fetch(`${API_ROOT}/health`, { signal: AbortSignal.timeout(2500) })
        if (resp.ok) {
          const data = await resp.json().catch(() => null)
          if (data && data.status === 'ok') {
            _offlineReady = false
            return false
          }
        }
      } catch {
        // PC 后端不可达 → 走离线
      }
    }
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
      // v3.5: sql.js 初始化加超时保护——wasm 加载挂起时不让 bootstrap 卡死（曾导致整页白屏）
      await Promise.race([
        initDatabase(),
        new Promise((_, reject) => setTimeout(() => reject(new Error('sql.js init timeout')), 10000)),
      ])
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
