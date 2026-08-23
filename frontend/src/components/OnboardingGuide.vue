<script setup lang="ts">
// v9.33: 新手引导 Onboarding——4 步完成激活（选目标→选题库→首练→勋章）
// 设计依据: 千轮研究 2026-08-23《墨题用户体验完善》
//   - 引导 ≤4 步, 完成首练即 Aha Moment（错题自动进错题本）
//   - 目标设定按钮比"继续"按钮有效(多邻国), 鼓励稍高目标
//   - localStorage 'epm_onboarded' 持久化, 可跳过
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from '../services/toast'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'close'): void }>()

const router = useRouter()
const step = ref(1)

// 步骤 1: 学习目标（3 选 1, 鼓励中高目标）
const goals = [
  { key: 'casual', label: '轻松练', desc: '每天 10 题 · 保持手感', value: 10, icon: '🌱' },
  { key: 'steady', label: '稳步提升', desc: '每天 30 题 · 系统刷完', value: 30, icon: '⚡' },
  { key: 'sprint', label: '冲刺备考', desc: '每天 50 题 · 全力以赴', value: 50, icon: '🔥' },
]
const pickedGoal = ref<number>(0)
const exam = localStorage.getItem('epm_exam_type') || ''

// 步骤 2: 入口推荐（按考试类型给一条最短路径）
const entryRoute = computed(() => {
  if (exam.includes('考研')) return { path: '/practice', label: '去真题练习', hint: '历年考研英语真题已就绪' }
  if (exam.includes('四级') || exam.includes('六级')) return { path: '/practice', label: '去真题练习', hint: '四六级真题已就绪' }
  return { path: '/library', label: '先逛题库', hint: '导入真题或从题库开始' }
})

function pickGoal(g: { value: number; label: string }) {
  pickedGoal.value = g.value
  localStorage.setItem('epm_daily_goal', String(g.value))
  step.value = 2
}

function goEntry() {
  localStorage.setItem('epm_onboarded_step', '3')
  router.push(entryRoute.value.path)
  finish('first_practice_pending')
}

function skip() {
  finish('skipped')
}

function finish(state: string) {
  localStorage.setItem('epm_onboarded', '1')
  localStorage.setItem('epm_onboarded_state', state)
  emit('close')
  showToast(state === 'skipped' ? '已跳过，随时可在目标中心设置' : `目标已设为 ${pickedGoal.value} 题/天`, 'success')
}
// 首练完成后由 Dashboard 调用：标记完成（v9.33）
function markOnboardDone() {
  localStorage.setItem('epm_onboarded_state', 'done')
}
defineExpose({ markOnboardDone })
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="onb-mask">
      <div class="onb-card">
        <!-- 步骤指示 -->
        <div class="onb-dots">
          <span v-for="i in 2" :key="i" class="dot" :class="{ active: step >= i }" />
        </div>

        <!-- Step 1: 选学习目标 -->
        <template v-if="step === 1">
          <h2 class="onb-title">👋 欢迎！设个小目标</h2>
          <p class="onb-sub">有目标的练习者坚持率高出 3 倍。选一个适合自己的节奏：</p>
          <button
            v-for="g in goals" :key="g.key"
            class="goal-card" @click="pickGoal(g)"
          >
            <span class="goal-icon">{{ g.icon }}</span>
            <span class="goal-body">
              <b>{{ g.label }}</b>
              <small>{{ g.desc }}</small>
            </span>
            <span class="goal-arrow">›</span>
          </button>
        </template>

        <!-- Step 2: 最短路径入口 -->
        <template v-else-if="step === 2">
          <h2 class="onb-title">🎯 目标 {{ pickedGoal }} 题/天</h2>
          <p class="onb-sub">{{ entryRoute.hint }}。完成第一次练习后，错题会自动收进错题本。</p>
          <button class="goal-card primary" @click="goEntry">
            <span class="goal-icon">📝</span>
            <span class="goal-body"><b>{{ entryRoute.label }}</b><small>完成首练 → 解锁「初出茅庐」徽章</small></span>
            <span class="goal-arrow">›</span>
          </button>
        </template>

        <button class="onb-skip" @click="skip">跳过引导</button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.onb-mask{position:fixed;inset:0;z-index:1000;background:rgba(0,0,0,.45);display:flex;align-items:center;justify-content:center;padding:20px}
.onb-card{background:var(--surface,#fff);border-radius:20px;padding:28px 24px 18px;max-width:400px;width:100%;box-shadow:0 20px 60px rgba(0,0,0,.25)}
.onb-dots{display:flex;gap:6px;margin-bottom:16px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--border,#ddd)}
.dot.active{background:var(--primary,#4f7cff);width:20px;border-radius:4px}
.onb-title{font-size:20px;font-weight:700;margin:0 0 6px;color:var(--text,#222)}
.onb-sub{font-size:13px;color:var(--text-secondary,#888);margin:0 0 18px;line-height:1.5}
.goal-card{display:flex;align-items:center;gap:12px;width:100%;padding:14px 16px;margin-bottom:10px;border:1.5px solid var(--border,#e5e5e5);border-radius:14px;background:var(--surface,#fff);cursor:pointer;text-align:left;transition:border-color .15s, transform .1s}
.goal-card:hover{border-color:var(--primary,#4f7cff);transform:translateY(-1px)}
.goal-card.primary{border-color:var(--primary,#4f7cff);background:color-mix(in srgb,var(--primary,#4f7cff) 6%,var(--surface,#fff))}
.goal-icon{font-size:26px;flex-shrink:0}
.goal-body{flex:1;display:flex;flex-direction:column;gap:2px}
.goal-body b{font-size:15px;color:var(--text,#222)}
.goal-body small{font-size:12px;color:var(--text-secondary,#999)}
.goal-arrow{font-size:22px;color:var(--text-secondary,#bbb)}
.onb-skip{width:100%;margin-top:6px;background:none;border:none;font-size:12px;color:var(--text-secondary,#aaa);cursor:pointer;padding:8px}
.onb-skip:hover{color:var(--text-secondary,#777)}
</style>
