# 批量导入真题

批量导入工具适合一次处理考研英语二、大学英语四级、大学英语六级等多年份、多场次题库。它复用桌面端现有导入接口，不直接修改 SQLite 数据库，因此单篇导入和批量导入遵循同一套解析、模型校对、草稿审核与发布规则。

## 工作流程

1. 递归扫描目录中的 `.doc` / `.docx` / 文本型 `.pdf` 试卷。
2. 按文件名、年份和所在目录配对含“答案 / answer / key / 解析”等字样的 `.doc`、`.docx` 或 `.pdf` 答案附件。
3. 按同目录和年份自动附带 `.mp3` 听力文件。
4. 上传本地解析草稿。
5. 全量调用指定模型校对答案、题号和结构；调用失败时保留本地草稿。
6. 默认将结果留在“导入题库”页面人工审核；可选仅自动发布无警告草稿。
7. 试卷入库后自动启动题目智能标注；听力题会在服务层统一排除，不计入标注进度，也不会发送给模型。
8. 每篇结果写入本地状态文件，断线或退出后再次运行会跳过内容未变化的已完成文件。

## 使用前准备

- 先启动 Windows 本地版英语刷题机。
- 在“模型与 API”中保存并启用基元律动配置。
- Base URL 使用 `https://tokenrhythm.studio/v1`。
- 拉取模型列表后选择 `deepseek-v4-flash`，或记录需要使用的模型 ID。
- 在“题库配置”中创建目标配置，并记下目标配置 ID。

工具不会读取、保存或输出 API Key；所有模型请求都由本地刷题机后端使用已加密保存的 API 配置发起。

## 推荐命令

先只扫描配对：

```powershell
.\.venv\Scripts\python.exe tools\batch_import.py `
  --source "C:\题库\考研英语二" `
  --profile-id 2 `
  --dry-run
```

批量建立草稿并进行高精度模型校对：

```powershell
.\.venv\Scripts\python.exe tools\batch_import.py `
  --source "C:\题库\考研英语二" `
  --profile-id 2 `
  --ai-profile-id 3 `
  --model deepseek-v4-flash `
  --correct-structure `
  --max-output-tokens 12000 `
  --workers 2
```

只自动发布完全无警告的草稿：

```powershell
.\.venv\Scripts\python.exe tools\batch_import.py `
  --source "C:\题库\大学英语四级" `
  --profile-id 3 `
  --ai-profile-id 3 `
  --model deepseek-v4-flash `
  --correct-structure `
  --publish-clean `
  --workers 2
```

## 参数建议

- `--workers 2`：推荐起点。可在供应商稳定且文件较小时提高到 3-4；大量 429/503 时降低到 1。
- `--retries 4`：对 429、500、502、503、504 和网络瞬断进行指数退避重试。
- `--max-output-tokens 12000`：适合完整试卷的答案映射与结构修正 JSON；若供应商返回输出长度超限，可按模型限制调低。
- `--correct-structure`：允许模型直接修正题干、选项归属和题号。批量建库时建议启用。
- `--publish-clean`：仅自动发布没有校验警告的草稿。首次批量导入建议先不启用，抽检稳定后再启用。
- 智能标注默认在成功入库后立即开始；若本次不需要，可临时增加 `--skip-labeling`。
- `--force-publish`：忽略警告强制发布，通常不建议使用。
- `--limit N`：先导入前 N 篇做小样本验证。

## 文件组织建议

每套试卷放在独立目录中最稳妥：

```text
大学英语四级题库/
├── 2023-06-第一套/
│   ├── 2023年6月四级第一套.docx
│   ├── 2023年6月四级第一套答案.pdf
│   └── 2023年6月四级第一套听力.mp3
└── 2023-12-第一套/
    ├── 2023年12月四级第一套.docx
    ├── 2023年12月四级第一套答案.docx
    └── 2023年12月四级第一套听力.mp3
```

如果答案文件没有“答案 / answer / key / 解析”等标识，工具会将该试卷标记为“未配对答案”并继续建立草稿，不会猜测答案文件。

## 断点续跑与隐私

默认状态文件为 `.codex-local/batch-import-state.json`，已加入 Git 忽略。它记录文件路径、内容哈希、导入任务 ID、状态和简短错误，不记录 API Key、题库正文或答案正文。

若修正了原文件，内容哈希会变化，下一次运行将自动重新处理该篇。若只想重新处理失败项，直接重复原命令即可。

## 基元律动接口依据

- 快速开始：`https://tokenrhythm.studio/docs/overview`
- API 接入与多协议支持：`https://tokenrhythm.studio/docs/api-integration`
- 错误码：`https://tokenrhythm.studio/docs/errors`
- 模型能力与价格：`https://tokenrhythm.studio/models`

实现使用平台文档所列的 OpenAI 兼容接口、Bearer 鉴权、`GET /v1/models` 模型发现和 `POST /v1/chat/completions` 对话协议。工具本身只调用刷题机本地接口，由后端统一管理密钥和供应商协议。
