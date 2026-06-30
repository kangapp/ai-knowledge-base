# 数据模型

## 时间约定

- 项目业务时间统一使用北京时间（Asia/Shanghai / UTC+8）。
- Python 代码统一通过 `src/core/time.py` 获取当前时间；SQLite 当前日期窗口使用 `date('now', '+8 hours', ...)`。
- `collected_at/created_at/updated_at/started_at/ended_at/recorded_at` 等项目生成字段存储为北京时间本地 ISO 字符串，不再带 `Z`。
- 外部源自身的 `published_at` 保留上游原始格式，不强制转换。

## SQLite Schema

### articles — 文章主表

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| title | TEXT | |
| url | TEXT UNIQUE | 防同源重复采集，不做跨源语义去重 |
| description | TEXT | 原始摘要/README 摘要 |
| summary | TEXT | AI 生成摘要（详情页按需加载） |
| source | TEXT | github / rss / hotlist / hn / feishu / arxiv |
| source_detail | TEXT | 来源详情 (repo、频道名等) |
| relevance_score | INTEGER | 0-100 |
| status | TEXT | pending / approved / retry / discarded |
| retry_count | INTEGER DEFAULT 0 | |
| collected_at | TEXT | 北京时间 ISO 字符串 |
| published_at | TEXT | 上游原始发布时间 |
| extra_data | TEXT | JSON: 四维评分 detail + raw metadata + language |
| analysis_cost | REAL | 该条分析总花费 ($) |
| analysis_tokens | INTEGER | 该条分析 token 总量 |
| created_at | TEXT DEFAULT (datetime('now', '+8 hours')) | 北京时间 |
| updated_at | TEXT DEFAULT (datetime('now', '+8 hours')) | 北京时间 |

FTS5 全文索引：`articles_fts` over (title, summary, description)

**样例数据：**

```json
{
  "id": 18250,
  "title": "Llama 4 Scout: 17B MoE with 10M context window",
  "url": "https://github.com/meta-llama/llama4/pull/142",
  "description": "Meta's latest open-source model featuring...",
  "summary": "Meta 发布 Llama 4 Scout，采用 MoE 架构...",
  "source": "github",
  "source_detail": "meta-llama/llama4",
  "relevance_score": 85,
  "status": "approved",
  "retry_count": 0,
  "collected_at": "2026-05-24T08:30:00",
  "published_at": "2026-05-23T14:00:00Z",
  "extra_data": "{\"dimensions\":{\"ai_relevance\":{\"score\":35,\"reason\":\"核心内容围绕 LLM Agent 工具链\"},\"content_depth\":{\"score\":24,\"reason\":\"包含架构和实现细节\"},\"info_density\":{\"score\":12,\"reason\":\"有明确的新功能和技术信息\"},\"timeliness\":{\"score\":13,\"reason\":\"近期发布\"}},\"raw\":{\"source_id\":\"github_ai_devtools\"},\"language\":\"en\"}",
  "analysis_cost": 0.0032,
  "analysis_tokens": 1240,
  "created_at": "2026-05-24T08:30:05",
  "updated_at": "2026-05-24T08:30:05"
}
```

### tags — 标签字典

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| name | TEXT UNIQUE | |
| color | TEXT | |

**样例数据：**

| id | name | color |
|----|------|-------|
| 1 | LLM | #10b981 |
| 2 | Agent | #3b82f6 |
| 3 | 论文解读 | #f59e0b |

### article_tags — 文章-标签关联

| 列 | 类型 |
|----|------|
| article_id | INTEGER FK → articles.id |
| tag_id | INTEGER FK → tags.id |

**样例数据：**

| article_id | tag_id |
|------------|--------|
| 18250 | 1 |
| 18250 | 2 |
| 18249 | 3 |

