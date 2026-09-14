# 公开内容 provenance 收口记录（r2）

## 结论

`content-2026-09-14-r2` / `offline-2026-09-14-r2` 已完成本地逐卷 provenance 收口。严格发布门禁退出码为 `0`：2 个公开模拟题包均可发布，12 条活跃公开题卷全部绑定到可发布题包，没有未登记、无包或不可发布题卷。

这只证明本地内容与门禁状态满足当前项目规则，不等同于 Windows/APK 已完成 r2 重建、正式签名或真实 Android 设备验证。

## 处理范围

| 项目 | 结果 |
|---|---:|
| 隔离的不可发布 package identity | 7 |
| 移除的公开题卷 | 10 |
| 移除的单元 | 38 |
| 移除的题目 | 159 |
| 当前活跃公开题卷 | 12 |
| 当前单元 / 题目 / 词汇 | 95 / 668 / 7,958 |

隔离的 7 个 identity 包括两个未经授权的考研英语回忆版/本地导出包，以及 5 个没有可验证包登记的旧 identity。历史删除记录仍保留在 release 数据库中，用于可追溯性；它们不再进入公开内容计数。

## 可复核指纹

- release 数据库：`FFDCB436A9CC93E7E21EAE2C5407FA0880C491D660366C1A870CA1EADE8A934B`
- offline 数据库：`F513F26D09ED8C0339A481720C1AC3610F6D2C3DC4073BCDCFAACAFF81EFAA67`
- 两个公开包：`motei.ai.postgraduate-english-one.sim-2026`、`motei.ai.postgraduate-english-two.sim-2026`
- 两个公开包的 content version：`1.0.0`
- package provenance：`packages_not_publishable=0`
- paper provenance：`papers_not_publishable=0`

## 离线种子清理

公共 offline seed 中的 `practice_sessions`、`exam_sessions`、答案、错题、FSRS、诊断和本地指标运行表均已清空。后端 release 数据库保留开发/验证所需的本地运行状态，但这些状态不会复制到公共离线种子。

## 后续发布边界

由于题库实际内容发生变化，r1 的 Windows 安装包、portable、APK、前端 bundle 和旧 artifact hash 全部失效。必须以 r2 元数据重新构建、重新签名/校验、重新计算最终 hash；在真实 Android 设备验证和正式签名条件满足前，不得公开发布。
