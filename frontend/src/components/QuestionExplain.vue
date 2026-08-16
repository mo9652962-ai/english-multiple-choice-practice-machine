<script setup lang="ts">
/**
 * 任务 E（第 4 部分）：题目解析展开面板。
 *
 * 用法（PracticeView 中，交卷后展示在题目卡片内）：
 *   import QuestionExplain from '../components/QuestionExplain.vue'
 *   <QuestionExplain
 *     v-if="activeUnitSubmitted"
 *     :question-id="question.id"
 *     :question="question"
 *   />
 *
 * 点击「查看解析」→ 懒加载 GET /api/questions/:id/explain 并展开面板：
 * 正确项分析（松绿 --success）、错误项分析（胭脂 --danger）、
 * 知识点标签（竹青/秋香）、复习建议（朱砂侧边卡）。
 * 样式沿用全局水墨文人书房体系（styles.css 的 CSS 变量）。
 */
import { BookOpenText, CheckCircle2, ChevronDown, Lightbulb, XCircle } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { get } from '../api'

type ExplainContent = {
  correct_analysis: string
  wrong_options: { key: string, reason: string }[]
  knowledge_points: string[]
  study_advice: string
}

const props = defineProps<{
  questionId: number
  /** 可选：传入题目对象以展示「你的答案/正确答案」摘要行 */
  question?: any
}>()

const open = ref(false)
const loading = ref(false)
const error = ref('')
const content = ref<ExplainContent | null>(null)
const meta = ref<{ source_model: string, updated_at: string } | null>(null)

const optionKeyLabel = computed(() => props.question?.options?.reduce(
  (map: Record<string, string>, option: any) => {
    map[option.stable_key ?? option.key] = option.label ?? option.key
    return map
  },
  {},
) || {})

function labelOf(key: string): string {
  return optionKeyLabel.value[key] || key
}

async function load() {
  if (loading.value || content.value) return
  loading.value = true
  error.value = ''
  try {
    const res: any = await get(`/questions/${props.questionId}/explain`)
    if (res?.available) {
      content.value = res.content
      meta.value = { source_model: res.source_model || '', updated_at: res.updated_at || '' }
    } else {
      error.value = '本题暂无解析，可稍后在题库管理中批量生成。'
    }
  } catch (e: any) {
    error.value = e?.status === 404 ? '题目不存在。' : `解析加载失败：${e?.message || e}`
  } finally {
    loading.value = false
  }
}

function toggle() {
  open.value = !open.value
  if (open.value) load()
}

watch(() => props.questionId, () => {
  open.value = false
  content.value = null
  meta.value = null
  error.value = ''
})
</script>

