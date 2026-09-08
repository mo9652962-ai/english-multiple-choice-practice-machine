// v50: 触觉反馈渐进增强 — Android WebView/Chrome 可用; iOS/桌面无振动硬件自动忽略
// 规范: 特性检测 + 短促可区分(轻点 10ms / 答对 20ms / 答错双脉冲) + 仅在用户手势内触发

let hapticEnabled = true
try {
  if (typeof window !== 'undefined' && window.localStorage) {
    hapticEnabled = localStorage.getItem('epm_haptic_enabled') !== 'false'
  }
} catch {
  hapticEnabled = true
}

export function isHapticEnabled(): boolean {
  return hapticEnabled
}

export function setHapticEnabled(val: boolean) {
  hapticEnabled = val
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      localStorage.setItem('epm_haptic_enabled', val ? 'true' : 'false')
    }
  } catch { /* ignore */ }
}

export function haptic(pattern: number | number[] = 10) {
  if (!hapticEnabled) return
  try {
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) {
      navigator.vibrate(pattern)
    }
  } catch { /* 无振动硬件或权限策略, 静默忽略 */ }
}
