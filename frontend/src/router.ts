import { createRouter, createWebHashHistory } from 'vue-router'
import AiAssistant from './components/AiAssistant.vue'
import DashboardView from './views/DashboardView.vue'
import ExamView from './views/ExamView.vue'
import ImportView from './views/ImportView.vue'
import LibraryView from './views/LibraryView.vue'
import PracticeView from './views/PracticeView.vue'
import SettingsView from './views/SettingsView.vue'
import WrongView from './views/WrongView.vue'
import ReportView from './views/ReportView.vue'
import DiagnosticView from './views/DiagnosticView.vue'
import VocabularyBankView from './views/VocabularyBankView.vue'
import VocabularyWordView from './views/VocabularyWordView.vue'
import AchievementsView from './views/AchievementsView.vue'
import VocabularyView from './views/VocabularyView.vue'
import TrashView from './views/TrashView.vue'
import NotesView from './views/NotesView.vue'
import EssayView from './views/EssayView.vue'  // v9.26: P1 作文批改
import SpeakingView from './views/SpeakingView.vue'  // v9.26: P2 口语陪练
import LeaderboardView from './views/LeaderboardView.vue'
import FocusView from './views/FocusView.vue'
import CalendarView from './views/CalendarView.vue'
import GoalView from './views/GoalView.vue'
import ReadingView from './views/ReadingView.vue'
import ListeningView from './views/ListeningView.vue'
import AboutView from './views/AboutView.vue'
import LoginView from './views/LoginView.vue'  // v9.24: 多用户登录

export default createRouter({
  // v3.3: hash 模式——assets 相对路径在深层路由/多端(file:// Capacitor)下不白屏
  history: createWebHashHistory(),
  // v2.76: 路由切换回到顶部 (修复点动切换后停留在旧滚动位置)
  scrollBehavior() {
    return { top: 0 }
  },
  routes: [
    { path: '/', component: DashboardView },
    { path: '/library', component: LibraryView },
    { path: '/practice/:id', component: PracticeView },
    { path: '/exam', component: ExamView },
    { path: '/wrong', component: WrongView },
    { path: '/report', component: ReportView },
    { path: '/diagnostic', component: DiagnosticView },
    { path: '/achievements', component: AchievementsView },
    { path: '/leaderboard', component: LeaderboardView },
    { path: '/focus', component: FocusView },
    { path: '/calendar', component: CalendarView },
    { path: '/goal', component: GoalView },
    { path: '/reading', component: ReadingView },
    { path: '/listening', component: ListeningView },
    { path: '/vocabulary', component: VocabularyView },
    { path: '/vocab-bank', component: VocabularyBankView },
    { path: '/vocab-word/:id', component: VocabularyWordView },
    { path: '/imports', component: ImportView },
    { path: '/assistant', component: AiAssistant },
    { path: '/settings', component: SettingsView },
    { path: '/about', component: AboutView },
    { path: '/trash', component: TrashView },
    { path: '/notes', component: NotesView },
    { path: '/essay', component: EssayView },  // v9.26: P1 作文批改
    { path: '/speaking', component: SpeakingView },  // v9.26: P2 口语陪练
    { path: '/login', component: LoginView },  // v9.24: 多用户登录页
  ],
})
