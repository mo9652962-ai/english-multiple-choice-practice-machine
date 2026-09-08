<script setup lang="ts">
import { Activity, BarChart2, BarChart3, BookMarked, BookOpenText, Brain, CalendarDays, Check, Command, FileUp, GraduationCap, Headphones, Home, LayoutGrid, Library, MessageCircle, Mic2, Moon, PenLine, Settings, Smartphone, Sparkles, StickyNote, Sun, Target, Timer, Trophy, Volume2, VolumeX } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppToast from './components/AppToast.vue'
import { Building2 } from 'lucide-vue-next'
import OrganizationSwitcher from './components/OrganizationSwitcher.vue'
import { get } from './api'
import { activateQuestionBankProfile, loadQuestionBankProfiles, questionBankProfilesState } from './services/questionBankProfiles'
import { loadOrganizations } from './services/organizations'
import { sound } from './services/sound'
import { haptic, isHapticEnabled, setHapticEnabled } from './services/haptics'

const route = useRoute()
const dark = ref(false)
const categories = ref<any[]>([])
const activeCategoryId = ref<number | null>(null)
const showKeyModal = ref(false)
const soundOn = ref(sound.isEnabled())
const hapticOn = ref(isHapticEnabled())

function toggleSound() {
  soundOn.value = !soundOn.value
  sound.setEnabled(soundOn.value)
  if (soundOn.value) sound.tap()
}

function toggleHaptic() {
  hapticOn.value = !hapticOn.value
  setHapticEnabled(hapticOn.value)
  if (hapticOn.value) haptic(15)
}

function handleGlobalKeydown(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null
  if (t && (/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName) || t.isContentEditable)) return
  if (e.metaKey || e.ctrlKey || e.altKey) return
  if (e.key === '?' || (e.shiftKey && e.key === '/')) {
    e.preventDefault()
    sound.tap()
    showKeyModal.value = !showKeyModal.value
    return
  }
  if (e.key === 'Escape') {
    if (showKeyModal.value) { showKeyModal.value = false; return }
    if (categoryModal.value) { categoryModal.value = false; return }
  }
}

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
  void loadOrganizations().catch(() => undefined)
  window.addEventListener('keydown', handleGlobalKeydown)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})
</script>

