# 全端发布产物证据（2026-09-14）

本记录对应内容版本 `content-2026-09-14-r1`、离线种子版本 `offline-2026-09-14-r1`、应用版本 `2.1.3`。所有 hash 均为本轮重新构建后的最终文件，不应与此前构建产物混用。

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
| `electron/dist/epm-setup-2.1.3.exe` | 134449018 | `FD71E70CEE100E2887F4E1124B2D935C1E3FB8BB34A1CF6078D41773E6A2CD43` |
| `electron/dist/epm-portable-2.1.3.exe` | 134116773 | `8C8D0C766ED1BEEDB37C4C83E6E7FB00FE438BE32949A0CAC354D68B67899BC3` |
| `electron/dist/epm-setup-2.1.3.exe.blockmap` | 135387 | `36707EEC80D75D2147394B39A7AB2800F4C6E365A8D85A8FD9277E3937519EC9` |
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

- Windows 安装包和 portable 包已启动后确认版本 `2.1.3`、内容版本 `content-2026-09-14-r1`、Schema `2`，且后端数据库可用。
- APK 内已确认包含 `release-metadata.json`、`question_bank.db` 和前端入口；解包检查确认内容版本为 `content-2026-09-14-r1`，题库为 48 套/827 题。
- Electron 构建日志显示当前没有代码签名证书，因此 Windows 产物为未签名构建；APK 为 debug 构建。它们证明构建链路和内容装配正确，不等同于面向终端用户的签名发布包。
- Android 真机/模拟器验证需要连接设备后重新执行 `tools/android_runtime_smoke.mjs`，当前不应宣称移动端真实运行已通过。

## 内容生成说明

本轮两个公开模拟题包由仓库内 `tools/generate_ai_simulation_banks.py` 的确定性模板和项目自有主题种子生成，可复现、无外部模型实时调用，也未读取旧未授权题包作为生成输入。它们不是官方真题，也不是本轮实时批量模型生成结果；如要升级为真实模型生成，仍需单独增加模型版本记录、提示词/输入证据、内容质量抽检和人工复核。

