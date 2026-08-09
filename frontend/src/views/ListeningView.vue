<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '../api'
import { Headphones, Play, Square } from 'lucide-vue-next'

const router = useRouter()
const units = ref<any[]>([])
const loading = ref(true)
const error = ref('')
const playingId = ref<number | null>(null)
const audioEl = ref<HTMLAudioElement | null>(null)

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
  // 复用单个 audio 元素（避免同时多音频）
  if (audioEl.value) {
    audioEl.value.src = p.audio_url
    audioEl.value.play().catch(() => { playingId.value = null })
  }
}

function onAudioEnded() { playingId.value = null }
</script>

<template>
  <div class="page page-listening">
    <div class="page-head">
      <div>
        <span class="eyebrow">LISTENING</span>
        <h1>听力精听</h1>
        <p class="lead">集中练习听力篇章，磨耳朵从每一句开始。</p>
      </div>
    </div>

    <audio ref="audioEl" @ended="onAudioEnded" style="display:none"></audio>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="!units.length" class="card empty illustrated-empty">
      <div><Headphones :size="25" /><strong>暂无听力单元</strong></div>
      <p>当前题库还没有听力篇章，去导入或添加听力题型。</p>
    </div>
    <div v-else class="listening-grid">
      <article v-for="(p, i) in units" :key="i" class="card listening-card" @click="listen(p)">
        <span class="listening-icon">🎧</span>
        <div class="listening-body">
          <h3 class="listening-title">{{ p.title || p.unit_title || `听力 ${i + 1}` }}</h3>
          <span class="listening-meta">{{ p.year || '听力练习' }} · {{ p.paper_title || '篇章' }}</span>
          <span v-if="p.audio_url" class="listening-audio-badge">🔊 含音频</span>
        </div>
        <button
          v-if="p.audio_url"
          class="listening-play"
          type="button"
          :aria-label="playingId === i ? '暂停' : '播放预览'"
          @click.stop="togglePlay(p, i)"
        >
          <Square v-if="playingId === i" :size="15" />
          <Play v-else :size="15" />
        </button>
        <span v-else class="listening-go">播放 →</span>
      </article>
    </div>
  </div>
</template>

<style scoped>
.listening-card { display: flex; align-items: center; gap: 12px; cursor: pointer; transition: transform .2s; }
.listening-card:hover { transform: translateY(-2px); }
.listening-icon { font-size: 20px; }
.listening-body { flex: 1; min-width: 0; }
.listening-title { margin: 0 0 4px; font-size: 15px; }
.listening-meta { font-size: 12px; color: var(--muted, #888); }
.listening-audio-badge { display: inline-block; margin-left: 8px; font-size: 11px; color: #e5444c; }
.listening-play { width: 34px; height: 34px; border-radius: 50%; border: 1px solid var(--line, #e5e0d6); background: var(--surface-solid, #fff); color: #e5444c; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.listening-go { font-size: 12.5px; color: #e5444c; font-weight: 600; flex-shrink: 0; }
</style>
