// v52: 文房金石微音效服务 (2026 精致化 Phase 1)
// 原理: 纯原生 Web Audio API 振荡器实时合成，0 外部音频文件依赖，0KB 额外体积，全离线可用
// 音效设计:
//   - tap: 棋子落盘微声 (320Hz->80Hz，35ms 衰减，短促清脆)
//   - correct: 玉石击鸣和弦 (C5-E5-G5 纯正大三和弦，正弦泛音 450ms)
//   - wrong: 古琴低沉沉吟 (196Hz->130Hz，260ms 温和回荡，绝非刺耳蜂鸣)
//   - fanfare: 庆祝清钟鸣音 (双频共振，连击与通关奖励)

class ScholarAudio {
  private ctx: AudioContext | null = null
  private enabled: boolean = true

  constructor() {
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        this.enabled = localStorage.getItem('epm_sound_enabled') !== 'false'
      }
    } catch {
      this.enabled = true
    }
  }

  public isEnabled(): boolean {
    return this.enabled
  }

  public setEnabled(val: boolean) {
    this.enabled = val
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.setItem('epm_sound_enabled', val ? 'true' : 'false')
      }
    } catch { /* ignore */ }
  }

  private getContext(): AudioContext | null {
    if (!this.enabled || typeof window === 'undefined') return null
    try {
      if (!this.ctx) {
        const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
        if (AudioCtx) {
          this.ctx = new AudioCtx()
        }
      }
      if (this.ctx && this.ctx.state === 'suspended') {
        void this.ctx.resume()
      }
      return this.ctx
    } catch {
      return null
    }
  }

  /**
   * 1. 棋子落盘微声（选项点击、按钮按压）
   */
  public tap() {
    const ctx = this.getContext()
    if (!ctx) return
    try {
      const now = ctx.currentTime
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()

      osc.type = 'sine'
      osc.frequency.setValueAtTime(320, now)
      osc.frequency.exponentialRampToValueAtTime(80, now + 0.035)

      gain.gain.setValueAtTime(0.09, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.035)

      osc.connect(gain)
      gain.connect(ctx.destination)

      osc.start(now)
      osc.stop(now + 0.04)
    } catch { /* 忽略音频调度偶发异常 */ }
  }

  /**
   * 2. 玉石击鸣和弦（答对、通过、卡片确认）
   */
  public correct() {
    const ctx = this.getContext()
    if (!ctx) return
    try {
      const now = ctx.currentTime
      const notes = [523.25, 659.25, 783.99] // C5 - E5 - G5
      notes.forEach((freq, idx) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        const start = now + idx * 0.055

        osc.type = 'triangle'
        osc.frequency.setValueAtTime(freq, start)

        gain.gain.setValueAtTime(0.06, start)
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.42)

        osc.connect(gain)
        gain.connect(ctx.destination)

        osc.start(start)
        osc.stop(start + 0.45)
      })
    } catch { /* ignore */ }
  }

  /**
   * 3. 古琴低泛音提示（答错、警告）
   */
  public wrong() {
    const ctx = this.getContext()
    if (!ctx) return
    try {
      const now = ctx.currentTime
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()

      osc.type = 'sine'
      osc.frequency.setValueAtTime(196, now) // G3
      osc.frequency.exponentialRampToValueAtTime(130.81, now + 0.22) // C3

      gain.gain.setValueAtTime(0.09, now)
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.25)

      osc.connect(gain)
      gain.connect(ctx.destination)

      osc.start(now)
      osc.stop(now + 0.26)
    } catch { /* ignore */ }
  }

  /**
   * 4. 钟磬共鸣清鸣（通关、高分、打卡庆祝）
   */
  public fanfare() {
    const ctx = this.getContext()
    if (!ctx) return
    try {
      const now = ctx.currentTime
      const freqs = [587.33, 880.0, 1174.66] // D5 - A5 - D6
      freqs.forEach((freq, idx) => {
        const osc = ctx.createOscillator()
        const gain = ctx.createGain()
        const start = now + idx * 0.08

        osc.type = 'sine'
        osc.frequency.setValueAtTime(freq, start)

        gain.gain.setValueAtTime(0.08, start)
        gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.8)

        osc.connect(gain)
        gain.connect(ctx.destination)

        osc.start(start)
        osc.stop(start + 0.85)
      })
    } catch { /* ignore */ }
  }
}

export const sound = new ScholarAudio()
