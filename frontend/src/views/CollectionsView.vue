<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { del, get } from '../api'
import { showToast } from '../services/toast'

const router = useRouter()
const items = ref<any[]>([])
const loading = ref(true)

const TYPE_LABELS: Record<string, string> = {
  long_sentence: '长难句', option: '选项', keyword: '关键词', note: '笔记',
}

async function load() {
  loading.value = true
  try {
    items.value = await get('/collections')
  } catch (e) {
    showToast(`加载典藏失败：${e}`, 'error')
  } finally {
    loading.value = false
  }
}

async function remove(id: number) {
  try {
    await del(`/collections/${id}`)
    items.value = items.value.filter((i) => i.id !== id)
    showToast('已取消典藏', 'success')
  } catch (e) {
    showToast(`删除失败：${e}`, 'error')
  }
}

function practice(questionId: number) {
  router.push(`/practice?question_id=${questionId}`)
}

onMounted(load)
</script>

<template>
  <div class="page page-vocab">
    <div class="page-head">
      <div>
        <span class="eyebrow">藏经阁 · 收藏夹</span>
        <h1>精讲典藏</h1>
        <p class="lead">AI 精讲中收藏的长难句与解析片段——复习时随时回看。</p>
      </div>
      <button class="button ghost" type="button" @click="router.push('/wrong')">← 返回错题本</button>
    </div>

    <div v-if="loading" class="lead" style="padding: 40px 0">加载中…</div>
    <div v-else-if="!items.length" class="card" style="padding: 32px; text-align:center">
      <p class="lead">暂无典藏——在真题精讲抽屉里点「典藏」收藏长难句/解析片段。</p>
    </div>

    <div v-else class="collections-list">
      <div v-for="item in items" :key="item.id" class="card collection-card">
        <div class="collection-head">
          <span class="collection-type">{{ TYPE_LABELS[item.fragment_type] || item.fragment_type }}</span>
          <span class="collection-meta">
            <span v-if="item.unit_title">{{ item.unit_title }}</span>
            <span v-if="item.question_number">第 {{ item.question_number }} 题</span>
            <span>{{ item.created_at }}</span>
          </span>
          <button class="button ghost compact" type="button" @click="remove(item.id)">移除</button>
        </div>
        <p class="collection-content">{{ item.content }}</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.collections-list { display: flex; flex-direction: column; gap: 12px; max-width: 860px; }
.collection-card { padding: 14px 18px; }
.collection-head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.collection-type { font-family: Georgia, 'Times New Roman', serif; font-size: 13px; color: #B84A39; border: 1px solid #E8E0D2; border-radius: 999px; padding: 2px 10px; }
.collection-meta { flex: 1; font-size: 11px; color: #8A7D6D; display: flex; gap: 10px; }
.collection-content { font-size: 14px; line-height: 1.7; color: #3B332B; white-space: pre-wrap; }
</style>
