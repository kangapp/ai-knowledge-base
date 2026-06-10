# Source Health Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复数据源调度漏跑、失效 RSS、GitHub 高重复和健康状态不可诊断问题。

**Architecture:** 继续使用单进程 APScheduler 和现有 pipeline 事实表。调度碰撞改为进程内锁排队；GitHub 在采集器内基于数据库 URL 优先选择新候选；健康 API 从配置、窗口聚合、最近 source run 和错误事件推导状态。

**Tech Stack:** Python 3.12、FastAPI、APScheduler、aiosqlite、httpx、pytest、原生 JavaScript。

---

### Task 1: 北京时间调度和排队执行

**Files:**
- Modify: `src/main.py`
- Modify: `src/scheduler/source_scheduler.py`
- Test: `tests/test_scheduler.py`

- [x] 增加失败测试，验证采集 Cron job 和每周维护 job 都显式使用 `Asia/Shanghai`。
- [x] 增加失败测试，验证两个重叠 pipeline 调用按顺序完成而不是丢弃第二次调用。
- [x] 将 `_running` 布尔值替换为惰性创建的 `asyncio.Lock`，等待时记录 `pipeline.queued`。
- [x] 使用 `AsyncIOScheduler(timezone=BEIJING_TZ)`，所有 `CronTrigger` 使用同一时区。
- [x] 运行 `tests/test_scheduler.py` 和受影响的 pipeline 测试。

### Task 2: 数据源配置和 GitHub 增量

**Files:**
- Modify: `config/sources.yaml`
- Modify: `src/graph/collector.py`
- Test: `tests/test_collector.py`
- Test: `tests/test_config.py`

- [x] 增加失败测试，验证 GitHub 请求候选池为 `max_items * 3`。
- [x] 增加失败测试，验证传入 DB 时未入库 URL 优先于已存在 URL。
- [x] 为 `collect_github` 增加可选 DB 参数，批量检查候选 URL 后稳定排序并截取。
- [x] Product Hunt 改为官方 Feed；禁用当前无稳定 Feed 的虎嗅、掘金和 Reuters。
- [x] 运行 Collector 和配置测试。

### Task 3: 健康 API 状态

**Files:**
- Modify: `src/api/sources.py`
- Test: `tests/test_api_contracts.py`

- [x] 增加失败契约测试，覆盖 disabled、not_scheduled、failed、success_zero、dedup_only、analysis_failed、healthy。
- [x] 查询窗口累计 source run、每个源最近 source run 和最近错误事件。
- [x] 遍历所有配置源组装统计，未产生 `source_health` 的源也必须返回。
- [x] 返回最近运行漏斗、错误和推导后的 `health_status`。
- [x] 运行 API 契约测试。

### Task 4: 仪表盘健康展示

**Files:**
- Modify: `src/site/templates/dashboard.html`
- Modify: `src/site/static/js/dashboard/renderers.js`
- Modify: `src/site/static/css/style.css`
- Test: `tests/test_dashboard_frontend_contract.py`

- [x] 增加失败前端契约测试，验证状态、有效新增、去重、分析失败、最近运行和错误列。
- [x] 只用有数据的源计算平均通过率和平均评分。
- [x] 增加健康状态中文标签和状态样式。
- [x] 运行前端契约测试并构建静态站。

### Task 5: 文档和最终验证

**Files:**
- Modify: `docs/task.md`
- Modify: `docs/codemap.md`
- Modify: `docs/api.md`
- Modify: `docs/architecture.md`
- Modify: `docs/operations.md`
- Modify: `docs/data-model.md`

- [x] 记录调度时区、排队语义、源配置决策、GitHub 增量和健康状态契约。
- [x] 运行 `pytest -m "not integration and not e2e"`。
- [x] 运行 `git diff --check` 并检查工作区只包含本任务改动。
