<script setup lang="ts">
import { Flame } from 'lucide-vue-next'
// v2.40: 庆祝动效覆盖层 (多邻国式 micro-interaction)
// 触发: 练习高正确率撒花 / 打卡里程碑火焰
import { onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{
  show: boolean
  kind?: 'confetti' | 'flame'
  title: string
  subtitle?: string
}>(), { kind: 'confetti', subtitle: '' })

const emit = defineEmits<{ (e: 'close'): void }>()

const particles = Array.from({ length: 24 }, (_, i) => ({
  id: i,
  left: 8 + Math.random() * 84,
  delay: Math.random() * 0.35,
  dur: 1.6 + Math.random() * 1.2,
  color: ['#c97b4a', '#4a6fa5', '#6b8e5a', '#a8842f', '#8e44ad', '#c0392b'][i % 6],
  size: 6 + Math.random() * 8,
}))

onMounted(() => {
  const t = setTimeout(() => emit('close'), 3200)
  return () => clearTimeout(t)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="celebrate-fade">
      <div v-if="show" class="celebrate-overlay" @click="emit('close')">
        <!-- 粒子撒花 -->
        <span
          v-for="p in particles" :key="p.id"
          class="celebrate-particle"
          :style="{
            left: p.left + '%',
            background: p.color,
            width: p.size + 'px',
            height: p.size + 'px',
            animationDelay: p.delay + 's',
            animationDuration: p.dur + 's',
          }"
        ></span>
        <!-- 火焰 (打卡里程碑) -->
        <div v-if="kind === 'flame'" class="celebrate-flame-wrap">
          <span class="celebrate-flame"><Flame :size="64" aria-hidden="true" /></span>
        </div>
        <!-- 墨滴扩散 (撒花) -->
        <div v-else class="celebrate-ink" aria-hidden="true"></div>
        <div class="celebrate-card">
          <b class="celebrate-title">{{ title }}</b>
          <p v-if="subtitle" class="celebrate-sub">{{ subtitle }}</p>
          <span class="celebrate-tip">点击关闭</span>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
