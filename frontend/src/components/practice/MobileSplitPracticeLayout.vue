<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { GripHorizontal, Grid3x3 } from 'lucide-vue-next'
import {
  sanitizeQuestionOptions,
  type PracticeOption,
} from '../../utils/optionSanitizer'

/**
 * MobileSplitPracticeLayout
 *
 * 墨题通用移动端分屏练习布局。在小于 breakpoint 且 enabled=true 时，
 * 将 passage 与 questions 转换为上下独立滚动布局；桌面端保留现有双栏布局。
 * 组件只负责布局基础设施、移动端题目导航和展示层选项清洗，不负责提交答案、
 * API 调用或任何具体题型业务。
 *
 * Props：enabled、questions、initialRatio、ratio、minRatio、maxRatio、draggable、
 * breakpoint、currentQuestionIndex、sanitizeOptions、toolbar、showQuestionPane、
 * answerSheetTitle、answeredCount、totalCount、passageClass。
 * Slots：passage、questions、bottom，以及可选 toolbar、answer-sheet。
 * Emits：update:ratio、prev、next、open-answer-sheet、jump-question、dirty-option-detected。
 *
 * @example
 * import MobileSplitPracticeLayout from '@/components/practice/MobileSplitPracticeLayout.vue'
 *
 * <MobileSplitPracticeLayout :enabled="!isListening" :questions="activeUnit.questions">
 *   <template #passage>文章内容</template>
 *   <template #questions="{ questions }">题目内容（使用清洗后的 questions）</template>
 * </MobileSplitPracticeLayout>
 */

export interface PracticeQuestion {
  id: number | string
  number?: number
  options?: PracticeOption[]
  user_answer?: unknown
  answer_selected?: unknown
  [key: string]: unknown
}

export interface MobileToolbarConfig {
  visible?: boolean
  showPrev?: boolean
  showNext?: boolean
  showAnswerSheet?: boolean
  showCounter?: boolean
}

interface Props {
  enabled?: boolean
  questions?: PracticeQuestion[]
  initialRatio?: number
  ratio?: number
  minRatio?: number
  maxRatio?: number
  draggable?: boolean
  breakpoint?: number
  currentQuestionIndex?: number
  sanitizeOptions?: boolean
  toolbar?: MobileToolbarConfig
  showQuestionPane?: boolean
  answerSheetTitle?: string
  answeredCount?: number
  totalCount?: number
  passageClass?: string | string[] | Record<string, boolean>
}

const props = withDefaults(defineProps<Props>(), {
  enabled: true,
  questions: () => [],
  initialRatio: 45,
  minRatio: 30,
  maxRatio: 78,
  draggable: true,
  breakpoint: 768,
  sanitizeOptions: true,
  showQuestionPane: true,
  toolbar: () => ({}),
})

const emit = defineEmits<{
  'update:ratio': [ratio: number]
  prev: []
  next: []
  'open-answer-sheet': []
  'jump-question': [index: number]
  'dirty-option-detected': [payload: { questionId: number | string; rawContent: string }]
}>()

defineSlots<{
  passage(props: { isSplit: boolean; ratio: number }): unknown
  questions(props: { questions: any[]; currentIndex: number; isSplit: boolean }): unknown
  bottom(props: { isSplit: boolean }): unknown
  toolbar(): unknown
  'answer-sheet'(props: { questions: any[]; currentIndex: number }): unknown
}>()

const rootRef = ref<HTMLElement | null>(null)
const viewportWidth = ref(typeof window === 'undefined' ? 1024 : window.innerWidth)
const internalRatio = ref(props.ratio ?? props.initialRatio)
const answerSheetOpen = ref(false)
const warnedQuestions = new Set<string>()
let dragCleanup: (() => void) | null = null

