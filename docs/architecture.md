# 应用架构

## LangGraph DAG 流程

```
APScheduler 北京时间 cron 分组触发 (同 cron 源合并为一个 pipeline run，重叠任务按触发顺序排队)
       │
       ▼
  Collector ─── 按源并行采集 (httpx + asyncio.gather, 含飞书 token 惰性刷新)
       │           ├── GitHub 扩大候选池并优先选择 DB 中未出现的 repo，再写入星标快照
       │           └── DB 批量查重 WHERE url IN (...) → 过滤已入库 url
       │
       ▼
   Router ─── 100% 规则匹配 (按 RawItem.source 字段分流)
       │
       ├──► analyzers/github    (Send fan-out)
       ├──► analyzers/rss       (并行执行, 空数据跳过)
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

## 数据流与阶段模型

三个核心 Pydantic 模型，通过 `ref_url` 关联（不继承，解耦采集和分析）：

| 阶段 | 模型 | 核心字段 | 产出者 |
|------|------|---------|--------|
| 采集 | **RawItem** | url, title, description, source, source_detail, published_at, raw_metadata, collected_at | Collector |
| 分析 | **AnalyzedItem** | ref_url → RawItem.url, title, summary, tags[], language, relevance_score (0-100), retry_count | Analyzer |
| 评分 | **ReviewedItem** | ref_url, total_score, dimensions{ai_relevance/内容深度/信息密度/时效性: {score, reason}}, verdict, retry_feedback | Reviewer |

最终合并写入 articles 表：`raw.url/description/source` + `analyzed.title/summary/tags/language` + `reviewed.total_score/verdict/dimensions`。四维评分细节存入 `extra_data` JSON。ref_url 未匹配的数据自然丢弃，由 `pipeline_runs.summary` 记录。

Reviewer 结果和文章持久化完成后，`run_deep_report_stage()` 作为图外后置阶段运行。它只从本轮 approved/retry 的 GitHub 仓库中选择最多 1 个达到阈值且 7 天内没有 completed 报告的候选，临时 shallow clone 后只读取受限大小的文本、manifest、入口文件和关键源码，不执行仓库代码。扫描结果压缩为证据包交给 `deep_report` Agent，其中每个关键文件内容最多保留 2,000 字符；completed 或 failed 结果写入 `deep_reports`，阶段返回状态也写入 `pipeline_runs.summary.deep_report`。该阶段采用 best-effort 隔离，候选选择、clone、扫描、LLM、成本或报告持久化失败均不会把主 pipeline 标记为失败。

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
- **Provider 熔断**：per-provider 独立，连续 3 次失败 → circuit open → 指数退避试探（60s/120s/240s/480s cap 600s）→ half_open 试探成功恢复；`LLMRegistry.get_client()` 自动遍历 primary → fallback[]
- **预算熔断**：全局软熔断（80% 月预算 → 降级切便宜模型）/ 硬熔断（100% → 停止服务），与 Provider 熔断独立运作
- **Cost Monitor**：`TrackedClient` wrapper 在 `chat.completions.create()` 层记账，非 LangGraph 节点

## 前端渲染策略

| 页面 | 策略 | 数据来源 |
|------|------|---------|
| 首页 | Jinja2 构建时预渲染 30 天首屏 HTML + JS 后台加载 `data.json` 无缝扩展全量；筛选（来源/标签/日期/评分）纯客户端过滤 | `data.json`（列表字段，不含 summary） |
| 详情页 | `article.html` + JS 读 URL param → `fetch /api/articles/{id}` 渲染完整 summary | `/api/articles/{id}` 实时 SQL |
| 仪表盘 | Jinja2 内联 `stats.json` 渲染 KPI 卡片 + Chart.js 画来源饼图 + 每日花费折线 | `stats.json`（KPI+分布+趋势，<10KB） |
| DAG 运行页 | 5 秒轮询 `/api/pipeline/dag?detail=full`，展示阶段、source 漏斗、活跃 item、事件流 | `pipeline_runs` + `pipeline_phase_logs` + `pipeline_events` + `pipeline_source_runs` |
| 深度报告列表 | `deep.html` 静态外壳 + JS 请求 completed 报告列表 | `/api/deep-reports` |
| 深度报告详情 | `deep-report.html` 静态外壳 + JS 按 id 请求详情；无有效 id 时读取 latest | `/api/deep-reports/{id}` / `/api/deep-reports/latest` |
| 搜索 | 300ms 去抖 → `/api/search?q=xxx` FTS5 全文检索 | `/api/search` FTS5 |

## 关键设计决策

- **Router 纯规则**：100% 按 `RawItem.source` 字段分流，无需 LLM
- **Fan-out 并行**：4 个 SubAgent 各自专属 Prompt 和 model，共享通用 `analyze_items()`
- **采集阶段去重**：Collector 后立即 DB 批量查重，已存在 url 不进入 LLM 分析
- **调度口径**：APScheduler、采集 Cron 和每周维护任务均显式使用 `Asia/Shanghai`；同一进程内 pipeline 使用 `asyncio.Lock` 串行执行，碰撞任务记录 `pipeline.queued` 并等待，不静默漏跑。
- **GitHub 采集口径**：Search API 查询由最多 5 个 `topic:` qualifier / 显式 `keywords` 单条件请求组成，每个查询获取 `max_items * 3`（最大 100）个候选；本地合并、阈值过滤后优先返回数据库中未出现的 repo，再用已存在 repo 补足。增速源基于 `github_repo_snapshots` 的最新快照与窗口前最近基线快照计算 star/day。
- **RSS 采集口径**：RSS feed 先由 `httpx.AsyncClient(timeout=30, follow_redirects=True)` 获取文本，再交给 `feedparser` 解析；英文关键词按词边界匹配，综合媒体源可用 `filter_scope: title` 只看标题强信号，避免长正文偶然提及 AI 造成误采集。
- **Reviewer 裁决口径**：LLM 只给四维分和原因；代码统一维度 key、重算 `total_score`，并按阈值裁决 verdict，避免模型自由放行弱相关内容。
- **成本记账口径**：只要 LLM 返回 usage 就记录 `cost_logs`；解析失败和 retry 都按真实调用次数计费，文章级成本由同一 `ref_url` 的 Analyzer + Reviewer 成本汇总得到。
- **Deep Reports 失败隔离**：源码级分析位于 Reviewer/入库后的图外阶段，最多处理一个候选；不执行仓库代码，失败记录保留排障信息但不阻塞主 pipeline。
- **Prompt Schema 强制**：`response_format={"type": "json_object"}` + 首个完整 JSON 对象提取（兼容 `<think>`、markdown、尾部解释）+ Pydantic 校验；Deep Reports 首轮解析失败后，第二轮只携带原输出、校验错误和 Schema 做定向 JSON 修复
- **标签自动生长**：Analyzer 自由建议标签，新标签自动插入 `tags` 表收录（不做强制从池选）
- **原子站点切换**：渲染到 `output.tmp/` → rename 双目录切换，Linux rename 原子操作