### pipeline_runs — 流水线运行记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | run_YYYYMMDD_HHMMSS |
| started_at | TEXT | 北京时间 |
| ended_at | TEXT | 北京时间 |
| status | TEXT | running / completed / failed |
| trigger | TEXT | cron / manual |
| summary | TEXT | JSON: approved / discarded / retry 数统计 |

**样例数据：**

| 字段 | 值 |
|------|-----|
| id | run_20260524_090000 |
| started_at | 2026-05-24T09:00:00 |
| ended_at | 2026-05-24T09:05:32 |
| status | completed |
| trigger | cron |
| summary | {"approved": 15, "discarded": 3, "retry": 2, "total_collected": 20, "cost": 0.15, "sources": {"github_trending": {"collected": 10, "approved": 8}, "rss_the_batch": {"collected": 10, "approved": 7}}} |

### pipeline_phase_logs — 流水线阶段日志

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| run_id | TEXT FK → pipeline_runs.id | |
| phase | TEXT | collect / route / analyze / aggregate / review |
| status | TEXT | running / done / failed |
| started_at | TEXT | 北京时间 |
| ended_at | TEXT | 北京时间 |
| duration_ms | INTEGER | 阶段耗时 |
| details | TEXT | 阶段摘要 |

**样例数据：**

| id | run_id | phase | status | started_at | ended_at | duration_ms | details |
|----|--------|-------|--------|------------|----------|-------------|---------|
| 1 | run_20260524_090000 | collect | done | 2026-05-24T09:00:00 | 2026-05-24T09:00:45 | 45000 | collected 20 items |
| 2 | run_20260524_090000 | analyze | done | 2026-05-24T09:00:45 | 2026-05-24T09:02:30 | 105000 | total:20, succeeded:18, failed:2 |

### pipeline_events — 流水线细粒度事件

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 递增事件 id，可用于前端增量轮询 |
| run_id | TEXT FK → pipeline_runs.id | |
| ts | TEXT | 北京时间 |
| phase | TEXT | collect / route / analyze / aggregate / review / persist / build / pipeline |
| event | TEXT | 事件名，如 `analyzer.item_done`、`reviewer.parse_failed` |
| level | TEXT | info / success / warning / error |
| status | TEXT | running / done / failed / approved / discarded / retry / inserted 等 |
| source_id | TEXT | 配置源 id |
| source | TEXT | github / rss / hotlist / hn / feishu / arxiv |
| source_detail | TEXT | 展示来源或 repo 名 |
| ref_url | TEXT | item URL |
| title | TEXT | item 标题 |
| agent | TEXT | analyzer/reviewer 名 |
| provider | TEXT | LLM provider |
| model | TEXT | LLM model |
| attempt_no | INTEGER | LLM 调用尝试次数 |
| latency_ms | INTEGER | 单次调用或阶段耗时 |
| cost | REAL | 单次事件关联成本 |
| tokens | INTEGER | tokens_in + tokens_out |
| message | TEXT | 人类可读短消息 |
| payload | TEXT | JSON 扩展字段 |

**样例数据：**

| run_id | phase | event | status | source_id | ref_url | message |
|--------|-------|-------|--------|-----------|---------|---------|
| run_20260602_211007 | analyze | analyzer.item_done | done | github_ai_devtools | https://github.com/Lum1104/Understand-Anything | 分析完成 |
| run_20260602_211007 | review | reviewer.item_done | approved | github_ai_devtools | https://github.com/Lum1104/Understand-Anything | 审核approved |

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
| ref_url | TEXT | LLM 调用关联的原始文章 URL |
| source | TEXT | 成本记录时的来源快照：github / rss / hotlist / hn / feishu / arxiv |
| source_detail | TEXT | 成本记录时的来源细分；RSS 存 feed 名称或展示名 |
| source_id | TEXT | 成本记录时的源 ID；统一使用 `config/sources.yaml` 中的配置 id |
| status | TEXT DEFAULT 'success' | success / parse_failed / request_failed |
| error | TEXT | 调用或解析错误 |
| latency_ms | INTEGER | LLM 调用耗时 |
| attempt_no | INTEGER DEFAULT 1 | 同一 item 的尝试序号 |
| prompt_name | TEXT | prompt/agent 名称 |
| prompt_version | TEXT | prompt 版本标识，当前为 `current` |
| created_at | TEXT DEFAULT (datetime('now', '+8 hours')) | 北京时间 |

