<script setup lang="ts">
// v3.4: 单词库独立页面——从 VocabularyView 拆分（点击"查看全部单词库"跳转此处）
// 含：分类筛选 / 统计 / 列表 / 详情 / 一键回到顶部
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { del, get, post, put } from '../api'
import { sanitizeHtml } from '../services/sanitize'  // v9.24: XSS 防护
import { ArrowUp, Check, RefreshCw, Search, Star, Trash2 } from 'lucide-vue-next'
import TtsButton from '../components/TtsButton.vue'

const route = useRoute()
const router = useRouter()
const items = ref<any[]>([])
const counts = ref<any>({ total: 0, frequent: 0, mastered: 0, pending: 0, review: 0 })
const filter = ref('all')
const category = ref('')
const catType = ref('')
const search = ref('')
const error = ref('')
const notice = ref('')
const selected = ref<any>(null)
const editing = ref(false)
const editForm = reactive<any>({})
const wordContexts = ref<any[]>([])
const wordContextsLoading = ref(false)
const expandedAll = ref(false)
// 回到顶部
const showTopBtn = ref(false)
const scrollEl = ref<HTMLElement | null>(null)

function vocabStatusText(status: string) {
  if (status === 'mastered') return '已掌握'
  if (status === 'familiar') return '认识'
  if (status === 'learning') return '模糊'
  return '生疏'
}

// v9.27: Gemini UI4——状态标签三色映射
function getStatusClass(status: string) {
  if (status === 'mastered') return 'vocab-status-tag--mastered'
  if (status === 'familiar' || status === 'learning') return 'vocab-status-tag--learning'
  return 'vocab-status-tag--raw'
}

function translationStatusText(status: string, detail = false) {
  if (status === 'translating') return detail ? '模型正在后台翻译' : '正在后台翻译…'
  if (status === 'failed') return detail ? '翻译暂未完成' : '等待重新翻译'
  return detail ? '等待练习提交或退出后翻译' : '等待练习结束后翻译'
}

async function load() {
  try {
    const catParam = category.value || catType.value ? `&category=${encodeURIComponent(category.value + catType.value)}` : ''
    const result: any = await get(`/vocabulary?status=${filter.value}&search=${encodeURIComponent(search.value)}${catParam}`)
    error.value = ''
    items.value = result.items || []
    counts.value = result.counts || counts.value
    const requested = Number(route.query.word)
    const target = items.value.find((item: any) => item.id === requested) || items.value[0]
    if (target) await select(target.id)
    else selected.value = null
  } catch (e) { error.value = String(e) }
}

async function select(id: number) {
  try {
    selected.value = await get(`/vocabulary/${id}`)
    error.value = ''
    Object.assign(editForm, selected.value)
    editing.value = false
    expandedAll.value = false
    wordContexts.value = []
    wordContextsLoading.value = true
    try {
      const ctx: any = await get(`/vocabulary/${id}/context`)
      wordContexts.value = ctx.contexts || []
    } catch { wordContexts.value = [] }
    wordContextsLoading.value = false
  } catch (e) { error.value = String(e) }
}

async function saveEdit() {
  selected.value = await put(`/vocabulary/${selected.value.id}`, {
    contextual_meaning: editForm.contextual_meaning,
    common_meaning: editForm.common_meaning,
    phonetic: editForm.phonetic,
    part_of_speech: editForm.part_of_speech,
    note: editForm.note,
    study_status: editForm.study_status,
    manually_frequent: Boolean(editForm.manually_frequent),
  })
  editing.value = false
  notice.value = '词条已保存'
  await load()
}

async function removeEntry() {
  if (!selected.value || !confirm(`删除 ${selected.value.term} 吗？`)) return
  await del(`/vocabulary/${selected.value.id}`)
  selected.value = null
  await load()
}

async function retryTranslation() {
  await post(`/vocabulary/${selected.value.id}/retry`)
  notice.value = '已重新提交翻译，请稍后刷新'
  await load()
}

async function exportAnki() {
  try {
    const result: any = await get('/vocabulary/export/anki')
    if (result.error) { alert(result.error); return }
    const resp = await fetch(`/api/vocabulary/export/anki/download?filename=${encodeURIComponent(result.filename)}`)
    if (!resp.ok) { alert('文件下载失败'); return }
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = result.filename; a.click()
    URL.revokeObjectURL(url)
  } catch (e) { alert(`导出失败：${e}`) }
}

// v2.36: 词文串学风格标签
const STYLE_LABELS: Record<string, string> = {
  interview: '🗣 访谈', argument: '📊 论述', news: '📰 新闻', story: '📖 故事', article: '📄 文章',
}
function styleLabel(style: string) { return STYLE_LABELS[style] || style }

function highlightContext(c: any): string {
  const word = c.highlight || ''
  if (!word) return c.sentence
  const re = new RegExp('(' + word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'ig')
  return c.sentence.replace(re, '<mark class="vocab-context-mark">$1</mark>')
}

let searchTimer = 0
watch(search, () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(load, 250)
})
watch(filter, load)
watch(category, load)
watch(catType, load)

