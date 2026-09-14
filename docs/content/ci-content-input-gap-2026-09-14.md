# Clean CI 内容输入边界（2026-09-14）

## 当前结论

正式 release workflow 需要两个经过核验的本地内容输入：

- `backend/data/question_bank.db`
- `frontend/public/question_bank.db`

这两个文件被 `.gitignore` 排除，不会随 clean checkout 自动出现。它们不能由 `initialize_database()` 代替：后者只创建/迁移 schema，不会恢复当前 7,958 条词汇、公开题卷和完整 provenance。

当前 workflow 已增加 `scripts/require_release_content.ps1`，在构建前检查两个文件存在、非空并记录 SHA-256。缺少输入时会直接阻断，并明确要求先注入经过核验的 seed；不会把空库或不完整库继续打包。

## 为什么不能直接用当前 APKG

仓库跟踪的 `exports/vocabulary-2026-08-08-all.apkg` 是历史 Anki 导出，不是当前 release 数据库的等价构建源：只读核验得到 7,965 条 note、7,952 个去重 term，而当前 release 库为 7,958 条；phonetic、category 和若干词形也存在差异。未经字段映射、差异清单和人工复核，不能把它直接接入正式构建。

## 解除该阻断的验收条件

后续需要二选一：

1. 提供一个版本化、可追溯授权的 vocabulary/content seed，并实现确定性导入；或
2. 将 clean release 数据库作为受控构建输入，通过受保护 artifact/secret 注入 CI，并在 manifest 中记录来源、版本和 SHA-256。

完成后必须从同一输入重新生成 Web、Windows 和 APK，并重新执行 provenance、题量、离线一致性、签名和运行验证。不能用本机忽略目录中的旧数据库替代 CI 输入证据。
