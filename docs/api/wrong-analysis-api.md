# 错题知识点归因分析 API（v3.0）

> 后端路由：`backend/app/routers/wrong_analysis.py`（`prefix=/api/wrong/analysis`）
> 服务层：`backend/app/services/wrong_analysis.py`
> 数据表：`wrong_knowledge_points` / `wrong_cause_diagnoses` / `wrong_cause_snapshots` / `wrong_kp_snapshots` / `wrong_cause_mastery`（迁移见 `docs/schemas/wrong_analysis_v3.sql`）
>
> 隐私边界：AI 归因在后台完成，面向本 API 返回的所有建议文案均来自本地白名单
> （`CAUSE_GUIDANCE` / 知识点目录 / `CAUSE_WEEKLY_PLANS`），不含题目原文。

## 总览

| 方法 | 路径 | 用途 |
|:---|:---|:---|
| POST | `/api/wrong/analysis/run` | 运行一次完整归因分析（12 分类 → 知识点 → 建议 → 趋势） |
| GET | `/api/wrong/analysis/report/{report_id}` | 读取单份归因报告（含逐题明细） |
| GET | `/api/wrong/analysis/history` | 历史归因分析列表 |
| GET | `/api/wrong/analysis/trend` | 趋势追踪（快照序列 + 掌握度档案 + 显著变化） |
| GET | `/api/wrong/analysis/knowledge-points` | 知识点跨报告累计统计 |
| GET | `/api/wrong/analysis/suggestions` | 学习建议（最新或指定报告） |
| GET | `/api/wrong/analysis/meta` | 12 分类 + 知识点白名单目录（图例用） |

---

## 1. POST `/api/wrong/analysis/run`

运行归因分析。归因明细、知识点快照、12 分类快照、掌握度档案全部落库。

### 请求体（JSON）

| 字段 | 类型 | 必填 | 说明 |
|:---|:---|:---|:---|
| `question_ids` | `int[]` | 否 | 分析范围；**为空时自动选取高频错题**（`wrong_count >= 3` 或手动标记，至多 20 道，按错误次数降序） |
| `scope_title` | `string` | 否 | 分析范围标题（如 `"2025 年"`），默认 `"错题归因（N 道）"` |
| `scope_key` | `string` | 否 | 范围去重键（沿用 `/ai/analyze-wrong` 的 `unit_ids` 排序串约定） |
| `unit_ids` | `int[]` | 否 | 涉及篇目 id，用于同步 `wrong_analysis_states` 锁定状态 |
| `with_ai_report` | `bool` | 否 | 是否生成 AI 匿名总结报告（默认 `true`；`false` 时纯本地，速度快） |

```json
{
  "question_ids": [101, 102, 103, 108],
  "scope_title": "2025 年完形填空",
  "unit_ids": [12],
  "with_ai_report": true
}
```

### 返回（200）

