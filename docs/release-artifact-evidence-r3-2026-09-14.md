# r3 全端发布产物证据（2026-09-14）

本记录对应程序版本 `2.1.3`、内容版本 `content-2026-09-14-r3`、离线种子版本 `offline-2026-09-14-r3`。r1/r2 的产物不能与本版本混用。

## 内容基线

| 项目 | 值 |
|---|---:|
| 活跃公开题卷 | 12 |
| 单元 / 题目 / 选项 | 36 / 180 / 720 |
| 公共词汇条目 | 7,958 |
| release 数据库 SHA-256 | `21A2C9DC26D780CD55FA685587674065A809D0AC720BFCE80CFA2FE9D3125A6F` |
| offline 数据库 SHA-256 | `E444341B9DDFB775B48199F0CA9613076EBC3E24808EF166D51EF27B43B79E9A` |
| 内容 bundle | `work/release-content-bundle-r3.zip` |

r3 清理掉了 26 套已删除题卷残留的 59 个单元、488 道题和 3,654 个选项；bundle 中 release/offline 的有效内容计数一致，运行时表已清空。两个公开包均为项目内确定性模板生成的 AI 模拟题，旧考研回忆版/本地导出题包仍保持 local-only，不进入公开资源。

## 构建与验证

| 目标 | 结果 | 证据边界 |
|---|---|---|
| 全量 Python 测试 | `167 passed, 13 skipped` | 通过，不替代人工内容复核；包含 Android release artifact contract 与 APK 资源一致性回归测试 |
| 前端生产构建 | 通过 | 入口最大 465 KB、最大懒加载块 922 KB；项目自身 512/1024 KB 门禁通过 |
| 后端 PyInstaller | 通过 | 在 Electron 实际引用的 `backend/dist/backend_app` 路径重建；hash 已更新 |
| Windows 安装包 / portable | 通过 | 本轮重新打包，builder 退出码 0；portable 新临时目录启动冒烟通过 |
| Windows portable 冒烟 | 通过 | 版本 `2.1.3`、内容 `r3`、Schema `2`、内置 seed hash 与 release DB 一致 |
| Android 前端资源同步 | 通过 | `npx cap sync android` 已将当前前端 dist 同步到生成工程 |
| Android debug APK | 通过 | 使用 Temurin JDK `21.0.12.1` 重建；Gradle 成功，APK v2 签名校验通过，APK 内离线数据库、迁移清单和版本元数据与当前 Web dist 一致 |
| Android 真机/模拟器运行 | 未完成 | `adb` 无设备、无可用 emulator/AVD；不能宣称运行验收通过 |
| 严格发布门禁 | 通过 | 退出码 0；`packages_not_publishable=0`、`papers_not_publishable=0` |

当前严格门禁报告：`work/release-manifest-r3-current-2026-09-14.json`；报告记录 r3 数据库和元数据，Windows hash 以本节本轮重建值为准；Android debug APK hash 已更新为本轮重建值，仍不等同于正式 release 签名或真实设备验收。

## r3 artifact SHA-256

| 文件 | 大小（bytes） | SHA-256 | 状态 |
|---|---:|---|---|
| `electron/dist/epm-setup-2.1.3.exe` | 147,691,456 | `CD56D173C2D77C561620B3CD802274280F943938521DAF5AB07ADD80BD722F0C` | 本轮重建；本机自签名，内部候选 |
| `electron/dist/epm-setup-2.1.3.exe.blockmap` | 149,609 | `80D519E5F5F386B3B249AEDD6A1410FBD454C126DF49C72613BCD34CD9D03CD0` | 对应本轮安装包 |
| `electron/dist/epm-portable-2.1.3.exe` | 147,352,328 | `294A510D27996B3EC0C588ABC1DB3C356DD528B336206875040FA6A7A98D2014` | 本轮重建；本机自签名，内部候选 |
| `frontend/android/app/build/outputs/apk/debug/app-debug.apk` | 32,928,594 | `F398377BC2A081BA7449453AA1D67E86DBE56AB3331BAFDEC03C67281FC8B19D` | 本轮使用 Temurin JDK 21.0.12.1 重建；debug 签名，静态资源已与 Web dist 对齐 |
| `backend/dist/backend_app/backend_app.exe` | 18,156,423 | `AD33692F7850F0158517D092AF1161FA45A450852570BCCBBBB1BF140E30538A` | 本轮后端重建；资源版本由 `_internal/CONTENT_VERSION` 核对 |

## 当前仍不能公开发布的原因

1. Windows 使用本机自签名证书 `227BFE4360866350CCDE133BA2A6E141F7A50E0E`；本机当前 `Get-AuthenticodeSignature` 状态为 `UnknownError`（证书链终止于不受信任根），正式 tag workflow 会拒绝 self-signed 或非 `Valid` 证书；需要公共 CA 代码签名证书或明确的内部信任分发边界。
2. Android 只有 debug APK，没有真实 release keystore Secrets；需要配置 `ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD`。
3. 本机没有 Android 真机、模拟器或 AVD；虽已补齐 JDK 并重建当前 debug APK，但尚未完成安装、离线启动、练习、返回键、后台恢复、重启和迁移验证。
4. GitHub Release、外部 artifact 存储和正式发布目标仍未获得明确授权，因此没有执行上传或 push。

## 可复现输入与下一步

`tools/create_release_content_bundle.py` 现在会从本地 release/offline 数据库生成只含公共内容的确定性 bundle，清除运行时数据、用户词汇和删除题卷残留；`tools/rebuild_public_content.py` 也会在常规重建中执行同样的非活跃题卷清理。CI 目前只检查受控内容输入存在并记录 hash，尚未把该 bundle 接入远程内容存储。Windows 本轮内部候选和 Android debug APK 已与当前前端/后端同步；下一步仍需补齐受保护的 CI 内容输入、正式签名和真实 Android 设备验收。

## CI 工作流复核

- `.github/workflows/android.yml`、`.github/workflows/ci.yml` 和 `.github/workflows/release.yml` 均通过本地 `actionlint`。
- Android workflow 通过 `tools/check_android_artifact.py` 逐项比较 APK 内离线资源与当前 Web dist，并上传检查报告，防止旧 APK 混入新内容版本。
- Android 标签构建会校验并上传 `app-release.apk`；普通分支构建只上传 `app-debug.apk`，避免缺失 release 文件导致误报。
- `scripts/check_windows_release_signing.ps1` 现在同时作为本地和 CI 的 Windows Authenticode 预检入口，检查签名状态、证书有效期、Code Signing EKU，并在公共发布模式拒绝自签名证书。
- 旧的 `scripts/release_all.py` 一键发布入口已安全封存，不再执行本地自签名、debug APK 构建或 GitHub 上传；发布统一走受保护的 GitHub Actions workflow。
- Android 工作流修复已单独提交为 `89bcc36 fix(ci): publish signed android artifact evidence`，Windows 签名预检接入已提交为 `c7a0deb ci: centralize windows signing preflight`；这些提交不等同于真实 release keystore、设备运行或公共证书已经配置。
