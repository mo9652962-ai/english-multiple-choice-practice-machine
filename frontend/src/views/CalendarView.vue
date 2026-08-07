<script setup lang="ts">
// v2.49: 学习日历 (Focus-To-Do 日历视图)
import { onMounted, ref } from 'vue'
import { get } from '../api'

const year = ref(new Date().getFullYear())
const month = ref(new Date().getMonth() + 1)
const data = ref<any>(null)
const loading = ref(true)
const error = ref('')

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

async function load() {
  loading.value = true
  try {
    data.value = await get(`/calendar?year=${year.value}&month=${month.value}`)
  } catch (e) { error.value = String(e) }
  loading.value = false
}
onMounted(load)

function prevMonth() {
  month.value -= 1
  if (month.value < 1) { month.value = 12; year.value -= 1 }
  load()
}
function nextMonth() {
  month.value += 1
  if (month.value > 12) { month.value = 1; year.value += 1 }
  load()
}
function firstWeekday(): number {
  return new Date(year.value, month.value - 1, 1).getDay()
}
function daysInMonth(): number {
  return new Date(year.value, month.value, 0).getDate()
}
function dayTotal(day: string): number {
  const found = (data.value?.days || []).find((d: any) => d.day === day)
  return found?.total || 0
}
function dayLevel(day: string): number {
  const t = dayTotal(day)
  if (t <= 0) return 0
  if (t < 5) return 1
  if (t < 15) return 2
  if (t < 40) return 3
  return 4
}
function isToday(day: string): boolean {
  const t = new Date().toISOString().slice(0, 10)
  return day === t
}
</script>

<template>
  <div class="page page-calendar">
    <div class="page-head">
      <div>
        <span class="eyebrow">CALENDAR</span>
        <h1>学习日历</h1>
        <p class="lead">每一天的学习足迹，都在这里留下印记。</p>
      </div>
      <div v-if="data" class="cal-total">
        本月 {{ data.total_activities }} 次学习活动
      </div>
    </div>

    <div class="card calendar-card">
      <div class="cal-head">
        <button class="button ghost compact" @click="prevMonth">‹</button>
        <h3 class="cal-title">{{ year }} 年 {{ month }} 月</h3>
        <button class="button ghost compact" @click="nextMonth">›</button>
      </div>

      <div v-if="loading" class="muted" style="padding:30px;text-align:center">加载中…</div>
      <div v-else-if="error" class="warning">{{ error }}</div>
      <template v-else>
        <div class="cal-weekdays">
          <span v-for="w in WEEKDAYS" :key="w">{{ w }}</span>
        </div>
        <div class="cal-grid">
          <span v-for="i in firstWeekday()" :key="'blank-' + i" class="cal-cell blank"></span>
          <span
            v-for="d in daysInMonth()" :key="d"
            class="cal-cell" :class="['heat-l' + dayLevel(`${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`), { today: isToday(`${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`) }]"
            :title="`${month}月${d}日 · ${dayTotal(`${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`)} 次活动`"
          >
            {{ d }}
          </span>
        </div>
        <div class="cal-legend">
          <span>少</span>
          <i class="heat-cell" style="width:14px;height:14px"></i>
          <i class="heat-cell" style="width:14px;height:14px"></i>
          <i class="heat-cell" style="width:14px;height:14px"></i>
          <i class="heat-cell" style="width:14px;height:14px"></i>
          <span>多</span>
        </div>
        <div v-if="data.type_total?.length" class="cal-types">
          <span v-for="t in data.type_total" :key="t.type" class="freq-type-chip">{{ t.type }} × {{ t.count }}</span>
        </div>
      </template>
    </div>
  </div>
</template>
