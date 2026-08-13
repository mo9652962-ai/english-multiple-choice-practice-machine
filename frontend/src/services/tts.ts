// TTS 统一服务：Capacitor 原生 TTS 优先（Android 稳定），Web speechSynthesis 回退
// 修复: Android WebView speechSynthesis 无声 bug（2026-08-13）
import { Capacitor } from '@capacitor/core'
import { TextToSpeech } from '@capacitor-community/text-to-speech'

let webSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
let webUtterance: SpeechSynthesisUtterance | null = null

// 是否原生 TTS（Android/iOS App 内）
export function isNativeTTS(): boolean {
  return Capacitor.isNativePlatform()
}

export async function speak(text: string, rate = 0.9): Promise<void> {
  const clean = String(text || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!clean) return

  if (Capacitor.isNativePlatform()) {
    try {
      await TextToSpeech.stop()
      await TextToSpeech.speak({
        text: clean,
        lang: 'en-US',
        rate: rate,
      })
      return
    } catch (e) {
      console.warn('原生 TTS 失败，回退 Web:', e)
    }
  }

  if (!webSupported) return
  const synth = window.speechSynthesis
  synth.cancel()
  if (synth.paused) synth.resume()
  webUtterance = new SpeechSynthesisUtterance(clean)
  webUtterance.lang = 'en-US'
  webUtterance.rate = rate
  synth.speak(webUtterance)
}

export async function stop(): Promise<void> {
  if (Capacitor.isNativePlatform()) {
    try { await TextToSpeech.stop() } catch { /* ignore */ }
  }
  if (webSupported) window.speechSynthesis?.cancel()
}
