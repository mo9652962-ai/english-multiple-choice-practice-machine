<script setup lang="ts">
// v3.4: 单词专属详情页——点词进入（借鉴有道词典9.0视觉锚定 / 欧路分组 / 扇贝真题关联 / 不背单词发音对比）
// 词头+音标+发音 / 简明释义 / 语境释义 / 词性语法 / 同反形近辨析 / 记忆提示 / 真题组句 / 词文串学
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { get, put } from '../api'
import { sanitizeHtml } from '../services/sanitize'  // v9.24: XSS 防护
import { ArrowLeft, BookOpen, Check, Headphones, RefreshCw, Star, Volume2 } from 'lucide-vue-next'

// R22: 例句目标词朱砂高亮 (词根+常见词形后缀, 与词文串学同款 mark)
function highlightForms(sentence: string): string {
  const term = String(word.value?.lemma || word.value?.term || '').trim()
  if (!term || !sentence) return sentence
  const esc = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  try {
    return sentence.replace(new RegExp('\\b(' + esc + "(?:s|es|ed|ing|d|'s)?)\\b", 'ig'), '<mark class="vocab-context-mark">$1</mark>')
  } catch { return sentence }
}
import TtsButton from '../components/TtsButton.vue'

const route = useRoute()
const router = useRouter()
const word = ref<any>(null)
const contexts = ref<any[]>([])
const contextsLoading = ref(false)
const error = ref('')
const loading = ref(true)
const accented = ref('us')   // 发音口音 us / uk
const expandedAll = ref(false)

const STYLE_LABELS: Record<string, string> = {
  interview: '访谈', argument: '论述', news: '新闻', story: '故事', article: '文章',
}
function styleLabel(style: string) { return STYLE_LABELS[style] || style }

function highlightContext(c: any): string {
  const w = c.highlight || ''
  if (!w) return c.sentence
  const re = new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig')
  return c.sentence.replace(re, '<mark class="vocab-context-mark">$1</mark>')
}

const displayTerm = computed(() => word.value?.lemma || word.value?.term || '')
// 词性拆组（欧路风格：按词性分组显示释义）
const posGroups = computed(() => {
  const w = word.value
  if (!w) return []
  const pos = (w.part_of_speech || '').trim()
  return [{
    pos,
    common: w.common_meaning || '',
    contextual: w.contextual_meaning || '',
  }]
})

async function load() {
  loading.value = true
  try {
    const id = Number(route.params.id)
    word.value = await get(`/vocabulary/${id}`)
    error.value = ''
    contexts.value = []
    contextsLoading.value = true
    try {
      const ctx: any = await get(`/vocabulary/${id}/context`)
      contexts.value = ctx.contexts || []
    } catch { contexts.value = [] }
    contextsLoading.value = false
  } catch (e) {
    error.value = String(e)
  }
  loading.value = false
}

