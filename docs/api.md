# API 接口文档

本文档记录所有 API 端点的详细信息。

---

## 基础信息

**Base URL:** `/api`

**响应格式:** 所有接口（除 `/api/health`）统一返回：

```json
{
  "code": 0,
  "data": { ... },
  "message": "ok"
}
```

**错误码:**

| code | 含义 | HTTP 状态码 |
|------|------|------------|
| 0 | 成功 | 200 |
| 40001 | 参数校验失败 | 422 |
| 40101 | API 未认证（预留） | 401 |
| 40401 | 资源不存在 | 404 |
| 50001 | 服务内部错误 | 500 |
| 50002 | 数据库错误 | 500 |
| 50003 | 上游 API 超时 | 504 |
| 50004 | LLM Provider 不可用 | 503 |

当前实现中：
- `HTTPException` 会按 HTTP 状态映射到项目错误码，例如 404 → `40401`。
- FastAPI 参数校验错误统一返回 HTTP 422 + `code=40001`。
- 未捕获异常统一返回 HTTP 500 + `code=50001`。

---

## 健康检查

### GET /api/health

健康检查接口，不包信封。

**响应:**
```json
{"status": "ok"}
```

---

## 文章接口

### GET /api/articles

文章列表（支持分页、来源筛选）。只返回 `status='approved'` 的文章。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| query | string | "" | 搜索关键词，走 FTS5 |
| source | string | "" | 来源筛选 |
| days | int | 30 | 近 N 个自然日（含今天） |
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页条数 |

