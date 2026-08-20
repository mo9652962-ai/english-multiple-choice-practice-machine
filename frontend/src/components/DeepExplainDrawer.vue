<template>
  <Teleport to="body">
    <Transition name="drawer-fade">
      <div v-if="visible" class="deep-explain-overlay" @click.self="close">
        <aside class="deep-explain-drawer" :class="{ loading }">
          <header class="drawer-head">
            <h3><span class="hero-seal" aria-hidden="true">讲</span>AI 助教精讲</h3>
            <button class="drawer-close" @click="close">✕</button>
          </header>

          <div v-if="loading" class="drawer-loading">
            <p>正在研读题目…</p>
            <div class="ink-progress-track"><div class="ink-progress-bar" style="width: 70%"></div></div>
          </div>

          <div v-else-if="error" class="drawer-error">
            <p>{{ error }}</p>
            <button class="button compact" @click="load(true)">重试</button>
          </div>

          <div v-else-if="data" class="drawer-body">
            <!-- 题型定位 -->
            <div class="explain-section">
              <span class="explain-tag type">{{ data.question_type_label || '题目解析' }}</span>
              <span v-if="data.core_skill" class="explain-tag skill">{{ data.core_skill }}</span>
            </div>

            <!-- 定位句 -->
            <div v-if="data.locator_sentence" class="explain-section">
              <h4>📌 原文定位</h4>
              <blockquote class="locator-quote">{{ data.locator_sentence }}</blockquote>
            </div>

            <!-- 解题步骤 -->
            <div v-if="data.solution_steps?.length" class="explain-section">
              <h4>🗺 解题路径</h4>
              <ol class="solution-steps">
                <li v-for="(s, i) in data.solution_steps" :key="i">
                  <span class="step-num">{{ i + 1 }}</span>{{ s }}
                </li>
              </ol>
            </div>

            <!-- 选项逐项解构 -->
            <div v-if="Object.keys(data.options_analysis || {}).length" class="explain-section">
              <h4>🔍 选项解构</h4>
              <div v-for="(opt, key) in data.options_analysis" :key="key" class="option-trap"
                   :class="opt.status === 'correct' ? 'trap-correct' : 'trap-wrong'">
                <span class="opt-key">{{ key }}</span>
                <span v-if="opt.trap_type" class="trap-badge"
                      :class="opt.status === 'correct' ? 'trap-badge-correct' : 'trap-badge-wrong'">
                  {{ opt.trap_type }}
                </span>
                <p>{{ opt.analysis }}</p>
              </div>
            </div>

            <!-- 长难句语法 -->
            <div v-if="data.sentence_grammar?.core_skeleton" class="explain-section">
              <h4>📐 长难句骨架</h4>
              <p class="skeleton-text">{{ data.sentence_grammar.core_skeleton }}</p>
              <p v-if="data.sentence_grammar.grammar_note" class="grammar-note">{{ data.sentence_grammar.grammar_note }}</p>
            </div>

            <!-- 知识点 + 建议 -->
            <div v-if="data.knowledge_points?.length" class="explain-section">
              <h4>🎯 考点</h4>
              <div class="knowledge-tags">
                <span v-for="k in data.knowledge_points" :key="k" class="knowledge-tag">{{ k }}</span>
              </div>
            </div>
            <div v-if="data.study_advice" class="explain-section advice">
              <p>💡 {{ data.study_advice }}</p>
            </div>

            <!-- 同类推荐 -->
            <div v-if="data.similar_recommendations?.length" class="explain-section">
              <h4>📚 同类巩固</h4>
              <div class="similar-list">
                <button v-for="sid in data.similar_recommendations" :key="sid" class="similar-btn"
                        @click="jumpToQuestion(sid)">第 {{ sid }} 题 →</button>
              </div>
            </div>

            <footer v-if="data.cached" class="drawer-foot">
              <span class="cached-mark">🈴 已缓存 · {{ data.source_model || 'AI' }}</span>
              <button class="button ghost compact" @click="load(true)">重新生成</button>
            </footer>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { post } from '../api'

const props = defineProps<{ questionId: number | null }>()
const emit = defineEmits<{ (e: 'jump', questionId: number): void }>()

const visible = ref(false)
const loading = ref(false)
const error = ref('')
const data = ref<any>(null)

async function load(forceRefresh = false) {
  if (!props.questionId) return
  loading.value = true
  error.value = ''
  try {
    data.value = await post(`/questions/${props.questionId}/deep-explain`, { force_refresh: forceRefresh })
  } catch (e) {
    error.value = String(e)
  } finally {
    loading.value = false
  }
}

function open() {
  visible.value = true
  data.value = null
  load()
}
function close() { visible.value = false }
function jumpToQuestion(id: number) { emit('jump', id) }

defineExpose({ open, close })
</script>

