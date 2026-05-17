# 数据模型

## SQLite Schema

### articles — 文章主表

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| title | TEXT | |
| url | TEXT UNIQUE | 防同源重复采集，不做跨源语义去重 |
| description | TEXT | 原始摘要/README 摘要 |
| summary | TEXT | AI 生成摘要（详情页按需加载） |
| source | TEXT | github / rss / feishu / arxiv |
| source_detail | TEXT | 来源详情 (repo、频道名等) |
| relevance_score | INTEGER | 0-100 |
| status | TEXT | pending / approved / retry / discarded |
| retry_count | INTEGER DEFAULT 0 | |
| collected_at | TEXT | ISO 8601 |
| published_at | TEXT | ISO 8601 |
| extra_data | TEXT | JSON: 四维评分 detail + language + 原始 API 返回 |
| analysis_cost | REAL | 该条分析总花费 ($) |
| analysis_tokens | INTEGER | 该条分析 token 总量 |
| created_at | TEXT DEFAULT CURRENT_TIMESTAMP | |
| updated_at | TEXT DEFAULT CURRENT_TIMESTAMP | |

FTS5 全文索引：`articles_fts` over (title, summary, description)

### tags — 标签字典

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| name | TEXT UNIQUE | |
| color | TEXT | |

### article_tags — 文章-标签关联

| 列 | 类型 |
|----|------|
| article_id | INTEGER FK → articles.id |
| tag_id | INTEGER FK → tags.id |

### pipeline_runs — 流水线运行记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | run_YYYYMMDD_HHMMSS |
| started_at | TEXT | |
| ended_at | TEXT | |
| status | TEXT | running / completed / failed |
| trigger | TEXT | cron / manual |
| summary | TEXT | JSON: 采集数/去重跳过/入库数/丢弃数/花费/每源状态 |

### cost_logs — LLM 调用花费

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| run_id | TEXT FK → pipeline_runs.id | |
| agent | TEXT | github_analyzer / rss_analyzer / feishu_analyzer / arxiv_analyzer / reviewer |
| provider | TEXT | deepseek / minimax / ... |
| model | TEXT | |
| tokens_in | INTEGER | |
| tokens_out | INTEGER | |
| cost | REAL | |

### provider_health — Provider 健康状态

| 列 | 类型 | 说明 |
|----|------|------|
| provider | TEXT | |
| status | TEXT | healthy / degraded / unhealthy |
| latency_ms | REAL | |
| error_count | INTEGER | |
| last_error | TEXT | |
| last_check | TEXT | |
| circuit | TEXT | closed / open / half_open |

### circuit_events — 熔断事件记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| provider | TEXT | |
| event | TEXT | open / half_open / close |
| reason | TEXT | |
| created_at | TEXT | |

### schema_version — 数据库迁移版本

| 列 | 类型 |
|----|------|
| version | INTEGER |

## 配置文件结构

### config/sources.yaml

RSS 按订阅源独立条目，各自 cron：

```yaml
sources:
  - id: github_trending
    name: GitHub Trending
    type: github
    enabled: true
    priority: 1
    cron: "0 */6 * * *"
    max_items: 10
    config:
      languages: [python, typescript]
      topics: [ai, llm, agent, machine-learning]

  - id: rss_the_batch
    name: The Batch
    type: rss
    enabled: true
    priority: 2
    cron: "0 9 * * 1"        # 周刊
    max_items: 5
    config:
      url: "https://www.deeplearning.ai/the-batch/feed/"

  - id: rss_hackernews_ai
    name: Hacker News AI
    type: rss
    enabled: true
    priority: 2
    cron: "0 */6 * * *"      # 高频
    max_items: 10
    config:
      url: "https://hnrss.org/frontpage?q=ai+llm+agent"
```

### config/agents.yaml

```yaml
budget:
  monthly: 10.0          # 月预算 ($)
  soft_limit: 0.8        # 80% 触发软熔断
  hard_limit: 1.0        # 100% 触发硬熔断

agents:
  github_analyzer:
    primary:
      provider: deepseek
      model: deepseek-chat
      temperature: 0.3
    fallback:
      - provider: minimax
        model: abab6.5s-chat
    prompt: prompts/github.md
    budget_weight: 1.0
```