**响应:**
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": 1,
        "title": "Example",
        "url": "https://example.com",
        "source": "rss",
        "source_id": "rss_36kr",
        "tags": ["AI"]
      }
    ],
    "total": 18250,
    "page": 1,
    "page_size": 20
  },
  "message": "ok"
}
```

### GET /api/articles/{article_id}

文章详情。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| article_id | int | 文章ID |

**响应:** 返回文章正文信息，并附加：

- `tags`：全部标签。
- `dimensions`：标准化四维审核评分，每项包含 `score`、`max_score`、`reason`。普通文章新写入使用 `ai_relevance/engineering_relevance/content_depth/info_density`；历史普通文章可能仍包含 `timeliness`；GitHub repo 默认使用 `ai_relevance/developer_utility/project_signal/content_clarity`；`github_data_infra` 使用 `data_infra_relevance/developer_utility/project_signal/content_clarity`。
- `deep_report`：关联的当前公开版本 completed 深度报告摘要；不存在时为 `null`。

内部存储字段 `extra_data` 不直接返回。

```json
{
  "code": 0,
  "data": {
    "id": 1,
    "title": "Example",
    "url": "https://example.com",
    "description": "原始简介",
    "summary": "AI 中文摘要",
    "source": "github",
    "source_id": "github_ai_devtools",
    "source_detail": "org/repo",
    "published_at": "2026-06-19T08:00:00+08:00",
    "collected_at": "2026-06-20T10:00:00+08:00",
    "relevance_score": 85,
    "tags": ["Agent"],
    "dimensions": {
      "ai_relevance": {
        "score": 35,
        "max_score": 35,
        "reason": "与 Agent 开发直接相关"
      },
      "developer_utility": {
        "score": 23,
        "max_score": 30,
        "reason": "能直接改善开发流程"
      }
    },
    "deep_report": {
      "id": 12,
      "repo_name": "org/repo",
      "candidate_score": 92,
      "trigger_reason": "值得深入评估",
      "url": "/deep-report.html?id=12"
    }
  },
  "message": "ok"
}
```

**错误:** 40401 - 文章不存在

### GET /api/search

全文搜索（FTS5）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| q | string | - | 搜索关键词（必填） |
| limit | int | 20 | 返回条数 |

**响应:** `total` 为本次返回数量。
```json
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 18250
  },
  "message": "ok"
}
```

---

## 统计接口

### GET /api/dashboard/summary

仪表盘首屏 KPI 聚合接口。该接口只返回首屏需要的摘要数据；各 Tab 仍使用对应领域接口懒加载。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 7 | 近 N 个自然日（含今天，1-3650） |

**响应:**
```json
{
  "code": 0,
  "data": {
    "total_articles": 125,
    "period_articles": 40,
    "period_cost": 0.5,
    "total_cost": 5.0,
    "active_sources": 4,
    "avg_score": 78.5,
    "pass_rate": 0.39,
    "period_total_collected": 102
  },
  "message": "ok"
}
```

**口径说明:**
- `period_articles`、`pass_rate`、`period_total_collected` 来自 `pipeline_runs.summary`，表示流水线审核口径。
- `total_articles`、`active_sources`、`avg_score` 来自 `articles` 表，仅统计 approved 文章。
- 成本字段来自 `cost_logs`。

### GET /api/stats

仪表盘基础统计。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 30 | 近 N 个自然日（含今天） |

**响应:**
```json
{
  "code": 0,
  "data": {
    "total_articles": 125,
    "period_articles": 103,
    "period_cost": 0.5,
    "active_sources": 4,
    "avg_score": 78.5
  },
  "message": "ok"
}
```

### GET /api/stats/enhanced

增强版统计（含成本趋势）。`summary` 与 `/api/dashboard/summary` 使用同一口径。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 30 | 近 N 个自然日（含今天，1-3650） |

**响应:**
```json
{
  "code": 0,
  "data": {
    "summary": {
      "total_articles": 125,
      "period_articles": 103,
      "period_cost": 0.5,
      "total_cost": 5.0,
      "active_sources": 4,
      "avg_score": 78.5,
      "pass_rate": 0.39,
      "period_total_collected": 264
    },
    "hourly_cost": [...],
    "daily_cost": [...],
    "weekly_cost": [...],
    "monthly_cost": [...],
    "source_distribution": [...],
    "active_source_details": [...]
  },
  "message": "ok"
}
```

### GET /api/stats/quality

数据质量统计（旧版）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 30 | 近 N 个自然日（含今天） |

### GET /api/stats/quality-detail

数据质量详细统计（新版，四维评分）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| period | string | "week" | day/week/month |

**响应:**
```json
{
  "code": 0,
  "data": {
    "content_quality": {
      "summary_coverage": 1.0,
      "avg_desc_length": 277.9,
      "avg_summary_length": 161.0
    },
    "audit_efficiency": {
      "one_pass_rate": 0.928,
      "retry_rate": 0,
      "exhausted_rate": 0.048
    },
    "tag_coverage": {
      "tagged_rate": 0.992,
      "avg_tags": 3.0
    },
    "dimensions": {
      "ai_relevance": {"avg_score": 24.4, "high_rate": 1.0, "mid_rate": 0, "low_rate": 0, "max_score": 30},
      "engineering_relevance": {"avg_score": 25.0, "high_rate": 0.6, "mid_rate": 0.4, "low_rate": 0, "max_score": 30},
      "content_depth": {"avg_score": 20.0, "high_rate": 0.6, "mid_rate": 0.4, "low_rate": 0, "max_score": 25},
      "info_density": {"avg_score": 12.0, "high_rate": 0.5, "mid_rate": 0.5, "low_rate": 0, "max_score": 15}
    },
    "reason_keywords": [
      {"word": "核心", "count": 47},
      {"word": "属于", "count": 35}
    ]
  },
  "message": "ok"
}
```

### GET /api/stats/runtime

运行状态统计。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 7 | 近 N 个自然日（含今天） |

### GET /api/stats/consumption

资源消耗统计（旧版）。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 30 | 近 N 个自然日（含今天） |

### GET /api/stats/consumption-detail

资源消耗详细统计（新版）。`period` 表示 KPI 日期窗口，`trend_window` 单独控制趋势回看窗口。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| period | string | "week" | day/week/month |
| trend_window | string | 跟随 period | 趋势回看窗口，格式为 `14d`、`4w`、`12m` |

**period 口径:**

| period | KPI 窗口 | 默认 trend_window | 趋势聚合粒度 |
|--------|----------|--------------------|--------------|
| day | 今天 | 14d | 按天 |
| week | 近 7 个自然日（含今天） | 4w | 按周 |
| month | 近 30 个自然日（含今天） | 12m | 按月 |

**趋势口径:**

- `period_cost`、`period_days`、`period_tokens`、`daily_avg` 使用 `period` 对应的 KPI 窗口。
- `trend`、`source_trend`、`provider_trend` 使用 `trend_window` 对应的趋势窗口，三者窗口保持一致。
- 前端默认传参：`day&trend_window=14d`、`week&trend_window=4w`、`month&trend_window=12m`。

**来源费用口径:**

- `source_trend.source` 优先读取 `cost_logs.source/source_detail`，这是新成本记录的显式来源快照。
- 旧成本记录没有显式来源时，通过 `cost_logs.ref_url = articles.url` 归因到文章真实来源。
- RSS 文章优先展示 `source_detail`（例如 `36氪`、`OpenAI Blog`）；`arxiv`、`github`、`feishu` 等非 RSS 来源展示 `source`。
- 如果历史成本记录无法关联文章，则根据 `ref_url` 域名兜底识别常见来源（例如 `36kr.com → 36氪`、`github.com → github`、`arxiv.org → arxiv`），最后才回退到 `cost_logs.agent`。
- `source_trend.type` 表示费用阶段：`analyze` 为 Analyzer 成本，`review` 为 Reviewer 成本；Reviewer 成本同样归到文章真实来源，不再把 `review` 当作来源。
- `trend[].llm_calls` 表示该趋势粒度内的 LLM 调用次数；历史兼容字段 `trend[].articles` 暂时保留同值。
- `budget_progress` 与 `budget_remaining` 使用 `config/agents.yaml` 中的 `budget.monthly`，不是硬编码值。

**响应:**
```json
{
  "code": 0,
  "data": {
    "period_cost": 0.1659,
    "period_days": 8,
    "period_tokens": 451000,
    "daily_avg": 0.0207,
    "cost_per_million_tokens": 0.37,
    "budget_progress": 0.017,
    "budget_remaining": 9.83,
    "monthly_budget": 10.0,
    "trend_window": "4w",
    "trend": [...],
    "source_trend": [...],
    "provider_trend": [...]
  },
  "message": "ok"
}
```

---

## 成本接口

### GET /api/cost/summary

花费统计。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| days | int | 30 | 近 N 个自然日（含今天，1-3650） |

**响应:**
```json
{
  "code": 0,
  "data": [
    {"provider": "deepseek", "model": "deepseek-chat", "total_cost": 2.5, "total_tokens": 1000000}
  ],
  "message": "ok"
}
```

---

## 深度报告接口

公开接口只返回 `status='completed'` 且 `report_version` 等于 `deep_report_settings.public_version` 的深度报告；`failed` 和非公开版本仅用于内部排障或重建，不参与公开列表、latest 或详情响应。

### GET /api/deep-reports

深度报告列表。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码，最小 1 |
| page_size | int | 20 | 每页数量，范围 1-100 |

**口径:**

- `items` 和 `total` 都只统计当前公开版本的 completed 报告。
- 按 `updated_at DESC, id DESC` 排序后分页。
- 列表只返回展示所需的摘要字段；完整 `report_json/report_markdown/evidence_json/file_tree_summary` 仅由 latest/detail 返回。

**响应:**
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": 1,
        "repo_url": "https://github.com/org/tool",
        "repo_name": "org/tool",
        "status": "completed",
        "report_version": 2,
        "candidate_score": 88,
        "trigger_reason": "实用性高，源码结构清晰",
        "report_summary": "项目概述",
        "report_tech_stack": ["Python", "FastAPI"],
        "tech_stack_json": {"languages": ["Python"]},
        "updated_at": "2026-06-09T10:00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 20
  },
  "message": "ok"
}
```

