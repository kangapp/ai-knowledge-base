# DAG Observability Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 DAG 页面忠实展示核心流水线与异步发布的两个生命周期，并为入库、深度报告、备份、构建提供真实可追踪状态。

**Architecture:** 保留现有数据库表，所有状态继续写入 `pipeline_phase_logs` 和 `pipeline_events`。主流程为图外阶段补齐 start/end；`DebouncedBuilder` 绑定触发它的 `run_id`，通过显式回调记录 queued/running/completed/failed/superseded。DAG API 将原始记录聚合为运行摘要、核心处理阶段、发布后处理、审核轮次和最近运行列表，前端不再使用混合事件计数百分比。

**Tech Stack:** Python 3.12、FastAPI、aiosqlite、Jinja2、原生 JavaScript、CSS、pytest

## Global Constraints

- 不新增数据库表或第三方依赖。
- `pipeline_runs.status` 只表达数据流水线状态，网站发布状态独立表达。
- 无新数据、无深度报告候选等正常分支显示 `skipped`，不能显示为等待。
- 延迟构建被新任务合并时显示 `superseded`，不能显示为失败。
- 页面保留原始事件作为可折叠排障信息。

---

### Task 1: 图外阶段生命周期

**Files:**
- Modify: `src/main.py`
- Modify: `src/graph/pipeline.py`
- Test: `tests/test_pipeline_observability.py`

**Interfaces:**
- Produces phase records for `persist`、`deep_report`、`backup`
- `record_phase_end()` accepts `done`、`failed`、`skipped`、`superseded`

- [x] 写失败测试，验证 phase end 的事件级别与正常跳过语义。
- [x] 写失败测试，验证图外 phase 状态、显式 skipped 分支和构建回写生命周期。
- [x] 为三个图外阶段补齐 start/end 和结果 details。
- [x] 运行 observability 测试确认通过。

### Task 2: 可归属的延迟构建

**Files:**
- Modify: `src/site/builder.py`
- Modify: `src/main.py`
- Test: `tests/test_site_builder.py`
- Test: `tests/test_pipeline_observability.py`

**Interfaces:**
- `DebouncedBuilder.schedule(run_id: str = "")`
- `DebouncedBuilder.build_now(run_id: str = "")`
- Callback: `on_status(run_id: str, status: str, details: str) -> Awaitable[None]`

- [x] 写失败测试：schedule 保存 run id，新任务取消旧任务并记录 superseded。
- [x] 写失败测试：实际构建依次记录 running/completed，异常记录 failed。
- [x] 实现最小 callback 和 run 归属逻辑。
- [x] pipeline 使用 `schedule(run_id)`，手动构建保持无 run 兼容。
- [x] 运行目标测试确认通过。

### Task 3: DAG 聚合 API

**Files:**
- Modify: `src/api/routes.py`
- Test: `tests/test_api_contracts.py`

**Interfaces:**
- Adds `recent_runs`
- Adds `summary`
- Adds `processing_stages`
- Adds `review_rounds`
- Adds `postprocess`
- Keeps raw `phases`、`events`、`source_funnels`、`active_items`

- [x] 写失败契约测试，覆盖完成、跳过、queued、superseded 和 retry 聚合。
- [x] 实现稳定状态聚合，页面不再使用 event 数量计算业务进度。
- [x] 最近运行列表支持页面切换已有 `run_id` 查询。
- [x] 运行 API 契约测试确认通过。

### Task 4: 三层运行页面

**Files:**
- Modify: `src/site/templates/dag.html`
- Modify: `src/site/static/css/style.css`
- Test: `tests/test_dashboard_frontend_contract.py`

**Interfaces:**
- Layer 1: 运行摘要 + 数据流水线/网站发布双状态
- Layer 2: 采集与去重 → 来源路由 → 并行分析 → 审核与重审 → 结果落库
- Layer 3: 深度报告 → 数据库备份 → 静态构建

- [x] 写失败静态契约测试，锁定三层区域、运行选择器和原始事件折叠区。
- [x] 重写 DAG 模板渲染，移除总百分比。
- [x] 来源漏斗、异常/活跃任务和原始事件保留为诊断区。
- [x] 增加桌面和移动端响应式样式。
- [x] 运行前端契约测试确认通过。

### Task 5: 文档与完整验证

**Files:**
- Modify: `docs/api.md`
- Modify: `docs/architecture.md`
- Modify: `docs/codemap.md`
- Modify: `docs/operations.md`

- [x] 更新 DAG API、生命周期和构建去抖语义。
- [x] 运行全部非 integration/e2e 测试和 JavaScript 语法检查。
- [x] 构建静态站，用浏览器验证运行切换、三层状态、移动端和原始事件。
- [x] 检查 diff 与工作区状态。
