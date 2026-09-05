<template>
  <Teleport to="body">
    <Transition name="drawer-fade">
      <div v-if="visible" class="deep-explain-overlay" @click.self="close">
        <aside class="deep-explain-drawer" :class="{ loading }" @click="handleWordClick">
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

            <!-- 定位句（v9.27 划词可点） -->
            <div v-if="data.locator_sentence" class="explain-section">
              <h4><Crosshair :size="14" aria-hidden="true" />原文定位</h4>
              <blockquote class="locator-quote" v-html="tokenizeText(data.locator_sentence)"></blockquote>
            </div>

            <!-- 解题步骤 -->
            <div v-if="data.solution_steps?.length" class="explain-section">
              <h4><Route :size="14" aria-hidden="true" />解题路径</h4>
              <ol class="solution-steps">
                <li v-for="(s, i) in data.solution_steps" :key="i">
                  <span class="step-num">{{ i + 1 }}</span>{{ s }}
                </li>
              </ol>
            </div>

            <!-- 选项逐项解构 -->
            <div v-if="Object.keys(data.options_analysis || {}).length" class="explain-section">
              <h4><Search :size="14" aria-hidden="true" />选项解构</h4>
              <div v-for="(opt, key) in data.options_analysis" :key="key" class="option-trap"
                   :class="opt.status === 'correct' ? 'trap-correct' : 'trap-wrong'">
                <span class="opt-key">{{ key }}</span>
                <span v-if="opt.trap_type" class="trap-badge"
                      :class="opt.status === 'correct' ? 'trap-badge-correct' : 'trap-badge-wrong'">
                  {{ opt.trap_type }}
                </span>
                <p v-html="tokenizeText(opt.analysis)"></p>
              </div>
            </div>

            <!-- 长难句语法（v9.27 划词可点 / v9.28 可收藏） -->
            <div v-if="data.sentence_grammar?.core_skeleton" class="explain-section">
              <h4><AlignLeft :size="14" aria-hidden="true" />长难句骨架
                <button class="collect-btn" type="button" @click.stop="collectFragment('long_sentence', data.sentence_grammar.core_skeleton)" title="收藏到典藏本">
                  <Bookmark :size="13" /> 典藏
                </button>
              </h4>
              <p class="skeleton-text" v-html="tokenizeText(data.sentence_grammar.core_skeleton)"></p>
              <p v-if="data.sentence_grammar.grammar_note" class="grammar-note">{{ data.sentence_grammar.grammar_note }}</p>
            </div>

            <!-- 知识点 + 建议 -->
            <div v-if="data.knowledge_points?.length" class="explain-section">
              <h4><Target :size="14" aria-hidden="true" />考点</h4>
              <div class="knowledge-tags">
                <span v-for="k in data.knowledge_points" :key="k" class="knowledge-tag">{{ k }}</span>
              </div>
            </div>
            <div v-if="data.study_advice" class="explain-section advice">
              <p><Lightbulb :size="13" aria-hidden="true" /> {{ data.study_advice }}</p>
            </div>

            <!-- 同类推荐 -->
            <div v-if="data.similar_recommendations?.length" class="explain-section">
              <h4><Library :size="14" aria-hidden="true" />同类巩固</h4>
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

          <!-- v9.27: Gemini UI4——划词悬浮卡片（点击解析中的英文单词查词） -->
          <div v-if="popover.visible" class="word-popover"
               :style="{ top: popover.y + 'px', left: popover.x + 'px' }">
            <div v-if="popover.loading" class="word-popover-loading">查词中…</div>
            <template v-else-if="popover.data">
              <div class="word-popover-term font-serif">{{ popover.data.term || popover.data.lemma }}</div>
              <div v-if="popover.data.phonetic" class="word-popover-phonetic">{{ popover.data.phonetic }}</div>
              <div class="word-popover-mean">{{ popover.data.common_meaning || popover.data.contextual_meaning || '词库暂无释义' }}</div>
              <button class="word-popover-add" @click.stop="addToVocab(popover.data)">
                <Star :size="12" />{{ popover.data.id ? '已在词库' : '加入生词本' }}
              </button>
            </template>
            <div v-else class="word-popover-loading">词库未收录</div>
          </div>
        </aside>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { AlignLeft, Bookmark, Crosshair, Lightbulb, Library, Route, Search, Star, Target } from 'lucide-vue-next'
import { get, post } from '../api'

const props = defineProps<{ questionId: number | null }>()
const emit = defineEmits<{ (e: 'jump', questionId: number): void }>()

const visible = ref(false)
const loading = ref(false)
const error = ref('')
const data = ref<any>(null)

