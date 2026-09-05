<script setup lang="ts">
// v3.4: 听力精听增强（借 SparkMo「逐句精听·变速复读」+ Echo Loop「循环播放」）
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '../api'
import { Headphones, Play, RotateCcw, Square } from 'lucide-vue-next'

const router = useRouter()
const units = ref<any[]>([])
const loading = ref(true)
const error = ref('')
const playingId = ref<number | null>(null)
const audioEl = ref<HTMLAudioElement | null>(null)
const speed = ref(1)
const loop = ref(false)
const progress = ref(0)
const duration = ref(0)

onMounted(async () => {
  try {
    const r: any = await get('/library/units?unit_type=listening&limit=20')
    units.value = Array.isArray(r) ? r : r?.items || []
  } catch (e) { error.value = String(e) }
  loading.value = false
})

function listen(p: any) {
  if (p.unit_id || p.id) {
    router.push(`/practice?unit=${p.unit_id || p.id}`)
  } else {
    router.push('/library')
  }
}

function togglePlay(p: any, index: number) {
  if (!p.audio_url) { listen(p); return }
  if (playingId.value === index && audioEl.value) {
    audioEl.value.pause()
    playingId.value = null
    return
  }
  playingId.value = index
  if (audioEl.value) {
    audioEl.value.src = p.audio_url
    audioEl.value.playbackRate = speed.value
    audioEl.value.loop = loop.value
    audioEl.value.play().catch(() => { playingId.value = null })
  }
}

function onAudioEnded() { playingId.value = null }

// v3.4: 变速（SparkMo 变速播放）
function setSpeed(s: number) {
  speed.value = s
  if (audioEl.value) audioEl.value.playbackRate = s
}

// v3.4: 单句循环（Echo Loop 循环播放）
function toggleLoop() {
  loop.value = !loop.value
  if (audioEl.value) audioEl.value.loop = loop.value
}

// v3.4: 重听当前片段（复读）
function replay() {
  if (!audioEl.value) return
  audioEl.value.currentTime = 0
  audioEl.value.play().catch(() => {})
}

function onTimeUpdate() {
  if (!audioEl.value) return
  progress.value = audioEl.value.currentTime
  duration.value = audioEl.value.duration || 0
}

function seek(e: Event) {
  if (!audioEl.value) return
  const el = e.target as HTMLInputElement
  audioEl.value.currentTime = Number(el.value)
}
</script>

<template>
  <div class="page page-listening">
    <div class="page-head">
      <div>
        <span class="eyebrow">听力研习</span>
        <h1>听力精听</h1>
        <p class="lead">集中练习听力篇章，磨耳朵从每一句开始。支持变速、单句循环、复读。</p>
      </div>
    </div>

    <audio ref="audioEl" @ended="onAudioEnded" @timeupdate="onTimeUpdate" @loadedmetadata="onTimeUpdate" style="display:none"></audio>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="!units.length" class="card empty illustrated-empty">
      <div><Headphones :size="25" /><strong>还没有听力材料</strong></div>
      <p>题库中暂无听力单元，导入真题后可在此精听。</p>
    </div>
    <div v-else class="listening-list">
      <article v-for="(p, i) in units" :key="p.id || i" class="card listening-item">
        <button class="listening-play" @click="togglePlay(p, i)" :aria-label="playingId === i ? '暂停' : '播放'">
          <Square v-if="playingId === i" :size="18" />
          <Play v-else :size="18" />
        </button>
        <div class="listening-info">
          <strong>{{ p.title || p.unit_title || '听力材料' }}</strong>
          <small>{{ p.paper_year || '' }}{{ p.subtitle || p.subtype || '' }}</small>
        </div>
        <button class="button ghost compact" @click="listen(p)">做题</button>
      </article>

      <!-- v3.4: 精听控制条（变速/循环/复读/进度） -->
      <div v-if="playingId !== null" class="listening-controls card">
        <div class="controls-row">
          <span class="controls-label">语速</span>
          <button v-for="s in [0.75, 1, 1.25, 1.5]" :key="s" class="speed-btn" :class="{ active: speed === s }" @click="setSpeed(s)">{{ s }}x</button>
          <button class="button ghost compact" :class="{ 'loop-on': loop }" @click="toggleLoop">{{ loop ? '循环开' : '循环关' }}</button>
          <button class="button ghost compact" @click="replay"><RotateCcw :size="14" /> 复读</button>
        </div>
        <div class="controls-progress">
          <input type="range" min="0" :max="duration || 0" step="0.1" :value="progress" @input="seek" />
          <span class="progress-time">{{ Math.floor(progress / 60) }}:{{ String(Math.floor(progress % 60)).padStart(2, '0') }} / {{ Math.floor(duration / 60) }}:{{ String(Math.floor(duration % 60)).padStart(2, '0') }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.listening-list { display: flex; flex-direction: column; gap: 10px; }
.listening-item { display: flex; align-items: center; gap: 12px; padding: 14px 16px; }
.listening-play { width: 40px; height: 40px; border-radius: 50%; border: 0; background: var(--primary); color: #fff; display: grid; place-items: center; cursor: pointer; flex-shrink: 0; }
.listening-info { flex: 1; min-width: 0; }
.listening-info strong { display: block; font-size: 14px; }
.listening-info small { font-size: 12px; color: var(--muted); }

.listening-controls { margin-top: 14px; padding: 14px 16px; }
.controls-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.controls-label { font-size: 12px; color: var(--muted); }
.speed-btn { padding: 5px 12px; border-radius: 99px; border: 1px solid var(--line); background: transparent; font-size: 12px; cursor: pointer; color: var(--muted); }
.speed-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
.loop-on { border-color: var(--primary); color: var(--primary); }
.controls-progress { display: flex; align-items: center; gap: 10px; margin-top: 10px; }
.controls-progress input[type=range] { flex: 1; }
.progress-time { font-size: 11px; color: var(--muted); white-space: nowrap; }
</style>
