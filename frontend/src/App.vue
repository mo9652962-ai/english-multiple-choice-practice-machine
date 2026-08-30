<script setup lang="ts">
import { Activity, BarChart2, BarChart3, BookMarked, BookOpenText, Brain, CalendarDays, FileUp, GraduationCap, Headphones, Home, LayoutGrid, Library, MessageCircle, Mic2, Moon, PenLine, Settings, Sparkles, StickyNote, Sun, Target, Timer, Trophy } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppToast from './components/AppToast.vue'
import { get } from './api'
import { activateQuestionBankProfile, loadQuestionBankProfiles, questionBankProfilesState } from './services/questionBankProfiles'

const route = useRoute()
const dark = ref(false)
const categories = ref<any[]>([])
const activeCategoryId = ref<number | null>(null)

async function loadCategories() {
  try {
    await loadQuestionBankProfiles()
    categories.value = questionBankProfilesState.items
    activeCategoryId.value = questionBankProfilesState.activeId
  } catch {
    // 离线模式或后端不可用
  }
}

async function switchCategory(id: number) {
  if (id === activeCategoryId.value) return
  try {
    await activateQuestionBankProfile(id)
    activeCategoryId.value = id
    recordCategoryUsage(id)
    window.location.reload()
  } catch {
    // ignore
  }
}

// v2.47: 常用类别 (localStorage 使用计数 top2) + 类别选择弹窗
const categoryModal = ref(false)
function recordCategoryUsage(id: number) {
  try {
    const raw = localStorage.getItem('epm_category_usage') || '{}'
    const usage: Record<string, number> = JSON.parse(raw)
    usage[String(id)] = (usage[String(id)] || 0) + 1
    localStorage.setItem('epm_category_usage', JSON.stringify(usage))
  } catch { /* ignore */ }
}
const frequentCategories = computed(() => {
  try {
    const raw = localStorage.getItem('epm_category_usage') || '{}'
    const usage: Record<string, number> = JSON.parse(raw)
    const sorted = [...categories.value]
      .filter((c) => c.id !== activeCategoryId.value && !c.deleted_at)
      .sort((a, b) => (usage[String(b.id)] || 0) - (usage[String(a.id)] || 0))
    return [...sorted.slice(0, 2)]
  } catch {
    return categories.value.filter((c) => c.id !== activeCategoryId.value).slice(0, 2)
  }
})
const activeCategory = computed(() =>
  categories.value.find((c) => c.id === activeCategoryId.value) || null
)
function openCategoryModal() {
  categoryModal.value = true
}
function pickCategory(cat: any) {
  categoryModal.value = false
  if (cat.id === activeCategoryId.value) return
  switchCategory(cat.id)
}

const categoryIcons: Record<string, any> = {
  'graduation-cap': GraduationCap,
  'book-open': BookOpenText,
  'book': BookMarked,
}
function applyTheme() {
  document.documentElement.classList.toggle('dark', dark.value)
  localStorage.setItem('linjian-theme', dark.value ? 'dark' : 'light')
}

function toggleTheme() {
  // v9.19 UI: View Transition API 圆形遮罩过渡 (fallback: 直接切换)
  const apply = () => {
    dark.value = !dark.value
    applyTheme()
  }
  const doc = document as any
  if (doc.startViewTransition) {
    doc.startViewTransition(() => apply())
  } else {
    apply()
  }
}

onMounted(() => {
  dark.value = localStorage.getItem('linjian-theme') === 'dark'
    || (!localStorage.getItem('linjian-theme') && matchMedia('(prefers-color-scheme: dark)').matches)
  applyTheme()
  document.body.classList.add('ink-landscape')
  void loadCategories()
})
</script>

