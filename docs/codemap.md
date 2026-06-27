# 代码地图

更新时间：2026-06-28

## CI/CD 与部署

- `.github/workflows/deploy.yml`
  - push `master` 自动部署，`workflow_dispatch` 支持指定 Git ref。
  - `resolve` job 将 ref 固定为完整 commit SHA，test、build-image、deploy 三阶段复用同一 SHA。
  - 镜像发布 SHA 与 `latest` 双标签，VPS 仅部署 SHA 标签；失败时恢复部署前的容器镜像。
  - production concurrency 串行化部署，避免并发 SSH 操作同一 Compose 项目。
  - 常见改动入口：测试命令、镜像标签、拉取超时、健康检查、静态页和公网验收。

- `docker-compose.yml`
  - pipeline 镜像由 `PIPELINE_IMAGE` 显式注入；只在本地或首次初始化未传值时回退 `latest`。

- `Dockerfile`
  - 生产镜像依赖固定版本 uv，并安装 Deep Reports 所需的 `curl` 和 `git`。

- `tests/test_deploy_workflow.py`
  - 部署工作流静态契约测试：SHA 镜像、快速失败、健康等待、自动回滚、手动 ref 和并发策略。

## API 入口

- `src/main.py`
  - FastAPI app 创建、lifespan 初始化、路由注册、异常 handler 注册。
  - APScheduler 和 CronTrigger 显式使用北京时间；采集任务按 cron 分组注册，重叠 pipeline 通过 `_pipeline_lock` 排队，不丢弃已触发任务。
  - `run_pipeline(source_filter=...)` 支持 `None`、单个 source id、多个 source id。
  - 新增 API 路由后需要在 `create_app()` 中 `include_router()`。

- `src/api/responses.py`
  - API 响应信封和错误码映射。
  - 常见改动入口：新增项目错误码、调整 validation 错误消息、统一异常响应格式。

- `src/api/routes.py`
  - 基础 API：文章列表/详情、搜索、基础统计、健康检查、成本 summary、pipeline 手动触发、pipeline DAG。
  - `/api/pipeline/dag` 聚合 `pipeline_runs`、`pipeline_phase_logs`、`pipeline_events`、`pipeline_source_runs`，输出运行摘要、核心处理阶段、审核轮次、发布后处理、最近运行、source 漏斗、活跃 item 和事件流。
  - 常见改动入口：文章接口字段、分页参数、pipeline DAG 状态展示。

- `src/api/stats.py`
  - 统计 API：`/api/stats/enhanced`、质量、运行、消耗、detail 统计。
  - 路由层只做参数校验和 envelope，复杂统计逻辑应下沉到 service 或 db operations。

- `src/api/dashboard.py`
  - 仪表盘专用轻量聚合接口。
  - 当前提供 `/api/dashboard/summary`，用于首屏 KPI，不承载所有 Tab 数据。

- `src/api/sources.py`
  - 数据源列表、数据源健康统计、启用/停用/删除、清理 source health、候选源列表。
  - 优先复用 `src/api/routes.py` 注入的全局 DB，测试或单独调用时 fallback 到 `data/kb.db`。
  - `/api/sources/stats` 返回全部配置源，并从最近 `pipeline_source_runs` 与 `pipeline_events` 推导请求失败、零命中、全重复、分析失败、未调度和禁用状态。
  - Collector 错误来自 `collector.source_error`；Analyzer 错误来自 `analyzer.provider_unavailable/request_failed/parse_failed`，健康表展示最新真实原因。
  - 健康统计响应中 `id` 是存储主键，`name` 是前端展示简称；常见状态入口为 `_derive_health_status()`。

- `src/api/config.py`
  - 配置查看接口：读取 `llm/sources/agents` YAML，返回 raw + parsed。

- `src/api/deep_reports.py`
  - 深度报告公开 API：completed 列表、latest 和详情。
  - 常见改动入口：分页限制、公开状态过滤、详情不存在时的错误契约。

## 业务与数据层

- `src/services/dashboard_stats.py`
  - 仪表盘 summary 和 enhanced stats 的共享统计口径。
  - 常见改动入口：首屏 KPI、通过率、周期成本、活跃来源统计。
  - 日期窗口按北京时间自然日计算，SQL 使用 `date('now', '+8 hours', ...)`。

