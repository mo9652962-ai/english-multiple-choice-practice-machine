# 词汇双语例句数据

v2.0.0-beta.16 将双语例句从词汇条目中拆成独立的 `vocabulary_examples` 表。这样可以为每条例句保留来源、来源链接和人工核验状态，也不会覆盖用户自己的词汇记录。

## 输入格式

维护者可以使用 JSONL 文件导入已获得授权、已完成校对的例句。每行对应一个词：

```json
{"term":"abandon","examples":[{"english":"The team had to abandon the plan after the deadline changed.","chinese":"截止日期改变后，团队只好放弃这个计划。","source":"editorial","source_url":"https://example.invalid/source","verified":true}]}
```

字段说明：

| 字段 | 必填 | 说明 |
|:---|:---:|:---|
| `term` | 是 | 对应词汇库中的单词或短语；按小写标准化匹配 |
| `examples` | 是 | 一个或多个例句对象 |
| `english` | 是 | 10–500 个字符的英文句子 |
| `chinese` | 是 | 2–500 个字符的中文翻译 |
| `source` | 否 | 数据源或编辑来源 |
| `source_url` | 否 | 可核验的来源链接 |
| `verified` | 否 | `true` 表示已人工核验；已核验翻译不会被普通导入覆盖 |

也兼容 `sentence`、`translation`、`example` 和 JSON 数组格式，方便将已有的审校数据转换后接入。

## 导入与检查

先执行 dry-run 检查，不写入数据库：

```powershell
python tools/import_vocabulary_examples.py .\data\vocabulary-examples.jsonl --dry-run
```

确认统计和错误后，再写入运行数据库：

```powershell
python tools/import_vocabulary_examples.py .\data\vocabulary-examples.jsonl
python tools/verify_release_data.py --check-templates
```

导入器具有幂等性：相同单词和英文句子重复导入时会更新来源信息；已核验的中文翻译保持不变。缺少词条、缺少中英任一侧或句子长度不合规时，整批返回错误，避免形成半套数据。

## 发布要求

例句正文和翻译不随代码仓库自动生成。发布前应提供可再分发的来源和授权说明，并将审校后的数据文件作为受控构建输入。公开 CI 只检查表结构和数据质量门槛；含个人题库、未授权真题或 API 返回原文的数据库仍应放在本地/私有构建环境，不能提交到 GitHub。

四六级真题同样建议通过 ESQ 包导入。导入包应声明来源、许可证、年份、套次和答案来源；`/api/exam-templates` 可供导入器读取 CET-4、CET-6 及其他考试模板的题号骨架。