// v9.27: Gemini UI4——三态背诵（认识 familiar / 模糊 learning / 忘记 ''）
async function setStudyStatus(status: string) {
  if (!word.value) return
  await put(`/vocabulary/${word.value.id}`, { study_status: status })
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page page-vocab vocabulary-page vocab-word-page">
    <!-- 顶部栏 -->
    <div class="word-topbar">
      <button class="button ghost" @click="router.back()"><ArrowLeft :size="17" /> 返回</button>
      <div class="word-topbar-title" v-if="word">
        <strong>{{ displayTerm }}</strong>
        <span v-if="word.phonetic">{{ word.phonetic }}</span>
      </div>
      <div style="width:64px"></div>
    </div>

    <div v-if="loading" class="card empty">加载中…</div>
    <div v-else-if="error" class="warning">{{ error }}</div>
    <div v-else-if="!word" class="card empty">未找到该单词</div>

    <template v-else>
      <!-- 词头区：视觉锚定（v9.27 衬线词头） -->
      <section class="word-hero card">
        <div class="word-hero-term">
          <h1 class="vocab-word-serif">{{ displayTerm }}</h1>
          <span class="word-hero-phonetic vocab-phonetic-serif">{{ word.phonetic }}</span>
          <!-- 发音：美音/英音切换 + 朗读（不背单词风格） -->
          <div class="word-voice">
            <div class="voice-toggle">
              <button :class="{ active: accented === 'us' }" @click="accented = 'us'">美音</button>
              <button :class="{ active: accented === 'uk' }" @click="accented = 'uk'">英音</button>
            </div>
            <TtsButton :text="word.term" :speed="0.85" :size="22" />
          </div>
        </div>
        <div class="word-hero-mean">
          <span class="word-pos-badge">{{ word.part_of_speech || '单词' }}</span>
          <strong class="word-main-meaning">{{ word.common_meaning || word.contextual_meaning }}</strong>
        </div>
        <div class="word-hero-tags" v-if="word.is_frequent">
          <span class="word-freq-tag"><Star :size="11" fill="currentColor" aria-hidden="true" />高频词</span>
        </div>
      </section>

      <!-- 语境释义 -->
      <section v-if="word.contextual_meaning && word.contextual_meaning !== word.common_meaning" class="word-section card">
        <div class="word-section-head"><BookOpen :size="16" /><strong>真题语境释义</strong></div>
        <p class="word-contextual">{{ word.contextual_meaning }}</p>
      </section>

      <!-- 词性语法 -->
      <section v-if="posGroups.length" class="word-section card">
        <div class="word-section-head"><BookOpen :size="16" /><strong>词性与语法</strong></div>
        <div v-for="(g, i) in posGroups" :key="i" class="word-pos-group">
          <span class="word-pos-badge">{{ g.pos || '通用' }}</span>
          <span class="word-pos-desc">{{ g.common }}</span>
        </div>
      </section>

      <!-- 同/反/形近 辨析（使用范围边界） -->
      <section v-if="word.synonyms?.length || word.antonyms?.length || word.similar_forms?.length || word.local_similar?.length" class="word-section card">
        <div class="word-section-head"><RefreshCw :size="16" /><strong>辨析 · 使用范围</strong></div>
        <div v-if="word.synonyms?.length" class="word-disc">
          <span class="disc-label syn">同义词</span>
          <div class="disc-items">
            <span v-for="s in word.synonyms" :key="`s-${s.word}`" class="disc-item"><b>{{ s.word }}</b>{{ s.note }}</span>
          </div>
        </div>
        <div v-if="word.antonyms?.length" class="word-disc">
          <span class="disc-label ant">反义词</span>
          <div class="disc-items">
            <span v-for="a in word.antonyms" :key="`a-${a.word}`" class="disc-item"><b>{{ a.word }}</b>{{ a.note }}</span>
          </div>
        </div>
        <div v-if="word.local_similar?.length || word.similar_forms?.length" class="word-disc">
          <span class="disc-label sim">形近词</span>
          <div class="disc-items">
            <span v-for="s in word.local_similar" :key="`l-${s.word}`" class="disc-item"><b>{{ s.word }}</b>{{ s.note }}</span>
            <span v-for="s in word.similar_forms" :key="`m-${s.word}`" class="disc-item"><b>{{ s.word }}</b>{{ s.note }}</span>
          </div>
        </div>
      </section>

      <!-- 记忆提示 -->
      <section v-if="word.memory_hint" class="word-section card memory-hint">
        <div class="word-section-head"><Star :size="16" /><strong>记忆提示</strong></div>
        <p>{{ word.memory_hint }}</p>
      </section>

      <!-- 真题组句：如何组成句子（扇贝真题例句 + 欧路按来源分组） -->
      <section class="word-section card">
        <div class="word-section-head"><Headphones :size="16" /><strong>真题组句 · 如何用</strong></div>
        <div v-if="!word.occurrences?.length && !word.examples?.length && !contexts.length" class="muted">暂无真题例句。</div>
        <template v-else>
          <article v-for="occ in (word.occurrences || []).slice(0, expandedAll ? 99 : 3)" :key="occ.id" class="word-sentence">
            <p v-html="highlightForms(occ.context_sentence)"></p>
            <small><TtsButton :text="occ.context_sentence" :speed="0.9" :size="13" /> {{ occ.year || '未知年份' }} · {{ occ.unit_title || occ.unit_type }}</small>
          </article>
          <article v-for="example in (word.examples || []).slice(0, expandedAll ? 99 : 3)" :key="`example-${example.id}`" class="word-sentence bilingual-example">
            <p v-html="highlightForms(example.english_sentence)"></p>
            <p class="example-translation">{{ example.chinese_translation }}</p>
            <small><TtsButton :text="example.english_sentence" :speed="0.9" :size="13" /> {{ example.source || '双语例句' }}</small>
          </article>
          <button v-if="word.occurrences?.length > 3" class="button ghost compact" @click="expandedAll = !expandedAll">{{ expandedAll ? '收起' : `展开全部 ${word.occurrences.length} 条` }}</button>
        </template>
      </section>

      <!-- 词文串学（扇贝词文串学 + 不背单词原声） -->
      <section class="word-section card">
        <div class="word-section-head"><Volume2 :size="16" /><strong>词文串学 · 真题语境</strong></div>
        <div v-if="contextsLoading" class="muted">检索真题语境…</div>
        <div v-else-if="contexts.length">
          <article v-for="(c, i) in contexts" :key="i" class="word-sentence">
            <p v-html="sanitizeHtml(highlightContext(c))"></p>
            <small><TtsButton :text="c.sentence" :speed="0.9" :size="13" /> {{ c.source }} <span v-if="c.style" class="style-badge" :class="`style-${c.style}`">{{ styleLabel(c.style) }}</span></small>
          </article>
        </div>
        <div v-else class="muted">题库中暂无该词的真题语境。</div>
      </section>

      <!-- v9.27: Gemini UI4——三态背诵底栏（认识/模糊/忘记，墨墨模式） -->
      <div class="word-actions vocab-recite-action-bar">
        <button class="vocab-btn-action btn-forgot" @click="setStudyStatus('')">忘记</button>
        <button class="vocab-btn-action btn-fuzzy" @click="setStudyStatus('learning')">模糊</button>
        <button class="vocab-btn-action btn-known" @click="setStudyStatus('familiar')">认识</button>
      </div>
      <!-- v9.27: 标记重点保留（独立小按钮，不占主操作位） -->
      <div class="word-actions-secondary">
        <button class="button ghost compact" @click="put(`/vocabulary/${word.id}`, { manually_frequent: !word.manually_frequent }).then(load)">
          <Star :size="14" />{{ word.manually_frequent ? '取消重点' : '标记重点' }}
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.word-topbar { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 16px; }
.word-topbar-title { display: flex; flex-direction: column; align-items: center; }
.word-topbar-title strong { font-size: 17px; }
.word-topbar-title span { font-size: 12px; color: var(--muted); }

.word-hero { padding: 24px 22px; text-align: center; }
.word-hero-term h1 { font-size: 40px; margin: 0 0 2px; letter-spacing: .5px; }
.word-hero-phonetic { color: var(--muted); font-size: 15px; }
.word-voice { display: flex; align-items: center; justify-content: center; gap: 12px; margin-top: 10px; }
.voice-toggle { display: flex; border: 1px solid var(--line); border-radius: 99px; overflow: hidden; }
.voice-toggle button { padding: 5px 14px; font-size: 12px; background: transparent; border: 0; cursor: pointer; color: var(--muted); }
.voice-toggle button.active { background: var(--primary); color: #fff; }
.word-hero-mean { margin-top: 16px; display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; }
.word-pos-badge { background: var(--primary-soft); color: var(--primary); font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 99px; }
.word-main-meaning { font-size: 17px; }
.word-hero-tags { margin-top: 8px; }
.word-freq-tag { background: #fdf1e0; color: #b7791f; font-size: 12px; padding: 3px 10px; border-radius: 99px; }

.word-section { padding: 16px 18px; margin-bottom: 12px; }
.word-section-head { display: flex; align-items: center; gap: 7px; color: var(--primary); margin-bottom: 10px; }
.word-section-head strong { font-size: 14px; color: var(--text); }
.word-contextual { font-size: 15px; line-height: 1.7; color: var(--text); background: var(--surface-2); border-radius: 10px; padding: 10px 14px; }
.word-pos-group { display: flex; align-items: baseline; gap: 10px; margin-bottom: 8px; flex-wrap: wrap; }
.word-pos-desc { font-size: 14px; }

.word-disc { display: flex; gap: 8px; margin-bottom: 8px; align-items: flex-start; }
.disc-label { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 99px; flex-shrink: 0; margin-top: 2px; }
.disc-label.syn { background: #e3f4ec; color: #1e7d4f; }
.disc-label.ant { background: #fdeaea; color: #c0392b; }
.disc-label.sim { background: #e8f0fb; color: #2d6db5; }
.disc-items { display: flex; flex-wrap: wrap; gap: 6px; }
.disc-item { font-size: 12px; color: var(--muted); background: var(--surface-2); border-radius: 8px; padding: 5px 10px; }
.disc-item b { color: var(--text); margin-right: 5px; }

.word-sentence { border-left: 3px solid var(--primary); padding-left: 12px; margin-bottom: 12px; }
.word-sentence p { font-size: 15px; line-height: 1.8; margin: 0 0 6px; }
.bilingual-example .example-translation { color: var(--muted); font-size: 13px; }
.word-sentence small { font-size: 11px; color: var(--muted); display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }

.word-actions { display: flex; gap: 10px; justify-content: center; margin-top: 8px; padding-bottom: 24px; }
</style>
