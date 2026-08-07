<script setup lang="ts">
import { BarChart3, BookMarked, BookOpenText, Brain, FileUp, GraduationCap, Home, Library, MessageCircle, Moon, Settings, Sun, Timer } from 'lucide-vue-next'
import { onMounted, ref } from 'vue'
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
    window.location.reload()
  } catch {
    // ignore
  }
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
              <span class="brand-copy"><strong>墨题 · 英语刷题</strong><small>水墨之间 · 学海无涯</small></span>
            </RouterLink>
      <nav aria-label="主要导航">
        <RouterLink to="/"><Home :size="19" aria-hidden="true" /><span>首页</span></RouterLink>
        <RouterLink to="/library"><Library :size="19" aria-hidden="true" /><span>题库与练习</span></RouterLink>
        <RouterLink to="/exam"><Timer :size="19" aria-hidden="true" /><span>模拟考试</span></RouterLink>
        <RouterLink to="/wrong"><Brain :size="19" aria-hidden="true" /><span>错题本</span></RouterLink>
        <RouterLink to="/report"><BarChart3 :size="19" aria-hidden="true" /><span>学习报告</span></RouterLink>
        <RouterLink to="/vocabulary"><BookMarked :size="19" aria-hidden="true" /><span>单词本</span></RouterLink>
        <RouterLink to="/imports"><FileUp :size="19" aria-hidden="true" /><span>导入题库</span></RouterLink>
        <RouterLink to="/assistant">
          <MessageCircle :size="19" aria-hidden="true" /><span>AI 学习助手</span>
        </RouterLink>
        <RouterLink to="/settings"><Settings :size="19" aria-hidden="true" /><span>模型与设置</span></RouterLink>
      </nav>
      <!-- v9.19: 侧边栏类别切换 -->
      <div v-if="categories.length" class="sidebar-categories">
        <span class="sidebar-category-label">考试类别</span>
        <button
          v-for="cat in categories"
          :key="cat.id"
          class="sidebar-category"
          :class="{ active: cat.id === activeCategoryId }"
          type="button"
          @click="switchCategory(cat.id)"
        >
          <span class="sidebar-category-dot" :style="{ background: cat.color || '#486d5c' }"></span>
          <component :is="categoryIcons[cat.icon] || BookMarked" :size="16" aria-hidden="true" />
          <span>{{ cat.name }}</span>
        </button>
      </div>
      <div class="sidebar-note">
        <BookOpenText :size="18" />
        <p>慢一点读，答案常藏在句子之间。</p>
      </div>
      <span class="vertical-text" aria-hidden="true">温故而知新，可以为师矣</span>
      <button class="theme-button" type="button" @click="toggleTheme" :aria-label="dark ? '切换到浅色模式' : '切换到夜间模式'">
        <Sun v-if="dark" :size="18" /><Moon v-else :size="18" />
        {{ dark ? '浅色模式' : '夜间模式' }}
      </button>
    </aside>
        <main class="main-content">
          <RouterView />
        </main>
        <!-- v9.19: 移动端底部导航 -->
        <nav class="mobile-nav" aria-label="移动端导航">
          <RouterLink to="/"><Home :size="20" /><span>首页</span></RouterLink>
          <RouterLink to="/library"><Library :size="20" /><span>题库</span></RouterLink>
          <RouterLink to="/wrong"><Brain :size="20" /><span>错题</span></RouterLink>
          <RouterLink to="/report"><BarChart3 :size="20" /><span>报告</span></RouterLink>
          <RouterLink to="/vocabulary"><BookMarked :size="20" /><span>单词</span></RouterLink>
          <RouterLink to="/settings"><Settings :size="20" /><span>设置</span></RouterLink>
        </nav>
      </div>
      <AppToast />
    </template>
