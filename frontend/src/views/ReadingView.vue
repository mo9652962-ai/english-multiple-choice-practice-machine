<script setup lang="ts">
// v2.49: 阅读训练 (词文串学短文阅读 — 借签薄荷阅读语境学习)
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '../api'

const router = useRouter()
const passages = ref<any[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    // 复用词文串学接口: 按题型取短文 (reading/cloze)
    const r: any = await get('/vocab/context?limit=6')
    const list = Array.isArray(r) ? r : r?.items || r?.passages || []
    passages.value = list
  } catch (e) {
    // 兜底: 用题库里的阅读单元
    try {
      const lib: any = await get('/library/units?unit_type=reading&limit=6')
      passages.value = Array.isArray(lib) ? lib : lib?.items || []
    } catch (e2) { error.value = String(e2) }
  }
  loading.value = false
})

function startPractice(p: any) {
  if (p.unit_id || p.id) {
    router.push(`/practice?unit=${p.unit_id || p.id}`)
  } else {
    router.push('/library')
  }
}
</script>

<template>
  <div class="page page-reading">
    <div class="page-head">
      <div>
        <span class="eyebrow">READING</span>
        <h1>阅读训练</h1>
        <p class="lead">在真实语境中读短文、学单词，理解比背诵更重要。</p>
      </div>
    </div>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="!passages.length" class="card empty illustrated-empty">
      <div><BookOpenText :size="25" /><strong>暂无阅读内容</strong></div>
      <p>去题库添加阅读篇章，或先在单词本学习一些词汇。</p>
    </div>
    <div v-else class="reading-grid">
      <article v-for="(p, i) in passages" :key="i" class="card reading-card" @click="startPractice(p)">
        <span class="reading-badge">READING</span>
        <h3 class="reading-title">{{ p.title || p.unit_title || `阅读短文 ${i + 1}` }}</h3>
        <p class="reading-excerpt">{{ (p.passage || p.excerpt || '').slice(0, 120) }}…</p>
        <span class="reading-go">开始阅读 →</span>
      </article>
    </div>
  </div>
</template>
