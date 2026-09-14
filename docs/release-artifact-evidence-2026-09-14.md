# 全端发布产物证据（2026-09-14）

本记录对应内容版本 `content-2026-09-14-r1`、离线种子版本 `offline-2026-09-14-r1`、应用版本 `2.1.3`。所有 hash 均为本轮重新构建后的最终文件，不应与此前构建产物混用。

> ⚠️ 本记录是 r1 的历史构建证据。2026-09-14 题库已完成 r2 provenance 收口并升版为 `content-2026-09-14-r2` / `offline-2026-09-14-r2`；因此本文列出的安装包、APK、数据库和 bundle hash 全部需要重新构建后才能恢复为当前发布证据。本轮不把这些旧产物当作 r2 发布物。

## r2 重建后的内容指纹

| 项目 | 当前值 |
|---|---|
| 活跃公开题卷 | 12 套（release/offline 一致） |
| 单元 / 题目 / 词汇 | 95 / 668 / 7,958 |
| release 数据库 SHA-256 | `FFDCB436A9CC93E7E21EAE2C5407FA0880C491D660366C1A870CA1EADE8A934B` |
| offline 数据库 SHA-256 | `F513F26D09ED8C0339A481720C1AC3610F6D2C3DC4073BCDCFAACAFF81EFAA67` |
| 严格逐卷 provenance 门禁 | 通过；`packages_not_publishable=0`、`papers_not_publishable=0` |

Web 静态产物、Windows 内部候选和 Android debug 候选已针对 r2 重新构建；但 Windows 仍使用本机自签名证书，APK 仍是 debug 签名，且 Android 真机/模拟器运行尚未验证，因此发布状态仍保持阻断。

## r2 内部候选产物指纹

| 文件 | 大小（bytes） | SHA-256 | 状态 |
|---|---:|---|---|
| `electron/dist/epm-setup-2.1.3.exe` | 147701496 | `25C94474D704FC975C06EA449E5EFCB73A75A92C94CA53DD7FD3E15EB85E0DE7` | 本机自签名，内部候选 |
| `electron/dist/epm-setup-2.1.3.exe.blockmap` | 149489 | `9FF81A7DC22966FF4CA0D71EBE6C66D6510B71C4B03538F1EB4C5C3B95EF9435` | 对应 r2 安装包 |
| `electron/dist/epm-portable-2.1.3.exe` | 147362352 | `4221A201B2960ADC43C7F4977FE83A0C5AE4BA27D98098421AAD9C62DD4ACAE4` | 本机自签名，内部候选 |
| `frontend/android/app/build/outputs/apk/debug/app-debug.apk` | 32925180 | `B0805D6862649B3BA72F6781A7DA5C51CDF5F3FCD76E45A8C21DBF1BB09BA4EC` | debug 候选，未做真机验证 |
| `backend/dist/backend_app/backend_app.exe` | 18153091 | `C2131C2A8B684BA542BBA19B11F33865BFBC862A6FA402AB712FF002F21C2452` | r2 后端重建 |

Windows 安装包和 portable 的 Authenticode 状态均为 `Valid`，签名者为本机自签名证书 `227BFE4360866350CCDE133BA2A6E141F7A50E0E`；这不等同于公共 CA 信任。正式 tag workflow 现在还会拒绝自签名、过期或缺少 Code Signing EKU 的证书。Windows portable smoke 会从本次运行的 `resources/seed/question_bank.db` 直接核对 release DB hash，不把启动后经过 SQLite 迁移的用户数据库 hash 误当作包内 seed hash。带上述 artifact 参数的严格 `release_check` 退出码为 `0`，但该门禁不替代正式签名和真实设备运行验证。

## 构建结果

| 目标 | 结果 | 说明 |
|---|---|---|
| 前端生产构建 | 通过 | Vite 构建成功；部分 chunk 仍有默认 500 KB 提示，但项目 512/1024 KB 发布门禁通过 |
| 后端 PyInstaller | 通过 | `backend/dist/backend_app/backend_app.exe` 已重新构建 |
| Windows 安装包 | 通过 | Electron 安装包已重新构建并完成打包后启动冒烟 |
| Windows portable | 通过 | portable 包已重新构建并完成打包后启动冒烟 |
| Android APK | 构建通过 | 本轮生成 debug APK，并完成资源/版本/题库静态检查 |
| Android 真机/模拟器运行 | 未完成 | `adb devices -l` 无设备或模拟器；运行冒烟脚本已如实记录为阻断 |

## 最终 artifact SHA-256

| 文件 | 大小（bytes） | SHA-256 |
|---|---:|---|
| `electron/dist/epm-setup-2.1.3.exe` | 134493192 | `4758095D96ED10828A9B34A81EF904348DB2B44EADB54A668A1D0371533AC4A7` |
| `electron/dist/epm-portable-2.1.3.exe` | 134154048 | `11D3F9B4AD79D69C5905FE48FCC55A7B58A6A237E484CC93FE7D7AF723F6FA2C` |
| `electron/dist/epm-setup-2.1.3.exe.blockmap` | 135023 | `FAAAC530A5B0D54CD806FBAFB5B65A723D7093A5F941933E5A0F5244298BBEC5` |
| `frontend/android/app/build/outputs/apk/debug/app-debug.apk` | 32817382 | `47B6A30AB6AA2BAF8413E7FDF15812BBC5562EBFE7D3FA31510AF0178C58B1C0` |
| `backend/dist/backend_app/backend_app.exe` | 10223257 | `CDE11C3A216D22F9DBF2F416FC32DC8FEBC68A467428E049BD141D29353B26AF` |