- `src/db/operations.py`
  - 数据库操作集合：文章保存、标签保存、成本记录、统计查询、备份等。
  - `get_article_detail()` 负责组合文章、标签、标准化四维评分和当前公开深度报告摘要。
  - 常见改动入口：文章查询、统计 SQL、pipeline run 记录、`collection_items` 明细、`pipeline_events` 事件流、`pipeline_source_runs` 漏斗、`cost_logs` 来源归因、GitHub repo 增速快照查询。
  - 费用统计读取 `cost_logs`，资源消耗预算使用 `config/agents.yaml` 的 `budget.monthly`。
  - 所有 `days=N` 查询窗口按北京时间“含今天的 N 个自然日”计算。
  - 目前仍包含较多统计 SQL；后续仪表盘重构时建议逐步拆到 service 层。

- `src/core/database.py`
  - SQLite 连接、迁移执行、基础 fetch/execute/backup API。
  - 常见改动入口：连接 PRAGMA、migration 运行策略、在线备份。

- `src/core/config.py`
  - YAML 配置加载和 Pydantic 模型。
  - 新增配置字段时先改这里，再改对应 YAML 和文档。
  - MiniMax 当前默认模型在 `config/llm.yaml` 注册为 `MiniMax-M3`，各 Agent 在 `config/agents.yaml` 绑定。

- `src/core/budget.py` / `src/core/llm_client.py`
  - 日预算由月预算除以 30；按北京时间自动跨日重置。
  - pipeline 开始时由 `src/main.py::_sync_registry_budget()` 使用 DB 当日费用覆盖内存快照，避免重启绕过预算。
  - soft limit 仅在 fallback 非空时切换；hard limit 才停止所有新请求。

- `src/core/source_registry.py`
  - DB-backed 数据源注册表；同步 `sources.yaml` bootstrap 数据，并返回可调度源和 pipeline 运行源。
  - 人工禁用源设置 `manual_override` 后，自动同步不得恢复；自动 degraded/quarantined/trial/rejected 状态不会被 YAML bootstrap 重置。
  - `trial` 源在这里统一限量到最多 3 条。

- `src/core/source_governance.py`
  - 计算每日数据源健康分，并执行 active/degraded/quarantined/disabled 自动迁移。
  - 预算阻断只记录 `budget_blocked`，不降低源质量分。
  - 候选源自动进入 trial；trial 最近 3 次健康记录达标后转 active，否则转 rejected。

- `src/core/time.py`
  - 项目业务时间统一入口，当前使用北京时间（Asia/Shanghai / UTC+8）。
  - 常见改动入口：日志时间、run_id、采集入库时间、站点构建更新时间。
  - 代码中不要直接使用 `datetime.now(timezone.utc)` 或 SQLite 裸 `datetime('now')` 作为业务时间。

## Deep Reports

- `src/deep_reports/models.py`
  - 候选、仓库扫描结果、源码包、V2 决策报告和阶段结果模型。
  - 常见改动入口：采用决策、架构图节点/边、快速上手/部署流程、源码证据和阶段返回契约。

- `src/deep_reports/selector.py`
  - 从本轮 approved GitHub 项目中选择最多 1 个候选；要求 `project_type=coding_tool`、Reviewer ≥85、AI 相关度 ≥28、开发者实用性 ≥24。
  - 候选分仅用于排序；选择结果附带单一拒绝原因汇总，供 `deep.selector_skipped` / `deep.selector_done` 事件排障。
  - 常见改动入口：项目类型准入、Reviewer 维度阈值、排序权重和 7 天重复分析窗口。

- `src/deep_reports/inspector.py`
  - 临时 shallow clone，过滤依赖/构建目录、二进制和超限文件，读取 README、manifest、入口文件、关键源码与 commit SHA；不执行仓库代码。
  - 常见改动入口：文件大小/数量上限、跳过目录、关键文件识别。

- `src/deep_reports/summarizer.py`
  - 将仓库扫描结果压缩为受限源码包，提取技术栈、文件树摘要和证据列表；每个关键文件内容最多保留 2,000 字符。
  - 常见改动入口：技术栈识别、证据优先级、LLM 输入体积。

- `src/deep_reports/analyzer.py`
  - 通过 `LLMRegistry` 调用 `deep_report` Agent，加载 `prompts/deep_report.md`，校验结构化输出并记录每次尝试成本；首轮解析失败时，第二轮使用原输出、校验错误和 Schema 做定向 JSON 修复。
  - 常见改动入口：报告 schema、Prompt 参数、解析与重试策略。

- `src/deep_reports/service.py`
  - 编排 selector → inspector → summarizer → analyzer → persistence，并记录 `deep.*` pipeline events。
  - 常见改动入口：主 pipeline 接入、失败隔离、V2 成本/报告持久化和内部 Markdown 审计文本。

