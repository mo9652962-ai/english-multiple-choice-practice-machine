<script setup lang="ts">
// 环形图组件 — 12 分类错误原因占比
// 零依赖纯 SVG 实现（与 StudyHeatmap 同风格）
// 数据格式: [{ label: '词汇基础', value: 12, color: '#c73e3a' }, ...]
// value 为 0 的项不绘制扇区；空数据渲染占位环。

import { computed } from 'vue'

export type DonutItem = {
  label: string
  value: number
  color?: string
}

const props = withDefaults(
  defineProps<{
    items: DonutItem[]
    size?: number
    thickness?: number
    centerLabel?: string
    centerValue?: string | number
    /** v3.1: 流式布局——SVG 撑满容器宽度（移动端必需），size 作为 viewBox 坐标系 */
    fluid?: boolean
  }>(),
  { size: 220, thickness: 26, centerLabel: '', centerValue: '', fluid: false },
)

const PALETTE = [
  '#c73e3a', '#e67e22', '#e6a23c', '#8a9a3b', '#3e6b52',
  '#3b7d8c', '#4c6ef5', '#7c5cd6', '#b05cd6', '#d65c9a',
  '#8d6e63', '#9aa0a6',
]

const RADIUS = computed(() => (props.size - props.thickness) / 2)
const CENTER = computed(() => props.size / 2)

// 过滤掉 0 值项并补默认色
const slices = computed(() => {
  const active = props.items.filter(item => item.value > 0)
  return active.map((item, index) => ({
    ...item,
    color: item.color || PALETTE[index % PALETTE.length],
    percentage: item.value,
  }))
})

const total = computed(() => slices.value.reduce((sum, s) => sum + s.value, 0))

// SVG 弧线路径（donut 段）
function arcPath(startAngle: number, endAngle: number): string {
  const t = props.thickness
  const r = RADIUS.value
  const c = CENTER.value
  const large = endAngle - startAngle > Math.PI ? 1 : 0
  const x1 = c + r * Math.cos(startAngle)
  const y1 = c + r * Math.sin(startAngle)
  const x2 = c + r * Math.cos(endAngle)
  const y2 = c + r * Math.sin(endAngle)
  // 全占比时闭合圆环用两个半环，避免 single-arc 渲染异常
  if (endAngle - startAngle >= 2 * Math.PI - 0.0001) {
    return [
      `M ${c} ${c - r} A ${r} ${r} 0 0 1 ${c} ${c + r}`,
      `A ${r} ${r} 0 0 1 ${c} ${c - r}`,
    ].join(' ')
  }
  return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`
}

const arcs = computed(() => {
  if (!total.value) return []
  let angle = -Math.PI / 2
  return slices.value.map(slice => {
    const sweep = (slice.value / total.value) * Math.PI * 2
    const path = arcPath(angle, angle + sweep)
    angle += sweep
    return { ...slice, path }
  })
})
</script>

<template>
  <div class="donut-chart" :class="{ fluid }" :style="fluid ? undefined : { width: `${size}px` }">
    <svg :width="fluid ? '100%' : size" :height="fluid ? '100%' : size"
         :viewBox="`0 0 ${size} ${size}`" role="img"
         :aria-label="`错误原因占比环形图，共 ${total} 项`">
      <!-- 空数据占位环 -->
      <circle v-if="!arcs.length" :cx="CENTER" :cy="CENTER" :r="RADIUS"
              fill="none" stroke="var(--line)" :stroke-width="thickness" opacity="0.6" />
      <path v-for="(arc, i) in arcs" :key="i" :d="arc.path" fill="none"
            :stroke="arc.color" :stroke-width="thickness" stroke-linecap="butt">
        <title>{{ arc.label }}：{{ arc.value }}（{{ arc.percentage }}%）</title>
      </path>
      <text v-if="centerValue !== ''" :x="CENTER" :y="CENTER - 4"
            text-anchor="middle" class="donut-center-value">{{ centerValue }}</text>
      <text v-if="centerLabel" :x="CENTER" :y="CENTER + 16"
            text-anchor="middle" class="donut-center-label">{{ centerLabel }}</text>
    </svg>
  </div>
</template>

<style scoped>
.donut-chart.fluid {
  width: 100%;
  max-width: 320px;
  margin: 0 auto;
}
.donut-chart.fluid svg {
  display: block;
  aspect-ratio: 1 / 1;
  height: auto;
}
.donut-center-value {
  font-size: 26px;
  font-weight: 700;
  fill: var(--ink, #2a2622);
}
.donut-center-label {
  font-size: 10px;
  fill: var(--muted, #8b8378);
}
</style>