### GET /api/deep-reports/latest

返回当前公开版本中按 `updated_at DESC, id DESC` 排序的最新 completed 深度报告。没有 completed 报告时仍返回成功信封，`data` 为 `{}`。

### GET /api/deep-reports/{report_id}

返回指定的当前公开版本 completed 深度报告详情。详情 `report_json` 为 V2 决策报告结构，源码证据字段仍可由 API 返回，但页面不渲染。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| report_id | int | 深度报告 ID |

**错误:** `40401` - 报告不存在、状态不是 completed，或不属于当前公开版本。

---

## 流水线接口

### POST /api/pipeline/run

手动触发采集。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| source | string | "" | 数据源ID（空=全量） |

**响应:**
```json
{
  "code": 0,
  "data": {"status": "queued"},
  "message": "Pipeline triggered"
}
```

### POST /api/pipeline/build

强制构建站点（跳过去抖）。

**响应:**
```json
{
  "code": 0,
  "data": {"status": "done"},
  "message": "Build triggered"
}
```

### GET /api/pipeline/dag

查看 DAG 状态。默认返回最近一次 run；可传 `run_id` 查看历史 run。接口同时保留原始 `phases/events/source_funnels/active_items` 排障字段，并返回三层页面聚合数据：

- `summary`：数据流水线与网站发布双状态，以及采集、新增、分析、入库、丢弃、失败、成本、Token。
- `processing_stages`：采集与去重、来源路由、并行分析、审核与重审、结果落库。
- `review_rounds`：初审及每轮重审的通过、重试、丢弃数量。
- `postprocess`：深度报告、数据库备份、静态站构建。
- `recent_runs`：最近 12 次运行，供页面切换。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| run_id | string | "" | 为空时返回最新 run |
| detail | string | "summary" | summary 返回最近 100 条事件；full 返回最近 500 条事件 |

