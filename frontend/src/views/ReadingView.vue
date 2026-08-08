<script setup lang="ts">
// v2.49: 阅读训练 (词文串学短文阅读 — 借签薄荷阅读语境学习)
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get, post } from '../api'

const router = useRouter()
const passages = ref<any[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    // v2.77: 直接使用 /library/units (原 /vocab/context 不存在, 会返回 HTML 导致 JSON 解析失败)
    const r: any = await get('/library/units?unit_type=reading&limit=6')
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

async function startPractice(p: any) {
  // v3.0-fix: 创建会话再跳转（原直跳 /practice?unit= 导致 params.id 为 undefined → 空白）
  const unitId = p.unit_id || p.id
  if (!unitId) { router.push('/library'); return }
  try {
    const session: any = await post('/practice/sessions', {
      mode: 'unit', unit_ids: [unitId], shuffle_options: true,
    })
    router.push(`/practice/${session.id}`)
  } catch (e) {
    error.value = String(e)
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