## 内容与发布门禁

最终严格检查命令包含：

```powershell
python tools/release_check.py `
  --release-db backend/data/question_bank.db `
  --offline-db frontend/public/question_bank.db `
  --min-vocabulary 7958 `
  --min-schema-version 2 `
  --require-package-provenance `
  --require-publishable-provenance `
  --strict-quality `
  --require-android-metadata `
  --check-templates `
  --artifact electron/dist/epm-setup-2.1.3.exe `
  --artifact electron/dist/epm-portable-2.1.3.exe `
  --artifact frontend/android/app/build/outputs/apk/debug/app-debug.apk `
  --write-report work/release-manifest-artifacts-2026-09-14.json
```

检查结果：

- 退出码：`0`
- `packages_not_publishable=0`
- release 数据库：48 套试卷、133 个单元、827 道题、7958 个词汇条目
- offline 数据库与 release 数据库题量一致
- release 数据库 SHA-256：`5BF7A80FE70B1902A2536D83A76D6BBEBCDFA5F89DED90D3621E35E625C77397`
- offline 数据库 SHA-256：`D385CA1A72527C2FE398CCEA20C1F62A9C3085345379EE528F7498B874331F95`
- 报告文件：`work/release-manifest-artifacts-2026-09-14.json`（本地构建证据，不纳入版本库）

## 运行与签名边界

- Windows 安装包和 portable 包已启动后确认版本 `2.1.3`、内容版本 `content-2026-09-14-r1`、Schema `2`，且后端数据库可用；重新签名后的 portable 冒烟仍通过。
- APK 内已确认包含 `release-metadata.json`、`question_bank.db` 和前端入口；解包检查确认内容版本为 `content-2026-09-14-r1`，题库为 48 套/827 题。
- 当前 Windows 产物已使用本机证书指纹 `227BFE4360866350CCDE133BA2A6E141F7A50E0E` 签名，PowerShell Authenticode 状态为 `Valid`；证书为自签名证书，依赖本机信任配置，不等同于公共 CA 信任。APK 仍为 debug 构建。
- Android 真机/模拟器验证需要连接设备后重新执行 `tools/android_runtime_smoke.mjs`，当前不应宣称移动端真实运行已通过。

## 下一阶段签名门禁已落地

- `scripts/sync_android_version.mjs` 会在 Capacitor 生成工程中注入 release signing config；`assembleDebug` 不要求签名变量，`assembleRelease` 缺少签名变量会主动失败。
- Android tag workflow 使用以下 GitHub Secrets，不把密钥写入仓库：`ANDROID_KEYSTORE_BASE64`、`ANDROID_KEYSTORE_PASSWORD`、`ANDROID_KEY_ALIAS`、`ANDROID_KEY_PASSWORD`。
- Windows tag workflow 使用 `WINDOWS_CSC_LINK` 和 `WINDOWS_CSC_KEY_PASSWORD`，并要求两个 Windows 产物的 Authenticode 状态为 `Valid`。
- 本地使用一次性测试 keystore 验证过 `assembleRelease` 与 `apksigner verify`；测试 keystore 和测试 release APK 已清理，未作为正式产物保留。
- 当前仓库仍不保存签名私钥；Android 尚未配置真实 release keystore，因此本记录中的 APK hash 仍属于 debug APK。Windows hash 为本机自签名后的内部验证产物，正式公开发布仍需确认公共信任证书或明确接受内部信任分发。

## 本轮配置与学习强化

- 新增 `scripts/check_android_release_signing.ps1`：可在本地用 keystore 路径和环境变量做签名预检，验证 alias、keystore 密码和 CI Secret 是否齐全；脚本不会输出任何密码，也不会写入仓库。
- 错题本的 FSRS“今日复习”区域新增“今日复习全部”入口：一次性把当前已加载的到期题目交给既有练习会话，继续沿用提交时的 FSRS 更新、错题回收和重启恢复逻辑，不引入第二套调度算法。
- 当前学习强化只覆盖已加载的队列上限（后端默认 30 题）；队列为空时仍需先完成练习或错题产生复习卡片。
- 已增加契约测试，锁定批量复习入口和 Android 预检的密钥不泄露约束。

## 内容生成说明

本轮两个公开模拟题包由仓库内 `tools/generate_ai_simulation_banks.py` 的确定性模板和项目自有主题种子生成，可复现、无外部模型实时调用，也未读取旧未授权题包作为生成输入。它们不是官方真题，也不是本轮实时批量模型生成结果；如要升级为真实模型生成，仍需单独增加模型版本记录、提示词/输入证据、内容质量抽检和人工复核。
