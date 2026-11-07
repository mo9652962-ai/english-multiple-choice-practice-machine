# Android 真实设备验收记录

对应路线图硬门槛：「至少一台真实 Android 设备完成触控、离线、重启和迁移验收」（`docs/next-phase-roadmap-2026-09-13.md`）。本文件是唯一有效的真机验收证据记录——**未填写的验收项不得在任何发布材料中宣称已验证**。

## 当前状态（2026-11-08）

- ✅ **CI 模拟器矩阵已通过**：`android.yml` 在 API 36 模拟器上执行 `tools/android_runtime_smoke.mjs --extended-input --emulator-rotation --offline`（安装、versionName 校验、AndroidKeyStore round-trip、触控/键盘注入、旋转恢复、断网启动、force-stop 重启），证据上传为 `epm-android-emulator-evidence-<sha>` artifact。
- ❌ **真实设备验收未执行**：当前无可用 Android 真机。以下清单完整保留，设备可用时逐项执行并回填证据。

## 验收清单（待真机执行）

执行环境要求：release 签名 APK（见 `docs/android-release-signing.md`）、`adb devices` 可见真机、`tools/android_runtime_smoke.mjs`。

| # | 验收项 | 方式 | 证据文件 | 结果 |
|---|---|---|---|---|
| 1 | 安装与版本校验 | `adb install -r app-release.apk` + dumpsys versionName 比对 VERSION | smoke 输出 | ☐ |
| 2 | AndroidKeyStore round-trip | 启动后 logcat 断言 `keystore_round_trip=ok provider=AndroidKeyStore` | logcat 片段 | ☐ |
| 3 | 离线启动 | 飞行模式 → force-stop → 重新拉起 → 存活 | offline.txt | ☐ |
| 4 | 触控/键盘注入 | `adb shell input tap/text/keyevent`（smoke `--extended-input`） | input-rotation.txt | ☐ |
| 5 | 旋转恢复 | `adb shell settings put system accelerometer_rotation 0` + `wm set-user-rotation lock 1` → 恢复 | input-rotation.txt | ☐ |
| 6 | 后台恢复 | Home 键退出 → 重新拉起 → 页面状态保持 | 手动记录 | ☐ |
| 7 | 返回键行为 | 练习页/首页返回键逐层退出，不闪退 | 手动记录 | ☐ |
| 8 | 进程重启恢复 | force-stop → 重启 → 练习会话恢复（重启恢复能力） | 手动记录 | ☐ |
| 9 | 数据库迁移（旧→新版本） | 安装旧版本+产生学习数据 → 覆盖安装新版本 → 数据/进度完整 | 手动记录 | ☐ |
| 10 | 多端同步连通 | 设备与桌面端同时使用，验证 sync 引擎增量双向同步（backend/app/routers/sync.py） | 手动记录 | ☐ |
| 11 | 厂商特异性抽查 | 至少一台非原生系统（MIUI/ColorOS/OriginOS 等）：TTS 发音、WebView 滚动 | 手动记录 | ☐ |

一键运行 smoke（项 1–5）：`node tools/android_runtime_smoke.mjs --apk <app-release.apk> --extended-input --offline`（证据目录 `android-emulator-evidence/`）。

## 结果记录

| 日期 | 设备型号 | Android 版本 | APK 版本 | 通过项 | 执行人 | 证据归档 |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — |

## 边界说明

- CI 模拟器证据**不能替代**真机验收（WebView 渲染差异、触控行为、文件权限、生命周期与厂商系统差异只有在真机暴露，路线图 P0 明确说明）。
- 未完成真机验收前，发布材料中 Android 端只能表述为「Debug/release 构建通过 CI 模拟器验收，真机验收待补」。
