<script setup lang="ts">
// 学习热力图组件 — GitHub 贡献图风格
// 零依赖纯 SVG 实现，7 行（周一~周日）× N 列（周）
// 数据格式: [{date: "2026-02-01", count: 3}, ...]

import { computed } from 'vue'

const props = defineProps<{
  values: { date: string; count: number }[]
  endDate?: string
  tooltipUnit?: string
}>()

const CELL = 11
const GAP = 3
const ROWS = 7

// 解析日期为 YYYY-MM-DD
function fmt(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

const end = computed(() => {
  const d = props.endDate ? new Date(props.endDate) : new Date()
  return fmt(d)
})

// 构建周矩阵（列=周，行=星期）
const weeks = computed(() => {
  const counts = new Map(props.values.map(v => [v.date, v.count]))
  const endDate = new Date(end.value + 'T00:00:00')
  // 找到结束日所在周的周一
  const dow = (endDate.getDay() + 6) % 7 // 周一=0
  const monday = new Date(endDate)
  monday.setDate(endDate.getDate() - dow)
  // 26 周 = 半年
  const start = new Date(monday)
  start.setDate(monday.getDate() - 26 * 7)

  const result: { date: string; count: number }[][] = []
  for (let w = 0; w < 27; w++) {
    const col: { date: string; count: number }[] = []
    for (let r = 0; r < ROWS; r++) {
      const d = new Date(start)
      d.setDate(start.getDate() + w * 7 + r)
      const ds = fmt(d)
      col.push({ date: ds, count: counts.get(ds) || 0 })
    }
    result.push(col)
  }
  return result
})

// 颜色分级（与主色调一致，从浅到深）
function level(count: number): number {
  if (count <= 0) return 0
  if (count === 1) return 1
  if (count <= 2) return 2
  if (count <= 4) return 3
  return 4
}

const maxCount = computed(() =>
  Math.max(1, ...props.values.map(v => v.count))
)

function titleFor(d: { date: string; count: number }): string {
  const label = props.tooltipUnit || '次学习'
  return `${d.date}：${d.count} ${label}`
}

const months = computed(() => {
  // 生成列底部月份标签
  const out: { index: number; label: string }[] = []
  let lastMonth = ''
  weeks.value.forEach((col, i) => {
    const d = new Date(col[3].date + 'T00:00:00') // 每周中间日
    const m = `${d.getFullYear()}-${d.getMonth()}`
    if (m !== lastMonth) {
      out.push({ index: i, label: `${d.getMonth() + 1}月` })
      lastMonth = m
    }
  })
  return out
})
</script>

<template>
  <div class="heatmap-wrap">
    <svg :width="weeks.length * (CELL + GAP) + 2" :height="ROWS * (CELL + GAP) + 24" class="heatmap-svg">
      <g v-for="(col, w) in weeks" :key="'c' + w">
        <rect
          v-for="(d, r) in col"
          :key="d.date"
          :x="w * (CELL + GAP)"
          :y="r * (CELL + GAP) + 12"
          :width="CELL"
          :height="CELL"
          rx="2"
          :class="`heat-cell l${level(d.count)}`"
          :data-count="d.count"
        >
          <title>{{ titleFor(d) }}</title>
        </rect>
      </g>
      <text
        v-for="m in months"
        :key="m.index"
        :x="m.index * (CELL + GAP)"
        :y="10"
        class="heat-month"
      >{{ m.label }}</text>
    </svg>
    <div class="heat-legend">
      <span>少</span>
      <span class="heat-cell l0 heat-legend-cell" />
      <span class="heat-cell l1 heat-legend-cell" />
      <span class="heat-cell l2 heat-legend-cell" />
      <span class="heat-cell l3 heat-legend-cell" />
      <span class="heat-cell l4 heat-legend-cell" />
      <span>多</span>
    </div>
  </div>
</template>

<style scoped>
.heatmap-wrap {
  overflow-x: auto;
  max-width: 100%;
}
.heatmap-svg {
  display: block;
}
.heat-cell {
  fill: var(--heat-l0, #ebedf0);
}
.heat-cell.l1 { fill: var(--heat-l1, #c6e6c9); }
.heat-cell.l2 { fill: var(--heat-l2, #8fd494); }
.heat-cell.l3 { fill: var(--heat-l3, #4cae57); }
.heat-cell.l4 { fill: var(--heat-l4, #2d8a3a); }
.heat-month {
  font-size: 9px;
  fill: var(--text-dim, #888);
}
.heat-legend {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-dim, #888);
  margin-top: 6px;
}
.heat-legend-cell {
  width: 11px;
  height: 11px;
  border-radius: 2px;
  display: inline-block;
}
</style>
