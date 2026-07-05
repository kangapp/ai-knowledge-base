# 应用架构

## LangGraph DAG 流程

```
APScheduler 北京时间 cron 分组触发 (同 cron 源合并为一个 pipeline run，重叠任务按触发顺序排队)
       │
       ▼
  Collector ─── 按源并行采集 (httpx + asyncio.gather, 含飞书 token 惰性刷新)
       │           ├── GitHub 扩大候选池并优先选择 DB 中未出现的 repo，再写入星标快照
       │           ├── NewsNow 热榜按平台抓取，执行 HTTPS/域名校验后复用文章分析链路
       │           └── DB 批量查重 WHERE url IN (...) → 过滤已入库 url
       │
       ▼
   Router ─── 100% 规则匹配 (按 RawItem.source 字段分流)
       │
       ├──► analyzers/github    (Send fan-out，base.analyze_items 按 Agent concurrency 有限并发)
       ├──► analyzers/rss       (RSS + hotlist + HN, 并行执行, 空数据跳过)
       ├──► analyzers/feishu    (共享 base.analyze_items())
       └──► analyzers/arxiv     (自动打 1-3 个标签)
       │
       ▼
  Aggregator ─── 汇总 analyzed_items + Pydantic 校验 + 成本统计
       │
       ▼
  Reviewer ─── 四维评分 (temp=0, 含逐维度 score+reason)
       │           ├── ≥80 → approved → 入库
       │           ├── 50-79 → retry (带 retry_feedback.suggestions, 限 2 轮)
       │           └── <50 → discarded
       │
       ▼
  入库 SQLite ─── articles + tags (新标签自动收录) + cost_logs + pipeline_runs
       │              └── DB 写入走 db/operations.py 兼容入口，内部拆分 articles/pipeline_ops/costs/deep_report_ops
       │
       ▼
  Deep Reports ─── Reviewer/入库后的图外后置阶段，最多选择 1 个高价值 GitHub repo
       │              ├── 临时 shallow clone → 确定性源码扫描 → 紧凑证据包 → LLM 深度分析
       │              ├── completed/failed 写入 deep_reports，LLM 调用独立写入 cost_logs
       │              └── 任一环节失败仅记录 deep.failed，不影响主 pipeline completed
       │
       ▼
  Site Builder ─── 去抖触发 (5min 计时器) → output.tmp/ 渲染 → 原子 rename → 上线
                    └── 手动 POST /api/pipeline/build 可调 build_now() 跳过去抖

横切: pipeline_phase_logs 记录阶段耗时；pipeline_events 记录 source/item/LLM 调用/入库/构建细粒度事件；TrackedClient wrapper 负责每次 LLM 调用记账 + 熔断检查 + fallback
```

数据源治理作为周/日维护闭环在主 pipeline 外运行：`SourceDiscovery` 只写候选源，`source_registry` 管理 candidate/trial/active/degraded/quarantined/rejected 等状态，trial 源小流量试跑后由 `SourceGovernance` 根据 `source_health_daily` 健康分自动上线或拒绝。预算阻断记录为 `budget_blocked`，不降低源质量分。

## 数据流与阶段模型

三个核心 Pydantic 模型，通过 `ref_url` 关联（不继承，解耦采集和分析）：

| 阶段 | 模型 | 核心字段 | 产出者 |
|------|------|---------|--------|
| 采集 | **RawItem** | url, title, description, source, source_detail, published_at, raw_metadata, collected_at | Collector |
| 分析 | **AnalyzedItem** | ref_url → RawItem.url, title, summary, tags[], language, relevance_score (0-100), retry_count | Analyzer |
| 评分 | **ReviewedItem** | ref_url, total_score, dimensions（普通文章：ai_relevance/content_depth/info_density/timeliness；GitHub repo：ai_relevance/developer_utility/project_signal/content_clarity）, verdict, retry_feedback | Reviewer |