**样例数据：**

| id | run_id | agent | provider | model | tokens_in | tokens_out | cost | ref_url | source | source_id | status | attempt_no | created_at |
|----|--------|-------|----------|-------|----------|-----------|------|---------|--------|-----------|--------|------------|------------|
| 1 | run_20260524_090000 | github_analyzer | deepseek | deepseek-chat | 1200 | 350 | 0.0021 | https://github.com/org/repo | github | github_trending | success | 1 | 2026-05-24T09:01:00 |
| 2 | run_20260524_090000 | reviewer | deepseek | deepseek-chat | 2800 | 420 | 0.0048 | https://36kr.com/p/123 | rss | rss_36kr | parse_failed | 2 | 2026-05-24T09:03:00 |

**成本来源记录口径：**

- 新记录写入时应保存 `source/source_detail/source_id` 快照，统计接口优先使用这些字段，避免审核未通过、重复或未入库文章无法归因。
- Analyzer 成本由 `RawItem` 直接填充来源字段。
- Reviewer 成本在图外入库阶段按 `ref_url` 从本轮 `RawItem` 映射补齐来源字段。
- 只要 LLM 返回 usage，即使 Analyzer/Reviewer JSON 解析失败，也应写入 `cost_logs`；一次重试对应一次真实 LLM 调用。
- `status/error/latency_ms/attempt_no/prompt_name/prompt_version` 用于追踪调用成功率、解析失败和 prompt/model 效果。
- `articles.analysis_cost/analysis_tokens` 为同一 `ref_url` 的 Analyzer + Reviewer 调用成本汇总，不再固定为 0。
- 历史记录缺少来源字段时，统计接口按 `articles` JOIN 和 URL 域名兜底归因。

### collection_items — 采集 item 明细

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| run_id | TEXT FK → pipeline_runs.id | |
| url | TEXT | 原始 URL |
| title | TEXT | 原始标题 |
| source | TEXT | github / rss / hotlist / hn / feishu / arxiv |
| source_id | TEXT | 配置 id |
| source_detail | TEXT | 来源细分 |
| status | TEXT | collected / dedup_skipped / inserted / reviewed_retry / reviewed_discarded / trial_approved / trial_retry |
| reason | TEXT | 状态原因 |
| raw_metadata | TEXT | JSON 原始元数据 |
| article_id | INTEGER FK → articles.id | 入库文章 id |
| created_at | TEXT | 北京时间 |
| updated_at | TEXT | 北京时间 |

UNIQUE(run_id, url)

该表保存每次 pipeline 中每条原始 item 的最终状态，用来回答“源有没有抓到、是否被去重、是否被审核丢弃、是否入库”。

### pipeline_source_runs — 单次运行的数据源漏斗

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| run_id | TEXT FK → pipeline_runs.id | |
| source_id | TEXT | 配置 id |
| source | TEXT | 数据源类型 |
| source_detail | TEXT | 来源细分 |
| collected | INTEGER | 原始采集量 |
| new_items | INTEGER | 查重后的新 item 数 |
| dedup_skipped | INTEGER | URL 已存在跳过数 |
| analyzed | INTEGER | Analyzer 成功产出数 |
| analysis_failed | INTEGER | Analyzer 未产出数 |
| approved | INTEGER | Reviewer 通过数 |
| retry | INTEGER | Reviewer retry 数 |
| discarded | INTEGER | Reviewer 丢弃数 |
| inserted | INTEGER | 最终入库数 |
| failed | INTEGER | 采集失败次数 |
| cost | REAL | 本源本轮 LLM 成本 |
| tokens | INTEGER | 本源本轮 token |
| created_at | TEXT | 北京时间 |
| updated_at | TEXT | 北京时间 |

