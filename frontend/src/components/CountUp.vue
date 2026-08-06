<script setup lang="ts">
// 数字滚动动画组件 — 从 0 滚动到目标值
// 参考: CSS-Tricks Animating Number Counters + prefers-reduced-motion 无障碍
// 用法: <CountUp :value="data.paper_count" />

import { onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  value: number
  duration?: number
}>(), {
  duration: 900,
})

const display = ref(0)
let raf = 0

// 尊重系统"减少动态效果"设置
const prefersReduced = typeof window !== 'undefined'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches

function animateTo(target: number) {
  cancelAnimationFrame(raf)
  if (prefersReduced) {
    display.value = target
    return
  }
  const start = performance.now()
  const from = display.value
  const step = (now: number) => {
    const t = Math.min(1, (now - start) / props.duration)
    // easeOutCubic: 先快后慢
    const eased = 1 - Math.pow(1 - t, 3)
    display.value = Math.round(from + (target - from) * eased)
    if (t < 1) raf = requestAnimationFrame(step)
    else display.value = target
  }
  raf = requestAnimationFrame(step)
}

onMounted(() => animateTo(props.value))
watch(() => props.value, animateTo)
</script>

<template>
  <span class="count-up">{{ display }}</span>
</template>

<style scoped>
.count-up { font-variant-numeric: tabular-nums; }
</style>