最终合并写入 articles 表：`raw.url/description/source` + `analyzed.title/summary/tags/language` + `reviewed.total_score/verdict/dimensions`。四维评分细节存入 `extra_data` JSON。ref_url 未匹配的数据自然丢弃，由 `pipeline_runs.summary` 记录。

## 核心链路细化

### Collector type / adapter 映射

| source type | 采集适配器 | 输入来源 | RawItem 输出特征 |
|-------------|------------|----------|------------------|
| `github` | `collect_github(source, db)` | GitHub Search repositories API | `source=github`，`source_detail=owner/repo`，`raw_metadata` 写 stars/forks/watchers/language/topics/source_id |
| `rss` | `collect_rss(source)` | RSS/Atom feed URL | `source=rss`，`source_detail=source.name`，`raw_metadata.feed/source_id` |
| `hotlist` | `collect_hotlist(source)` | NewsNow hotlist API | `source=hotlist`，`raw_metadata.rank/platform_id/source_id`，执行 HTTPS 与 expected_domain 校验 |
| `hn` | `collect_hn(source)` | Hacker News Algolia API | `source=hn`，`description` 写 points/comments，`raw_metadata.points/num_comments/source_id` |
| `feishu` | `collect_feishu(source)` | 飞书 wiki space/page API | `source=feishu`，`source_detail=space_id`，`raw_metadata.node_id/space_id/source_id` |
| `arxiv` | `collect_arxiv(source)` | arXiv export API | `source=arxiv`，`source_detail=category`，`raw_metadata.categories/source_id` |

Collector 流程：

```text
SourceConfig[] → collect_all()
  → COLLECTOR_MAP[source.type]
  → collect_* 适配器并发执行
  → RawItem[]
  → URL 批量查重
  → PipelineState.raw_items
```

示例 `RawItem`：

```json
{
  "url": "https://github.com/example/agent-runtime",
  "title": "agent-runtime",
  "source": "github",
  "source_detail": "example/agent-runtime",
  "raw_metadata": {
    "source_id": "github_ai_devtools",
    "stars": 1240,
    "language": "Python"
  }
}
```

### Router / Analyzer 映射

| RawItem.source | routed key | Analyzer | 说明 |
|----------------|------------|----------|------|
| `github` | `routed_github` | `github_analyzer` | GitHub repo 专用 prompt，输出 `project_type` |
| `rss` | `routed_rss` | `rss_analyzer` | 普通资讯 |
| `hotlist` | `routed_rss` | `rss_analyzer` | 热榜条目按资讯处理，但入库保留 `source=hotlist` |
| `hn` | `routed_rss` | `rss_analyzer` | HN story 按资讯处理，但入库保留 `source=hn` |
| `feishu` | `routed_feishu` | `feishu_analyzer` | 内部知识库文档 |
| `arxiv` | `routed_arxiv` | `arxiv_analyzer` | 论文条目 |

LangGraph 图内流程：

```text
START
  → router
  → continue_to_analyzers()
  → Send(github/rss/feishu/arxiv analyzer, state)
  → aggregator
  → reviewer
  → END
```

LangGraph 图外流程：

```text
collector / dedupe / retry reviewer / persist / deep_reports / site_builder
```

示例 `PipelineState` 片段：

```json
{
  "run_id": "run_20260705_093000",
  "raw_items": [{"source": "github", "url": "https://github.com/example/agent-runtime"}],
  "routed_github": [{"url": "https://github.com/example/agent-runtime"}],
  "analyzed_items": [{"ref_url": "https://github.com/example/agent-runtime", "project_type": "coding_tool"}],
  "reviewed_items": [{"ref_url": "https://github.com/example/agent-runtime", "total_score": 88, "verdict": "approved"}]
}
```

### 失败路径

