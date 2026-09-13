# 研究任务书：墨题两个题包 provenance 补证与发布门禁处理

> 交接对象：Hermes（k）  
> 项目：`D:\english-multiple-choice-practice-machine`  
> 日期：2026-09-13  
> 优先级：发布前阻断项，P0（内容授权/来源证据）

## 1. Task（要做什么，自包含）

处理墨题发布库中以下两个题包的 provenance 缺口：

1. `wssfk.postgraduate-english-one.2010-2026`
2. `local.english-practice.postgraduate-english-two.2010-2025`

目标不是简单修改数据库字段，而是：

- 收集每个题包真实、可追溯的许可证/授权和来源证据；
- 补齐人工复核、AI 修改差异和发布抽样记录；
- 更新对应 ESQ 包的 `manifest.json`；
- 重新校验、重新导入并生成 release 数据库；
- 重新执行严格发布门禁；
- 只有两个包均满足公开分发条件时，才判定 provenance 处理完成。

如果无法取得真实授权或来源证据，不得标记为 `verified`，应将题包维持为 `pending`，并明确限制为本地/内部使用，阻断公开发布。

## 2. Why this matters（为什么做，优先级）

当前严格发布检查会阻断公开 Windows/APK 发布：

```text
packages_total = 2
packages_with_complete_provenance = 2
packages_publishable = 0
packages_not_publishable = 2
```

两个包虽然具备结构完整性、答案和题型检查结果，但结构检查不能证明题库内容拥有公开分发权。当前 ESQ 声明中存在：

- `license.spdx = NOASSERTION`；
- 来源类型为考生回忆或本地导出；
- 没有许可证核验记录；
- 没有来源核验记录；
- 没有可审计的人工复核、AI diff 和发布抽样证据。

若绕过该门禁，风险不是普通代码 bug，而是内容来源、授权和公开分发责任风险。

## 3. Prior findings verbatim（已有结论原样贴，不许压缩）

以下内容来自当前仓库核验结果，交接时不得改写成“已完成”：

### 题包一

- package：`wssfk.postgraduate-english-one.2010-2026`
- 原包：`examples/bundled-banks/postgraduate-english-one.esq`
- `contentVersion = 1.0.0`
- 原包 SHA-256：`EDE30FAE65F2FBAB53C830BA39EF618E5E82F0FA7EBC789D363093C5C1B47075`
- `license.spdx = NOASSERTION`
- `source.type = candidate_recollection`
- 原始 source 声明：由考生回忆版真题整理并人工校正，非官方发布。

### 题包二

- package：`local.english-practice.postgraduate-english-two.2010-2025`
- 原包：`examples/bundled-banks/postgraduate-english-two.esq`
- `contentVersion = 1.1.1`
- 原包 SHA-256：`D25AC946FA0543A61BEB88EB02664D1E3A55EB819632667603268A6346FE2E83`
- `license.spdx = NOASSERTION`
- `source.type = local_export`
- 原始 source 声明：从英语刷题机本地题库导出。

### 当前发布门禁缺口

两个包均缺少：

```text
license.verified
source.verified
review.status
ai_assist.diff_status
quality.release_sample
```

### 已有文件

- provenance 规则：[docs/content-release-evidence.md](D:/english-multiple-choice-practice-machine/docs/content-release-evidence.md)
- 逐包证据台账：[docs/package-provenance-intake-2026-09-13.md](D:/english-multiple-choice-practice-machine/docs/package-provenance-intake-2026-09-13.md)
- 严格检查器：[tools/release_check.py](D:/english-multiple-choice-practice-machine/tools/release_check.py)
- ESQ 校验器：[tools/validate_question_bank.py](D:/english-multiple-choice-practice-machine/tools/validate_question_bank.py)

## 4. Specific actions（具体步骤）

### 阶段 A：先固定对象，避免证据与包错配

