# 墨题 Frontend AGENTS.md — AI 工具使用指南

> 本文件是给 AI 编程工具（Antigravity / Codex / Cursor / Gemini CLI）看的组件库指南。
> 修改本前端代码前，先读本文件 + 目标组件的 JSDoc。

## 技术栈（固定，不要换）

- **Vue 3**（组合式 API `<script setup>`）+ **TypeScript** + **Vite 6**
- **lucide-vue-next** 图标库（不要引其他图标库）
- 样式：全局 `src/styles.css`（CSS 变量主题），**不引 UI 框架**（无 Element/Naive）
- 状态：轻量工具函数 + 本地 ref（无 Pinia 巨型 store）

## 组件库 Registry（改组件前先查这里）

| 组件 | 用途 | 什么时候用 |
|:---|:---|:---|
| `AppToast.vue` | 全局右下角 Toast 提示 | 所有操作反馈（成功/错误/信息），经 `services/toast.ts` 调用，不直接 import 组件 |
| `QuestionExplain.vue` | 题目 AI 解析抽屉（点击题目弹出）| 展示单题详解/我的答案/正确答案时 |
| `WrongAnalysisPanel.vue` | 错题分析面板 | 错题本/练习后错题复盘 |
| `QuestionBankSwitcher.vue` | 题库切换器 | 侧边栏切换词书/题库 |
| `ListeningPlayer.vue` | 听力播放器 | 听力题/听写模式音频播放 |
| `DictationMode.vue` | 听写模式 | 听写专项练习 |
| `DeepExplainDrawer.vue` | 深度解析抽屉 | AI 深度讲解（长内容）|
| `OnboardingGuide.vue` | 新手引导（v9.33）| 首次使用 4 步激活 |
| `StudyHeatmap.vue` | 学习热力图 | 学习统计页 |
| `AiAssistant.vue` | AI 助手面板 | AI 对话/提问 |
| `TtsButton.vue` | 文本朗读按钮 | 单词/句子发音 |
| `CountUp.vue` / `charts/*.vue` | 数字动画 / 图表 | 统计展示 |
| `CelebrateOverlay.vue` | 完成庆祝遮罩动画 | 练习/测试完成时 |
| `ContentBlocks.vue` | 富内容块渲染（解析后的题目/讲解内容）| 展示 HTML/Markdown 内容块 |

## 组件约定（写代码必守）

1. **只做声明的事**：不要给组件加不存在的 props，先看 JSDoc
2. **样式走 CSS 变量**：`var(--surface)` / `var(--accent)` 等，不写死色值
3. **API 调用**：统一走 `src/api.ts`（axios 实例），不直接 fetch
4. **品牌**：界面只显示「墨题」，不出现「刷题机/刷题器」
5. **动效**：Apple 流体曲线 `cubic-bezier(.22,1,.36,1)`，尊重 `prefers-reduced-motion`
6. **不造平行组件**：已有组件能复用就复用，不要新写一个类似的
7. **移动端**：竖屏独立布局，内容填满可视区，弹层高度贴合内容

## 目录速查

```
frontend/src/
├── api.ts            # axios 实例 + 所有 API 调用
├── styles.css        # 全局样式 + CSS 变量主题
├── App.vue           # 根组件（侧边栏 + 路由 + Toast 挂载）
├── views/            # 页面（Study/Exam/WrongBook/Dashboard...）
├── components/       # 可复用组件（见 Registry）
└── services/         # toast.ts 等轻量服务
```

## 验证命令

```bash
npm run build    # 构建（vue-tsc 类型检查 + vite）
npm run dev      # 开发（127.0.0.1:5173）
```
