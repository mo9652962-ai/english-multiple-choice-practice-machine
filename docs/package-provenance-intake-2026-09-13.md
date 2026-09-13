# 题包 provenance 采集台账（2026-09-13）

本台账固定当前两个发布题包的原始 ESQ 文件、声明内容和待补证据。它不是授权证明，也不改变发布门禁结果；在证据未核验前，两个题包必须保持 `pending`，不得公开分发。

## 当前原包指纹

| package_id | ESQ 文件 | contentVersion | SHA-256 | 当前声明 |
|---|---|---:|---|---|
| `wssfk.postgraduate-english-one.2010-2026` | `examples/bundled-banks/postgraduate-english-one.esq` | `1.0.0` | `EDE30FAE65F2FBAB53C830BA39EF618E5E82F0FA7EBC789D363093C5C1B47075` | `license.spdx=NOASSERTION`；`source.type=candidate_recollection`；考生回忆整理、非官方发布 |
| `local.english-practice.postgraduate-english-two.2010-2025` | `examples/bundled-banks/postgraduate-english-two.esq` | `1.1.1` | `D25AC946FA0543A61BEB88EB02664D1E3A55EB819632667603268A6346FE2E83` | `license.spdx=NOASSERTION`；`source.type=local_export`；从本地题库导出 |

## 两个题包都必须补齐的证据

### 1. 许可证与授权

需要提供至少一种可核验材料：

- 原始来源的许可证页面或明确授权条款；
- 权利人/内容提供方的授权声明；
- 若只允许个人学习使用，提供明确的分发边界，并将包改为不进入公开发布包。

材料必须能回答：谁授权、授权什么内容、允许哪些分发方式、有效日期/版本是什么。不能用项目 GPL-3.0 代码许可证替代题库内容授权。

### 2. 来源核验

每个 package 需要记录：

- 原始 URL、原始文件路径或授权人；
- 获取日期；
- 覆盖的年份/题型范围；
- 核验人、核验日期和核验结论。

“考生回忆版”“本地导出”只能作为来源类型，不能自动变成已核验来源。

### 3. 人工复核

需要记录复核范围、抽查数量、发现的问题、处理结论、复核人和日期，并把 `review.status` 设为 `reviewed` 或 `locked`。

### 4. AI 修改差异

需要二选一：

- 提供 AI 修改前后 diff，并将 `ai_assist.diff_status` 设为 `recorded` 或 `reviewed`；
- 明确该包没有经过 AI 修改，并将 `ai_assist.diff_status` 设为 `not_applicable`，同时保留确认记录。

### 5. 发布抽样

需要记录抽样范围、样本数、失败数、处理结果、复核人和日期，并将 `quality.release_sample.status` 设为 `passed` 或 `reviewed`。

## 处理边界

在上述材料到位前，不应做以下操作：

- 把 `NOASSERTION` 改成 `CC-BY`、`CC-BY-NC` 或其他 SPDX 标识；
- 把 `verified`、`review.status`、`diff_status` 或抽样状态直接改成通过值；
- 直接修改 `release-manifest.json` 使门禁显示为可发布；
- 把题包复制到公开分发目录来绕过 `question_bank_packages` 检查。

## 证据到位后的闭环

1. 更新对应 ESQ 包的 `manifest.json`，保留本台账中的原包 SHA-256 和新包 SHA-256。
2. 用 ESQ 校验器重新校验包。
3. 重新导入/构建 `backend/data/question_bank.db`，不要直接修改 SQLite 中的 `manifest_data`。
4. 运行严格发布检查：

```powershell
.\scripts\release_check.ps1 `
  -RequirePackageProvenance `
  -RequirePublishableProvenance `
  -StrictQuality `
  -RequireAndroidMetadata `
  -CheckTemplates `
  -WriteReport work\release-manifest-publishable.json
```

5. 只有报告中的 `packages_not_publishable = 0`，并且新生成的 Windows/APK 产物重新通过 smoke，才允许进入公开分发流程。
