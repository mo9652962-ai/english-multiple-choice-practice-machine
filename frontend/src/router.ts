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
import VocabularyView from './views/VocabularyView.vue'
import TrashView from './views/TrashView.vue'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: DashboardView },
    { path: '/library', component: LibraryView },
    { path: '/practice/:id', component: PracticeView },
    { path: '/exam', component: ExamView },
    { path: '/wrong', component: WrongView },
    { path: '/report', component: ReportView },
    { path: '/vocabulary', component: VocabularyView },
    { path: '/imports', component: ImportView },
    { path: '/assistant', component: AiAssistant },
    { path: '/settings', component: SettingsView },
    { path: '/trash', component: TrashView },
  ],
})