<style scoped>
.deep-explain-overlay {
  position: fixed; inset: 0; z-index: 9000;
  background: rgba(43, 40, 37, 0.35);
  backdrop-filter: blur(2px);
  display: flex; justify-content: flex-end;
}
.deep-explain-drawer {
  width: min(440px, 92vw); height: 100%;
  background: rgba(250, 247, 242, 0.97);
  border-left: 1px solid rgba(60, 50, 40, 0.1);
  box-shadow: -12px 0 32px rgba(60, 50, 40, 0.12);
  display: flex; flex-direction: column;
  overflow-y: auto;
}
.drawer-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(60, 50, 40, 0.08);
}
.drawer-head h3 { font-family: var(--font-serif); font-size: 17px; color: var(--text-pine); display: flex; align-items: center; gap: 8px; }
.drawer-close {
  background: none; border: 1px solid rgba(60, 50, 40, 0.15);
  border-radius: 9999px; width: 30px; height: 30px;
  color: var(--text-faint); cursor: pointer;
}
.drawer-body { padding: 16px 20px 24px; }
.explain-section { margin-bottom: 20px; }
.explain-section h4 { font-size: 13px; color: var(--text-faint); margin-bottom: 8px; font-weight: 600; letter-spacing: 0.5px; }
.explain-tag { display: inline-block; font-size: 12px; padding: 3px 10px; border-radius: 4px; margin-right: 8px; font-family: var(--font-serif); }
.explain-tag.type { background: rgba(184, 74, 57, 0.08); color: var(--accent-vermilion); border: 1px solid rgba(184, 74, 57, 0.2); }
.explain-tag.skill { background: rgba(74, 95, 78, 0.08); color: var(--accent-bamboo); border: 1px solid rgba(74, 95, 78, 0.2); }
.locator-quote {
  background: rgba(74, 95, 78, 0.06);
  border-left: 3px solid var(--accent-bamboo);
  padding: 10px 14px; border-radius: 0 8px 8px 0;
  font-family: var(--font-en-serif); font-size: 14px; line-height: 1.6;
  color: rgba(43, 40, 37, 0.85);
}
.solution-steps { list-style: none; padding: 0; margin: 0; }
.solution-steps li { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; font-size: 14px; color: var(--text-pine); }
.step-num {
  width: 22px; height: 22px; border-radius: 4px; flex-shrink: 0;
  background: rgba(184, 74, 57, 0.08); color: var(--accent-vermilion);
  font-family: var(--font-serif); font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.option-trap { border: 1px solid rgba(60, 50, 40, 0.08); border-radius: 10px; padding: 10px 12px; margin-bottom: 8px; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.option-trap.trap-correct { background: rgba(74, 95, 78, 0.06); border-color: rgba(74, 95, 78, 0.25); }
.option-trap.trap-wrong { background: rgba(184, 74, 57, 0.03); }
.opt-key { width: 24px; height: 24px; border-radius: 9999px; border: 1px solid currentColor; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-serif); font-weight: 600; font-size: 12px; color: var(--accent-bamboo); flex-shrink: 0; }
.option-trap.trap-wrong .opt-key { color: var(--accent-vermilion); }
.option-trap p { width: 100%; margin: 0; font-size: 13px; color: var(--text-pine); line-height: 1.6; }
.trap-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-family: var(--font-serif); }
.trap-badge-correct { background: rgba(74, 95, 78, 0.1); color: var(--accent-bamboo); border: 1px solid rgba(74, 95, 78, 0.25); }
.trap-badge-wrong { background: rgba(184, 74, 57, 0.08); color: var(--accent-vermilion); border: 1px solid rgba(184, 74, 57, 0.2); }
.skeleton-text { font-family: var(--font-en-serif); font-size: 14px; color: var(--text-pine); background: rgba(60, 50, 40, 0.04); padding: 8px 12px; border-radius: 8px; }
.grammar-note { font-size: 13px; color: var(--text-faint); margin-top: 6px; }
.knowledge-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.knowledge-tag { font-size: 12px; padding: 3px 10px; border-radius: 9999px; background: rgba(166, 122, 56, 0.08); color: var(--accent-ochre); border: 1px solid rgba(166, 122, 56, 0.2); }
.explain-section.advice { background: rgba(166, 122, 56, 0.05); border-radius: 10px; padding: 10px 14px; }
.similar-list { display: flex; gap: 8px; flex-wrap: wrap; }
.similar-btn { background: rgba(255, 255, 255, 0.85); border: 1px solid var(--border-paper); border-radius: 9999px; padding: 6px 14px; font-size: 13px; color: var(--text-regular); cursor: pointer; transition: all 0.2s; }
.similar-btn:hover { color: var(--accent-bamboo); border-color: var(--accent-bamboo); }
.drawer-foot { display: flex; justify-content: space-between; align-items: center; padding: 12px 20px; border-top: 1px solid rgba(60, 50, 40, 0.08); }
.cached-mark { font-family: var(--font-serif); font-size: 11px; color: var(--accent-ochre); }
.drawer-loading, .drawer-error { padding: 40px 20px; text-align: center; color: var(--text-faint); }
.drawer-fade-enter-active, .drawer-fade-leave-active { transition: opacity 0.2s; }
.drawer-fade-enter-active .deep-explain-drawer, .drawer-fade-leave-active .deep-explain-drawer { transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1); }
.drawer-fade-enter-from, .drawer-fade-leave-to { opacity: 0; }
.drawer-fade-enter-from .deep-explain-drawer, .drawer-fade-leave-to .deep-explain-drawer { transform: translateX(100%); }
</style>
