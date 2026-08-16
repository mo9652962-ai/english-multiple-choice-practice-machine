<script setup lang="ts">
// 趋势折线图组件 — 错误原因占比随报告序列的变化
// 零依赖纯 SVG 实现，多序列 + 网格 + 图例 + 悬停数值
// 数据格式: { labels: ['8/10', '8/12'], series: [{ name: '词汇', color: '#c73e3a', points: [50, 25] }] }

import { computed } from 'vue'

export type TrendSeries = {
  name: string
  color?: string
  points: number[]
}

const props = withDefaults(
  defineProps<{
    labels: string[]
    series: TrendSeries[]
    width?: number
    height?: number
    maxValue?: number
    unit?: string
    /** v3.1: 流式布局——SVG 撑满容器宽度按 viewBox 等比缩放（移动端横滑查看细节） */
    fluid?: boolean
  }>(),
  { width: 560, height: 240, maxValue: 100, unit: '%', fluid: false },
)

const PALETTE = [
  '#c73e3a', '#e67e22', '#3e6b52', '#4c6ef5', '#7c5cd6',
  '#d65c9a', '#3b7d8c', '#8a9a3b',
]

const PADDING = { top: 16, right: 16, bottom: 34, left: 38 }
const plotWidth = computed(() => props.width - PADDING.left - PADDING.right)
const plotHeight = computed(() => props.height - PADDING.top - PADDING.bottom)

const coloredSeries = computed(() =>
  props.series.map((s, i) => ({ ...s, color: s.color || PALETTE[i % PALETTE.length] })),
)

const GRID_STEPS = computed(() => [0, 0.25, 0.5, 0.75, 1])

function x(index: number): number {
  const count = Math.max(props.labels.length, 2)
  return PADDING.left + (index / (count - 1)) * plotWidth.value
}

function y(value: number): number {
  const ratio = Math.max(0, Math.min(1, value / props.maxValue))
  return PADDING.top + (1 - ratio) * plotHeight.value
}

const polylines = computed(() =>
  coloredSeries.value.map(series => ({
    ...series,
    points: series.points
      .map((value, index) => `${x(index).toFixed(1)},${y(value).toFixed(1)}`)
      .join(' '),
    dots: series.points.map((value, index) => ({
      cx: x(index),
      cy: y(value),
      value,
      label: props.labels[index],
      seriesName: series.name,
    })),
  })),
)

const xLabels = computed(() =>
  props.labels.map((label, index) => ({
    x: x(index),
    y: props.height - PADDING.bottom + 18,
    text: label.length > 8 ? label.slice(0, 8) + '…' : label,
    full: label,
  })),
)

const yLabels = computed(() =>
  GRID_STEPS.value.map(step => ({
    x: PADDING.left - 8,
    y: y(step * props.maxValue),
    text: `${Math.round(step * props.maxValue)}${props.unit}`,
  })),
)

const gridLines = computed(() =>
  GRID_STEPS.value.map(step => ({
    x1: PADDING.left,
    y1: y(step * props.maxValue),
    x2: props.width - PADDING.right,
    y2: y(step * props.maxValue),
  })),
)
</script>

<template>
  <div class="trend-line-chart" :class="{ fluid }">
    <svg :width="fluid ? '100%' : width" :height="fluid ? '100%' : height"
         :viewBox="`0 0 ${width} ${height}`" role="img"
         aria-label="错误原因占比趋势折线图">
      <g>
        <line v-for="(line, i) in gridLines" :key="i" v-bind="line"
              stroke="var(--line, #e5ded3)" stroke-width="1" opacity="0.6" />
        <text v-for="(label, i) in yLabels" :key="'y' + i" :x="label.x" :y="label.y + 3"
              text-anchor="end" class="trend-axis-text">{{ label.text }}</text>
        <text v-for="(label, i) in xLabels" :key="'x' + i" :x="label.x" :y="label.y"
              text-anchor="middle" class="trend-axis-text">
          <title>{{ label.full }}</title>
          {{ label.text }}
        </text>
      </g>
      <g v-for="(line, i) in polylines" :key="'s' + i">
        <polyline :points="line.points" fill="none" :stroke="line.color"
                  stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
        <circle v-for="(dot, j) in line.dots" :key="j" :cx="dot.cx" :cy="dot.cy" r="4"
                :fill="line.color" stroke="var(--surface-solid, #fff)" stroke-width="1.5">
          <title>{{ dot.seriesName }} · {{ dot.label }}：{{ dot.value }}{{ unit }}</title>
        </circle>
      </g>
    </svg>
    <div v-if="coloredSeries.length" class="trend-legend">
      <span v-for="series in coloredSeries" :key="series.name" class="trend-legend-item">
        <i :style="{ background: series.color }" />
        {{ series.name }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.trend-line-chart.fluid svg {
  display: block;
  width: 100%;
  height: auto;
}
.trend-axis-text {
  font-size: 10px;
  fill: var(--muted, #8b8378);
}
.trend-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  justify-content: center;
  margin-top: 6px;
}
.trend-legend-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--muted, #8b8378);
}
.trend-legend-item i {
  width: 10px;
  height: 3px;
  border-radius: 2px;
  display: inline-block;
}
</style>
