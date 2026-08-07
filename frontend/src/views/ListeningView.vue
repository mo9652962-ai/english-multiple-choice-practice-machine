<script setup lang="ts">
// v2.49: 听力精听 (听力单元聚合 — 可可英语式精听入口)
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '../api'

const router = useRouter()
const units = ref<any[]>([])
const loading = ref(true)
const error = ref('')

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
        </div>
        <span class="listening-go">播放 →</span>
      </article>
    </div>
  </div>
</template>
