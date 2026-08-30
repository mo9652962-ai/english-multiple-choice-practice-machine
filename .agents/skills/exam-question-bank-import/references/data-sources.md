# 真题数据源明细（2026-08 实测可用）

## 仓库与关键文件
```bash
# 高考（高中英语）— 完形/七选五带答案，最高价值
git clone --depth 1 https://github.com/OpenLMLab/GAOKAO-Bench          # 2010-2022
git clone --depth 1 https://github.com/OpenLMLab/GAOKAO-Bench-Updates  # 2023-2024
# Data/Objective_Questions/{year}_English_Fill_in_Blanks.json = 完形
# Data/Objective_Questions/{year}_English_Cloze_Test.json     = 七选五

# 四六级 — markdown 全文（含选词填空 Section A）
git clone --depth 1 https://github.com/wamich/english-exem-md
# CET4|CET6/2023.06|cet4-2023-06-1.md 等；2023.12 部分文件格式不同

# 考研一 — LaTeX 全文 2001-2023
git clone --depth 1 https://github.com/ayaka-notes/201-english
# 1/2019年-英语一.tex 等；Part B 排序/七选五/标题 3 种形式轮换

# 考研一 — JSON 1998-2025（最高价值！阅读+新题型完整）
git clone --depth 1 https://github.com/XixiGod7/kaoyan-english
# public/data/2024.json, 2025.json 等
# sections: {cloze: {article, text(选项)}, reading-a: {texts[], questions[]}, new-type: {questions[]}}
# 阅读 texts[ti].article + questions[ti*5+21..ti*5+25] 每题有 choices[{label, text}]
# 新题型 questions 每题有 stem(文章片段) + choices[{label, text}]
# 完形 text 是选项行（1.[A]xxx [B]xxx...），article 数字空位需替换为 {{blank:N}}

# 考研二 — PDF（部分字体编码乱码）
git clone --depth 1 https://github.com/Fantasia1999/kaoyanzhenti
# 公共课/英语真题/英语二/*.pdf

# 真题高频词（kajweb）— JSONL 每行一个对象
git clone --depth 1 https://github.com/kajweb/dict
# book/1521164649209_CET4_1.zip = 四级真题核心词 1162
# book/1521164668667_CET6_1.zip = 六级真题核心词 1228
# book/1521164669833_KaoYan_1.zip = 考研必考词汇 1341
# JSONL 字段: wordRank / headWord / content.word.content.{trans[{pos,tranCn}], usphone, syno}

# 完整词库（kylebing）— txt word\t释义
git clone --depth 1 https://github.com/KyleBing/english-vocabulary
# "2 高中-乱序.txt" "3 四级-乱序.txt" "4 六级-乱序.txt" "5 考研-乱序.txt"
```

## 被挡数据源（2026-08 实测，勿再浪费时间）
| 源 | 年份 | 障碍 |
|:---|:---|:---|
| zhenti.burningvocabulary.cn | 四六级/考研全 | 登录 + JS 渲染 |
| wehuster.com | 四六级 2024-2025 PDF | Cloudflare 防护 |
| 163.com 高考真题 | 2026 | 图片版（jpg）|
| en-sky.com 高考 | 2026 | 百度网盘提取码 |
| 51jiaoxi 教习网 | 高考文字版 | 需账号 |
| 中国教育在线 kaoyan.eol.cn | 考研 | 页面正文图片 |
| 启航考研 jixun.iqihang.com | 2025 考研二 | 图片 PNG（真题+解析，可 OCR） |

→ 以上一律用基元律动 AI 模拟补（标注"AI 模拟题·非真题"）

## 高频词分类设计（前端双维 chips）
- category 格式: "四级·高频" / "考研·热点" / "高中·高频" / 基础词保持 "四级" 等
- 前端 chips: 级别行（全部/高中/四级/六级/考研）+ 类型行（全部/⭐高频/🔥热点/📚基础词）
- 组合参数: `category=高中·高频`（后端 LIKE 前缀匹配）