| 失败点 | 记录位置 | 是否中断 | 恢复方式 |
|--------|----------|----------|----------|
| 单 source 采集超时 | `error_log`、`source_health.failed`、`collector.error` | 不影响其它 source | 下次 cron 自动重试 |
| Analyzer 单 item 失败 | `pipeline_events`、`cost_logs.status=request_failed/parse_failed` | 不影响其它 item | fallback 或下次运行；parse_failed 调整 prompt |
| 有新条目但 Analyzer 全失败 | `pipeline_runs.status=failed`、逐条 `pipeline_events` | 中断后置 Deep Reports 和 Site Builder | 修复 Provider/Prompt 后手动重跑 |
| Reviewer retry | `ReviewedItem.retry_feedback`、`pipeline_events` | 不直接失败，最多重审 2 轮 | 根据 feedback 调整 prompt 或接受丢弃 |
| Deep Reports 失败 | `deep_reports.status=failed`、`deep.failed` | 不影响主 pipeline completed | 单 repo 重试或重建 |
| Site Builder 失败 | `build.failed` | 不影响数据 pipeline，旧站点保留 | 修复模板/权限后手动 build |

Reviewer 结果和文章持久化完成后，`run_deep_report_stage()` 作为图外后置阶段运行。GitHub Analyzer 先按仓库主要交付物输出结构化 `project_type`；该阶段只从本轮 `approved`、Reviewer 总分至少 85、`ai_relevance` 至少 28、`developer_utility` 至少 24 且 `project_type=coding_tool` 的 GitHub 仓库中选择最多 1 个候选，并跳过 7 天内已有 completed 报告的仓库。论文、模型权重、数据集、benchmark、资源合集、通用 AI 基础设施和框架均通过结构化类型排除。候选分只用于合格项目之间排序，不再作为第二道准入门槛；stars 不参与候选评分。`deep.selector_skipped` 和 `deep.selector_done` 事件携带汇总诊断，可直接查看各拒绝原因数量。

入选仓库临时 shallow clone 后只读取受限大小的文本、manifest、入口文件和关键源码，不执行仓库代码。扫描结果压缩为证据包交给 `deep_report` Agent，其中每个关键文件内容最多保留 2,000 字符。V2 Agent 输出采用决策、架构节点/连线、快速上手、部署运行、核心模块和运行时数据流；源码证据继续约束 LLM 结论，但不在详情页展示。completed 或 failed 结果以 `report_version=2` 写入 `deep_reports`，阶段返回状态也写入 `pipeline_runs.summary.deep_report`。该阶段采用 best-effort 隔离，候选选择、clone、扫描、LLM、成本或报告持久化失败均不会把主 pipeline 标记为失败。

历史 V1 报告由 `python -m src.deep_reports.rebuild` 独立重建。重建期间公开 API 继续读取 `deep_report_settings.public_version=1`；完整批次结束后在同一事务中切换到 V2 并删除 V1。失败仓库保留 V2 failed 记录，可按 repo 单独重试。

## Reviewer 四维评分锚点

| 维度 | 权重 | 评分标准 |
|------|------|---------|
| AI 相关度 | 0-40 | 35-40: 核心 AI/LLM/Agent/MCP/RAG；25-34: AI 基础设施；10-24: 泛技术提及 AI；0-9: 无关 |
| 内容深度 | 0-30 | 25-30: 深度内容有原创贡献；15-24: 有具体细节；5-14: 简要介绍；0-4: 空内容 |
| 信息密度 | 0-15 | 12-15: 新颖/独家信息；7-11: 有一定信息量；0-6: 重复/营销 |
| 时效性 | 0-15 | 12-15: 本周内；7-11: 本月；0-6: 较早 |

- temperature=0, 每维度强制 `score` + `reason`（隐式 CoT）
- verdict=retry 时附带 `retry_feedback.suggestions`，系统最多再重审 2 轮
- retry 轮复用已有 `AnalyzedItem`，不再重新跑 Analyzer；当前 Analyzer prompt 不消费 reviewer feedback，重复分析只增加耗时和成本

## LLM 模型管理

