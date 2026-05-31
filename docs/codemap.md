# 代码地图

更新时间：2026-05-31

## API 入口

- `src/main.py`
  - FastAPI app 创建、lifespan 初始化、路由注册、异常 handler 注册。
  - 新增 API 路由后需要在 `create_app()` 中 `include_router()`。

- `src/api/responses.py`
  - API 响应信封和错误码映射。
  - 常见改动入口：新增项目错误码、调整 validation 错误消息、统一异常响应格式。

- `src/api/routes.py`
  - 基础 API：文章列表/详情、搜索、基础统计、健康检查、成本 summary、pipeline 手动触发、pipeline DAG。
  - 常见改动入口：文章接口字段、分页参数、pipeline 状态展示。

- `src/api/stats.py`
  - 统计 API：`/api/stats/enhanced`、质量、运行、消耗、detail 统计。
  - 路由层只做参数校验和 envelope，复杂统计逻辑应下沉到 service 或 db operations。

- `src/api/dashboard.py`
  - 仪表盘专用轻量聚合接口。
  - 当前提供 `/api/dashboard/summary`，用于首屏 KPI，不承载所有 Tab 数据。

- `src/api/sources.py`
  - 数据源列表、数据源健康统计、启用/停用/删除、清理 source health、候选源列表。
  - 优先复用 `src/api/routes.py` 注入的全局 DB，测试或单独调用时 fallback 到 `data/kb.db`。

- `src/api/config.py`
  - 配置查看接口：读取 `llm/sources/agents` YAML，返回 raw + parsed。

## 业务与数据层

- `src/services/dashboard_stats.py`
  - 仪表盘 summary 和 enhanced stats 的共享统计口径。
  - 常见改动入口：首屏 KPI、通过率、周期成本、活跃来源统计。

- `src/db/operations.py`
  - 数据库操作集合：文章保存、标签保存、成本记录、统计查询、备份等。
  - 常见改动入口：文章查询、统计 SQL、pipeline run 记录。
  - 目前仍包含较多统计 SQL；后续仪表盘重构时建议逐步拆到 service 层。

- `src/core/database.py`
  - SQLite 连接、迁移执行、基础 fetch/execute/backup API。
  - 常见改动入口：连接 PRAGMA、migration 运行策略、在线备份。

- `src/core/config.py`
  - YAML 配置加载和 Pydantic 模型。
  - 新增配置字段时先改这里，再改对应 YAML 和文档。

## Pipeline

- `src/graph/collector.py`
  - 多源采集和 DB 查重。

- `src/graph/pipeline.py`
  - LangGraph DAG 编排和 phase log 记录。

- `src/graph/router.py`
  - 按 `RawItem.source` 做规则路由。

- `src/graph/analyzers/`
  - 各源 Analyzer 薄层；通用实现位于 `base.py`。

- `src/graph/reviewer.py`
  - 四维评分审核。

## 静态站与仪表盘前端

- `src/site/builder.py`
  - 静态站生成、临时目录原子替换、dashboard 模板渲染。

- `src/site/templates/dashboard.html`
  - 仪表盘 DOM 结构。
  - 后续重构时保持模板只描述结构，不塞复杂逻辑。

- `src/site/static/js/app.js`
  - 当前包含首页筛选和 dashboard Tab 控制逻辑。
  - 后续重构建议拆分：API 请求、状态管理、Chart.js 生命周期、DOM 渲染。

- `src/site/static/css/style.css`
  - 全站样式和 dashboard 样式。

## 测试入口

- `tests/test_api_contracts.py`
  - API 契约测试：响应信封、错误码、分页、tags、sources DB 注入、dashboard summary。

- `tests/test_stats_quality_detail.py`
  - 仪表盘质量详情统计契约测试。

- `tests/test_database.py`
  - SQLite migration、唯一约束、FTS5 同步。

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