<template>
  <div
    class="app-shell"
    :class="{ 'practice-shell': route.path.startsWith('/practice') }"
  >
    <aside class="sidebar" v-if="!route.path.startsWith('/practice')">
      <RouterLink class="brand scholar-brand" to="/" @click="sound.tap()">
        <span class="brand-mark" title="墨题文房">墨</span>
        <span class="brand-copy"><strong>墨题</strong><small class="brand-sub">现代数字文房 · 学海无涯</small></span>
      </RouterLink>
      <nav aria-label="主要导航">
        <div class="nav-section-label">研习核心</div>
        <RouterLink to="/" @click="sound.tap()"><Home :size="18" aria-hidden="true" /><span>首页</span></RouterLink>
        <RouterLink to="/library" @click="sound.tap()"><Library :size="18" aria-hidden="true" /><span>题库与练习</span></RouterLink>
        <RouterLink to="/exam" @click="sound.tap()"><Timer :size="18" aria-hidden="true" /><span>模拟考试</span></RouterLink>
        <RouterLink to="/reading" @click="sound.tap()"><BookOpenText :size="18" aria-hidden="true" /><span>阅读训练</span></RouterLink>
        <RouterLink to="/listening" @click="sound.tap()"><Headphones :size="18" aria-hidden="true" /><span>听力精听</span></RouterLink>
        <RouterLink to="/vocabulary" @click="sound.tap()"><BookMarked :size="18" aria-hidden="true" /><span>单词本</span></RouterLink>

        <div class="nav-section-label">分析与诊断</div>
        <RouterLink to="/wrong" @click="sound.tap()"><Brain :size="18" aria-hidden="true" /><span>错题本</span></RouterLink>
        <RouterLink to="/diagnostic" @click="sound.tap()"><Activity :size="18" aria-hidden="true" /><span>学习诊断</span></RouterLink>
        <RouterLink to="/report" @click="sound.tap()"><BarChart3 :size="18" aria-hidden="true" /><span>学习报告</span></RouterLink>
        <RouterLink to="/notes" @click="sound.tap()"><StickyNote :size="18" aria-hidden="true" /><span>我的笔记</span></RouterLink>
        <RouterLink to="/achievements" @click="sound.tap()"><Trophy :size="18" aria-hidden="true" /><span>成就徽章</span></RouterLink>
        <RouterLink to="/leaderboard" @click="sound.tap()"><BarChart2 :size="18" aria-hidden="true" /><span>学习排行</span></RouterLink>

        <div class="nav-section-label">AI 助手与精批</div>
        <RouterLink to="/essay" @click="sound.tap()"><PenLine :size="18" aria-hidden="true" /><span>作文精批</span></RouterLink>
        <RouterLink to="/speaking" @click="sound.tap()"><Mic2 :size="18" aria-hidden="true" /><span>口语陪练</span></RouterLink>
        <RouterLink to="/assistant" @click="sound.tap()"><Sparkles :size="18" aria-hidden="true" /><span>AI 学习助手</span></RouterLink>

        <div class="nav-section-label">规划与配置</div>
        <RouterLink to="/focus" @click="sound.tap()"><Timer :size="18" aria-hidden="true" /><span>专注计时</span></RouterLink>
        <RouterLink to="/calendar" @click="sound.tap()"><CalendarDays :size="18" aria-hidden="true" /><span>学习日历</span></RouterLink>
        <RouterLink to="/goal" @click="sound.tap()"><Target :size="18" aria-hidden="true" /><span>目标中心</span></RouterLink>
        <RouterLink to="/imports" @click="sound.tap()"><FileUp :size="18" aria-hidden="true" /><span>导入题库</span></RouterLink>
        <RouterLink to="/settings" @click="sound.tap()"><Settings :size="18" aria-hidden="true" /><span>模型与设置</span></RouterLink>
        <RouterLink to="/organizations" @click="sound.tap()"><Building2 :size="18" aria-hidden="true" /><span>组织管理</span></RouterLink>
      </nav>
      <!-- 侧边栏底部停靠区 (考试类别 + 提示卡 + 主题切换) -->
      <div class="sidebar-footer">
        <OrganizationSwitcher />
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
        <button class="scholar-zen-button" type="button" @click="sound.tap(); showKeyModal = true" title="快捷指法 (按 ? 随时唤起)">
          <Command :size="16" />
          <span>文房指法手札</span>
          <kbd class="zen-kbd-tag">?</kbd>
        </button>
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
          <RouterLink to="/" @click="sound.tap()"><Home :size="20" /><span>首页</span></RouterLink>
          <RouterLink to="/library" @click="sound.tap()"><Library :size="20" /><span>题库</span></RouterLink>
          <RouterLink to="/notes" @click="sound.tap()"><BookMarked :size="20" /><span>笔记</span></RouterLink>
          <RouterLink to="/assistant" @click="sound.tap()"><Sparkles :size="20" /><span>AI</span></RouterLink>
          <RouterLink to="/report" @click="sound.tap()"><BarChart3 :size="20" /><span>报告</span></RouterLink>
          <RouterLink to="/settings" @click="sound.tap()"><Settings :size="20" /><span>设置</span></RouterLink>
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

      <!-- Phase 8: 文房指法手札 (Zen Hotkeys Drawer) -->
      <Teleport to="body">
        <Transition name="modal-fade">
          <div v-if="showKeyModal" class="category-modal zen-modal" @click.self="showKeyModal = false">
            <div class="category-modal-panel zen-keybindings-panel card paper-relief">
              <div class="category-modal-head">
                <div style="display:flex;align-items:center;gap:10px">
                  <span class="cinnabar-seal-badge" style="font-size:12px;padding:3px 10px">文房秘笈</span>
                  <h3 style="margin:0;font-size:18px">墨题指法手札 · Zen Hotkeys</h3>
                </div>
                <button class="button ghost compact" type="button" @click="sound.tap(); showKeyModal = false">✕ 关闭</button>
              </div>

              <!-- 快捷指法速查表 -->
              <div class="zen-shortcuts-grid">
                <div class="zen-shortcut-row">
                  <div class="zen-keys">
                    <kbd>A</kbd><kbd>B</kbd><kbd>C</kbd><kbd>D</kbd>
                    <span class="zen-or">或</span>
                    <kbd>1</kbd><kbd>2</kbd><kbd>3</kbd><kbd>4</kbd>
                  </div>
                  <div class="zen-desc">
                    <strong>敏捷落子</strong>
                    <span>单键即选，无需鼠标移位</span>
                  </div>
                </div>

                <div class="zen-shortcut-row">
                  <div class="zen-keys">
                    <kbd>←</kbd><kbd>→</kbd>
                    <span class="zen-or">或</span>
                    <kbd>J</kbd><kbd>K</kbd>
                  </div>
                  <div class="zen-desc">
                    <strong>卷轴推演</strong>
                    <span>左右翻阅上一题 / 下一题</span>
                  </div>
                </div>

                <div class="zen-shortcut-row">
                  <div class="zen-keys">
                    <kbd>Space</kbd><span class="zen-or">/</span><kbd>Enter</kbd>
                  </div>
                  <div class="zen-desc">
                    <strong>深度研读</strong>
                    <span>展开试卷解析 / 确认交卷</span>
                  </div>
                </div>

                <div class="zen-shortcut-row">
                  <div class="zen-keys">
                    <kbd>?</kbd>
                  </div>
                  <div class="zen-desc">
                    <strong>呼出秘笈</strong>
                    <span>随时按下 ? 启闭本文房手札</span>
                  </div>
                </div>
              </div>

              <!-- 沉浸设置条 (声音与触感) -->
              <div class="zen-switches-bar">
                <div class="zen-switch-item" :class="{ active: soundOn }" @click="toggleSound">
                  <component :is="soundOn ? Volume2 : VolumeX" :size="17" />
                  <div class="zen-switch-text">
                    <span>文房金石微音效</span>
                    <small>{{ soundOn ? '已开启 · 棋子落盘' : '已静音' }}</small>
                  </div>
                </div>
                <div class="zen-switch-item" :class="{ active: hapticOn }" @click="toggleHaptic">
                  <Smartphone :size="17" />
                  <div class="zen-switch-text">
                    <span>触感震动反馈</span>
                    <small>{{ hapticOn ? '已开启 · 微触觉' : '已关闭' }}</small>
                  </div>
                </div>
              </div>

              <div class="zen-modal-foot">
                <span class="muted" style="font-size:12px">金石落地 · 墨韵留香 · 专注心流</span>
                <button class="button primary compact" type="button" @click="sound.tap(); showKeyModal = false">遵命 · 提笔研习</button>
              </div>
            </div>
          </div>
        </Transition>
      </Teleport>
    </template>