- **协议**：所有 Provider 统一走 OpenAI 兼容协议 (base_url + api_key)
- **配置三层**：`llm.yaml`（Provider 注册 + 模型价格）→ `agents.yaml`（SubAgent 绑定 primary/fallback[] + 参数）→ `.env`（密钥）
- **飞书认证**：`FeishuAuth` 类内存缓存 `tenant_access_token` + 过期时间，有效期 <3min 自动刷新；token 频率由 2h 有效期决定而非采集频率
- **健康检查**：被动探测（调用失败记录）+ 主动探测（定时最小请求）
- **Provider 熔断**：per-provider 独立，仅网络、超时等请求失败计入；连续 3 次失败 → circuit open → 指数退避试探（60s/120s/240s/480s cap 600s）→ half_open 试探成功恢复。JSON/Pydantic 解析失败属于输出质量问题，不打开 Provider 熔断。
- **预算熔断**：`monthly / 30` 得到北京时间日预算。每次 pipeline 开始从 `cost_logs` 对账当天真实费用，内存跟踪器也会在北京时间跨日自动清零。达到 80% 时仅在配置了 fallback 时切换便宜模型；无 fallback 继续 primary。达到 100% 时停止新的 LLM 请求。
- **全量分析失败**：有新条目但 Analyzer 产出为 0 时，pipeline 标记 `failed`，逐条写入 `provider_unavailable/request_failed/parse_failed` 原因，不再以 completed 掩盖故障。
- **Cost Monitor**：`TrackedClient` wrapper 在 `chat.completions.create()` 层记账，非 LangGraph 节点

## 前端渲染策略

展示链路：

```text
SQLite
  → Site Builder 生成 output/
  → Caddy serve 静态 HTML/CSS/JS/data.json/stats.json
  → 浏览器加载页面外壳
  → 页面 JS 按需请求 FastAPI /api/*
  → DOM 渲染详情、搜索结果、DAG 状态和 Deep Reports
```

前端采用“静态首屏 + 动态详情”的口径：公开阅读所需的首页、仪表盘外壳、DAG 外壳和 Deep Reports 外壳由 Site Builder 生成；文章详情、搜索、运行状态和深度报告正文按需请求 FastAPI。

| 页面 | 策略 | 数据来源 |
|------|------|---------|
| 首页 | Jinja2 构建时预渲染最近 100 条 + JS 后台加载 `data.json` 无缝扩展全量；卡片展示不超过 120 字的 Analyzer 中文摘要并限制三行；普通点击在右侧抽屉打开详情，修饰键仍打开独立详情页；筛选（来源/标签/日期/评分）纯客户端过滤 | `data.json`（列表 summary + 原始 description 搜索字段）+ `/api/articles/{id}` |
| 详情页 | `article.html` 与首页抽屉复用 `article-detail.js`；通过 DOM API 安全渲染完整摘要、原始简介、全部标签、发布时间、四维评分和公开深度报告入口；加载/404/网络错误统一展示状态 | `/api/articles/{id}` 实时 SQL |
| 仪表盘 | Jinja2 内联 `stats.json` 渲染 KPI 卡片 + Chart.js 画来源饼图 + 每日花费折线 | `stats.json`（KPI+分布+趋势，<10KB） |
| DAG 运行页 | 5 秒轮询 `/api/pipeline/dag?detail=full`；按运行摘要、核心处理、发布后处理三层展示，区分数据流水线和网站发布状态，支持切换最近运行；source 漏斗、活跃 item、原始事件用于排障 | `pipeline_runs` + `pipeline_phase_logs` + `pipeline_events` + `pipeline_source_runs` |
| 深度报告列表 | `deep.html` 静态外壳 + JS 请求 completed 报告列表 | `/api/deep-reports` |
| 深度报告详情 | `deep-report.html` 静态外壳 + JS 按 id 请求 V2 详情；按采用结论 → 场景 → 架构图 → 快速上手 → 部署运行 → 技术细节渲染，移动端架构降级为卡片 | `/api/deep-reports/{id}` / `/api/deep-reports/latest` |
| 搜索 | 300ms 去抖 → `/api/search?q=xxx` FTS5 全文检索 | `/api/search` FTS5 |

## 关键设计决策

