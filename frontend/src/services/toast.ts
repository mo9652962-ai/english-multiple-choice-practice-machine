// 全局 Toast 通知系统
// 参考: web.dev Building a toast component + LogRocket toast UX
// 用法: import { showToast } from '../services/toast'
//       showToast('已保存', 'success')

export type ToastType = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  message: string
  type: ToastType
  duration: number
}

// 简单响应式 store (模块级)
let toasts: ToastItem[] = []
let nextId = 1
const listeners = new Set<() => void>()

export function subscribeToast(fn: () => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getToasts(): ToastItem[] {
  return toasts
}

function emit() {
  listeners.forEach(fn => fn())
}

export function showToast(message: string, type: ToastType = 'info', duration = 3200) {
  const id = nextId++
  toasts = [...toasts, { id, message, type, duration }]
  emit()
  window.setTimeout(() => dismissToast(id), duration)
}

export function dismissToast(id: number) {
  toasts = toasts.filter(t => t.id !== id)
  emit()
}