<template>
  <div class="q-explain">
    <button
      class="q-explain-toggle"
      type="button"
      :aria-expanded="open"
      @click="toggle"
    >
      <BookOpenText :size="15" />
      <span>查看解析</span>
      <ChevronDown :size="15" class="q-explain-chevron" :class="{ open }" />
    </button>

    <div v-if="open" class="q-explain-panel">
      <div v-if="loading" class="q-explain-status">解析加载中…</div>
      <div v-else-if="error" class="q-explain-status muted">{{ error }}</div>
      <template v-else-if="content">
        <!-- 答案摘要 -->
        <div v-if="question" class="q-explain-answer-row">
          <template v-if="question.is_correct">
            <span class="ok"><CheckCircle2 :size="14" /> 回答正确</span>
          </template>
          <template v-else>
            <span class="bad">你的答案：{{ question.user_answer || '未作答' }}</span>
            <span class="ok">正确答案：{{ question.answer }}</span>
          </template>
        </div>

        <!-- 正确项分析：松绿 -->
        <div class="q-explain-block correct">
          <div class="q-explain-block-title">
            <CheckCircle2 :size="15" /> 正确项分析
          </div>
          <p class="q-explain-text">{{ content.correct_analysis }}</p>
        </div>

        <!-- 错误项分析：胭脂 -->
        <div v-if="content.wrong_options?.length" class="q-explain-block wrong">
          <div class="q-explain-block-title">
            <XCircle :size="15" /> 干扰项拆解
          </div>
          <ul class="q-explain-wrong-list">
            <li v-for="wrong in content.wrong_options" :key="wrong.key">
              <span class="q-explain-wrong-key">{{ labelOf(wrong.key) }}</span>
              <span>{{ wrong.reason }}</span>
            </li>
          </ul>
        </div>

        <!-- 知识点标签 -->
        <div v-if="content.knowledge_points?.length" class="q-explain-tags">
          <span
            v-for="(point, index) in content.knowledge_points"
            :key="point"
            class="q-explain-tag"
            :class="index % 2 === 0 ? 'bamboo' : 'gold'"
          >{{ point }}</span>
        </div>

        <!-- 复习建议 -->
        <div v-if="content.study_advice" class="q-explain-block advice">
          <div class="q-explain-block-title">
            <Lightbulb :size="15" /> 复习建议
          </div>
          <p class="q-explain-text">{{ content.study_advice }}</p>
        </div>

        <div v-if="meta?.source_model" class="q-explain-meta">
          AI 解析 · {{ meta.source_model }} · {{ meta.updated_at }}
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.q-explain { margin-top: 12px; }

.q-explain-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border: 1px solid var(--line-strong);
  border-radius: 999px;
  background: var(--primary-faint);
  color: var(--ink);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color .16s ease, background-color .16s ease;
}
.q-explain-toggle:hover { border-color: var(--primary); background: var(--primary-soft); }
.q-explain-chevron { transition: transform .18s ease; }
.q-explain-chevron.open { transform: rotate(180deg); }

.q-explain-panel {
  margin-top: 10px;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--primary);
  border-radius: var(--radius-md);
  background: var(--surface-solid);
  box-shadow: var(--shadow-sm);
}

.q-explain-status { font-size: 13.5px; color: var(--muted); }
.q-explain-status.muted { color: var(--muted); }

.q-explain-answer-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 12px;
  font-size: 13.5px;
  font-weight: 600;
}
.q-explain-answer-row .ok { color: var(--success); display: inline-flex; align-items: center; gap: 4px; }
.q-explain-answer-row .bad { color: var(--danger); }

.q-explain-block {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  margin-bottom: 10px;
  font-size: 14px;
  line-height: 1.75;
}
.q-explain-block.correct { background: var(--bamboo-soft); color: var(--success); }
.q-explain-block.wrong { background: var(--danger-soft); color: var(--danger); }
.q-explain-block.advice {
  background: var(--apricot);
  color: var(--ink);
  border-left: 3px solid var(--accent);
}
.q-explain-block-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 700;
  margin-bottom: 6px;
}
.q-explain-block.correct .q-explain-text { color: var(--ink); }
.q-explain-block.wrong .q-explain-text,
.q-explain-block.wrong li { color: var(--ink); }
.q-explain-text { margin: 0; white-space: pre-wrap; }

.q-explain-wrong-list { margin: 0; padding: 0; list-style: none; }
.q-explain-wrong-list li {
  display: flex;
  gap: 8px;
  padding: 5px 0;
  font-size: 13.5px;
  line-height: 1.7;
}
.q-explain-wrong-key {
  flex: none;
  min-width: 22px;
  height: 22px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--danger);
  color: #fdfaf3;
  font-weight: 700;
  font-size: 12px;
}

.q-explain-tags { display: flex; flex-wrap: wrap; gap: 8px; margin: 2px 0 12px; }
.q-explain-tag {
  padding: 3px 12px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 600;
}
.q-explain-tag.bamboo { background: var(--bamboo-soft); color: var(--bamboo); }
.q-explain-tag.gold { background: var(--gold-soft); color: var(--gold); }

.q-explain-meta { margin-top: 2px; font-size: 11.5px; color: var(--muted); text-align: right; }
</style>