```jsonc
{
  "report_id": 7,
  "scope_title": "2025 年完形填空",
  "scope_key": "12",
  // 逐题归因明细（同时已写入 wrong_cause_diagnoses 表）
  "diagnoses": [
    {
      "question_id": 101,
      "primary_cause": "vocabulary",
      "secondary_causes": ["context"],
      "knowledge_points": ["vocab_synonym", "vocab_polysemy"],
      "confidence": 0.85,
      "reason_codes": ["近义词边界不清"],
      "recommended_actions": ["先概括空格所需语义再比较选项"]
    }
  ],
  // 12 分类聚合
  "aggregate": {
    "question_count": 4,
    "categories": [
      { "code": "vocabulary", "label": "词汇基础与词义辨析", "count": 2,
        "percentage": 50, "average_confidence": 0.82 }
    ],
    "recommended_actions": ["复习近义词、熟词僻义与语境词义……"],
    "uncertain_count": 0
  },
  // 知识点聚合（本次命中）
  "knowledge_points": [
    { "code": "vocab_synonym", "label": "近义词边界不清", "cause_code": "vocabulary",
      "cause_label": "词汇基础与词义辨析", "hit_count": 2, "percentage": 40,
      "guidance": "成对整理近义词，各写一个例句并标注差异维度。" }
  ],
  // 学习建议（本地白名单生成）
  "suggestions": {
    "report_id": 7,
    "generated_at": "2026-08-16 22:10:03",
    "priority_order": ["vocabulary", "context"],
    "suggestions": [
      {
        "cause_code": "vocabulary",
        "label": "词汇基础与词义辨析",
        "question_count": 2,
        "percentage": 50,
        "average_confidence": 0.82,
        "priority_score": 41.0,            // 占比% × max(0.35, 置信度)
        "immediate_actions": ["复习近义词、熟词僻义与语境词义……"],
        "knowledge_points": [
          { "code": "vocab_synonym", "label": "近义词边界不清", "hit_count": 2,
            "guidance": "成对整理近义词，各写一个例句并标注差异维度。" }
        ],
        "weekly_plan": [
          { "days": "第 1-2 天", "task": "把本次归因到词汇题的近义词/僻义整理成对照表……" },
          { "days": "第 3-4 天", "task": "每天精做 1 篇完形……" },
          { "days": "第 5-7 天", "task": "隔天重做本范围错题……" }
        ],
        "recommended_unit_types": ["完形填空", "词汇运用"],
        "trend": { "recent_percentage": 50, "previous_percentage": 66,
                   "trend_direction": "improving", "mastery_score": 55 }
      }
    ],
    "top_weakness": { "cause_code": "vocabulary", "label": "词汇基础与词义辨析", "percentage": 50 },
    "overall_summary": ["词汇基础与词义辨析占 50%（2 道），优先执行：复习近义词……"]
  },
  // 本次 vs 上次的趋势对比
  "trend": {
    "report_id": 7,
    "has_previous": true,
    "improved":  [{ "code": "vocabulary", "label": "词汇基础与词义辨析",
                    "previous_percentage": 66, "percentage": 50, "delta": -16 }],
    "worsened":  [{ "code": "grammar", "label": "语法结构",
                    "previous_percentage": 0, "percentage": 25, "delta": 25 }],
    "new":       [],
    "captured_at": "2026-08-16 22:10:03"
  },
  "report": "（AI 匿名中文总结，500-900 字；with_ai_report=false 时为空字符串）",
  "model_name": "deepseek-v4-flash"
}
```

### 错误

| 状态码 | 场景 |
|:---|:---|
| 400 | 没有可分析的错题 / AI 调用失败（含网络、解析异常） |
| 422 | 归因服务返回业务错误（如题目无作答记录） |

---

## 2. GET `/api/wrong/analysis/report/{report_id}`

### 参数

| 位置 | 参数 | 类型 | 说明 |
|:---|:---|:---|:---|
| path | `report_id` | `int` | 报告 id |

### 返回（200）

结构同 `POST /run` 的主结构，但 `diagnoses` 每项额外带展示字段：

```jsonc
{
  "report_id": 7,
  "scope_key": "12",
  "scope_title": "2025 年完形填空",
  "question_count": 4,
  "aggregate": { /* 同上 */ },
  "diagnoses": [
    {
      "question_id": 101,
      "primary_cause": "vocabulary",
      "primary_cause_label": "词汇基础与词义辨析",
      "secondary_causes": ["context"],
      "knowledge_points": [{ "code": "vocab_synonym", "label": "近义词边界不清" }],
      "confidence": 0.85,
      "reason_codes": ["近义词边界不清"],
      "recommended_actions": ["……"],
      "number": 15,                    // 题号
      "stem": "The word “x” is closest…", // 截断到 80 字符
      "unit_title": "2025 完形 Text 1",
      "unit_type": "完形填空",
      "year": 2025
    }
  ],
  "knowledge_points": [ /* 本次快照（code/label/cause_code/cause_label/hit_count/percentage） */ ],
  "suggestions": { /* 同上 */ },
  "report": "……",
  "model_name": "deepseek-v4-flash",
  "created_at": "2026-08-16 22:10:05"
}
```

### 错误：`404` 报告不存在。

---

## 3. GET `/api/wrong/analysis/history`

### 参数：`limit`（query，int，默认 20，上限 50）

### 返回（200）

```jsonc
{
  "items": [
    {
      "report_id": 7,
      "scope_title": "2025 年完形填空",
      "question_count": 4,
      "detail_count": 4,               // 逐题明细条数
      "knowledge_point_count": 6,      // 知识点快照条数
      "top_categories": [
        { "code": "vocabulary", "label": "词汇基础与词义辨析", "percentage": 50 }
      ],
      "created_at": "2026-08-16 22:10:05"
    }
  ]
}
```

> 只列出包含逐题明细（`wrong_cause_diagnoses` 有记录）的报告；旧版 `/ai/analyze-wrong` 只存聚合，不会混入。

---