1. 备份或记录当前两个 `.esq` 文件的 SHA-256。
2. 不直接修改 `backend/data/question_bank.db` 中的 `manifest_data`。
3. 不直接修改 `release-manifest.json` 来消除阻断。
4. 保留当前严格检查报告，确保后续能比较前后差异。

### 阶段 B：逐包收集原始证据

对每个 package 分别建立证据目录或证据包，至少包含：

```text
package-id/
  manifest.json
  source-evidence.md
  license-evidence.md
  review-record.md
  ai-diff-record.md
  release-sample.md
  files.sha256
```

每个包必须回答以下问题：

#### 许可证/授权

- 谁是权利人或授权人？
- 授权覆盖哪些年份、题型和文件？
- 是否允许公开下载、随桌面程序分发、随 APK 分发？
- 授权是否有日期、版本或地域限制？
- 证据是原始许可证、授权页面、授权邮件，还是权利人确认？

仅有“学习交流”“本地导出”“考生回忆版”等描述，不足以通过许可证核验。

#### 来源

- 原始 URL、文件路径或授权人联系方式是什么？
- 获取日期是什么？
- 当前 ESQ 包覆盖范围是否与来源范围一致？
- 核验人和核验日期是什么？

#### 人工复核

- 复核了哪些年份/题型/题量？
- 是否存在重复题、答案错位、缺选项、OCR 错误或人工改写？
- 问题如何处理？
- 复核人、复核日期和结论是什么？

#### AI 修改差异

- 如果使用 AI：保存修改前后 diff 或批次记录；
- 如果未使用 AI：明确记录 `not_applicable` 和确认人；
- 不得只写“AI 已检查”，必须能说明 AI 是否改变了题干、选项、答案或解析。

#### 发布抽样

- 抽样范围和样本数量；
- 失败数量；
- 失败项的处理结果；
- 抽样人和日期；
- 结论是否为 `passed` 或 `reviewed`。

### 阶段 C：更新 ESQ，而不是直接改数据库

当且仅当真实证据已经取得：

1. 更新原 ESQ 包的 `manifest.json`：

```json
{
  "license": {
    "spdx": "真实 SPDX 标识",
    "verified": true,
    "verification": {
      "reviewer": "真实核验人",
      "date": "YYYY-MM-DD",
      "evidence": "证据文件或 URL"
    }
  },
  "source": {
    "verified": true,
    "verification": {
      "reviewer": "真实核验人",
      "date": "YYYY-MM-DD",
      "evidence": "来源文件或 URL"
    }
  },
  "review": {
    "status": "reviewed",
    "reviewer": "真实复核人",
    "reviewed_at": "YYYY-MM-DD",
    "scope": "真实复核范围",
    "notes": "真实复核结论"
  },
  "ai_assist": {
    "diff_status": "recorded 或 not_applicable",
    "diff_reference": "真实 diff 或确认记录"
  },
  "quality": {
    "release_sample": {
      "status": "passed 或 reviewed",
      "sample_size": 0,
      "checked_at": "YYYY-MM-DD",
      "reviewer": "真实抽样人",
      "notes": "真实抽样结论"
    }
  }
}
```

2. 重新打包 ESQ。
3. 运行：

```powershell
python tools/validate_question_bank.py examples\bundled-banks\postgraduate-english-one.esq
python tools/validate_question_bank.py examples\bundled-banks\postgraduate-english-two.esq
```

4. 确认 `valid=true` 且 `errors=0`。
5. 通过墨题 ESQ 导入流程重新导入/发布，生成新的 `backend/data/question_bank.db`。

### 阶段 D：重新跑发布门禁

```powershell
.\scripts\release_check.ps1 `
  -RequirePackageProvenance `
  -RequirePublishableProvenance `
  -StrictQuality `
  -RequireAndroidMetadata `
  -CheckTemplates `
  -WriteReport work\release-manifest-publishable.json
```

通过标准：

- 退出码为 `0`；
- `packages_without_provenance = 0`；
- `packages_not_publishable = 0`；
- 两个包的 `license.verified`、`source.verified`、人工复核、AI diff、发布抽样均有证据引用；
- release 数据库 hash 与报告一致。