// 回到顶部
function onScroll() {
  const el = scrollEl.value || document.documentElement
  showTopBtn.value = (el.scrollTop || window.scrollY || 0) > 300
}
function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
onMounted(() => { load(); window.addEventListener('scroll', onScroll, { passive: true }) })
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))
</script>

<template>
  <div class="page page-vocab vocabulary-page vocab-bank-page" ref="scrollEl">
    <div class="page-head">
      <div>
        <span class="eyebrow">VOCABULARY BANK</span>
        <h1>全部单词库</h1>
        <p class="lead">从真题语境中收集的全部词汇，可按分类/状态筛选浏览。</p>
      </div>
      <div style="display:flex;gap:8px;align-items:center">
        <button class="button ghost" @click="router.push('/notes')">← 返回</button>
        <button class="button ghost" @click="exportAnki"><RefreshCw :size="16" />导出 Anki</button>
      </div>
    </div>

    <div v-if="error" class="warning">{{ error }}</div>

    <!-- 分类筛选 -->
    <div class="vocab-categories">
      <button class="vocab-cat-chip" :class="{ active: category === '' }" @click="category=''">全部</button>
      <button class="vocab-cat-chip" :class="{ active: category === '高中' }" @click="category='高中'">🏫 高中</button>
      <button class="vocab-cat-chip" :class="{ active: category === '四级' }" @click="category='四级'">📘 四级</button>
      <button class="vocab-cat-chip" :class="{ active: category === '六级' }" @click="category='六级'">📙 六级</button>
      <button class="vocab-cat-chip" :class="{ active: category === '考研' }" @click="category='考研'">🎓 考研</button>
    </div>
    <div class="vocab-categories vocab-cat-types">
      <button class="vocab-cat-chip" :class="{ active: catType === '' }" @click="catType=''">全部类型</button>
      <button class="vocab-cat-chip" :class="{ active: catType === '·高频' }" @click="catType='·高频'">⭐ 高频词</button>
      <button class="vocab-cat-chip" :class="{ active: catType === '·热点' }" @click="catType='·热点'">🔥 热点词</button>
      <button class="vocab-cat-chip" :class="{ active: catType === '·' }" @click="catType='·'">📚 基础词</button>
    </div>

    <!-- 统计 -->
    <div class="vocab-stats">
      <button class="card" @click="filter='all'"><span>全部单词</span><strong>{{ counts.total || 0 }}</strong></button>
      <button class="card amber" @click="filter='frequent'"><span>🌟 高频生词</span><strong>{{ counts.frequent || 0 }}</strong></button>
      <button class="card" @click="filter='review'"><span>今日待复习</span><strong>{{ counts.review || 0 }}</strong></button>
      <button class="card" @click="filter='mastered'"><span>已掌握</span><strong>{{ counts.mastered || 0 }}</strong></button>
      <button class="card" @click="filter='pending'"><span>等待翻译</span><strong>{{ counts.pending || 0 }}</strong></button>
    </div>

    <div class="vocabulary-layout">
      <aside class="vocab-filters card">
        <div class="search-field"><Search :size="16" /><input v-model="search" placeholder="搜索单词或释义"></div>
        <button v-for="item in [
          ['all','全部单词'],['review','今日复习'],['frequent','🌟 高频词'],
          ['familiar','认识'],['learning','模糊'],['mastered','已掌握'],['pending','等待翻译']
        ]" :key="item[0]" :class="{active:filter===item[0]}" @click="filter=item[0]">{{ item[1] }}</button>
      </aside>

      <section class="vocab-list card">
        <button v-for="word in items" :key="word.id" class="vocab-list-item" :class="{active:selected?.id===word.id}" @click="router.push(`/vocab-word/${word.id}`)">
          <div class="vocab-list-head"><strong><span v-if="word.is_frequent">🌟 </span>{{ word.lemma || word.term }}</strong><small>遇到 {{ word.encounter_count }} 次</small></div>
          <p v-if="word.translation_status==='ready'">{{ word.common_meaning || word.contextual_meaning }}</p>
          <p v-else class="pending-text">{{ translationStatusText(word.translation_status) }}</p>
          <div class="vocab-list-meta"><span>{{ word.part_of_speech }}</span><span class="vocab-status-tag" :class="getStatusClass(word.study_status)">{{ vocabStatusText(word.study_status) }}</span></div>
        </button>
        <div v-if="!items.length" class="empty">这里还没有符合条件的单词。</div>
      </section>

      <section class="vocab-detail card" v-if="selected">
        <div class="vocab-detail-head">
          <div><span class="eyebrow">{{ selected.is_frequent ? '🌟 HIGH FREQUENCY' : 'VOCABULARY' }}</span><h2>{{ selected.lemma || selected.term }}<TtsButton :text="selected.term" :speed="0.8" /></h2><p>{{ selected.phonetic }} <span v-if="selected.part_of_speech">· {{ selected.part_of_speech }}</span></p></div>
          <div class="vocab-tools"><button class="button ghost" @click="expandedAll=!expandedAll">{{ expandedAll ? '收起全部' : '展开全部' }}</button><button class="button ghost" @click="exportAnki">导出 Anki</button><button class="button ghost" @click="editing=!editing">编辑</button><button class="button ghost danger-text" @click="removeEntry"><Trash2 :size="17" /></button></div>
        </div>
        <div v-if="selected.translation_status!=='ready'" class="vocab-pending-panel">
          <RefreshCw :size="22" /><strong>{{ translationStatusText(selected.translation_status, true) }}</strong>
          <button v-if="selected.translation_status==='failed'" class="button secondary" @click="retryTranslation">重新翻译</button>
        </div>
        <template v-else-if="!editing">
          <div class="detail-section"><label>常用释义</label><strong>{{ selected.common_meaning || selected.contextual_meaning }}</strong></div>
          <div v-if="selected.contextual_meaning && selected.contextual_meaning !== selected.common_meaning" class="detail-section"><label>本句语境</label><strong>{{ selected.contextual_meaning }}</strong></div>
          <div v-if="selected.synonyms?.length" class="detail-section discrimination-section">
            <label>同义词辨析</label>
            <ul class="discrimination-list"><li v-for="item in selected.synonyms" :key="`s-${item.word}`"><strong>{{ item.word }}</strong><span>{{ item.note }}</span></li></ul>
          </div>
          <div v-if="selected.antonyms?.length" class="detail-section discrimination-section">
            <label>反义词辨析</label>
            <ul class="discrimination-list"><li v-for="item in selected.antonyms" :key="`a-${item.word}`"><strong>{{ item.word }}</strong><span>{{ item.note }}</span></li></ul>
          </div>
          <div v-if="selected.memory_hint" class="detail-section memory-hint"><label>记忆提示</label><p>{{ selected.memory_hint }}</p></div>
          <div v-if="selected.note" class="detail-section"><label>我的笔记</label><p>{{ selected.note }}</p></div>
          <div class="detail-section">
            <label>真题中的遇见</label>
            <template v-if="selected.occurrences?.length || expandedAll">
              <article v-for="occ in selected.occurrences" :key="occ.id" class="occurrence">
                <p>{{ occ.context_sentence }}</p>
                <small>{{ occ.year || '未知年份' }} · {{ occ.unit_title || occ.unit_type }}</small>
              </article>
            </template>
            <div v-else class="muted">暂无真题例句记录。</div>
          </div>
          <div class="detail-section vocab-context-section">
            <label>词文串学 · 真题语境</label>
            <div v-if="wordContextsLoading" class="muted">检索真题语境…</div>
            <div v-else-if="wordContexts.length">
              <article v-for="(c, i) in wordContexts" :key="i" class="occurrence">
                <p v-html="sanitizeHtml(highlightContext(c))"></p>
                <small>{{ c.source }} <span v-if="c.style" class="style-badge" :class="`style-${c.style}`">{{ styleLabel(c.style) }}</span></small>
              </article>
            </div>
            <div v-else class="muted">题库中暂无该词的真题例句。</div>
          </div>
          <div class="detail-actions">
            <button class="button secondary" @click="put(`/vocabulary/${selected.id}`,{manually_frequent:!selected.manually_frequent}).then(()=>load())"><Star :size="16" />{{ selected.manually_frequent ? '取消重点' : '标记重点' }}</button>
            <button class="button" @click="put(`/vocabulary/${selected.id}`,{study_status:selected.study_status==='mastered'?'learning':'mastered'}).then(()=>load())"><Check :size="16" />{{ selected.study_status === 'mastered' ? '恢复学习' : '标记已掌握' }}</button>
          </div>
        </template>
        <div v-else class="vocab-edit">
          <label>音标<input v-model="editForm.phonetic"></label>
          <label>词性<input v-model="editForm.part_of_speech"></label>
          <label>当前语境释义<textarea rows="3" v-model="editForm.contextual_meaning"></textarea></label>
          <label>常用释义<textarea rows="3" v-model="editForm.common_meaning"></textarea></label>
          <label>我的笔记<textarea rows="4" v-model="editForm.note"></textarea></label>
          <div><button class="button" @click="saveEdit">保存修改</button><button class="button ghost" @click="editing=false">取消</button></div>
        </div>
      </section>
      <section v-else class="vocab-detail card empty">选择一个单词查看详细释义与真题语境。</section>
    </div>

    <!-- 一键回到顶部 -->
    <Transition name="fade-in">
      <button v-if="showTopBtn" class="vocab-top-btn" type="button" @click="scrollToTop" aria-label="回到顶部">
        <ArrowUp :size="20" />
      </button>
    </Transition>
  </div>
</template>

<style scoped>
.vocab-top-btn {
  position: fixed;
  right: 22px;
  bottom: calc(76px + env(safe-area-inset-bottom, 0px));
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 1px solid var(--line);
  background: var(--surface-solid, #fff);
  color: var(--primary);
  display: grid;
  place-items: center;
  box-shadow: 0 6px 20px rgba(0,0,0,.15);
  cursor: pointer;
  z-index: 60;
  transition: transform .15s ease, box-shadow .15s ease;
}
.vocab-top-btn:active { transform: scale(.92); }
</style>
