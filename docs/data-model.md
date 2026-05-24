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
| summary | TEXT | JSON: approved / discarded / retry 数统计 |

### pipeline_phase_logs — 流水线阶段日志

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| run_id | TEXT FK → pipeline_runs.id | |
| phase | TEXT | collector / router / analyzer / reviewer |
| source | TEXT | 源名称（analyzer 阶段按源记录） |
| event | TEXT | started / completed / failed |
| message | TEXT | 日志内容 |
| created_at | TEXT | |

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
| created_at | TEXT DEFAULT CURRENT_TIMESTAMP | |

### source_health — 数据源健康统计

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| source_id | TEXT | 数据源ID（对应 sources.yaml 中的 id） |
| date | TEXT | YYYY-MM-DD |
| total_collected | INTEGER | 当日采集总数 |
| approved | INTEGER | 当日审核通过数 |
| rejected | INTEGER | 当日审核拒绝数 |
| failed | INTEGER | 当日采集失败数 |
| avg_score | REAL | 当日平均相关性评分 |
| recorded_at | TEXT | 记录时间 |

UNIQUE(source_id, date)

### discovered_sources — 已发现待审核的数据源

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| url | TEXT UNIQUE | 数据源 URL |
| name | TEXT | 数据源名称 |
| type | TEXT | 类型（github / rss / feishu / arxiv） |
| discovered_at | TEXT | 发现时间 |
| status | TEXT | candidate / enabled / disabled |
| added_at | TEXT | 加入时间 |
| rejected_at | TEXT | 拒绝时间 |
| reject_reason | TEXT | 拒绝原因 |

### github_repo_snapshots — GitHub 仓库星标快照

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| repo_url | TEXT | 仓库 URL |
| repo_name | TEXT | 仓库名称 |
| stars | INTEGER | 星标数 |
| forks | INTEGER | Fork 数 |
| watchers | INTEGER | Watcher 数 |
| snapshot_date | TEXT | YYYY-MM-DD |
| created_at | TEXT | |

UNIQUE(repo_url, snapshot_date)

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

## extra_data JSON 结构

`articles.extra_data` 存储 AI 分析产生的四维评分等详细信息：

```json
{
  "dimensions": {
    "ai_relevance": {"avg_score": 34.4, "high_rate": 1.0, "mid_rate": 0, "low_rate": 0},
    "内容深度": {"avg_score": 0, "high_rate": 0, "mid_rate": 0, "low_rate": 0},
    "信息密度": {"avg_score": 0, "high_rate": 0, "mid_rate": 0, "low_rate": 0},
    "时效性": {"avg_score": 16.0, "high_rate": 0.008, "mid_rate": 0, "low_rate": 0}
  },
  "reason_keywords": [
    {"word": "核心", "count": 47},
    {"word": "属于", "count": 35}
  ],
  "language": "zh",
  "raw_api_response": {...}
}
```

四维评分说明：

| 维度 | 说明 | 高分标准 |
|------|------|----------|
| ai_relevance | AI 相关性 | 与 AI/LLM/Agent 领域相关程度 |
| 内容深度 | 内容深度 | 有详细技术实现或分析 |
| 信息密度 | 信息密度 | 内容充实、信息价值高 |
| 时效性 | 时效性 | 近期发布的内容 |

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