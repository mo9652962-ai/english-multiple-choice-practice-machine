<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../api'

const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    data.value = await get('/achievements')
  } catch (e) { error.value = String(e) }
  loading.value = false
})
</script>

<template>
  <div class="page page-achievements">
    <div class="page-head">
      <div><span class="eyebrow">ACHIEVEMENTS</span><h1>成就徽章</h1><p class="lead">坚持学习，解锁属于你的里程碑。游戏化激励，让每天进步看得见。</p></div>
      <div v-if="data" class="achieve-summary card">
        <strong>{{ data.earned_count }}</strong><span>/ {{ data.total }} 已解锁</span>
      </div>
    </div>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="data" class="achieve-grid">
      <div v-for="b in data.badges" :key="b.key" class="achieve-card" :class="{ earned: b.earned, locked: !b.earned }">
        <div class="achieve-icon" :class="{ 'achieve-icon-dim': !b.earned }">{{ b.icon }}</div>
        <div class="achieve-body">
          <h3>{{ b.name }}</h3>
          <p>{{ b.desc }}</p>
          <div class="achieve-progress">
            <i :style="{ width: b.percent + '%' }"></i>
          </div>
          <span class="achieve-meta">
            <template v-if="b.earned">✅ {{ b.earned_at }}</template>
            <template v-else>{{ b.progress }}/{{ b.target }}</template>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>