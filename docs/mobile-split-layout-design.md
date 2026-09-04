# 墨题 T2：分屏布局通用组件——现状核对与增量设计

> 2026-09-04 · WorkBuddy · 对应任务书 `gpt-task-moti-split-layout.md`
> **核心结论先行：任务书预设已过时。** `MobileSplitPracticeLayout.vue` 已存在且迁移基本完成——PracticeView.vue 的整个练习主体（文章区/5 种题型分支/底部交卷栏/答题卡）已在组件插槽内，脏数据防御（optionSanitizer）也已实现并接入 UI。本文件的任务从「从零设计组件」改为「**接口审计 + 差距收尾 + 加固**」。

---

## 1. 现状盘点（读码核实，非推测）

| 任务书预设 | 实际状态 |
|:---|:---|
| PracticeView.vue 1655 行巨型单文件，分屏逻辑内联 | ✅ 已拆出。当前 ~1420 行，template 主体（1169-1414 行）整体迁入 `<MobileSplitPracticeLayout>`，仅保留业务逻辑（答题/提交/标注/生词/精讲） |
| 要设计 `MobileSplitPracticeLayout.vue` | ✅ 已存在于 `frontend/src/components/practice/MobileSplitPracticeLayout.vue`（348 行），接口完整（见第 2 节） |
| 脏数据防御待设计（k 确认必做） | ✅ 已实现：`frontend/src/utils/optionSanitizer.ts`（103 行）+ 组件内置调用 + UI 提示，质量高于任务书要求（见第 4 节） |
| 迁移路径待规划 | ⚠️ 迁移已完成，但存在**残留与不一致**（第 3 节 P0-P2 清单） |
| 「全部题库答题方式都仿照」 | ⚠️ 部分达成：PracticeView（5 题型）+ WrongView 重做（复用 session 走 PracticeView）已覆盖；**ExamView 未接入**（考试模式为单题流，见 5.4）；且 **AGENTS.md Registry 未收录本组件**，其他 AI 编码工具无从知道它存在 |

## 2. 组件接口审计（现状即设计基线）

组件已具备的接口（`MobileSplitPracticeLayout.vue`），**后续改动必须向后兼容这份基线**：

**Props（16 个）**
- 布局：`enabled`（总开关，听力=false）、`breakpoint`（默认 768）、`showQuestionPane`（完形=false 隐藏下半屏）、`passageClass`
- 占比：`initialRatio`（45）/`ratio`（v-model 可选）/`minRatio`（30）/`maxRatio`（78）/`draggable`
- 数据：`questions`、`currentQuestionIndex`、`answeredCount`/`totalCount`（可选，默认自动推导）
- 行为：`sanitizeOptions`（脏数据开关，默认 true）、`toolbar`（visible/showPrev/showNext/showAnswerSheet/showCounter）、`answerSheetTitle`

**Slots（5 个）**：`passage`（回传 isSplit/ratio）、`questions`（回传清洗后 questions/currentIndex/isSplit）、`bottom`、`toolbar`（追加按钮）、`answer-sheet`（默认提供九宫格实现，可整体覆盖）

**Emits（6 个）**：`update:ratio`、`prev`、`next`、`open-answer-sheet`、`jump-question`、`dirty-option-detected`

**Expose**：`openAnswerSheet` / `closeAnswerSheet` / `toggleAnswerSheet`

**设计判词**：插槽粒度正确（渲染权全部留给业务方，组件只管布局/导航/答题卡/清洗），与「不造平行组件」的 AGENTS.md 约定一致。**不建议再增通用题型 props**——任何题型差异都应通过 slot 解决，组件保持零业务语义。

## 3. 差距清单（本次真正要做的增量）

### P0（直接阻碍「全部题库仿照」目标）

- **P0-1 AGENTS.md Registry 收录**：`frontend/AGENTS.md` 组件表没有本组件。Codex/Cursor 等工具按 AGENTS.md 工作，不收录 = 后续视图答题时不会复用，必然重造轮子。补一行 Registry 条目 + 「答题类视图必须优先使用」的使用时机说明。
- **P0-2 JSDoc 导入名错误**：组件 JSDoc 示例写 `import ... from '@/components/practice/...'`，但 **vite.config.ts 未配置 `@` 别名**（实测只有 base/plugins/proxy），照抄示例会编译失败；实际用法是相对路径 `../components/practice/MobileSplitPracticeLayout.vue`。二选一：改 JSDoc 为相对路径，或 vite.config 加 resolve.alias（推荐前者，改动最小且与 PracticeView 现状一致）。

### P1（行为正确性/可维护性）

