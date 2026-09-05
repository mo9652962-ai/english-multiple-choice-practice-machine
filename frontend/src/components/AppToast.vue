<script setup lang="ts">
/**
 * 全局 Toast 提示组件（右下角堆叠 + 进度条 + 类型图标）。
 * ⚠️ 不要直接 import 本组件使用——统一通过 `services/toast.ts` 的
 * `showToast({ message, type, duration })` 调用，本组件挂载在 App.vue 一次即可。
 * @example
 * import { showToast } from '../services/toast'
 * showToast({ message: '已保存', type: 'success' })
 */

import { CheckCircle2, Info, XCircle } from 'lucide-vue-next'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { dismissToast, getToasts, subscribeToast, type ToastItem } from '../services/toast'

const items = ref<ToastItem[]>(getToasts())
let unsubscribe: (() => void) | null = null

onMounted(() => {
  unsubscribe = subscribeToast(() => {
    items.value = getToasts()
  })
})
onBeforeUnmount(() => unsubscribe?.())

function iconFor(type: ToastItem['type']) {
  if (type === 'success') return CheckCircle2
  if (type === 'error') return XCircle
  return Info
}
</script>

<template>
  <div class="toast-stack" aria-live="polite">
    <TransitionGroup name="toast">
      <div
        v-for="t in items"
        :key="t.id"
        class="toast-item"
        :class="`toast-${t.type}`"
        @click="dismissToast(t.id)"
      >
        <component :is="iconFor(t.type)" :size="17" class="toast-icon" />
        <span class="toast-msg">{{ t.message }}</span>
        <span class="toast-progress" :style="{ animationDuration: `${t.duration}ms` }" />
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-stack {
  position: fixed;
  right: 24px;
  bottom: 24px;
  z-index: 100;
  display: grid;
  gap: 10px;
  pointer-events: none;
}
.toast-item {
  pointer-events: auto;
  position: relative;
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 240px;
  max-width: 380px;
  padding: 12px 16px 14px;
  border-radius: 13px;
  background: var(--ink);
  color: var(--surface-solid);
  box-shadow: var(--shadow);
  font-size: 13.5px;
  line-height: 1.5;
  cursor: pointer;
  overflow: hidden;
  border: 1px solid transparent;
}
.toast-icon { flex-shrink: 0; }
.toast-success .toast-icon { color: #6fcf8f; }
.toast-error .toast-icon { color: #f29b95; }
.toast-info .toast-icon { color: #8db5a3; }
.toast-msg { flex: 1; }
.toast-progress {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  background: color-mix(in srgb, var(--primary) 80%, white);
  animation: toast-shrink linear forwards;
}
.toast-success .toast-progress { background: #6fcf8f; }
.toast-error .toast-progress { background: #f29b95; }
@keyframes toast-shrink { from { width: 100%; } to { width: 0; } }

/* 入场减速 / 出场加速 (v12 运动曲线: 消失比出现快) */
.toast-enter-active { transition: all .3s var(--motion-enter, cubic-bezier(.22,1,.36,1)); }
.toast-leave-active { transition: all .18s var(--motion-exit, cubic-bezier(.3,0,.8,.15)); }
.toast-enter-from { opacity: 0; transform: translateY(16px) scale(.95); }
.toast-leave-to { opacity: 0; transform: translateX(30px); }
</style>