const clampRatio = (value: number) => Math.min(props.maxRatio, Math.max(props.minRatio, value))
const currentRatio = computed(() => clampRatio(props.ratio ?? internalRatio.value))
const isSplit = computed(() => props.enabled && viewportWidth.value < props.breakpoint)
const showQuestionPane = computed(() => props.showQuestionPane)
const questionsForSlot = computed(() => {
  if (!props.sanitizeOptions) return props.questions
  return props.questions.map((question) => {
    const result = sanitizeQuestionOptions(question.options)
    const safeQuestion = { ...question, options: result.options } as PracticeQuestion & { option_data_dirty?: boolean }

    // Keep answer state reactive and writable while options come from a safe copy.
    for (const key of ['user_answer', 'answer_selected', 'is_correct'] as const) {
      Object.defineProperty(safeQuestion, key, {
        configurable: true,
        enumerable: true,
        get: () => question[key],
        set: value => { question[key] = value },
      })
    }
    Object.defineProperty(safeQuestion, 'option_data_dirty', {
      configurable: true,
      enumerable: false,
      value: result.dirty,
    })

    if (result.dirty) {
      const questionId = question.id ?? question.number ?? ''
      const warningKey = `${questionId}:${result.rawContent ?? ''}`
      if (!warnedQuestions.has(warningKey)) {
        warnedQuestions.add(warningKey)
        console.warn('[MobileSplitPracticeLayout] Dirty option content detected', {
          questionId,
          content: result.rawContent,
          reason: result.reason,
        })
        emit('dirty-option-detected', {
          questionId,
          rawContent: result.rawContent ?? '',
        })
      }
    }
    return safeQuestion
  })
})

const answeredCount = computed(() => props.answeredCount ?? questionsForSlot.value.filter(isAnswered).length)
const totalCount = computed(() => props.totalCount ?? questionsForSlot.value.length)
const currentIndex = computed(() => {
  const max = Math.max(0, questionsForSlot.value.length - 1)
  return Math.min(max, Math.max(0, props.currentQuestionIndex ?? 0))
})
const toolbarVisible = computed(() => isSplit.value && props.toolbar.visible !== false && showQuestionPane.value)

function isAnswered(question: PracticeQuestion): boolean {
  return Boolean(question.user_answer || question.answer_selected)
}

function setRatio(value: number) {
  const next = clampRatio(value)
  internalRatio.value = next
  emit('update:ratio', next)
}

function onResize() {
  viewportWidth.value = window.innerWidth
}

function startDragDivider(event: PointerEvent) {
  if (!rootRef.value || !isSplit.value || !props.draggable) return
  event.preventDefault()
  dragCleanup?.()
  const rect = rootRef.value.getBoundingClientRect()
  const move = (moveEvent: PointerEvent) => {
    if (!rect.height) return
    setRatio(((moveEvent.clientY - rect.top) / rect.height) * 100)
  }
  const stop = () => {
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', stop)
    window.removeEventListener('pointercancel', stop)
    dragCleanup = null
  }
  dragCleanup = stop
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', stop)
  window.addEventListener('pointercancel', stop)
}

function openAnswerSheet() {
  answerSheetOpen.value = true
  emit('open-answer-sheet')
}

function closeAnswerSheet() {
  answerSheetOpen.value = false
}

function toggleAnswerSheet() {
  answerSheetOpen.value = !answerSheetOpen.value
  if (answerSheetOpen.value) emit('open-answer-sheet')
}

function jumpQuestion(index: number) {
  answerSheetOpen.value = false
  emit('jump-question', index)
}

defineExpose({ openAnswerSheet, closeAnswerSheet, toggleAnswerSheet })

watch(() => props.ratio, value => {
  if (value !== undefined) internalRatio.value = clampRatio(value)
})
watch(currentRatio, value => {
  rootRef.value?.style.setProperty('--passage-ratio', `${value}%`)
}, { immediate: true })
watch(() => props.questions, () => { answerSheetOpen.value = false })

onMounted(() => {
  onResize()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  dragCleanup?.()
})
</script>

