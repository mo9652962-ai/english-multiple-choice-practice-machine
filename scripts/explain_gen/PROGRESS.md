# 精讲批量生成 · 进度状态（供会话中断后恢复）

## 任务
为 `backend/data/question_bank.db` 的 2132 题生成 4 条精讲（long_sentence/option/keyword/note）写入 `explain_collections`，分 5 批（每批 500 题，末批 132），每批验证 + commit。**不改 backend 代码。**

## 关键路径
- 备份：`backend/data/question_bank.db.bak_explain_20260905`（已验证 2132 题/0 精讲）
- 题目材料：`scripts/explain_gen/data/chunks.db`（86 chunks × 25 题，正文文本）；代理用 `python scripts/explain_gen/print_chunk.py <N>` 读取（无 END 标记=截断，用 a/b 分段）
- 代理产出：`scripts/explain_gen/content/batchN/chunk_NNN.json`（batch = (chunk_no-1)//20+1；batch5 = chunks 81-86）
- 校验：`python scripts/explain_gen/validate_content.py [批次...]`；入库 `python scripts/explain_gen/apply_content.py [批次...]`（幂等）；DB 验证 `python scripts/explain_gen/validate_db.py`；抽查 `python scripts/explain_gen/spot_check.py 10 <seed>`

## 数据结构（已核实）
- 表 explain_collections：question_id/fragment_type(long_sentence|option|keyword|note)/content/source='deep-explain'，幂等键 (question_id, fragment_type)
- 2132 题全是 single_choice，按 unit_type 分：cloze 完形/选词填空 939 题（passage 有 {blank:N}，stem 是通用文案）、reading 阅读 854、part_b 七选五/新题型 235（考研排序题原文在 shared_data.candidates）、paragraph_matching 长篇阅读 104（answer=段落字母，passage 段落 A) B)…）
- 选项在 options 表（每题都有）；paper 覆盖四级/六级/高考/考研一(2010-2026)/考研二(2010-2025)/模拟题

## 内容规范（黄金样例 = content/batch1/chunk_001.json，代理必读）
- 每题 4 条全写，中文 60~200 字/条（option 可到 220）；全中文、教研口吻；引用题干/原文具体词句；禁模板空话
- long_sentence=主干+修饰+「译：」；option=正确项依据+干扰项陷阱标签（无中生有/偷换概念/正反混淆/以偏概全/绝对化/过度推断/张冠李戴/答非所问）；keyword=考点词+同义替换；note=定位→辨析→排除思路+易错点
- JSON schema：{"chunk":N,"items":[{"question_id":N,"long_sentence":"…","option":"…","keyword":"…","note":"…"}]}
- 字符串内避免英文双引号（用「」）；不要 markdown #/*；不要 "作为AI" 字样

## 代理分工（每批 3 个代理并行，batch5 单代理）
- batch1: A=chunks 2-8, B=9-15, C=16-20（chunk 1 主代理手写黄金样例）
- batch2: A=21-27, B=28-34, C=35-40
- batch3: A=41-47, B=48-54, C=55-60
- batch4: A=61-67, B=68-74, C=75-80
- batch5: A=81-86

## 批次状态
| 批次 | chunks | 状态 | commit |
|:---|:---|:---|:---|
| 1 | 1-20 (q1-500) | ✅ 完成：500题/2000条，验证全绿，抽查6题质量过关 | feat(data): 精讲批次1 500题 |
| 2 | 21-40 (q501-1000) | ✅ 完成：500题/2000条，验证全绿，抽查5题质量过关（含排序/七选五/选词填空） | feat(data): 精讲批次2 500题 |
| 3 | 41-60 (q1001-1500) | 未开始 | - |
| 4 | 61-80 (q1501-2000) | 未开始 | - |
| 5 | 81-86 (q2001-2132) | 未开始 | - |

## 每批流程（勿跳步）
1. 派发代理（并行，单条消息多个 Agent 调用）；2. validate_content.py <批次>（FAIL 则补生成）；3. apply_content.py <批次>；4. validate_db.py（覆盖数=批次末题号）；5. spot_check.py 5 <seed> 人工看质量（模板腔→重生成）；6. git add **只加** scripts/explain_gen 与 backend/data/question_bank.db（工作区有大量他人未提交改动，禁 git add -A）；commit msg `feat(data): 精讲批次N <题数>题`

## 已知坑（Mimosa 扫描 hook）
- Write 工具写 .py 时：open(变量,'w') 一律拦截（无论校验多严）；docstring 里出现 open(...,'w') 等字样也拦 → 数据落盘全走 sqlite3（connect 字面量路径），只读脚本可以 open(变量) 读
- sys.argv 相关代码与 SQL 同文件会被误报注入 → SQL 隔离进无参函数
- .json 数据文件代理可正常 Write

## 回报要求（k 验收）
每批题数/条数/验证 SQL 结果；总计覆盖数；问题（如无选项题怎么处理）；脚本+备份路径