<template>
  <div
    class="app-shell"
    :class="{ 'practice-shell': route.path.startsWith('/practice') }"
  >
    <aside class="sidebar" v-if="!route.path.startsWith('/practice')">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">墨</span>
        <span class="brand-copy"><strong>墨题</strong><small>水墨之间 · 学海无涯</small></span>
      </RouterLink>
      <nav aria-label="主要导航">
        <div class="nav-section-label">研习核心</div>
        <RouterLink to="/"><Home :size="18" aria-hidden="true" /><span>首页</span></RouterLink>
        <RouterLink to="/library"><Library :size="18" aria-hidden="true" /><span>题库与练习</span></RouterLink>
        <RouterLink to="/exam"><Timer :size="18" aria-hidden="true" /><span>模拟考试</span></RouterLink>
        <RouterLink to="/reading"><BookOpenText :size="18" aria-hidden="true" /><span>阅读训练</span></RouterLink>
        <RouterLink to="/listening"><Headphones :size="18" aria-hidden="true" /><span>听力精听</span></RouterLink>
        <RouterLink to="/vocabulary"><BookMarked :size="18" aria-hidden="true" /><span>单词本</span></RouterLink>

        <div class="nav-section-label">分析与诊断</div>
        <RouterLink to="/wrong"><Brain :size="18" aria-hidden="true" /><span>错题本</span></RouterLink>
        <RouterLink to="/diagnostic"><Activity :size="18" aria-hidden="true" /><span>学习诊断</span></RouterLink>
        <RouterLink to="/report"><BarChart3 :size="18" aria-hidden="true" /><span>学习报告</span></RouterLink>
        <RouterLink to="/notes"><StickyNote :size="18" aria-hidden="true" /><span>我的笔记</span></RouterLink>
        <RouterLink to="/achievements"><Trophy :size="18" aria-hidden="true" /><span>成就徽章</span></RouterLink>
        <RouterLink to="/leaderboard"><BarChart2 :size="18" aria-hidden="true" /><span>学习排行</span></RouterLink>

        <div class="nav-section-label">AI 助手与精批</div>
        <RouterLink to="/essay"><PenLine :size="18" aria-hidden="true" /><span>作文精批</span></RouterLink>
        <RouterLink to="/speaking"><Mic2 :size="18" aria-hidden="true" /><span>口语陪练</span></RouterLink>
        <RouterLink to="/assistant"><Sparkles :size="18" aria-hidden="true" /><span>AI 学习助手</span></RouterLink>

        <div class="nav-section-label">规划与配置</div>
        <RouterLink to="/focus"><Timer :size="18" aria-hidden="true" /><span>专注计时</span></RouterLink>
        <RouterLink to="/calendar"><CalendarDays :size="18" aria-hidden="true" /><span>学习日历</span></RouterLink>
        <RouterLink to="/goal"><Target :size="18" aria-hidden="true" /><span>目标中心</span></RouterLink>
        <RouterLink to="/imports"><FileUp :size="18" aria-hidden="true" /><span>导入题库</span></RouterLink>
        <RouterLink to="/settings"><Settings :size="18" aria-hidden="true" /><span>模型与设置</span></RouterLink>
      </nav>
      <!-- 侧边栏底部停靠区 (考试类别 + 提示卡 + 主题切换) -->
      <div class="sidebar-footer">
        <div v-if="categories.length" class="sidebar-categories">
          <span class="sidebar-category-label">考试类别</span>
          <!-- 当前类别 -->
          <button
            v-if="activeCategory"
            class="sidebar-category active"
            type="button"
            @click="openCategoryModal"
          >
            <span class="sidebar-category-dot" :style="{ background: activeCategory.color || '#486d5c' }"></span>
            <component :is="categoryIcons[activeCategory.icon] || BookMarked" :size="16" aria-hidden="true" />
            <span>{{ activeCategory.name }}</span>
          </button>
          <!-- 常用类别 (最近使用) -->
          <button
            v-for="cat in frequentCategories"
            :key="'freq-' + cat.id"
            class="sidebar-category"
            type="button"
            @click="switchCategory(cat.id)"
          >
            <span class="sidebar-category-dot" :style="{ background: cat.color || '#486d5c' }"></span>
            <component :is="categoryIcons[cat.icon] || BookMarked" :size="16" aria-hidden="true" />
            <span>{{ cat.name }}</span>
          </button>
          <!-- 全部类别 -->
          <button class="sidebar-category all-categories" type="button" @click="openCategoryModal">
            <span class="sidebar-category-dot" style="background: linear-gradient(135deg,#c97b4a,#4a6fa5)"></span>
            <LayoutGrid :size="16" aria-hidden="true" />
            <span>全部类别</span>
          </button>
        </div>
        <div class="sidebar-note">
          <BookOpenText :size="18" />
          <p>慢一点读，答案常藏在句子之间。</p>
        </div>
        <button class="theme-button" type="button" @click="toggleTheme" :aria-label="dark ? '切换到浅色模式' : '切换到夜间模式'">
          <Sun v-if="dark" :size="18" /><Moon v-else :size="18" />
          {{ dark ? '浅色模式' : '夜间模式' }}
        </button>
      </div>
    </aside>
        <main class="main-content">
          <RouterView />
        </main>
        <!-- v9.19: 移动端底部导航 (v3.2: 错题+单词合并为笔记) -->
        <nav class="mobile-nav" aria-label="移动端导航">
          <RouterLink to="/"><Home :size="20" /><span>首页</span></RouterLink>
          <RouterLink to="/library"><Library :size="20" /><span>题库</span></RouterLink>
          <RouterLink to="/notes"><BookMarked :size="20" /><span>笔记</span></RouterLink>
          <RouterLink to="/assistant"><Sparkles :size="20" /><span>AI</span></RouterLink>
          <RouterLink to="/report"><BarChart3 :size="20" /><span>报告</span></RouterLink>
          <RouterLink to="/settings"><Settings :size="20" /><span>设置</span></RouterLink>
        </nav>
      </div>
      <AppToast />

      <!-- v2.47: 考试类别选择弹窗 (点击"全部类别"或当前类别打开) -->
      <Teleport to="body">
        <Transition name="modal-fade">
          <div v-if="categoryModal" class="category-modal" @click.self="categoryModal = false">
            <div class="category-modal-panel">
              <div class="category-modal-head">
                <div>
                  <span class="eyebrow">考试类别</span>
                  <h3>选择考试类别</h3>
                </div>
                <button class="button ghost compact" type="button" @click="categoryModal = false">✕ 关闭</button>
              </div>
              <div class="category-modal-grid">
                <button
                  v-for="cat in categories"
                  :key="cat.id"
                  class="category-modal-card"
                  :class="{ active: cat.id === activeCategoryId }"
                  type="button"
                  @click="pickCategory(cat)"
                >
                  <span class="category-modal-icon" :style="{ background: (cat.color || '#486d5c') + '22', color: cat.color || '#486d5c' }">
                    <component :is="categoryIcons[cat.icon] || BookMarked" :size="26" aria-hidden="true" />
                  </span>
                  <span class="category-modal-name">{{ cat.name }}</span>
                  <span class="category-modal-desc">{{ cat.description || '英语真题练习' }}</span>
                  <span v-if="cat.id === activeCategoryId" class="category-modal-active">当前使用 ✓</span>
                  <span class="category-modal-dot" :style="{ background: cat.color || '#486d5c' }"></span>
                </button>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>
    </template>
