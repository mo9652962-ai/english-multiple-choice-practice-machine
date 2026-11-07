# Android 正式签名与 GitHub Secrets 配置指南

本文档描述墨题 Android release APK 的签名材料生成、GitHub secrets 配置、本地验证与密钥轮换流程。对应路线图硬门槛「Windows/APK 正式分发签名、密钥保管和回滚记录」（`docs/next-phase-roadmap-2026-09-13.md`）。

## 1. 角色与名称对照

同一条签名链路在三层使用不同变量名，勿混用：

| 层 | 变量名 | 说明 |
|---|---|---|
| GitHub Actions secrets（CI） | `ANDROID_KEYSTORE_BASE64` | keystore 文件的 base64 编码，runner 上解码为临时文件 |
| | `ANDROID_KEYSTORE_PASSWORD` | keystore 存储密码 |
| | `ANDROID_KEY_ALIAS` | 密钥别名（默认 `epm-release`） |
| | `ANDROID_KEY_PASSWORD` | 密钥密码（与存储密码一致时填同一个） |
| Gradle（`frontend/android/app/build.gradle` 的 `EPM_RELEASE_SIGNING_CONFIG` 块） | `EPM_ANDROID_KEYSTORE_FILE` | CI 解码后的 keystore 临时路径 |
| | `EPM_ANDROID_KEYSTORE_PASSWORD` / `EPM_ANDROID_KEY_ALIAS` / `EPM_ANDROID_KEY_PASSWORD` | 同上 |
| 本地预检脚本（`scripts/check_android_release_signing.ps1`） | `EPM_ANDROID_KEYSTORE_PASSWORD`（回退 `ANDROID_KEYSTORE_PASSWORD`）等 | 与 Gradle 同名 |

任一 `assembleRelease` 变体在缺少签名环境变量时会直接抛 `GradleException`（fail-closed），不会静默产出未签名包；`android.yml` 仅在 push `v*` tag 时要求 secrets 并执行 `assembleRelease` + `apksigner verify`。

## 2. 快速开始（生成 + 配置）

前置：JDK 21（`keytool` 在 PATH 或 `%USERPROFILE%\jdk21\bin`）；可选 gh CLI（自动配置 secrets 用）。

```powershell
# 生成 keystore（输出在仓库外 %USERPROFILE%\epm-release-keystore\），交互输入密码
powershell -ExecutionPolicy Bypass -File scripts\setup_android_keystore.ps1

# 结束时选择 y 自动配置以下 4 个 secrets（需要 gh auth login 过）：
#   ANDROID_KEYSTORE_BASE64 / ANDROID_KEYSTORE_PASSWORD / ANDROID_KEY_ALIAS / ANDROID_KEY_PASSWORD
```

脚本行为：keystore 默认写到 `%USERPROFILE%\epm-release-keystore\epm-release.keystore`（RSA 4096，有效期 11000 天，覆盖到 2033 年后）；生成后自动跑 `check_android_release_signing.ps1` 预检；secrets 通过 `gh secret set` 传递，密码全程不打印、不落明文临时文件（base64 临时文件用完即删）。

已有 keystore 只补配置 secrets：`powershell -File scripts\setup_android_keystore.ps1 -ConfigureSecretsOnly`

## 3. 密钥保管要求

- keystore 文件与密码**不进仓库、不进网盘/聊天工具明文传输**。提交前自查：`git ls-files | grep -iE "keystore|\.jks$|\.p12$"`（AGENTS.md 坑 23）。
- 建议线下保留：keystore 文件一份 + 密码一份，分开存放（如密码管理器 + 加密 U 盘）。**丢失 keystore = 永久失去对已分发 APK 的升级能力**（签名不一致时 Android 拒绝覆盖安装）。
- 记录证书 SHA-256 指纹（脚本生成时展示）供下游渠道校验。

## 4. 本地 release 构建验证

```powershell
cd frontend
npx cap add android; npx cap sync android   # 干净 checkout 先执行；已生成过则跳过
node scripts\sync_android_plugins.mjs
node scripts\sync_android_version.mjs

$env:EPM_ANDROID_KEYSTORE_FILE = "$env:USERPROFILE\epm-release-keystore\epm-release.keystore"
$env:EPM_ANDROID_KEYSTORE_PASSWORD = "<store 密码>"
$env:EPM_ANDROID_KEY_ALIAS = "epm-release"
$env:EPM_ANDROID_KEY_PASSWORD = "<key 密码>"
cd android; .\gradlew.bat assembleRelease

# 验签（build-tools/36.0.0/apksigner）
$env:Path = "$env:ANDROID_HOME\build-tools\36.0.0;$env:Path"
apksigner verify --verbose app\build\outputs\apk\release\app-release.apk
```

产物 `app-release.apk` 即正式签名包；CI 会在 tag 触发时做同样构建并以 `epm-android-release-<sha>` artifact 上传。

## 5. 发布流程（secrets 就绪后）

1. 确认 4 个 secrets 已配置：`gh secret list`
2. （Windows 未签名豁免见 `docs/release-artifact-evidence-*.md`；Windows 与 Android 发布互相独立）
3. 打 tag 触发：`git tag v2.3.0 && git push origin v2.3.0` → Android workflow 构建 release APK + 模拟器取证 + artifact 上传
4. 将 `epm-android-release-<sha>` artifact 中的 APK 附到发布仓库 `mo9652962-ai/epm-releases` 的 Release（发布产物集中在该独立仓库）

## 6. 密钥轮换流程

Android 签名身份不支持「原地轮换」——新 keystore 签的包无法覆盖安装旧包。轮换 = 发布升级路径的变更，仅用于密钥泄露等场景：

1. 用本脚本生成**新 keystore**（新路径/新别名，勿覆盖旧文件）。
2. `gh secret set` 更新 4 个 secrets 为新值。
3. 在发布仓库 Release notes 中说明：新版本与历史版本签名不一致，需卸载重装（本地数据导出/导入路径需同步说明）。
4. 归档旧 keystore 至少一个发布周期后再销毁。

## 7. 当前状态（2026-11-07）

- [x] Gradle 环境变量签名配置 + fail-closed 守卫（`sync_android_version.mjs` 自动维护）
- [x] CI tag 触发 `assembleRelease` + `apksigner verify`（`android.yml`）
- [x] keystore 生成/配置工具（`scripts/setup_android_keystore.ps1`）
- [ ] 用户生成 keystore 并配置 4 个 secrets（一次性人工操作）
- [ ] tag 触发的 release APK 端到端产出

历史上 HBuilderX 云打包测试证书配置（`epm_app/unpackage/`）已于 2026-11 从 git 全部历史清除，且正式签名使用全新 keystore，与其无任何关系（见 AGENTS.md 坑 23）。
