<script setup lang="ts">
// 雷达图组件 — 12 分类掌握度画像
// 零依赖纯 SVG 实现。value 为 0-100 的掌握分（越高越好，弱点在低分区）
// 数据格式: [{ label: '词汇基础', value: 62 }, ...]，建议 6-12 个轴。

import { computed } from 'vue'

export type RadarAxis = {
  label: string
  value: number
  color?: string
}

const props = withDefaults(
  defineProps<{
    axes: RadarAxis[]
    size?: number
    maxValue?: number
    rings?: number
    /** v3.1: 流式布局——SVG 撑满容器宽度，size 作为 viewBox 坐标系 */
    fluid?: boolean
  }>(),
  { size: 260, maxValue: 100, rings: 4, fluid: false },
)

const CENTER = computed(() => props.size / 2)
const RADIUS = computed(() => props.size / 2 - 40) // 留标签空间

// 轴角度（从正上方开始顺时针）
function axisAngle(index: number): number {
  const count = Math.max(props.axes.length, 3)
  return -Math.PI / 2 + (index / count) * Math.PI * 2
}

function axisPoint(index: number, ratio: number): { x: number; y: number } {
  const angle = axisAngle(index)
  return {
    x: CENTER.value + RADIUS.value * ratio * Math.cos(angle),
    y: CENTER.value + RADIUS.value * ratio * Math.sin(angle),
  }
}

// 数据多边形
const polygon = computed(() =>
  props.axes
    .map((axis, index) => {
      const ratio = Math.max(0, Math.min(1, axis.value / props.maxValue))
      const point = axisPoint(index, ratio)
      return `${point.x.toFixed(1)},${point.y.toFixed(1)}`
    })
    .join(' '),
)

// 网格环
const ringPolygons = computed(() =>
  Array.from({ length: props.rings }, (_, ring) => {
    const ratio = (ring + 1) / props.rings
    return Array.from({ length: Math.max(props.axes.length, 3) }, (_, index) => {
      const point = axisPoint(index, ratio)
      return `${point.x.toFixed(1)},${point.y.toFixed(1)}`
    }).join(' ')
  }),
)

// 轴线与标签
const axisLines = computed(() =>
  props.axes.map((_, index) => {
    const outer = axisPoint(index, 1)
    return { x1: CENTER.value, y1: CENTER.value, x2: outer.x, y2: outer.y }
  }),
)

const axisLabels = computed(() =>
  props.axes.map((axis, index) => {
    const point = axisPoint(index, 1.18)
    return {
      x: point.x,
      y: point.y,
      text: axis.label.length > 5 ? axis.label.slice(0, 5) + '…' : axis.label,
      full: axis.label,
      value: axis.value,
    }
  }),
)

// 数据点（悬停提示用）
const dataPoints = computed(() =>
  props.axes.map((axis, index) => ({
    ...axisPoint(index, Math.max(0, Math.min(1, axis.value / props.maxValue))),
    color: axis.color,
    label: axis.label,
    value: axis.value,
  })),
)
</script>

<template>
  <div class="radar-chart" :class="{ fluid }">
    <svg :width="fluid ? '100%' : size" :height="fluid ? '100%' : size"
         :viewBox="`0 0 ${size} ${size}`" role="img"
         aria-label="错误原因掌握度雷达图">
      <polygon v-for="(ring, i) in ringPolygons" :key="i" :points="ring"
               fill="none" stroke="var(--line, #e5ded3)" stroke-width="1"
               :opacity="i === ringPolygons.length - 1 ? 1 : 0.55" />
      <line v-for="(line, i) in axisLines" :key="i" v-bind="line"
            stroke="var(--line, #e5ded3)" stroke-width="1" opacity="0.55" />
      <polygon :points="polygon" fill="var(--primary, #486d5c)"
               fill-opacity="0.18" stroke="var(--primary, #486d5c)" stroke-width="2"
               stroke-linejoin="round" />
      <circle v-for="(point, i) in dataPoints" :key="i" :cx="point.x" :cy="point.y"
              r="3.5" :fill="point.color || 'var(--primary, #486d5c)'">
        <title>{{ point.label }}：掌握度 {{ point.value }}/100</title>
      </circle>
      <text v-for="(label, i) in axisLabels" :key="i" :x="label.x" :y="label.y"
            text-anchor="middle" dominant-baseline="middle" class="radar-axis-label">
        <title>{{ label.full }}</title>
        {{ label.text }}
      </text>
    </svg>
  </div>
</template>

<style scoped>
.radar-chart.fluid {
  width: 100%;
  max-width: 300px;
  margin: 0 auto;
}
.radar-chart.fluid svg {
  display: block;
  aspect-ratio: 1 / 1;
  height: auto;
}
.radar-axis-label {
  font-size: 10px;
  fill: var(--muted, #8b8378);
}
</style>
