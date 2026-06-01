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

**响应:** 返回完整 articles 表记录，并附加 `tags` 数组。

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
      "ai_relevance": {"avg_score": 34.4, "high_rate": 1.0, "mid_rate": 0, "low_rate": 0},
      "content_depth": {"avg_score": 24.0, "high_rate": 0.6, "mid_rate": 0.4, "low_rate": 0},
      "info_density": {"avg_score": 12.0, "high_rate": 0.5, "mid_rate": 0.5, "low_rate": 0},
      "timeliness": {"avg_score": 13.0, "high_rate": 0.8, "mid_rate": 0.2, "low_rate": 0}
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
| trend_window | string | 跟随 period | 趋势回看窗口，格式为 `14d`、`12w`、`12m` |

**period 口径:**

| period | KPI 窗口 | 默认 trend_window | 趋势聚合粒度 |
|--------|----------|--------------------|--------------|
| day | 今天 | 14d | 按天 |
| week | 近 7 个自然日（含今天） | 12w | 按周 |
| month | 近 30 个自然日（含今天） | 12m | 按月 |

**趋势口径:**

- `period_cost`、`period_days`、`period_tokens`、`daily_avg` 使用 `period` 对应的 KPI 窗口。
- `trend`、`source_trend`、`provider_trend` 使用 `trend_window` 对应的趋势窗口，三者窗口保持一致。
- 前端默认传参：`day&trend_window=14d`、`week&trend_window=12w`、`month&trend_window=12m`。

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
    "trend_window": "12w",
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

查看 DAG 状态。

**响应:**
```json
{
  "code": 0,
  "data": {
    "run_id": "run_20260524_090000",
    "run_id_bj": "run_20260524_090000",
    "status": "completed",
    "current_phase": null,
    "phases": [...],
    "logs": [...]
  },
  "message": "ok"
}
```

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
- `sources[].type` 使用配置中的数据源类型，例如 `rss`、`github`、`arxiv`。
- `period` 映射到真实日期窗口：day=今天、week=近 7 个自然日（含今天）、month=近 30 个自然日（含今天）。
- `total_collected` 为窗口内 `source_health.total_collected` 求和。
- `approved_rate` 为窗口内 `approved / total_collected`。
- `avg_score` 为窗口内每日 `avg_score` 的简单平均。
- `trend` 通过窗口前后半段 approved rate 对比得出：超过 10% 为 `rising`，低于 10% 为 `falling`，否则 `stable`。
- `source_health` 按天合并：Collector 累加 `total_collected/failed`，Reviewer 累加 `approved/rejected`，`avg_score` 按 approved 数加权合并。
- `new_items/dedup_skipped/analyzed/analysis_failed/retry/discarded/inserted/cost/tokens` 来自 `pipeline_source_runs`，表示窗口内每个 source 的 pipeline 漏斗和成本效率。

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
        "cost": 0.12,
        "tokens": 3200
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
| 2026-06-02 | `/api/sources/stats` 补充 source-run 漏斗、成本、token 字段；DAG 示例 run_id 改为北京时间真实 run_id |
| 2026-05-31 | 统一 API 错误信封；新增 `/api/dashboard/summary`；修正 `/api/articles` total 和详情 tags；数据源接口复用注入 DB |
| 2026-05-24 | 新增 `/api/stats/quality-detail` 端点 |
| 2026-05-24 | 新增 `/api/stats/consumption-detail` 端点 |
