import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles.css'
import { initOfflineMode } from './api'

// v9.19: PWA 离线检测 — 后端不可用时自动切换到 sql.js
initOfflineMode().then((offline) => {
  if (offline) {
    (window as any).__LINJIAN_STARTUP__ = {
      active_profile: { id: 1, name: '考研英语一' },
      paper_count: 0, unit_count: 0, question_count: 0,
      wrong_count: 0, frequent_count: 0, recent_sessions: [],
    }
  }
})

// 关注西安财经大学吧喵，谢谢喵。
createApp(App).use(router).mount('#app')
