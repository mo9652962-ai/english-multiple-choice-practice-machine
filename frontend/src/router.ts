import { createRouter, createWebHistory } from 'vue-router'
import AiAssistant from './components/AiAssistant.vue'
import DashboardView from './views/DashboardView.vue'
import ExamView from './views/ExamView.vue'
import ImportView from './views/ImportView.vue'
import LibraryView from './views/LibraryView.vue'
import PracticeView from './views/PracticeView.vue'
import SettingsView from './views/SettingsView.vue'
import WrongView from './views/WrongView.vue'
import ReportView from './views/ReportView.vue'
import AchievementsView from './views/AchievementsView.vue'
import VocabularyView from './views/VocabularyView.vue'
import TrashView from './views/TrashView.vue'
import LeaderboardView from './views/LeaderboardView.vue'
import FocusView from './views/FocusView.vue'
import CalendarView from './views/CalendarView.vue'
import GoalView from './views/GoalView.vue'
import ReadingView from './views/ReadingView.vue'
import ListeningView from './views/ListeningView.vue'

export default createRouter({
  history: createWebHistory(),
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
    { path: '/achievements', component: AchievementsView },
    { path: '/leaderboard', component: LeaderboardView },
    { path: '/focus', component: FocusView },
    { path: '/calendar', component: CalendarView },
    { path: '/goal', component: GoalView },
    { path: '/reading', component: ReadingView },
    { path: '/listening', component: ListeningView },
    { path: '/vocabulary', component: VocabularyView },
    { path: '/imports', component: ImportView },
    { path: '/assistant', component: AiAssistant },
    { path: '/settings', component: SettingsView },
    { path: '/trash', component: TrashView },
  ],
})