<template>
  <div
    ref="rootRef"
    class="practice-layout mobile-split-practice-layout"
    :class="{ 'is-split': isSplit, 'no-question-pane': !showQuestionPane }"
  >
    <section class="passage-pane" :class="passageClass">
      <slot name="passage" :is-split="isSplit" :ratio="currentRatio" />
    </section>

    <div
      v-if="isSplit && showQuestionPane && draggable"
      class="pane-divider"
      role="separator"
      aria-orientation="horizontal"
      title="拖动调整上下占比"
      @pointerdown="startDragDivider"
    >
      <span class="pane-divider-grip"><GripHorizontal :size="16" /></span>
    </div>

    <section v-if="showQuestionPane" class="question-pane">
      <div v-if="toolbarVisible" class="mobile-question-toolbar">
        <button v-if="props.toolbar.showPrev !== false" class="mob-q-btn" type="button" :disabled="currentIndex <= 0" @click="emit('prev')">
          ‹ 上一题
        </button>
        <button v-if="props.toolbar.showCounter !== false && props.toolbar.showAnswerSheet !== false" class="mob-q-indicator" type="button" title="点击打开答题卡" @click="openAnswerSheet">
          <Grid3x3 :size="14" />
          <span>第 {{ currentIndex + 1 }} / {{ questionsForSlot.length }} 题</span>
        </button>
        <slot name="toolbar" />
        <button v-if="props.toolbar.showNext !== false" class="mob-q-btn" type="button" :disabled="currentIndex >= questionsForSlot.length - 1" @click="emit('next')">
          下一题 ›
        </button>
      </div>
      <div class="question-scroll-area">
        <slot name="questions" :questions="questionsForSlot" :current-index="currentIndex" :is-split="isSplit" />
      </div>
      <div class="question-bottom">
        <slot name="bottom" :is-split="isSplit" />
      </div>
    </section>

    <Transition name="sheet-fade">
      <div v-if="answerSheetOpen && showQuestionPane" class="answer-sheet-drawer" @click.self="closeAnswerSheet">
        <div class="answer-sheet-panel">
          <div class="answer-sheet-head">
            <strong>{{ props.answerSheetTitle || '答题卡' }}</strong>
            <span>{{ answeredCount }}/{{ totalCount }} 已答</span>
            <button type="button" class="answer-sheet-close" aria-label="关闭答题卡" @click="closeAnswerSheet">✕</button>
          </div>
          <slot name="answer-sheet" :questions="questionsForSlot" :current-index="currentIndex">
            <div class="answer-sheet-grid">
              <button
                v-for="(question, index) in questionsForSlot"
                :key="question.id"
                type="button"
                class="answer-sheet-cell"
                :class="{ answered: isAnswered(question), current: currentIndex === index }"
                @click="jumpQuestion(index)"
              >{{ question.number ?? index + 1 }}</button>
            </div>
          </slot>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.mobile-split-practice-layout {
  --passage-ratio: 45%;
  min-width: 0;
  min-height: 0;
}

.question-scroll-area {
  min-height: 0;
}

.question-bottom {
  min-width: 0;
}

:deep(.option-content) {
  white-space: pre-wrap;
}

@media (max-width: 767px) and (orientation: portrait) {
  .mobile-split-practice-layout.is-split {
    grid-template-rows: minmax(200px, var(--passage-ratio)) 10px minmax(0, 1fr);
    min-height: 0;
  }

  .mobile-split-practice-layout.is-split.no-question-pane {
    grid-template-rows: minmax(0, 1fr);
  }

  .mobile-split-practice-layout.is-split .passage-pane {
    min-height: 0;
    overflow: auto;
  }

  .mobile-split-practice-layout.is-split .question-pane {
    min-height: 0;
    overflow: hidden;
    display: grid;
    grid-template-rows: auto minmax(0, 1fr) auto;
  }

  .mobile-split-practice-layout.is-split .question-scroll-area {
    overflow-y: auto;
    min-height: 0;
  }
}
</style>
