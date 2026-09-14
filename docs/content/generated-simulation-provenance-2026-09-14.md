# 原创 AI 模拟题包 provenance 记录（2026-09-14）

本记录对应公开 starter 目录中的两个替代 ESQ 包。它们用于替代未取得公开分发授权的考研英语考生回忆版/本地导出包，不是官方真题，也不声称获得教育考试机构授权。

> 注意：下方最初的 48 套/827 题记录属于 r1 历史构建。2026-09-14 的 r2 逐卷 provenance 收口已将未登记或不可发布的历史题卷隔离；当前公开库以本文末尾的 r2 记录为准。旧 r1 安装包、APK 和数据库 hash 不得继续作为当前发布证据。

## 包与生成物

| package_id | 文件 | 内容 | 题量 |
|---|---|---|---:|
| `motei.ai.postgraduate-english-one.sim-2026` | `examples/bundled-banks/postgraduate-english-one.esq` | 6 套 AI 模拟卷、完形/阅读/新题型 | 90 |
| `motei.ai.postgraduate-english-two.sim-2026` | `examples/bundled-banks/postgraduate-english-two.esq` | 6 套 AI 模拟卷、完形/阅读/新题型 | 90 |

生成入口：`tools/generate_ai_simulation_banks.py`。

生成包 SHA-256：

- `postgraduate-english-one.esq`: `D2703F9B0CA9BBDA251843933D3A0CBF456D29FACE5883C837E26B79241C2A93`
- `postgraduate-english-two.esq`: `9EFF6A673FE02A8552E630954CDBBC3F90E697F49E32838F0FB61C4609F17D00`

生成内容使用项目自有主题种子和模板，不读取原两个 ESQ 包的题干、选项、答案、解析或标签；生成器不引用官方真题、考生回忆文本或本地导出内容。

## 授权与来源声明

- `license.spdx = CC0-1.0`：这是墨题项目对本次自建模拟内容作出的项目方公开使用声明，不是第三方官方授权。
- `license.verified = true`：核验对象是“内容由本项目生成且不依赖原真题文本”的生成记录；不代表官方考试内容授权。
- `source.type = ai_generated`；`source.verified = true`：来源为仓库内可复现的生成脚本和原创主题种子。
- 原考研英语（一/二）包仍保留在本机忽略目录 `examples/internal-banks/`，不作为模拟题生成输入，也不进入公开资源目录。

## 质量记录

- ESQ 校验：两个包均 `valid=true`，各 6 套、18 个单元、90 道题，错误数为 0。
- 历史 r1 重建的 release/offline 数量与 hash 见本文顶部说明；该记录不再代表当前可发布内容。
- 答案映射：每道题均有答案，答案选项均存在于对应选项集合。
- 题型覆盖：每包包含 `cloze`、`reading`、`part_b` 三类单元。
- 抽样复核：每包抽查 12 道题，检查题干、选项、答案映射和“AI 模拟·非真题”标识。
- AI 差异记录：内容由生成器直接创建，没有对原题包进行 AI 改写；记录为 `recorded`，参考 `tools/generate_ai_simulation_banks.py`。

## 发布边界

这两个新包只有在重新导入 release 数据库、同步离线种子并通过严格 `release_check` 后，才可进入公开 Windows/APK/Web 发布流程。原两个未授权包必须保持 local-only，不得被重新复制到公开 starter 目录或离线数据库。

## r2 逐卷 provenance 收口证据

- 内容版本：`content-2026-09-14-r2`；离线种子版本：`offline-2026-09-14-r2`。
- 活跃公开内容：12 套试卷、95 个单元、668 道题、7,958 个词汇条目；release 数据库物理上另保留 26 条历史删除题卷记录。
- 本轮隔离：7 个不可公开 package identity，共移除 10 条公开题卷、38 个单元和 159 道题。
- release 数据库 SHA-256：`FFDCB436A9CC93E7E21EAE2C5407FA0880C491D660366C1A870CA1EADE8A934B`。
- offline 数据库 SHA-256：`F513F26D09ED8C0339A481720C1AC3610F6D2C3DC4073BCDCFAACAFF81EFAA67`。
- 严格 `release_check`：退出码 `0`；`packages_not_publishable=0`；逐卷 `papers_not_publishable=0`。
- 离线公共种子中的练习、考试、错题、FSRS 和本地指标运行数据均为 0，避免把本机状态带入分发包。
