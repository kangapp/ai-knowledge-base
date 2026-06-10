# 数据源健康可靠性修复设计

## 目标

修复 VPS 上数据源长期显示零采集的根因，并让仪表盘能区分调度、请求、过滤、去重、分析和入库阶段，不再把不同问题都表现成“采集量为 0”。

## 已确认根因

1. APScheduler 使用容器 UTC，`sources.yaml` 中的 Cron 被错后 8 小时执行。
2. 所有 pipeline 共用 `_running` 布尔锁，碰撞任务直接跳过，Ars Technica 和 Reuters 因此长期漏跑。
3. 虎嗅、掘金 RSS 地址返回 404，Product Hunt 旧 FeedBurner 地址超时，Reuters Feed 超时。
4. GitHub 每次只取按 stars 排序的前 10 条，热门源 7 天重复率接近 90%。
5. 健康接口只聚合 `source_health`，没有运行记录、禁用源、请求错误和阶段状态的清晰表达。

## 方案

### 调度

- `AsyncIOScheduler` 和 `CronTrigger` 显式使用 `Asia/Shanghai`。
- 使用进程内 `asyncio.Lock` 串行 pipeline。任务碰撞时等待执行并记录 `pipeline.queued`，不再静默丢弃。
- 保留按相同 Cron 分组的 source group，避免同一时刻创建无意义的并发 pipeline。

### 数据源配置

- Product Hunt 改用可从 VPS 正常访问的官方 `https://www.producthunt.com/feed`。
- 虎嗅、掘金、Reuters 暂时禁用。不存在稳定官方 Feed 时不接入非官方代理，避免引入新的外部依赖。
- Ars Technica 保持启用，由北京时间调度和排队机制恢复执行。
- arXiv 保持每周一执行，飞书保持禁用。

### GitHub 增量

- 每个 GitHub Search 查询获取 `max_items * 3` 个候选，最大不超过 GitHub Search 单页上限 100。
- 当 Collector 有数据库连接时，批量查询候选 URL，优先返回未入库仓库，再用已存在仓库补足 `max_items`。
- 不改变 stars/forks/watchers、关键词、排除词和 Reviewer 策略，控制改动范围和成本。

### 健康状态

`/api/sources/stats` 返回所有配置源，并增加：

- `health_status`：`disabled`、`not_scheduled`、`failed`、`success_zero`、`dedup_only`、`analysis_failed`、`healthy`
- `last_run_at`
- `last_error`
- `last_collected`、`last_new_items`、`last_dedup_skipped`
- `last_analyzed`、`last_analysis_failed`、`last_inserted`

状态以最近一次 `pipeline_source_runs` 为主，最近一次 `pipeline_events` 错误作为原因说明。窗口累计指标继续保留，兼容现有前端和 API 调用方。

### 前端

- 数据源健康 KPI 的“活跃数据源”只统计 `healthy/dedup_only/success_zero/analysis_failed`，禁用和未调度不计入。
- 表格增加状态、有效新增、去重、分析失败、最近运行和错误信息。
- 平均通过率和平均分只对有有效分母的数据源计算，避免大量空源把平均值拉成 0。

## 错误处理

- 单源请求失败继续隔离，不影响同批其它源。
- HTTP 状态和异常文本继续写 `pipeline_events`；健康 API 只返回简短错误文本，不暴露堆栈。
- 无稳定官方 Feed 的源保持 disabled，而不是用不可靠地址制造连续失败。

## 验证

1. 调度测试验证北京时间和碰撞任务等待执行。
2. Collector 测试验证 GitHub 候选池扩大、未入库 URL 优先和 RSS 地址配置。
3. API 契约测试覆盖全部健康状态和无历史记录的配置源。
4. 前端契约测试覆盖状态列和有效平均值计算。
5. 运行非 integration/e2e 全量测试并执行 `git diff --check`。
