<script setup lang="ts">
import { Award, BookOpen, Brush, Flame, Landmark, Medal, PenLine, Play, NotebookPen, Target, Trophy } from 'lucide-vue-next'

// R29: 徽章图标线性化 — 后端 icon 字段(emoji)保留兼容旧版, 前端按 key 映射
const BADGE_ICONS: Record<string, any> = {
  first_practice: Play, streak_7: Flame, streak_14: Flame, streak_30: Flame,
  vocab_100: BookOpen, vocab_1000: Landmark, vocab_master_500: Award,
  wrong_10: Brush, exam_1: PenLine, paper_5: NotebookPen, paper_30: Trophy,
  correct_500: Target,
}
function badgeIcon(key: string) { return BADGE_ICONS[key] || Medal }
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
      <div><span class="eyebrow">成就里程碑</span><h1>成就徽章</h1><p class="lead">坚持学习，解锁属于你的里程碑。游戏化激励，让每天进步看得见。</p></div>
      <div v-if="data" class="achieve-summary card">
        <strong>{{ data.earned_count }}</strong><span>/ {{ data.total }} 已解锁</span>
      </div>
    </div>

    <div v-if="loading" class="card skeleton-card"><span class="skeleton-line"></span><span class="skeleton-line" style="width:72%"></span><span class="skeleton-line" style="width:46%"></span></div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="data" class="achieve-grid">
      <div v-for="b in data.badges" :key="b.key" class="achieve-card" :class="{ earned: b.earned, locked: !b.earned }">
        <div class="achieve-icon" :class="{ 'achieve-icon-dim': !b.earned }"><component :is="badgeIcon(b.key)" :size="26" aria-hidden="true" /></div>
        <div class="achieve-body">
          <h3>{{ b.name }}</h3>
          <p>{{ b.desc }}</p>
          <div class="achieve-progress">
            <i :style="{ width: b.percent + '%' }"></i>
          </div>
          <span class="achieve-meta">
            <template v-if="b.earned">{{ b.earned_at }}</template>
            <template v-else>{{ b.progress }}/{{ b.target }}</template>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