## 4. GET `/api/wrong/analysis/trend`

### 参数：`limit`（query，int，默认 8，上限 20——取最近 N 次报告）

### 返回（200）

```jsonc
{
  "series": [                       // 时间升序，直接喂折线图
    {
      "report_id": 6,
      "scope_title": "2025 年阅读",
      "question_count": 6,
      "captured_at": "2026-08-10 21:00:12",
      "categories": {               // 12 分类齐全（未出现计 0）
        "vocabulary": { "percentage": 66, "count": 4, "average_confidence": 0.8 },
        "grammar":    { "percentage": 0,  "count": 0, "average_confidence": 0 }
        // ……其余 10 类
      }
    }
  ],
  "mastery": [                      // 掌握度档案（排除 uncertain，按掌握分升序 = 最薄弱在前）
    {
      "cause_code": "vocabulary",
      "label": "词汇基础与词义辨析",
      "recent_percentage": 50,       // 最近一次快照占比
      "previous_percentage": 66,     // 上一次快照占比
      "trend_direction": "improving",// improving | worsening | stable
      "mastery_score": 55,           // 0-100 = 100 - 近 8 次快照平均占比
      "total_occurrences": 9,        // 历史累计错误题次
      "report_count": 3,             // 出现过的报告次数
      "last_seen_at": "2026-08-16 22:10:03"
    }
  ],
  "highlights": [                   // 最近两次快照对比的显著变化（|Δ| ≥ 3pt，前 5 条）
    { "code": "grammar", "label": "语法结构", "delta": 25, "direction": "worsening" }
  ],
  "snapshot_count": 2,
  "tracked_causes": 12
}
```

---

## 5. GET `/api/wrong/analysis/knowledge-points`

### 参数：`limit`（query，int，默认 20，上限 50）

### 返回（200）

```jsonc
{
  "items": [
    {
      "code": "vocab_synonym",
      "label": "近义词边界不清",
      "cause_code": "vocabulary",
      "cause_label": "词汇基础与词义辨析",
      "total_hits": 7,           // 跨全部报告累计命中
      "report_count": 3,         // 出现过的报告数
      "last_seen_at": "2026-08-16 22:10:03",
      "guidance": "成对整理近义词，各写一个例句并标注差异维度。"
    }
  ]
}
```

---

## 6. GET `/api/wrong/analysis/suggestions`

### 参数：`report_id`（query，int，可选——缺省取最近一份含明细的报告）

### 返回（200）：结构同 `POST /run` 返回中的 `suggestions` 对象。

### 错误

- `404` 没有归因分析记录（从未运行过）或 report_id 不存在。

---

## 7. GET `/api/wrong/analysis/meta`

无需数据库，返回静态目录（前端图例 / 筛选器使用）。

```jsonc
{
  "causes": [ { "code": "vocabulary", "label": "词汇基础与词义辨析" }, /* 共 12 项 */ ],
  "knowledge_points": {
    "vocabulary": [ { "code": "vocab_synonym", "label": "近义词边界不清" }, /* 5 项 */ ],
    "grammar":    [ { "code": "gram_tense", "label": "时态与语态" }, /* 7 项 */ ]
    // ……每类下的知识点白名单
  }
}
```

---

## 12 分类代码表

| code | 标签 | code | 标签 |
|:---|:---|:---|:---|
| `vocabulary` | 词汇基础与词义辨析 | `inference` | 推理判断 |
| `collocation` | 固定搭配 | `main_idea` | 主旨概括 |
| `grammar` | 语法结构 | `attitude` | 作者态度 |
| `context` | 上下文逻辑 | `trap` | 干扰项排除 |
| `discourse` | 篇章衔接 | `carelessness` | 审题与细节疏忽 |
| `detail` | 细节定位 | `uncertain` | 证据不足，暂不能确定 |

## 前端对接

- 组件：`frontend/src/components/WrongAnalysisPanel.vue`（四标签页面板）
- 图表：`frontend/src/components/charts/`（DonutChart / RadarChart / TrendLineChart，纯 SVG 零依赖）
- 调用方：`frontend/src/views/WrongView.vue`（页头「🧩 知识点归因」+ 年份行「归因」按钮）
- 离线模式：`get/post` 走 `services/api-adapter`（sql.js），接口路径不变。

## 变更记录

- v3.0（2026-08-16）：初次实现——12 分类归因 + 知识点白名单 + 本地学习建议 + 快照/掌握度趋势追踪。