UNIQUE(run_id, source_id)

该表是仪表盘数据源健康 Tab 的扩展事实表，适合展示 source 级采集漏斗、成本效率和失败定位。健康接口以每个 `source_id` 最新一行为状态事实：请求失败、零命中、全重复和分析失败均由该行的漏斗字段推导；错误文本从同源最近一次 `collector.source_error` 事件读取，不在本表重复存储。

**审核评分口径：**

- 普通文章新写入的 `extra_data.dimensions` 使用 `ai_relevance/content_depth/info_density/timeliness` 四个 key；GitHub repo 使用 `ai_relevance/developer_utility/project_signal/content_clarity` 四个 key。
- Reviewer 模型输出会在代码层规范化，`information_density` 历史别名会映射到 `info_density`，`currency` 历史别名会映射到 `timeliness`。
- `relevance_score` 不信任模型输出的 `total_score`，由四维分相加得到。
- `status` 不信任模型输出的 `verdict`，由代码按阈值裁决：低 AI 相关度直接丢弃，高总分且高 AI 相关度才通过。

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

**样例数据：**

| id | source_id | date | total_collected | approved | rejected | failed | avg_score | recorded_at |
|----|-----------|------|-----------------|----------|----------|--------|---------|------------|
| 1 | github_trending | 2026-05-23 | 20 | 15 | 4 | 1 | 82.5 | 2026-05-23T09:00:05 |
| 2 | rss_36kr | 2026-05-23 | 10 | 9 | 1 | 0 | 78.3 | 2026-05-23T09:00:10 |

**数据源健康主键口径：**

- `source_id` 始终使用 `config/sources.yaml` 中的配置 id。
- Collector 阶段采集成功/失败直接按配置 id 写入，并按天累加 `total_collected/failed`。
- Reviewer 阶段通过 `RawItem.raw_metadata.source_id` 归并审核结果，并按天累加 `approved/rejected`；`avg_score` 按 approved 数加权合并。
- `source_detail` 只作为展示和文章来源细分，不作为健康统计主键。
- 这样 RSS 展示名（如 `36氪`）和 arXiv 分类（如 `cs.AI`）不会被误当成数据源 id。
- 迁移 `007_normalize_source_health_ids.sql` 会将历史 `36氪` 合并到 `rss_36kr`，将历史 `cs.AI/cs.CL/cs.LG` 合并到 `rss_arxiv`。
- `source_health` 继续承担按天累计和历史趋势；当前状态以 `pipeline_source_runs` 最近一行为准，避免把旧日累计值误当成本轮结果。

### discovered_sources — 已发现待审核的数据源

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| url | TEXT UNIQUE | 数据源 URL |
| name | TEXT | 数据源名称 |
| type | TEXT | 类型（github / rss / hotlist / hn / feishu / arxiv） |
| discovered_at | TEXT | 发现时间 |
| status | TEXT | candidate / enabled / disabled |
| added_at | TEXT | 加入时间 |
| rejected_at | TEXT | 拒绝时间 |
| reject_reason | TEXT | 拒绝原因 |

**样例数据：**

| id | url | name | type | discovered_at | status | added_at | rejected_at | reject_reason |
|----|-----|------|------|---------------|--------|----------|-------------|--------------|
| 1 | https://example.com/feed.xml | Example RSS | rss | 2026-05-20T10:00:00 | candidate | null | null | null |
| 2 | https://github.com/foo/bar | foo/bar | github | 2026-05-18T08:00:00 | enabled | 2026-05-19T09:00:00 | null | null |

### source_registry — 数据源运行注册表