### 阶段 E：内容发生变化后的全端验证

若重新导入导致题库内容或发布数据库变化，必须重新执行：

1. 后端 PyInstaller 构建；
2. Windows backend smoke；
3. Electron 安装版/便携版重建；
4. Windows portable smoke；
5. 前端 build、bundle gate、offline seed gate；
6. APK `cap sync`、Gradle 构建；
7. 有真机/模拟器时运行 Android runtime smoke；
8. 重新生成 artifact SHA-256。

## 5. Knowledge sources（已知资源/关键词）

### 本地原始资源

- `examples/bundled-banks/postgraduate-english-one.esq`
- `examples/bundled-banks/postgraduate-english-two.esq`
- `backend/data/question_bank.db`
- `backend/app/services/esq.py`
- `backend/app/services/bundled_banks.py`
- `tools/release_check.py`
- `tools/validate_question_bank.py`

### 项目规则

- `docs/content-release-evidence.md`
- `docs/package-provenance-intake-2026-09-13.md`
- `docs/schemas/esq-1.0.schema.json`
- `AGENTS.md` 中的题库发布质量门禁与公开发布证据规则

### 外部核验关键词

仅在确实存在来源线索时检索：

- 原始来源 URL
- 权利人/发布者名称
- 题包标题与年份范围
- 许可证名称或授权声明
- “允许公开分发 / redistribution / educational use”

外部检索结果必须保留 URL、页面标题、获取日期、关键证据位置和本地快照/哈希；搜索摘要不能单独作为授权证据。

## 6. Relevant skills（可复用技能）

- `sora-team-workflow`：8 槽密任务包、阶段验证、证据回报、小步提交；
- `esq-question-bank-import`：ESQ 构造、校验、导入和发布流程；
- `english-practice-machine-dev`：墨题题库、三库同步和项目验证规则；
- `epm-all-end-release`：内容变化后的前后端、Windows、APK 同步构建；
- `codex-security:assess-patch-risk`：如果后续把题包从公开发布范围移除，需要评估分发行为变化，不得静默改变用户可见内容。

## 7. Success criteria（可验证的完成标准）

### 正常完成

- 两个 ESQ 包都有真实许可证/授权证据；
- 两个 ESQ 包都有真实来源核验记录；
- 两个包均具备人工复核、AI diff/不适用声明、发布抽样记录；
- ESQ 校验均为 `valid=true`、错误数为 0；
- 重新导入后严格 release check 退出码为 0；
- `packages_not_publishable = 0`；
- 内容变化后的全端产物和 smoke 结果可追溯；
- Git diff、提交和报告路径明确。

### 证据无法取得时

这不算“发布完成”，但必须交付一个明确的阻断结论：

- 两个包继续为 `pending`；
- 公开 Windows/APK 发布继续阻断；
- 说明缺的是许可证、来源还是复核材料；
- 如需继续提供内部版本，必须明确标记为 local-only/internal-only，并确认没有被公开发布流程打包。

## 8. Report back with（回报格式：结构/长度/证据要求）

请按以下结构回报：

```text
结论：已解除 / 仍阻断

1. 题包证据状态
| package_id | license | source | review | ai_diff | sample | 结论 |

2. 原包与新包指纹
| package_id | old_sha256 | new_sha256 | content_version |

3. 实际修改
- manifest 文件路径
- 证据文件路径或 URL
- 是否重新导入数据库
- 是否改变题库内容/数量

4. 验证结果
- validate_question_bank：结果
- release_check：退出码和 packages_not_publishable
- strict quality：关键计数
- Windows/APK smoke：结果

5. Git 状态
- commit hash
- working tree 是否干净
- 是否 push

6. 未完成项
- 逐项写清阻断原因和需要谁提供什么材料
```

禁止只回报“已补齐”“门禁通过”而不提供原始证据路径、包 hash、命令结果和 release 报告。