- **Router 纯规则**：100% 按 `RawItem.source` 字段分流，无需 LLM
- **Fan-out 并行**：4 个 SubAgent 各自专属 Prompt 和 model，共享通用 `analyze_items()`
- **Analyzer 有限并发**：`base.analyze_items()` 读取 `agents.yaml` 的 `params.concurrency`，默认保守并保持输入输出顺序稳定。
- **采集阶段去重**：Collector 后立即 DB 批量查重，已存在 url 不进入 LLM 分析
- **调度口径**：APScheduler、采集 Cron 和每周维护任务均显式使用 `Asia/Shanghai`；同一进程内 pipeline 使用 `asyncio.Lock` 串行执行，碰撞任务记录 `pipeline.queued` 并等待，不静默漏跑。
- **双生命周期**：`pipeline_runs.status` 只表示数据流水线；静态构建独立记录 queued/running/completed/failed/superseded。5 分钟去抖期间若有新流水线完成，旧构建标记 superseded，由最新 run 统一发布。
- **GitHub 采集口径**：Search API 查询由最多 5 个 `topic:` qualifier / 显式 `keywords` 单条件请求组成，每个查询获取 `max_items * 3`（最大 100）个候选；本地合并、阈值过滤后优先返回数据库中未出现的 repo，再用已存在 repo 补足。增速源基于 `github_repo_snapshots` 的最新快照与窗口前最近基线快照计算 star/day。
- **RSS 采集口径**：RSS feed 先由 `httpx.AsyncClient(timeout=30, follow_redirects=True)` 获取文本，再交给 `feedparser` 解析；遍历完整 feed，先做关键词过滤，再限制 `max_items`；英文关键词按词边界匹配，综合媒体源可用 `filter_scope: title` 只看标题强信号。
- **热榜采集口径**：`hotlist` 通过配置中的 NewsNow `api_url + platform_id` 获取榜单；只接受 HTTPS URL，可按 `expected_domain` 限制目标域名，先过滤关键词再限制数量。热榜条目路由到 `rss_analyzer`，但入库保留 `source=hotlist` 和配置 source ID。
- **HN 采集口径**：`hn` 通过 Algolia Hacker News Search API 获取 `story`，先按关键词过滤再限制数量；无外链时回退到 HN item URL。HN 条目路由到 `rss_analyzer`，入库保留 `source=hn` 和配置 source ID。
- **Reviewer 裁决口径**：LLM 只给四维分和原因；代码统一维度 key、重算 `total_score`，并按阈值裁决 verdict，避免模型自由放行弱相关内容。
- **成本记账口径**：只要 LLM 返回 usage 就记录 `cost_logs`；解析失败和 retry 都按真实调用次数计费，文章级成本由同一 `ref_url` 的 Analyzer + Reviewer 成本汇总得到。
- **Deep Reports 失败隔离**：源码级分析位于 Reviewer/入库后的图外阶段，最多处理一个候选；不执行仓库代码，失败记录保留排障信息但不阻塞主 pipeline。
- **Deep Reports 版本切换**：公开 API 只查询 `deep_report_settings.public_version` 对应的 completed 报告；V1/V2 可在重建期间并存，最终切换与 V1 删除原子完成。
- **DB 访问层拆分**：业务模块继续从 `src/db/operations.py` 导入数据库函数；实现按职责拆到 `articles.py`、`pipeline_ops.py`、`costs.py`、`deep_report_ops.py`，统计和备份等兼容逻辑仍留在 `operations.py`。
- **Prompt Schema 强制**：`response_format={"type": "json_object"}` + 首个完整 JSON 对象提取（兼容 `<think>`、markdown、尾部解释）+ Pydantic 校验；Deep Reports 首轮解析失败后，第二轮只携带原输出、校验错误和 Schema 做定向 JSON 修复
- **标签自动生长**：Analyzer 自由建议标签，新标签自动插入 `tags` 表收录（不做强制从池选）
- **原子站点切换**：渲染到 `output.tmp/` → rename 双目录切换，Linux rename 原子操作