- `src/deep_reports/rebuild.py`
  - 批量读取 V1 报告，重新 clone/分析为 V2，支持 dry-run、数量/成本限制、单仓库重试，并在完整批次结束后原子切换公开版本和删除 V1。
  - 常见改动入口：重建筛选、预算停止条件、失败仓库重试和静态站重建。

## Pipeline

- `src/graph/collector.py`
  - 多源采集和 DB 查重。
  - GitHub 采集将 `topics`/`keywords` 拆成最多 5 个单条件 Search 请求，每个请求获取扩大后的候选池；合并和阈值过滤后优先返回 DB 中未出现的 repo。
  - `github_ai_devtools` 用于抓取 Coding Agent、AI 编程助手、代码生成/审查和 AI IDE 类仓库，并在采集阶段过滤教程、课程、writeup 和资源合集等明显噪音；关键词在 `config/sources.yaml` 维护。
  - RSS 采集先用 `httpx.AsyncClient(timeout=30)` 拉取 feed 文本，再交给 `feedparser` 解析；先过滤关键词再限制数量，关键词过滤使用 `_matches_rss_keywords()`。
  - `collect_hotlist()` 通过 NewsNow 统一接口抓取 AIHOT、掘金、知乎等热榜，校验 HTTPS/目标域名并保留榜单排名元数据。
  - `RawItem.raw_metadata.source_id` 保存配置 id，供 source health、成本归因等后续阶段使用。

- `src/main.py`
  - Pipeline 运行源从 `source_registry` 读取，`sources.yaml` 只在运行前同步 bootstrap 数据。
  - GitHub repo 快照在 DB 查重前写入，`trend_mode=true` 的源只过滤本源采集结果，不影响同批次其它 GitHub/RSS/arXiv 源。
  - 图外入库前按 `ref_url` 汇总 Analyzer + Reviewer 成本，写入文章级 `analysis_cost/analysis_tokens`，并为 Reviewer 成本补齐来源快照。
  - `trial` 源通过审核后只记录试跑事件和健康数据，不写入正式文章。
  - Pipeline 会写入 `collection_items`、`pipeline_source_runs` 和 `pipeline_events`，用于追踪采集、去重、分析、审核、入库的 source 级漏斗和 item 级事件。
  - Retry 轮复用已有 `AnalyzedItem` 直接重审 Reviewer，不再重新进入 Analyzer；入口为 `_prepare_retry_review_items()`。
  - 有新条目但 Analyzer 全部失败时写入失败 item/cost/source funnel，并将 pipeline 标记 failed；不会继续 Deep Report 或站点构建。

- `src/graph/pipeline.py`
  - LangGraph DAG 编排、phase log 记录、Analyzer/Reviewer item 级事件记录。

- `src/scheduler/source_scheduler.py`
  - 每周数据源维护：发现候选源、候选转小流量 trial、评估 trial 自动上线或拒绝。
  - 使用 `data/kb.db` 并显式初始化数据库连接；维护 Cron 使用 `Asia/Shanghai`。

- `src/graph/router.py`
  - 按 `RawItem.source` 做规则路由；`hotlist` 复用 `routed_rss` 和 RSS Analyzer。

- `src/graph/analyzers/`
  - 各源 Analyzer 薄层；通用实现位于 `base.py`。
  - Analyzer 成本记录在 `base.py` 写入 `CostRecord`，来源字段来自 `RawItem`。
  - `AnalyzedItem` 会透传 `source/source_id/source_detail/metadata`，供 Reviewer 做 source-aware 审核。
  - Analyzer 输出 JSON 解析复用 `src/core/json_utils.py::extract_json_object()`。

- `src/graph/reviewer.py`
  - 四维评分审核。
  - LLM 输出只作为四维打分草稿；解析阶段会统一维度 key、重算 `total_score`，并由代码按阈值裁决 `approved/retry/discarded`。
  - 普通文章/arXiv 使用 `prompts/reviewer.md` 和文章型四维评分；GitHub repo 使用 `prompts/github_reviewer.md` 和 repo-aware 四维评分，避免 AI 开源工具被文章深度标准误伤。
  - Reviewer 使用 `config/agents.yaml` 中 `reviewer.params.concurrency` 控制有限并发，`timeout_seconds` 控制单次 LLM 请求超时；默认建议为并发 3、超时 60 秒。
  - Reviewer 成本记录先保留 `ref_url`，图外入库前由 `src/main.py` 按本轮 `RawItem` 补齐来源字段。
  - Reviewer 节点结束后由 `src/graph/pipeline.py` 按配置 id 汇总 source health。
  - Reviewer 输出 JSON 解析复用 `src/core/json_utils.py::extract_json_object()`，兼容 M3 thinking tags、markdown 包裹和尾部解释。

