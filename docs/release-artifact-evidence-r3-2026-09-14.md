# r3 全端发布产物证据（2026-09-14）

本记录对应程序版本 `2.1.3`、内容版本 `content-2026-09-14-r3`、离线种子版本 `offline-2026-09-14-r3`。r1/r2 的产物不能与本版本混用。

## 内容基线

| 项目 | 值 |
|---|---:|
| 活跃公开题卷 | 12 |
| 单元 / 题目 / 选项 | 36 / 180 / 720 |
| 公共词汇条目 | 7,958 |
| release 数据库 SHA-256 | `2A8F6E4C3EB4AE2F48102A86E7C893AF170AE0CD2E21C610ABCD0B473994BAD6` |
| offline 数据库 SHA-256 | `E444341B9DDFB775B48199F0CA9613076EBC3E24808EF166D51EF27B43B79E9A` |
| 内容 bundle | `work/release-content-bundle-r3.zip` |

r3 清理掉了 26 套已删除题卷残留的 59 个单元、488 道题和 3,654 个选项；bundle 中 release/offline 的有效内容计数一致，运行时表已清空。两个公开包均为项目内确定性模板生成的 AI 模拟题，旧考研回忆版/本地导出题包仍保持 local-only，不进入公开资源。

## 构建与验证

| 目标 | 结果 | 证据边界 |
|---|---|---|
| 全量 Python 测试 | `137 passed, 13 skipped` | 通过，不替代人工内容复核 |
| 前端生产构建 | 通过 | Vite 默认 500 KB chunk 提示仍存在；项目自身 512/1024 KB 门禁通过 |
| 后端 PyInstaller | 通过 | 在 Electron 实际引用的 `backend/dist/backend_app` 路径重建 |
| Windows 安装包 / portable | 通过 | 完整 builder 退出码 0；portable 新临时目录启动冒烟通过 |
| Windows portable 冒烟 | 通过 | 版本 `2.1.3`、内容 `r3`、Schema `2`、内置 seed hash 与 release DB 一致 |
| Android debug APK | 构建通过 | `assembleDebug` 成功；不是正式 release 签名 |
| Android 真机/模拟器运行 | 未完成 | `adb` 无设备、无可用 emulator/AVD；不能宣称运行验收通过 |
| 严格发布门禁 | 通过 | 退出码 0；`packages_not_publishable=0`、`papers_not_publishable=0` |

最终严格门禁报告：`work/release-manifest-artifacts-r3.json`。它记录了 r3 数据库、元数据、两个 Windows 候选和 Android debug APK 的 hash。

## r3 artifact SHA-256

| 文件 | 大小（bytes） | SHA-256 | 状态 |
|---|---:|---|---|
| `electron/dist/epm-setup-2.1.3.exe` | 147,682,392 | `6D4C71FB676E4C28291F9891430D08E0C4F701A4BC1021225FF9FFB825044934` | 本机自签名，内部候选 |
| `electron/dist/epm-setup-2.1.3.exe.blockmap` | 149,497 | `89574C06D8A5D3FC74A04F6E25490BA25568CDBEA551B13BEA3E9D6926852445` | 对应 r3 安装包 |
| `electron/dist/epm-portable-2.1.3.exe` | 147,343,248 | `6212535E07ECB771378FFAF635A56AC0955DB7D69F76EC9035931E8ECCCB4B36` | 本机自签名，内部候选 |
| `frontend/android/app/build/outputs/apk/debug/app-debug.apk` | 32,928,594 | `1B4F8610BCE1BD6CE27C7357784EA6079E7689252542E34F16FAD9398CA853AF` | debug 候选，未做真机验证 |
| `backend/dist/backend_app/backend_app.exe` | 18,153,091 | `C2131C2A8B684BA542BBA19B11F33865BFBC862A6FA402AB712FF002F21C2452` | r3 后端重建；资源版本另由 `_internal/CONTENT_VERSION` 核对 |

## 当前仍不能公开发布的原因

1. Windows 使用本机自签名证书 `227BFE4360866350CCDE133BA2A6E141F7A50E0E`，正式 tag workflow 会拒绝 self-signed 证书；需要公共 CA 代码签名证书或明确的内部信任分发边界。
2. Android 只有 debug APK，没有真实 release keystore Secrets；需要配置 `ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD`。
3. 本机没有 Android 真机、模拟器或 AVD，尚未完成安装、离线启动、练习、返回键、后台恢复、重启和迁移验证。
4. GitHub Release、外部 artifact 存储和正式发布目标仍未获得明确授权，因此没有执行上传或 push。

## 可复现输入与下一步

`tools/create_release_content_bundle.py` 现在会从本地 release/offline 数据库生成只含公共内容的确定性 bundle，清除运行时数据、用户词汇和删除题卷残留；`tools/rebuild_public_content.py` 也会在常规重建中执行同样的非活跃题卷清理。CI 目前只检查受控内容输入存在并记录 hash，尚未把该 bundle 接入远程内容存储。下一步应先补齐受保护的 CI 内容输入，再完成正式签名和真实 Android 设备验收。