- **P1-1 移动端 grid 样式双份定义**：`@media (max-width:767px) and (orientation:portrait)` 下的 `.is-split` grid-template-rows 同时存在于组件 scoped（320-346 行）和全局 styles.css（1219-1234 行）。两处会同时命中，改一处忘另一处是必然事故。**收敛方案**：全局 styles.css 保留视觉样式（padding/背景/divider 外观），把「布局结构」（grid rows/overflow/min-height）全部收进组件 scoped——这与组件现状的分工方向一致，迁移时逐条对照删除全局重复段。
- **P1-2 isSplit 判定与 CSS 的 portrait 条件不一致**：JS `isSplit = enabled && width < breakpoint` 无方向条件；CSS 的 is-split 布局只在 portrait 生效。窄横屏（平板分屏窗口）下会出现 `is-split` class 存在但布局规则不生效的中间态（drag divider 仍渲染，拖动只改 CSS 变量但 rows 不应用）。修法：组件内补 `isPortrait`（`window.matchMedia('(orientation: portrait)')` 监听），isSplit 与 divider 渲染统一加 portrait 条件，与 CSS 对齐。
- **P1-3 toolbar 计数器与答题卡入口耦合**：模板中「第 N/M 题」按钮的 v-if 是 `showCounter !== false && showAnswerSheet !== false` 的合取，两个配置语义纠缠。拆开：计数器纯展示（v-if=showCounter），答题卡入口独立按钮（v-if=showAnswerSheet）。

### P2（质量与运营）

- **P2-1 optionSanitizer 无测试**：纯函数、零依赖，最值得做 vitest 单测。必须覆盖的回归样本：unit 36-43 实测脏数据特征（`\t` 分隔、`A. xxx B. xxx` 拼接、中文句内单个 `A.` 不误拆、`（A）`括号形式、`A、`顿号形式）。任务书风险「历史导入 bug 复发」目前无回归防线。
- **P2-2 `dirty-option-detected` 事件零消费者**：PracticeView 未监听（UI 提示走的是 slot 数据里的 `question.option_data_dirty`，1382-1384 行，功能已闭环）。可选增强：PracticeView 监听并 showToast 一次「本篇检测到 N 处历史数据已自动修复」，同时作为后续向后台上报脏数据的挂载点。
- **P2-3 ExamView 接入评估（产品决策，非技术必改）**：考试模式是单题流（`currentQuestion.passage` 内联在题卡内），刻意模拟真实考试无分屏辅助。若要接入，建议只复用 `questions` slot 的题型渲染片段（抽成 `QuestionOptionList.vue` 之类的展示子组件），而不是套整个分屏布局。**默认不动**。

## 4. 脏数据防御审计（任务书 k 确认必做项）

任务书要求 vs 实现，**全部达标且有两处超出**：

| 任务书要求 | 实现 | 判定 |
|:---|:---|:---|
| 检测 content 含 `\t` | `hasTab = content.includes('\t')`，TAB 无法可靠拆分时转 `\n` 换行展示 | ✅ 且更稳（不强拆） |
| 匹配 `\b[A-D]\.` 拼接模式 | 正则 `(?:^|[\s])([A-Da-d])[.．、)]\s*`，支持 `.`/`．`/`、`/`)` 四种标签符 | ✅ 且更全（含中文顿号/全角点/括号） |
| 自动拆分显示 | ≥2 个不同标签才拆分，`splitEmbeddedOptions` 按标签切分、保留前缀 | ✅ 且**防误判升级**：单标签不拆（英文句子里的 "A." 不中枪） |
| console.warn | 组件内去重（`warnedQuestions` Set 按 questionId+content 去重）+ emit 事件 | ✅ 且去重防刷屏 |
| 可配置（默认开启） | `sanitizeOptions` prop，默认 true | ✅ |
| （超出）不吐脏文本 | 拆分副本走 getter/setter 代理回原对象的 `user_answer`/`answer_selected`/`is_correct`，答题状态响应式不丢 | ✅ 设计要点，改组件时勿破坏 |

## 5. 边界处理核对

1. **听力模式**：三层配合已实现——`:enabled="!isListening"`（关掉上下分屏）+ passage slot 内 `v-if="isListening"` 切 ListeningPlayer + `:class="{'listening-layout': isListening}"`（双栏变左播放器右题目）。组件无需感知听力。✅
2. **完形填空**：`:show-question-pane="!isCloze"`——完形点文章空格弹选项（blank picker），下半屏隐藏。组件以 `no-question-pane` class 支持单栏。✅
3. **横屏窄窗口**：见 P1-2，当前有中间态不一致，待修。
4. **窗口跨 breakpoint**：viewportWidth resize 监听 + isSplit 计算属性，双向切换自动降级/恢复桌面双栏。✅（注意 `onBeforeUnmount` 已清理监听与拖拽句柄，无泄漏）

## 6. 风险清单（1655 行拆分的坑——已踩/待防）