| 列 | 类型 | 说明 |
|----|------|------|
| id | TEXT PK | 数据源 ID |
| name | TEXT | 数据源名称 |
| type | TEXT | github / rss / hotlist / hn / feishu / arxiv |
| status | TEXT | candidate / trial / active / degraded / quarantined / disabled / rejected |
| enabled | INTEGER | 是否参与调度 |
| priority | INTEGER | 调度优先级 |
| cron | TEXT | cron 表达式 |
| max_items | INTEGER | 单次最大采集数 |
| config_json | TEXT | 源配置 JSON |
| manual_override | INTEGER | 人工覆盖标记，自动治理不得覆盖 |
| created_at | TEXT | 北京时间 |
| updated_at | TEXT | 北京时间 |

`sources.yaml` 只作为 bootstrap 和人工兜底；运行时调度和 pipeline 均读取该表。自动治理只能调整状态或禁用源，不自动删除源。`trial` 源小流量试跑，单轮最多采集 3 条；试跑通过审核的 item 只写 `collection_items/cost_logs/source_health_daily`，不写入正式 `articles`。

### source_health_daily — 数据源每日治理指标

| 列 | 类型 | 说明 |
|----|------|------|
| source_id | TEXT | 数据源 ID |
| date | TEXT | YYYY-MM-DD |
| request_success_rate | REAL | 请求成功率 |
| collected | INTEGER | 采集数 |
| new_items | INTEGER | 新增数 |
| analyzed | INTEGER | 分析成功数 |
| analysis_failed | INTEGER | 分析失败数 |
| approved | INTEGER | 审核通过数 |
| discarded | INTEGER | 审核丢弃数 |
| avg_score | REAL | 平均分 |
| cost | REAL | LLM 成本 |
| tokens | INTEGER | Token 数 |
| health_score | REAL | 自动治理健康分 |
| budget_blocked | INTEGER | 是否预算阻断 |
| updated_at | TEXT | 北京时间 |

UNIQUE(source_id, date)

预算阻断轮次只记录 `budget_blocked`，不降低 `health_score`。采集成功但没有新条目的轮次不计算健康分，避免把全量重复误判为低质量源。同一天多轮运行会先累计指标，再按当天累计值重算 `health_score`。`active` 源只有最近 3 次可评分记录的平均健康分低于 50 时才自动转为 `degraded`；最近 3 次均低于 30 时转为 `quarantined`。

`trial` 源最近 3 次健康记录全部满足请求成功率 >= 0.8、有新增、健康分 >= 50 且非预算阻断时，自动转为 `active`；否则转为 `rejected`。

### source_governance_events — 数据源治理事件

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| source_id | TEXT | 数据源 ID |
| event | TEXT | 事件名 |
| from_status | TEXT | 原状态 |
| to_status | TEXT | 新状态 |
| reason | TEXT | 自动动作原因 |
| payload_json | TEXT | 事件上下文 |
| created_at | TEXT | 北京时间 |

所有自动降权、隔离、禁用和人工操作都写入该表，方便 Dashboard 和运维追溯。

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

**样例数据：**

| id | repo_url | repo_name | stars | forks | watchers | snapshot_date | created_at |
|----|----------|-----------|-------|-------|----------|---------------|------------|
| 1 | https://github.com/meta-llama/llama4 | meta-llama/llama4 | 12400 | 1800 | 560 | 2026-05-24 | 2026-05-24T00:00:00 |

**趋势增速口径：**

- 每次 GitHub 采集后写入当日 `repo_url + snapshot_date` 快照。
- `github_trending_velocity` 使用最新快照与目标窗口前最近一次基线快照计算 star/day，不要求数据库里刚好存在精确 N 天前快照。
- 增速筛选只作用于 `raw_metadata.source_id == github_trending_velocity` 的采集结果，不影响同一批次里的常规 GitHub、RSS 或 arXiv 数据。