**响应:**
```json
{
  "code": 0,
  "data": {
    "run_id": "run_20260524_090000",
    "run_id_bj": "run_20260524_090000",
    "status": "completed",
    "current_phase": null,
    "summary": {
      "pipeline_status": "completed",
      "publication_status": "completed",
      "collected": 26,
      "new_items": 16,
      "analyzed": 16,
      "inserted": 5,
      "discarded": 11,
      "failed": 0
    },
    "processing_stages": [...],
    "review_rounds": [...],
    "postprocess": {
      "deep_report": {"status": "skipped"},
      "backup": {"status": "completed"},
      "build": {"status": "completed"}
    },
    "recent_runs": [...],
    "progress": {
      "total_units": 40,
      "completed_units": 40,
      "percent": 100
    },
    "phases": [...],
    "events": [
      {
        "id": 12,
        "ts": "2026-06-02T21:10:07",
        "phase": "review",
        "event": "reviewer.item_done",
        "level": "success",
        "status": "approved",
        "source_id": "github_ai_devtools",
        "ref_url": "https://github.com/Lum1104/Understand-Anything",
        "agent": "reviewer",
        "message": "审核approved",
        "payload": {"score": 93}
      }
    ],
    "source_funnels": [
      {
        "source_id": "github_ai_devtools",
        "source": "github",
        "source_detail": "AI DevTools",
        "collected": 8,
        "new_items": 7,
        "analyzed": 7,
        "inserted": 7,
        "failed": 0
      }
    ],
    "active_items": [],
    "logs": [...]
  },
  "message": "ok"
}
```

网站发布状态独立于 `pipeline_runs.status`：`queued` 等待去抖，`running` 正在构建，`completed` 已发布，`failed` 构建失败，`superseded` 被后续流水线合并，`skipped` 本轮无需构建。

---

## 数据源接口

### GET /api/sources/

数据源列表（含状态）。

