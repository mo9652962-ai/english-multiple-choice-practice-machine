# 题包公开发布证据清单

本清单用于题库从“本地/授权范围内可用”转为“可公开分发”。它不替代原始许可证、来源页面、人工审核记录或抽样结果；缺少证据时应保持 `pending`，不能用题目数量、结构检查或 AI 输出代替授权证明。

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

`-StrictQuality` 还会把以下确定性题型门禁写入 release manifest，并在任一计数大于 0 时阻断发布：

| 检查项 | 含义 |
|---|---|
| `units_with_unknown_type` | 单元 `unit_type` 不在导入器支持的题型枚举中 |
| `questions_with_unknown_type` | 题目 `question_type` 不在当前题目契约中 |
| `questions_with_insufficient_options` | 选择题少于两个可用选项 |

这些检查只验证稳定的结构契约，不会把某一套考试的固定题号或固定选项数量硬编码到所有题库中；考试模板完整性由 `-CheckTemplates` 单独检查。

## 当前题包状态

当前公开 starter 源目录已替换为两个明确标注的原创 AI 模拟题包。数据库和离线种子属于被 Git 忽略的本地产物，必须在重新导入/重建后才会反映这次替换；在重建前不得使用旧数据库执行发布。

| package_id | 当前状态 | 阻断原因 |
|---|---|---|
| `motei.ai.postgraduate-english-one.sim-2026` | `generated; awaiting database rebuild` | 需重新导入 release/offline 数据库并重新跑严格门禁 |
| `motei.ai.postgraduate-english-two.sim-2026` | `generated; awaiting database rebuild` | 需重新导入 release/offline 数据库并重新跑严格门禁 |

原考研英语（一/二）题包已移出公开 starter 目录，保留在本机被忽略的 `examples/internal-banks/` 目录，仅用于内部留档，不进入 PyInstaller、Web 或 APK 资源。它们仍然不能公开分发，也不能作为新模拟题的来源文本。

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
  -StrictQuality `
  -RequireAndroidMetadata `
  -CheckTemplates `
  -WriteReport work\release-manifest-publishable.json
```

只有该命令退出码为 `0`，并且报告中的 `packages_not_publishable` 为 `0`，才可以进入公开分发流程。