### deep_reports — GitHub 源码级深度报告

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| repo_url | TEXT | 规范化 GitHub 仓库 URL |
| repo_name | TEXT | `owner/repo` |
| article_id | INTEGER FK → articles.id | 关联文章，可为空 |
| run_id | TEXT FK → pipeline_runs.id | 触发分析的 pipeline run |
| commit_sha | TEXT DEFAULT '' | 本次源码扫描对应 commit |
| status | TEXT | completed / failed |
| candidate_score | INTEGER DEFAULT 0 | 候选选择分 |
| trigger_reason | TEXT | 触发原因和评分摘要 |
| report_json | TEXT DEFAULT '{}' | JSON：结构化深度报告 |
| report_markdown | TEXT DEFAULT '' | 兼容展示的 Markdown 文本 |
| evidence_json | TEXT DEFAULT '[]' | JSON：源码证据路径及理由 |
| tech_stack_json | TEXT DEFAULT '{}' | JSON：扫描得到的技术栈 |
| file_tree_summary | TEXT | 截断后的文件树摘要 |
| analysis_cost | REAL DEFAULT 0 | 本次深度分析成本 |
| analysis_tokens | INTEGER DEFAULT 0 | 本次深度分析 token 总量 |
| error | TEXT | 失败原因；成功记录为空 |
| created_at | TEXT DEFAULT (datetime('now', '+8 hours')) | 北京时间 |
| updated_at | TEXT DEFAULT (datetime('now', '+8 hours')) | 北京时间 |
| report_version | INTEGER DEFAULT 1 | 报告结构版本；V1=旧列表结构，V2=决策/架构/流程结构 |

UNIQUE(repo_url, commit_sha, report_version)

**索引：**

- `idx_deep_reports_status_created(status, created_at DESC)`
- `idx_deep_reports_repo_url(repo_url)`
- `idx_deep_reports_run_id(run_id)`
- `idx_deep_reports_public(report_version, status, updated_at DESC)`

**写入与公开口径：**

- 同一 `repo_url + commit_sha + report_version` 使用 upsert；已完成记录不会被后续 failed 尝试降级覆盖。
- `report_json/evidence_json/tech_stack_json` 在数据库中存 TEXT，DB operations 返回时解码为对象或数组。
- failed 记录保留源码包、成本和错误信息用于排障。
- 公开 API 只读取 `deep_report_settings.public_version` 对应的 completed 记录。
- V2 `report_json` 包含采用决策、架构节点/边、快速上手、部署运行、核心模块和运行时数据流；`evidence_json` 保留但前端不展示。
- `report_markdown` 仅作为内部审计文本，不再承担旧报告前端回退。

### deep_report_settings — 深度报告公开版本

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK CHECK(id = 1) | 固定单行 |
| public_version | INTEGER | 当前公开 API 可见的报告版本 |

批量重建 V2 时先保持 `public_version=1`；完整批次结束后原子更新为 2 并删除全部 V1。当前数据库 schema version 为 11。

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

**样例数据：**

| provider | status | latency_ms | error_count | last_error | last_check | circuit |
|----------|---------|-----------|-------------|-----------|------------|---------|
| deepseek | healthy | 850 | 0 | null | 2026-05-24T09:00:00 | closed |
| minimax | degraded | 2200 | 3 | rate limit | 2026-05-24T09:00:00 | half_open |

### circuit_events — 熔断事件记录

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| provider | TEXT | |
| event | TEXT | open / half_open / close |
| reason | TEXT | |
| created_at | TEXT | |

**样例数据：**

| id | provider | event | reason | created_at |
|----|----------|-------|--------|------------|
| 1 | minimax | open | 连续 3 次 rate limit | 2026-05-24T08:45:00 |
| 2 | minimax | half_open | 尝试恢复 | 2026-05-24T08:50:00 |
| 3 | minimax | close | 连续 5 次成功 | 2026-05-24T09:00:00 |

### schema_version — 数据库迁移版本

| 列 | 类型 |
|----|------|
| version | INTEGER |

**样例数据：**