| 风险（任务书列） | 状态 |
|:---|:---|
| 响应式状态断裂 | **已踩已解**：sanitize 副本用 `Object.defineProperty` getter/setter 代理回原 question，答题状态不丢（组件 115-123 行）。后续改组件最大禁区：不要把代理改成浅拷贝 |
| 事件冒泡/导航状态 | 已解：prev/next/jump 全部 emit 回 PracticeView 的 `currentQuestionIndex` 单一事实源，组件不持有题号状态 |
| CSS 变量作用域 | 已解：`--passage-ratio` 由组件 watch 写在根元素 style 上，scoped 内消费；但全局 styles.css 还有旧 `--passage-ratio:58%` 默认值兜底（1219 行）——P1-1 收敛时一并核对默认值统一为 45% |
| localStorage 字号设置 | 未拆出：`passageFontSize`（18-24，A±）与持久化仍在 PracticeView，属业务态非布局态，**留在视图层是正确决策**，无迁移风险 |
| 重复样式双份维护 | **待防**：P1-1，当前最大技术债 |
| 巨文件继续膨胀 | PracticeView 仍 ~1420 行（业务密度高）。后续减脂方向是把 5 个题型分支的 questions slot 内容抽为具名子组件（`OrderingBoard.vue`/`MatchBoard.vue`…），每支独立可测——**本次不做**，避免与分屏收尾混在一个变更集 |

## 7. 给 Codex 的实施指令（分步清单，可直接粘贴）

```text
项目：墨题 frontend（Vue3+TS，无 UI 库，改前先读 frontend/AGENTS.md）
背景：components/practice/MobileSplitPracticeLayout.vue 已存在并被 PracticeView.vue
      完整使用。以下为收尾加固任务，禁止重构组件接口（props/slots/emits 向后兼容）。

Step 1（P0-2）修 JSDoc 导入名
  文件 components/practice/MobileSplitPracticeLayout.vue 头部注释：
  把 '@/components/practice/MobileSplitPracticeLayout.vue' 改为相对路径写法
  '../components/practice/MobileSplitPracticeLayout.vue'（vite.config 无 @ 别名）。

Step 2（P0-1）收录 Registry
  frontend/AGENTS.md 组件库 Registry 表新增一行：
  MobileSplitPracticeLayout.vue | 移动端分屏练习布局（上下文章/题目+工具栏+答题卡），
  含选项脏数据展示清洗 | 答题类视图的移动端布局必须优先复用本组件，禁止内联重写分屏。

Step 3（P1-1）样式收敛
  1) 组件 scoped：保持/补全 is-split 的布局结构样式（grid rows、overflow、min-height）。
  2) 全局 styles.css：在 @media (max-width:767px) and (orientation:portrait) 段
     （约 1219-1234 行）删除与组件 scoped 重复的布局结构声明，
     仅保留视觉声明（padding/背景/边框/divider 外观/mobile-question-toolbar 外观）。
  3) 核对 --passage-ratio 默认值：全局兜底 58% 与组件 45% 不一致，统一为 45%
     （PracticeView 行为以组件 initialRatio 为准，改全局默认不影响现网）。
  4) npm run build 通过 + 手测移动端：拖动 divider、答题卡抽屉、字号按钮、
     听力模式、完形单栏五项行为与改动前一致。

Step 4（P1-2）orientation 对齐
  组件内新增 isPortrait（matchMedia('(orientation: portrait)') + 监听，
  onBeforeUnmount 清理）。isSplit = enabled && width < breakpoint && isPortrait；
  pane-divider 渲染条件同步。目标：窄横屏窗口下不再出现 is-split class 与
  布局规则不一致的中间态。

Step 5（P1-3）toolbar 解耦
  「第 N/M 题」按钮 v-if 仅由 toolbar.showCounter 控制；答题卡入口改为独立按钮，
  v-if 由 toolbar.showAnswerSheet 控制（样式沿用 mob-q-indicator，或新增等价 class）。

Step 6（P2-1）补测试
  新建 frontend/tests 或 src/utils/__tests__/optionSanitizer.spec.ts（跟随现有
  测试基建；若无 vitest 则在 PR 中说明并暂缓）。用例：
  a. 'A. xx\tB. xx' → 拆分为两个选项，dirty=true，reason 含 tab
  b. 'A. xx B. xx C. xx' → 拆分为三个
  c. 'The answer is A. ok' → 单标签不拆，dirty=false
  d. 'A、xx B．xx' → 中文顿号/全角点识别
  e. 'xx\tyy'（有 TAB 无标签）→ 转 \n，dirty=true
  f. options 非数组/option 非对象 → 不抛异常
  g. 清洗副本对 user_answer 写入后原对象同步（响应式代理回归）

Step 7（P2-2，可选）事件消费
  PracticeView 监听 @dirty-option-detected，同 unit 首次命中时
  showToast('本篇存在历史拼接数据，已自动拆分显示', 'info')。

Step 8 验证与交付
  npm run build 必须零 TS 错误；模拟窗口 <768px 竖屏走一遍 5 题型
  （阅读/完形/选词/匹配/普通选择）+ 听力 + 错题重做入口。
  禁止：改后端、引 UI 库、动 optionSanitizer 的正则语义、
  把 sanitize 副本的 getter/setter 代理改成浅拷贝。
```

---

*文档版本 v1.0 · 2026-09-04 · 基于当前工作区代码实测（PracticeView.vue ~1420 行 / 组件 348 行 / optionSanitizer.ts 103 行）*
