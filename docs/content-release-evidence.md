# 题包公开发布证据清单

本清单用于题库从“本地/授权范围内可用”转为“可公开分发”。它不替代原始许可证、来源页面、人工审核记录或抽样结果；缺少证据时应保持 `pending`，不能用题目数量、结构检查或 AI 输出代替授权证明。

## 2026-09-20 本地扩充题库状态

本轮题库扩充后，开发库包含 50 个题包；其中 2 个项目自建 CC0 模拟包具备完整发布证据，另外 48 个题包仍缺少许可证核验、来源核验、人工复核、AI 差异或发布抽样中的至少一项。新增的 2025/2026 模拟包和 OCR/公开数据整理包暂按 `local-only` 处理，不得随 Windows、Web 或 APK 公开分发。

发布重建脚本已将这 48 个 package identity 纳入隔离清单：[tools/rebuild_public_content.py](../tools/rebuild_public_content.py)。开发库中的题目仍可用于本地研究和质量复核；只有完成真实证据采集、更新 ESQ manifest 并重新导入后，才可从隔离清单移出。

本轮没有把 `NOASSERTION`、`open`、`公开真题数据` 或 `AI生成` 等描述自动当作授权证明，也没有把 `pending` 字段改成通过状态。正式发布前仍需重新运行严格门禁并检查 `packages_not_publishable=0` 与 `papers_not_publishable=0`。

## 当前发布门禁

正式 Windows release workflow 会运行：

```powershell
.\scripts\release_check.ps1 `
  -RequirePackageProvenance `
  -RequirePublishableProvenance `
  -StrictQuality `
  -RequireAndroidMetadata `
  -CheckTemplates