- `src/core/json_utils.py`
  - LLM JSON 输出容错工具。
  - 常见改动入口：新增 provider 特殊输出格式、调整 JSON 提取策略。

## 静态站与仪表盘前端

- `src/site/builder.py`
  - 静态站生成、临时目录原子替换、dashboard 模板渲染。
  - 首页使用 `list_summary`（120 字），`data.json` 保留最长 200 字 summary 供筛选和动态列表展示。
  - `DebouncedBuilder` 绑定触发 run id，记录构建 queued/running/completed/failed；后续 run 合并旧任务时记录 superseded。

- `src/site/templates/index.html` / `src/site/templates/article.html`
  - 首页文章卡片、详情抽屉静态结构和可分享的独立详情页挂载点。
  - 文章链接始终保留 `/article.html?id={id}`，普通点击由首页抽屉接管。

- `src/site/templates/dashboard.html`
  - 仪表盘 DOM 结构。
  - 后续重构时保持模板只描述结构，不塞复杂逻辑。

- `src/site/templates/dag.html` / `src/site/static/js/dag.js`
  - Pipeline 三层运行视图：运行摘要、核心处理、发布与后处理。
  - 区分数据流水线和网站发布状态；审核 retry 在节点内部按轮次展示；支持最近运行切换和原始事件折叠排障。

- `src/site/templates/deep.html` / `src/site/templates/deep-report.html`
  - 深度报告列表和详情静态外壳，由浏览器端请求公开 API。
  - 常见改动入口：页面结构、加载/空/错误状态容器。

- `src/site/static/js/deep-reports.js`
  - 深度报告列表/详情请求、安全转义、V2 决策漏斗、SVG 架构图和流程卡片渲染；移动端架构自动降级为节点卡片。
  - 常见改动入口：采用结论、架构/流程布局、latest 回退和外链安全。

- `src/site/static/js/app.js`
  - 首页文章列表筛选、来源/标签/日期过滤和详情抽屉点击接入。
  - 不再承载 dashboard Tab 控制逻辑。

- `src/site/static/js/article-detail.js`
  - 首页抽屉与独立详情页共用的文章详情请求和 DOM 安全渲染。
  - 展示完整摘要、原始简介、全部标签、四维评分、处理信息和深度报告入口；负责加载/错误状态及抽屉关闭、焦点恢复。

- `src/site/static/js/dashboard/api.js`
  - 仪表盘 API 请求封装，统一校验响应信封。

- `src/site/static/js/dashboard/state.js`
  - 仪表盘当前 Tab、周期、缓存状态。

- `src/site/static/js/dashboard/charts.js`
  - Chart.js 创建、销毁和通用图表封装。

- `src/site/static/js/dashboard/renderers.js`
  - 数据质量、资源消耗、数据源健康三个 Tab 的 DOM 和图表渲染。

- `src/site/static/js/dashboard/main.js`
  - 仪表盘初始化、Tab 切换、周期切换和数据调度。

- `src/site/static/css/style.css`
  - 全站样式、dashboard 样式和 DAG 运行页样式。

## 测试入口

- `tests/test_api_contracts.py`
  - API 契约测试：响应信封、错误码、分页、tags、sources DB 注入、dashboard summary、pipeline DAG 细粒度响应。

- `tests/test_stats_quality_detail.py`
  - 仪表盘质量详情统计契约测试。

- `tests/test_database.py`
  - SQLite migration、唯一约束、FTS5 同步、pipeline event 持久化。

- `tests/test_deep_reports_db.py` / `tests/test_deep_reports_api.py`
  - 深度报告迁移、upsert 保护、completed-only 公开查询和 404 契约。

- `tests/test_deep_reports_selector.py` / `tests/test_repo_inspector.py`
  - 候选评分/去重窗口和源码扫描安全边界。

- `tests/test_deep_reports_analyzer.py` / `tests/test_deep_reports_pipeline.py`
  - V2 Prompt/结构化输出、图关系校验、成本记录、阶段编排和主 pipeline 失败隔离。

- `tests/test_deep_reports_rebuild.py`
  - dry-run、完整切换、部分失败、单仓库重试、数量限制和成本上限。

## 文档入口

- `docs/api.md`
  - API 契约事实表。新增/修改 API 后必须同步。

- `docs/structure.md`
  - 目录职责和核心约定。新增模块或移动职责后同步。

- `docs/architecture.md`
  - 架构设计、DAG、数据流、前端渲染策略。

- `docs/task.md`
  - 当前任务拆解、优先级、状态。

- `docs/codemap.md`
  - 常见代码入口和模块职责地图。