**响应:**
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "github_trending",
        "name": "GitHub Trending",
        "type": "github",
        "status": "active",
        "priority": 1,
        "cron": "0 */6 * * *",
        "recent_approved_rate": 0.75,
        "recent_total": 20,
        "avg_score": 82.5
      }
    ],
    "total": 4
  },
  "message": "ok"
}
```

### GET /api/sources/stats

数据源健康统计。

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| period | string | "week" | day/week/month，其他值按 week 处理 |

**统计口径:**

- `sources[].id` 使用 `config/sources.yaml` 中的数据源配置 id，例如 `rss_36kr`、`github_trending`、`rss_arxiv`。
- `sources[].name` 使用 `config/sources.yaml` 中的数据源展示名，例如 `36氪`、`arXiv AI/ML`；前端图表和表格展示该简称，不直接展示存储 id。
- `sources[].type` 使用配置中的数据源类型，例如 `rss`、`github`、`hotlist`、`hn`、`arxiv`。
- 接口返回 `config/sources.yaml` 中的全部配置源，包括禁用源和尚无健康历史的源。
- `period` 映射到真实日期窗口：day=今天、week=近 7 个自然日（含今天）、month=近 30 个自然日（含今天）。
- `total_collected` 为窗口内 `source_health.total_collected` 求和。
- `approved_rate` 为窗口内 `approved / total_collected`。
- `avg_score` 只对窗口内非空的每日评分求平均；没有 approved 文章的日期不按 0 分参与计算。
- `trend` 通过窗口前后半段 approved rate 对比得出：超过 10% 为 `rising`，低于 10% 为 `falling`，否则 `stable`。
- `source_health` 按天合并：Collector 累加 `total_collected/failed`，Reviewer 累加 `approved/rejected`，`avg_score` 按 approved 数加权合并。
- `new_items/dedup_skipped/analyzed/analysis_failed/retry/discarded/inserted/failed/cost/tokens` 来自 `pipeline_source_runs`，表示窗口内每个 source 的 pipeline 漏斗和成本效率。
- `filtered_items = retry + discarded`，表示采集后被质量门槛拦下或仍需重审的数量；它不是采集失败。
- `request_success_rate = collected / (collected + failed)`，用于区分上游源不可用和内容被正常过滤。
- `insert_rate = inserted / new_items`，用于衡量新采集内容最终入库效率。
- `health_status` 按最近一次 `pipeline_source_runs` 推导：
  - `disabled`：配置禁用。
  - `not_scheduled`：尚无运行记录。
  - `failed`：最近一次请求失败且没有采集结果。
  - `success_zero`：请求成功但关键词过滤后为 0。
  - `dedup_only`：有原始采集，但查重后没有新条目。
  - `analysis_failed`：有新条目，但最近一次全部分析失败。
  - `healthy`：最近一次正常推进到后续阶段。
- `last_run_at/last_error` 返回最近运行时间和最近采集错误；`last_collected/last_new_items/last_dedup_skipped/last_analyzed/last_analysis_failed/last_inserted` 返回最近一次漏斗。
- `governance_status` 返回自动治理状态：`candidate/trial/active/degraded/quarantined/disabled/rejected`。
- `health_score` 返回自动治理健康分；预算阻断和采集成功但无新条目的轮次不更新该分数。`active` 源按最近 3 次可评分记录的平均分低于 50 才降权。
- `budget_blocked` 表示最近治理汇总是否被预算硬熔断阻断。
- `last_governance_reason` 返回最近一次自动治理动作原因。
- GitHub repo 的审核策略与普通文章不同：系统会按 repo-aware 维度裁决，因此 `approved/retry/discarded` 不能直接与 RSS 新闻按同一内容深度标准比较。

**响应:**
```json
{
  "code": 0,
  "data": {
    "period": "week",
    "sources": [
      {
        "id": "github_trending",
        "name": "GitHub Trending AI",
        "type": "github",
        "enabled": true,
        "health_status": "healthy",
        "governance_status": "active",
        "health_score": 82.5,
        "budget_blocked": false,
        "last_governance_reason": null,
        "approved_rate": 0.75,
        "total_collected": 20,
        "avg_score": 82.5,
        "trend": "rising",
        "new_items": 14,
        "dedup_skipped": 6,
        "analyzed": 13,
        "analysis_failed": 1,
        "retry": 1,
        "discarded": 3,
        "inserted": 10,
        "failed": 0,
        "filtered_items": 4,
        "request_success_rate": 1,
        "insert_rate": 0.714,
        "cost": 0.12,
        "tokens": 3200,
        "last_run_at": "2026-06-10 14:08:11",
        "last_error": null,
        "last_collected": 10,
        "last_new_items": 4,
        "last_dedup_skipped": 6,
        "last_analyzed": 4,
        "last_analysis_failed": 0,
        "last_inserted": 3
      }
    ]
  },
  "message": "ok"
}
```

### GET /api/sources/discovered

已发现待审核的数据源。

**响应:**
```json
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 0
  },
  "message": "ok"
}
```

### POST /api/sources/{source_id}/action

数据源操作。

**参数:**

| 参数 | 类型 | 说明 |
|------|------|------|
| source_id | string | 数据源ID |
| action | string | enable/disable/remove |

**响应:**
```json
{
  "code": 0,
  "data": {"message": "Source github_trending enabled"},
  "message": "ok"
}
```

### POST /api/sources/maintenance/clear-health

清除 source_health 数据（用于修正旧格式数据）。

**响应:**
```json
{
  "code": 0,
  "data": {"message": "source_health cleared, will rebuild on next pipeline run"},
  "message": "ok"
}
```

---

## 变更记录

| 日期 | 变更内容 |
|------|----------|
| 2026-06-02 | `/api/pipeline/dag` 支持 `run_id/detail` 参数，返回 `progress/events/source_funnels/active_items` 细粒度运行数据 |
| 2026-06-02 | `/api/sources/stats` 补充 source-run 漏斗、成本、token 字段；DAG 示例 run_id 改为北京时间真实 run_id |
| 2026-05-31 | 统一 API 错误信封；新增 `/api/dashboard/summary`；修正 `/api/articles` total 和详情 tags；数据源接口复用注入 DB |
| 2026-05-24 | 新增 `/api/stats/quality-detail` 端点 |
| 2026-05-24 | 新增 `/api/stats/consumption-detail` 端点 |