```

`-RequirePublishableProvenance` 只有在发布库中每个 `question_bank_packages.manifest_data` 都满足下列条件时才会通过：

| 证据项 | 可通过状态 | 需要保留的证据 |
|---|---|---|
| `license.verified` | `true`，且 SPDX 不能是 `NOASSERTION`/`UNKNOWN` | 原始许可证、授权声明或权利人确认；记录核验人和日期 |
| `source.verified` | `true` | 原始来源地址/文件、获取日期、范围和核验说明 |
| `review.status` | `reviewed` 或 `locked` | 人工复核范围、发现的问题、处理结论和复核人 |
| `ai_assist.diff_status` | `recorded`、`reviewed` 或 `not_applicable` | AI 修改前后 diff 或明确“不使用 AI 修改”的记录 |
| `quality.release_sample.status` | `passed` 或 `reviewed` | 发布前抽样范围、样本数、失败数和处理结果 |

`-RequirePaperProvenance` 是更严格的逐卷门禁：发布库中每一条未删除且状态为 `published` 的 `papers` 记录，都必须绑定 `package_id + content_version`，并解析到一个通过上述发布证据检查的题包。只验证“登记了哪些包”不等于验证“公开库里的每一卷都来自可发布包”。

`-StrictQuality` 还会把以下确定性题型门禁写入 release manifest，并在任一计数大于 0 时阻断发布：

| 检查项 | 含义 |
|---|---|
| `units_with_unknown_type` | 单元 `unit_type` 不在导入器支持的题型枚举中 |
| `questions_with_unknown_type` | 题目 `question_type` 不在当前题目契约中 |
| `questions_with_insufficient_options` | 选择题少于两个可用选项 |

这些检查只验证稳定的结构契约，不会把某一套考试的固定题号或固定选项数量硬编码到所有题库中；考试模板完整性由 `-CheckTemplates` 单独检查。

## 当前题包状态

### `content-2026-09-14-r3` 重建结果

2026-09-14 对公开库做了逐卷 provenance 收口，并进一步清除了已删除题卷残留的子表数据。r2 数据库虽然只有 12 套活跃题卷，但仍保留 26 套已删除题卷的 59 个单元、488 道题和 3,654 个选项；这些行不再进入 r3 release/offline seed。最终可公开内容为 12 套试卷、36 个单元、180 道题、720 个选项和 7,958 个词汇条目，全部来自两个项目自建 AI 模拟题包。

严格门禁结果：`release_check` 退出码为 `0`，`packages_not_publishable=0`，`paper_provenance.papers_not_publishable=0`。release/offline 数据库的 r3 指纹分别为 `21A2C9DC26D780CD55FA685587674065A809D0AC720BFCE80CFA2FE9D3125A6F` 和 `E444341B9DDFB775B48199F0CA9613076EBC3E24808EF166D51EF27B43B79E9A`。可审计内容 bundle 见 `work/release-content-bundle-r3.zip`，其中 release/offline 清洗后内容计数一致。

由于题库内容已变化，旧 r1/r2 的 Windows、APK 和前端产物均视为过期；本轮已按 r3 重新构建 Windows/Web/Android debug APK 并重新计算对应 artifact hash，且 APK 内离线资源已与 Web dist 对齐。Windows 仍是内部候选，Android 仍为 debug 签名且尚未完成真实设备运行，不因此解除正式发布阻断。

当前公开 starter 源目录已替换为两个明确标注的原创 AI 模拟题包。数据库和离线种子属于被 Git 忽略的本地产物，必须在重新导入/重建后才会反映这次替换；在重建前不得使用旧数据库执行发布。

| package_id | 当前状态 | 阻断原因 |
|---|---|---|
| `motei.ai.postgraduate-english-one.sim-2026` | `verified in current local release seed` | 后续任何内容变更仍需重新跑严格门禁 |
| `motei.ai.postgraduate-english-two.sim-2026` | `verified in current local release seed` | 后续任何内容变更仍需重新跑严格门禁 |

原考研英语（一/二）题包已移出公开 starter 目录，保留在本机被忽略的 `examples/internal-banks/` 目录，仅用于内部留档，不进入 PyInstaller、Web 或 APK 资源。它们仍然不能公开分发，也不能作为新模拟题的来源文本。

2026-09-14 已完成 r3 release/offline 数据库重建：严格 `release_check` 退出码为 `0`，`packages_not_publishable=0`、`papers_not_publishable=0`，前后端题库均不再登记两个旧 package ID，且不再保留非公开题卷的子表残留。

新模拟题的生成记录与 manifest 证据见：[generated-simulation-provenance-2026-09-14.md](content/generated-simulation-provenance-2026-09-14.md)。这里的项目方授权声明是自建内容的发布决策记录，不是第三方官方授权证明。

本轮已固定两个原始 ESQ 文件的 SHA-256，并建立逐包证据采集台账：[package-provenance-intake-2026-09-13.md](package-provenance-intake-2026-09-13.md)。台账只记录可复核事实和待补材料，不把 `NOASSERTION` 或“本地导出”推断为公开授权。

发布清单中的离线库 `schema_version` 使用 `content-manifest.json` 声明的应用 Schema；同时保留 `physical_schema_version`，用于表示该离线 SQLite 文件是否包含后端迁移表。离线种子由前端迁移清单管理，因此不能把物理迁移表缺失误判为应用 Schema 未声明。

## 建议的证据记录格式

将以下字段加入对应 ESQ 包的 `manifest.json`，字段值必须反映已完成的真实工作：

```json
{
  "license": {
    "spdx": "待核验的 SPDX 标识",
    "verified": false,
    "verification": {
      "reviewer": "",
      "date": "",
      "evidence": ""
    }
  },
  "source": {
    "verified": false,
    "verification": {
      "reviewer": "",
      "date": "",
      "evidence": ""
    }
  },
  "review": {
    "status": "pending",
    "reviewer": "",
    "reviewed_at": "",
    "scope": "",
    "notes": ""
  },
  "ai_assist": {
    "diff_status": "pending",
    "diff_reference": ""
  },
  "quality": {
    "release_sample": {
      "status": "pending",
      "sample_size": 0,
      "checked_at": "",
      "reviewer": "",
      "notes": ""
    }
  }
}
```

其中的空值和 `pending` 是明确的未完成状态，不是可发布证据。完成后仍需运行：

```powershell
.\scripts\release_check.ps1 `
  -RequirePackageProvenance `
  -RequirePublishableProvenance `
  -RequirePaperProvenance `
  -StrictQuality `
  -RequireAndroidMetadata `
  -CheckTemplates `
  -WriteReport work\release-manifest-publishable.json
```

只有该命令退出码为 `0`，并且报告中的 `packages_not_publishable` 为 `0`，才可以进入公开分发流程。