// v9.27: Gemini UI4——划词联动（点击英文单词查词）
const popover = ref<{ visible: boolean; x: number; y: number; loading: boolean; data: any }>({
  visible: false, x: 0, y: 0, loading: false, data: null,
})
const collectedFlash = ref(false)
const wordCache = new Map<string, any>()

// 转义 HTML + 包裹英文单词为可点击 span（仅限解析文本）
function tokenizeText(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  return escaped.replace(/([A-Za-z][A-Za-z'-]{1,})/g,
    '<span class="clickable-word" data-word="$1">$1</span>')
}

// v9.28: Gemini batch5 任务4——精讲典藏收藏
async function collectFragment(type: string, content: string) {
  if (!props.questionId || !content.trim()) return
  try {
    await post('/collections', {
      question_id: props.questionId,
      fragment_type: type,
      content: content.trim(),
      source: 'deep-explain',
    })
    // 轻提示：抽屉内无 toast，用按钮短暂反馈
    collectedFlash.value = true
    setTimeout(() => (collectedFlash.value = false), 1200)
  } catch { /* 收藏失败静默（不阻断浏览） */ }
}

async function handleWordClick(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (!target.classList.contains('clickable-word')) {
    if (!target.closest('.word-popover')) popover.value.visible = false
    return
  }
  const word = (target.dataset.word || '').toLowerCase()
  if (!word) return
  const rect = target.getBoundingClientRect()
  popover.value = { visible: true, x: rect.left, y: rect.bottom + 8, loading: true, data: null }

  if (wordCache.has(word)) {
    popover.value.data = wordCache.get(word)
    popover.value.loading = false
    return
  }
  try {
    const res: any = await get(`/vocabulary?search=${encodeURIComponent(word)}&exact=true`)
    const item = (res.items || [])[0] || null
    wordCache.set(word, item)
    popover.value.data = item
  } catch {
    wordCache.set(word, null)
    popover.value.data = null
  } finally {
    popover.value.loading = false
  }
}

async function addToVocab(entry: any) {
  if (!entry || entry.id) return
  try {
    const created: any = await post('/vocabulary', { term: entry.term || entry.lemma })
    wordCache.set((entry.term || entry.lemma || '').toLowerCase(), created)
    popover.value.data = created
  } catch { /* 词库已有或失败——忽略 */ }
}

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
/* v12 运动曲线: 进抽屉减速停稳, 出抽屉加速滑走 (离场更短) */
.drawer-fade-enter-active .deep-explain-drawer { transition: transform 0.3s var(--motion-enter, cubic-bezier(.22,1,.36,1)); }
.drawer-fade-leave-active .deep-explain-drawer { transition: transform 0.22s var(--motion-exit, cubic-bezier(.3,0,.8,.15)); }
.drawer-fade-enter-from, .drawer-fade-leave-to { opacity: 0; }
.drawer-fade-enter-from .deep-explain-drawer, .drawer-fade-leave-to .deep-explain-drawer { transform: translateX(100%); }

/* v9.27: Gemini UI4——划词悬浮卡片 */
.collect-btn {
  display: inline-flex; align-items: center; gap: 3px;
  margin-left: 8px; padding: 2px 8px; border: 1px solid #E8E0D2; border-radius: 999px;
  background: transparent; color: #8A7D6D; font-size: 11px; cursor: pointer; vertical-align: middle;
  transition: all .15s;
}
.collect-btn:hover, .collect-btn.flash { background: #B84A39; border-color: #B84A39; color: #fff; }
.explain-section h4 { display: flex; align-items: center; }
.clickable-word { color: var(--zhusha, #B84A39); text-decoration: underline dashed; text-underline-offset: 3px; cursor: pointer; }
.word-popover { position: fixed; z-index: 9999; min-width: 200px; max-width: 260px; background: #FAF7F2; border: 1px solid #E8E0D2; border-radius: 10px; box-shadow: 0 10px 30px rgba(44, 38, 34, 0.16); padding: 12px 14px; }
.word-popover-loading { font-size: 12px; color: var(--muted, #8a7d6d); }
.word-popover-term { font-size: 18px; font-weight: 700; color: #3a322b; }
.word-popover-phonetic { font-size: 12px; color: var(--muted, #8a7d6d); margin: 2px 0 6px; }
.word-popover-mean { font-size: 13px; line-height: 1.5; color: #4a4138; }
.word-popover-add { display: inline-flex; align-items: center; gap: 4px; margin-top: 8px; padding: 3px 8px; font-size: 12px; color: #B84A39; background: transparent; border: 1px solid #D8C9B8; border-radius: 6px; cursor: pointer; }
.word-popover-add:hover { background: rgba(184, 74, 57, 0.08); }
</style>
