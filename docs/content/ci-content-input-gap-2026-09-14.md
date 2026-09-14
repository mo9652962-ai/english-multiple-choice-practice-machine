# Clean CI 内容输入边界（2026-09-14）

## 当前结论

正式 release workflow 需要两个经过核验的本地内容输入：

- `backend/data/question_bank.db`
- `frontend/public/question_bank.db`

这两个文件被 `.gitignore` 排除，不会随 clean checkout 自动出现。它们不能由 `initialize_database()` 代替：后者只创建/迁移 schema，不会恢复当前 r3 的 7,958 条词汇、12 套题卷、180 道题和完整 provenance。

当前 workflow 已增加 `scripts/prepare_release_content.ps1`：如果受控 runner 已提供 `EPM_RELEASE_CONTENT_BUNDLE_PATH`，它会调用 `tools/prepare_release_content_bundle.py`，校验 manifest、两个版本号、文件 hash、大小、有效题量和 offline schema 差异后再安装两个 seed；未提供 bundle 时回退到 `scripts/require_release_content.ps1`，检查两个文件存在、非空并记录 SHA-256。缺少输入时会直接阻断，并明确要求先注入经过核验的 seed；不会把空库或不完整库继续打包。

当前只落地了“注入协议”和 fail-closed 门禁，没有擅自选择 GitHub Release、外部对象存储或其他远程传输位置。后续由发布负责人明确授权内容存储和 runner 注入方式后，再配置 `EPM_RELEASE_CONTENT_BUNDLE_PATH` 的实际来源。

## 为什么不能直接用当前 APKG

仓库跟踪的 `exports/vocabulary-2026-08-08-all.apkg` 是历史 Anki 导出，不是当前 release 数据库的等价构建源：只读核验得到 7,965 条 note、7,952 个去重 term，而当前 release 库为 7,958 条；phonetic、category 和若干词形也存在差异。未经字段映射、差异清单和人工复核，不能把它直接接入正式构建。

## 解除该阻断的验收条件

后续需要二选一：

1. 提供一个版本化、可追溯授权的 vocabulary/content seed，并实现确定性导入；或
2. 将 clean release 数据库作为受控构建输入，通过受保护 artifact/secret 注入 CI，并在 manifest 中记录来源、版本和 SHA-256。

完成后必须从同一输入重新生成 Web、Windows 和 APK，并重新执行 provenance、题量、离线一致性、签名和运行验证。不能用本机忽略目录中的旧数据库替代 CI 输入证据。

本地验证命令：

```powershell
python tools/prepare_release_content_bundle.py `
  --bundle work/release-content-bundle-r3.zip `
  --release-db work/verify-r3-release.db `
  --offline-db work/verify-r3-offline.db
```

本轮真实 r3 bundle 已通过该注入器和完整 `release_check`；验证数据库仍留在被忽略的 `work/` 目录，不进入版本库。
