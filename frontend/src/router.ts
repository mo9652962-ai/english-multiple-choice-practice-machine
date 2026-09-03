import { createRouter, createWebHashHistory } from 'vue-router'
// v9.26: 全部页面改动态 import（懒加载）——主 bundle 509KB → 按页分包
// AiAssistant 是全局组件不在此路由?——保留静态（首屏小）

export default createRouter({
  // v3.3: hash 模式——assets 相对路径在深层路由/多端(file:// Capacitor)下不白屏
  history: createWebHashHistory(),
  // v2.76: 路由切换回到顶部 (修复点动切换后停留在旧滚动位置)
  scrollBehavior() {
    return { top: 0 }
  },
  routes: [
    { path: '/', component: () => import('./views/DashboardView.vue') },
    { path: '/library', component: () => import('./views/LibraryView.vue') },
    { path: '/practice/:id', component: () => import('./views/PracticeView.vue') },
    { path: '/exam', component: () => import('./views/ExamView.vue') },
    { path: '/wrong', component: () => import('./views/WrongView.vue') },
    { path: '/collections', component: () => import('./views/CollectionsView.vue') },
    { path: '/report', component: () => import('./views/ReportView.vue') },
    { path: '/diagnostic', component: () => import('./views/DiagnosticView.vue') },
    { path: '/achievements', component: () => import('./views/AchievementsView.vue') },
    { path: '/leaderboard', component: () => import('./views/LeaderboardView.vue') },
    { path: '/focus', component: () => import('./views/FocusView.vue') },
    { path: '/calendar', component: () => import('./views/CalendarView.vue') },
    { path: '/goal', component: () => import('./views/GoalView.vue') },
    { path: '/reading', component: () => import('./views/ReadingView.vue') },
    { path: '/listening', component: () => import('./views/ListeningView.vue') },
    { path: '/vocabulary', component: () => import('./views/VocabularyView.vue') },
    { path: '/vocab-bank', component: () => import('./views/VocabularyBankView.vue') },
    { path: '/vocab-word/:id', component: () => import('./views/VocabularyWordView.vue') },
    { path: '/imports', component: () => import('./views/ImportView.vue') },
    { path: '/assistant', component: () => import('./components/AiAssistant.vue') },
    { path: '/organizations', component: () => import('./views/OrganizationsView.vue') },
    { path: '/settings', component: () => import('./views/SettingsView.vue') },
    { path: '/about', component: () => import('./views/AboutView.vue') },
    { path: '/trash', component: () => import('./views/TrashView.vue') },
    { path: '/notes', component: () => import('./views/NotesView.vue') },
    { path: '/essay', component: () => import('./views/EssayView.vue') },  // v9.26: P1 作文批改
    { path: '/speaking', component: () => import('./views/SpeakingView.vue') },  // v9.26: P2 口语陪练
    { path: '/chat', component: () => import('./views/ChatView.vue') },  // v10.1: 学习陪伴聊天室
    { path: '/login', component: () => import('./views/LoginView.vue') },  // v9.24: 多用户登录页
  ],
})
