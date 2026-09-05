<template>
  <div class="page essay-page">
    <div class="page-head">
      <h2><PenLine :size="18" aria-hidden="true" />AI 作文精批</h2>
      <p class="muted">考研大小作文 · 阅卷组标准多维批改 · 逐句批注 + 满分范文</p>
    </div>

    <div class="essay-layout">
      <!-- 左栏: 作文编辑器 -->
      <div class="card essay-editor-card">
        <div class="essay-meta">
          <select v-model="essayType" class="essay-select">
            <option value="essay_small">小作文（10 分）</option>
            <option value="essay_large">大作文（20 分）</option>
          </select>
          <input v-model="subject" class="essay-select" placeholder="科目（英语一/二）" style="width:120px" />
          <input v-model="promptTitle" class="essay-select" placeholder="题目要求（可选）" style="flex:1" />
        </div>
        <textarea v-model="content" class="essay-textarea" placeholder="在此输入你的英语作文…" maxlength="1500"
                  :class="{ 'word-warn': wordCount < 80 }"></textarea>
        <div class="essay-footer">
          <span class="word-count" :class="{ ok: wordCount >= 80 && wordCount <= 220, warn: wordCount > 0 && wordCount < 80 }">
            {{ wordCount }} 词
            <template v-if="wordCount >= 80 && wordCount <= 220"><CircleCheck :size="13" aria-hidden="true" />达标区间</template>
            <template v-else-if="wordCount > 0 && wordCount < 80"><TriangleAlert :size="13" aria-hidden="true" />不足 80 词</template>
          </span>
          <button class="button essay-submit" :disabled="loading || content.trim().length < 10" @click="evaluate">
            {{ loading ? '阅卷中…' : '<FileText :size="15" aria-hidden="true" />AI 精批' }}
          </button>
        </div>
      </div>

      <!-- 右栏: 批改结果 -->
      <div v-if="result" class="essay-result">
        <!-- 评分印章 -->
        <div class="card essay-score-card">
          <div class="grade-seal-badge score-row">
            <span class="score-huge">{{ result.score }}</span>
            <span class="score-total">/ {{ result.max_score }}</span>
          </div>
          <div class="score-band">{{ result.band }}</div>
          <div class="score-dims">
            <div v-for="(v, k) in result.dimensions" :key="k" class="dim-row">
              <span class="dim-name">{{ dimLabel(String(k)) }}</span>
              <div class="dim-track ink-progress-track"><div class="dim-fill ink-progress-bar" :style="{ width: (v / 5 * 100) + '%' }"></div></div>
              <span class="dim-value">{{ v }}</span>
            </div>
          </div>
          <p class="overall-comment">{{ result.overall_comment }}</p>
        </div>

        <!-- 行内批注 -->
        <div v-if="result.markups?.length" class="card essay-section-card">
          <h3><PenLine :size="15" aria-hidden="true" />行内纠错</h3>
          <div v-for="(m, i) in result.markups" :key="i" class="markup-item" :class="'markup-' + (m.type || 'grammar')">
            <span class="markup-type">{{ markupTypeLabel(m.type) }}</span>
            <p class="markup-original"><s>{{ m.original_text }}</s> → <b>{{ m.replacement }}</b></p>
            <p class="markup-explanation">{{ m.explanation }}</p>
          </div>
        </div>

        <!-- 词汇升格 -->
        <div v-if="result.lexical_upgrades?.length" class="card essay-section-card">
          <h3><Sparkles :size="15" aria-hidden="true" />词汇升格 <small class="section-hint">点击「收录」加入词库，进入复习流</small></h3>
          <div v-for="(u, i) in result.lexical_upgrades" :key="i" class="upgrade-item">
            <span class="upgrade-orig">{{ u.original_word }}</span>
            <span class="upgrade-arrow">→</span>
            <span class="upgrade-new">{{ u.advanced_alternative }}</span>
            <span v-if="u.position" class="upgrade-pos">{{ u.position }}</span>
            <!-- v9.28: Gemini batch5 任务4——作文语料收录 -->
            <button class="upgrade-collect" type="button" @click="collectUpgrade(u)" :disabled="collectedUpgrades.has(u.advanced_alternative)">
              {{ collectedUpgrades.has(u.advanced_alternative) ? '已收录' : '+ 收录' }}
            </button>
          </div>
        </div>

        <!-- 满分范文 -->
        <div v-if="result.model_essay" class="card essay-section-card model-essay">
          <h3><Award :size="15" aria-hidden="true" />满分范文</h3>
          <p class="model-essay-text">{{ result.model_essay }}</p>
          <div v-if="result.essay_highlights?.length" class="highlight-list">
            <span v-for="(h, i) in result.essay_highlights" :key="i" class="highlight-item">🈴 {{ h }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 历史批改 -->
    <div v-if="history.length" class="card essay-history">
      <h3><Library :size="15" aria-hidden="true" />历史批改</h3>
      <div class="history-list">
        <button v-for="h in history" :key="h.id" class="history-item" @click="loadHistory(h.id)">
          <span class="history-score">{{ h.score }} 分</span>
          <span class="history-title">{{ h.prompt_title || '（未命名作文）' }}</span>
          <span class="history-date">{{ h.created_at?.slice(0, 10) }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Award, BookOpen, FileText, Lightbulb, Library, PenLine, Sparkles, CircleCheck, TriangleAlert } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { get, post } from '../api'
import { showToast } from '../services/toast'

const essayType = ref('essay_large')
const subject = ref('英语一')
const promptTitle = ref('')
const content = ref('')
const loading = ref(false)
const result = ref<any>(null)
const history = ref<any[]>([])

const wordCount = computed(() => content.value.trim() ? content.value.trim().split(/\s+/).length : 0)

const DIM_LABELS: Record<string, string> = {
  content_relevance: '内容相关', syntax_variety: '句式多样',
  vocabulary_richness: '词汇丰富', coherence_structure: '连贯结构',
}
const dimLabel = (k: string) => DIM_LABELS[k] || k.replace(/_/g, ' ')

const markupTypeLabel = (t: string) => ({
  grammar: '语法', spelling: '拼写', collocation: '搭配',
}[t] || t)

async function evaluate() {
  loading.value = true
  try {
    result.value = await post('/essays/evaluate', {
      essay_type: essayType.value,
      subject: subject.value,
      prompt_title: promptTitle.value,
      user_content: content.value,
    })
    await loadHistoryList()
  } catch (e) {
    alert(String(e))
  } finally {
    loading.value = false
  }
}

// v9.28: Gemini batch5 任务4——作文语料收录（升格词 → 词库复习流）
const collectedUpgrades = ref<Set<string>>(new Set())
async function collectUpgrade(u: any) {
  const word = (u.advanced_alternative || '').trim()
  if (!word || collectedUpgrades.value.has(word)) return
  try {
    await post('/vocabulary', {
      term: word,
      context_sentence: `作文升格：${u.original_word || ''} → ${word}`,
    })
    collectedUpgrades.value.add(word)
    showToast(`已收录「${word}」到词库`, 'success')
  } catch (e) {
    showToast(`收录失败：${e}`, 'error')
  }
}

async function loadHistoryList() {
  try { history.value = (await get<{ items: any[] }>('/essays'))?.items || [] } catch { /* ignore */ }
}
async function loadHistory(id: number) {
  try { result.value = await get(`/essays/${id}`) } catch { /* ignore */ }
}

onMounted(loadHistoryList)
</script>

<style scoped>
.essay-layout { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap; }
.essay-editor-card { flex: 1 1 420px; min-width: 340px; }
.essay-meta { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.essay-select {
  background: rgba(255, 255, 255, 0.65); border: 1px solid var(--border-paper);
  border-radius: 10px; color: var(--text-pine); padding: 8px 12px; font-size: 13px;
}
.essay-textarea {
  width: 100%; min-height: 320px; resize: vertical;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid var(--border-paper); border-radius: 12px;
  padding: 16px; font-size: 15px; line-height: 1.8; color: var(--text-pine);
  font-family: var(--font-en-serif), serif;
}
.essay-textarea:focus { outline: none; border-color: var(--accent-vermilion); box-shadow: 0 0 0 3px rgba(184, 74, 57, 0.12); }
.essay-textarea.word-warn { border-color: rgba(184, 74, 57, 0.3); }
.essay-footer { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
.word-count { font-size: 13px; color: var(--text-faint); font-family: var(--font-en-serif); }
.word-count.ok { color: var(--accent-bamboo); }
.word-count.warn { color: var(--accent-vermilion); }
.essay-submit { background: var(--accent-vermilion); color: #FFFDF9; border-radius: 9999px; box-shadow: 0 4px 12px rgba(184, 74, 57, 0.2); }
.essay-result { flex: 1 1 420px; min-width: 340px; display: flex; flex-direction: column; gap: 16px; }
.score-row { align-items: center; gap: 8px; }
.score-band { font-family: var(--font-serif); color: var(--accent-vermilion); font-size: 14px; margin-top: 8px; }
.score-dims { margin-top: 12px; }
.overall-comment { margin-top: 12px; font-size: 14px; color: var(--text-pine); line-height: 1.7; }
.essay-section-card h3 { font-family: var(--font-serif); font-size: 15px; margin-bottom: 10px; color: var(--text-pine); }
.markup-item { border-left: 3px solid; padding: 8px 12px; margin-bottom: 8px; border-radius: 0 8px 8px 0; }
.markup-grammar { border-color: var(--accent-vermilion); background: rgba(184, 74, 57, 0.04); }
.markup-spelling { border-color: var(--accent-ochre); background: rgba(166, 122, 56, 0.04); }
.markup-collocation { border-color: var(--accent-bamboo); background: rgba(74, 95, 78, 0.04); }
.markup-type { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: rgba(60, 50, 40, 0.06); color: var(--text-faint); }
.markup-original { font-size: 13px; margin: 6px 0 2px; }
.markup-original b { color: var(--accent-bamboo); }
.markup-explanation { font-size: 12px; color: var(--text-faint); }
.upgrade-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; font-size: 13px; border-bottom: 1px dashed var(--line); }
.upgrade-orig { color: var(--text-faint); text-decoration: line-through; }
.upgrade-arrow { color: var(--accent-ochre); }
.upgrade-new { color: var(--accent-bamboo); font-weight: 600; }
.upgrade-collect {
  margin-left: auto; padding: 2px 10px; border: 1px solid rgba(74, 95, 78, 0.3);
  border-radius: 999px; background: transparent; color: #4A5F4E;
  font-size: 11px; cursor: pointer; transition: all .15s; flex-shrink: 0;
}
.upgrade-collect:hover { background: #4A5F4E; color: #fff; border-color: #4A5F4E; }
.upgrade-collect:disabled { opacity: 0.55; cursor: default; }
.section-hint { font-size: 11px; color: var(--text-faint); font-weight: 400; }
.upgrade-pos { margin-left: 6px; font-size: 11px; color: var(--text-muted-2); }
.model-essay-text { font-family: var(--font-en-serif), serif; font-size: 14px; line-height: 1.8; color: var(--text-pine); }
.highlight-list { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.highlight-item { font-family: var(--font-serif); font-size: 11px; color: var(--accent-ochre); background: rgba(166, 122, 56, 0.06); border: 1px solid rgba(166, 122, 56, 0.2); border-radius: 4px; padding: 2px 8px; }
.essay-history { margin-top: 16px; }
.history-list { display: flex; flex-direction: column; gap: 4px; }
.history-item { display: flex; align-items: center; gap: 12px; padding: 8px 12px; border: 1px solid var(--border-paper); border-radius: 8px; background: var(--bg-card); cursor: pointer; transition: all 0.2s; }
.history-item:hover { border-color: var(--accent-bamboo); transform: translateY(-1px); }
.history-score { font-family: var(--font-en-serif); color: var(--accent-vermilion); font-weight: 600; }
.history-title { flex: 1; font-size: 13px; color: var(--text-pine); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.history-date { font-size: 11px; color: var(--text-muted-2); }
</style>