| version |
|---------|
| 11 |

## extra_data JSON 结构详解

`articles.extra_data` 存储 AI 分析产生的四维评分等详细信息：

```json
{
  "dimensions": {
    "ai_relevance": {
      "score": 35,
      "reason": "核心内容围绕 LLM Agent 工具链"
    },
    "content_depth": {
      "score": 24,
      "reason": "包含架构和实现细节"
    },
    "info_density": {
      "score": 12,
      "reason": "有明确的新功能和技术信息"
    },
    "timeliness": {
      "score": 13,
      "reason": "近期发布"
    }
  },
  "raw": {"source_id": "github_ai_devtools"},
  "language": "en"
}
```

**字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| dimensions | object | 四维评分对象 |
| dimensions[].score | int | 单篇文章该维度得分 |
| dimensions[].reason | string | 单篇文章该维度评分理由 |
| raw | object | Collector 原始元数据快照 |
| language | string | Analyzer 判断的文章语言（en/zh） |

**四维评分说明：**

| 维度 | 说明 | 高分标准 |
|------|------|----------|
| ai_relevance | AI 相关性 | 与 AI/LLM/Agent 领域相关程度 |
| content_depth | 内容深度 | 有详细技术实现或分析 |
| info_density | 信息密度 | 内容充实、信息价值高 |
| timeliness | 时效性 | 近期发布的内容 |
| developer_utility | 项目实用性 | GitHub repo 能直接改善开发者工作流 |
| project_signal | 项目信号 | GitHub repo 有 stars、topics、趋势等社区信号 |
| content_clarity | 内容清晰度 | GitHub repo 摘要清楚说明做什么、给谁用、如何接入 |

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
      topics: [llm, artificial-intelligence, machine-learning, rag, mcp]
      keywords: ["AI agent", "multi-agent", "LLM", "RAG", "MCP"]
      exclude_terms: [wallpaper, porn, nsfw, account, registration, card]
      min_stars: 50
      min_forks: 10
      min_watchers: 20
      lookback_days: 7

  - id: github_ai_devtools
    name: GitHub AI 开发工具
    type: github
    enabled: true
    priority: 1
    cron: "0 */6 * * *"
    max_items: 10
    config:
      topics: []
      keywords: ["interactive knowledge graph", "codebase knowledge graph", "code understanding", "codebase understanding", "repository analysis"]
      exclude_terms: [wallpaper, porn, nsfw, account, registration, card]
      lookback_type: pushed
      lookback_days: 90
      min_stars: 100

  - id: rss_the_batch
    name: The Batch
    type: rss
    enabled: true
    priority: 2
    cron: "0 9 * * 1"        # 周刊
    max_items: 5
    config:
      url: "https://www.deeplearning.ai/the-batch/feed/"
      filter_keywords: [AI, LLM, Agent, RAG, machine learning]
      filter_scope: title_summary

  - id: hn_ai
    name: Hacker News AI
    type: hn
    enabled: true
    priority: 3
    cron: "0 */6 * * *"      # 高频
    max_items: 10
    config:
      api_url: "https://hn.algolia.com/api/v1/search_by_date"
      query: "AI OR LLM OR agent OR RAG OR MCP"
      filter_keywords: [AI, LLM, agent, RAG, MCP, OpenAI]
```

RSS 过滤约定：

- `filter_keywords` 为任一命中即保留；英文关键词按词边界匹配，`AI` 不会命中 `raises` 这类普通单词片段。
- `filter_scope` 默认为 `title_summary`；综合媒体源建议配置为 `title`，避免整篇正文或推荐内容里偶然出现 AI 词导致误采集。
- 配置中避免使用 `技术/科技/智能/technology/Python` 等泛词，优先使用 `大模型/Agent/OpenAI/DeepSeek/豆包/Kimi` 等强信号词。

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
        model: MiniMax-M3
    prompt: prompts/github.md
    budget_weight: 1.0
```
