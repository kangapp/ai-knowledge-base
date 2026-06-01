# 当前任务拆解

更新时间：2026-06-01

## P0 已完成

- [x] 统一 API 成功/失败响应入口
  - 成功响应走 `src/api/responses.py::envelope()`
  - `HTTPException` 按项目错误码映射返回
  - FastAPI 参数校验错误统一返回 `40001`
- [x] 修正文章接口契约
  - `/api/articles` 返回真实分页总数
  - `/api/articles/{id}` 与列表保持一致，补充 `tags`
  - 搜索/列表查询统一只返回 `status='approved'`
- [x] 收口数据源接口 DB 使用方式
  - `src/api/sources.py` 优先复用 lifespan 注入的全局 DB
  - 无注入 DB 时保留本地运行 fallback
  - 删除 `clear-health` 后不可达的重复 action 代码
- [x] 增加仪表盘首屏聚合接口
  - 新增 `/api/dashboard/summary`
  - 新增 `src/services/dashboard_stats.py`
  - `/api/stats/enhanced` 复用同一套 summary 口径
- [x] 增加 API 契约测试
  - 覆盖错误码、validation、分页 total、详情 tags、sources DB 注入、dashboard summary
- [x] 维护文档
  - 更新 `docs/api.md`
  - 更新 `docs/structure.md`
  - 新增 `docs/codemap.md`

## P1 后续建议

- [x] 仪表盘前端模块化
  - 拆 `api.js`、`state.js`、`charts.js`、`renderers.js`、`main.js`
  - 首屏 KPI 使用 `/api/dashboard/summary`
  - 各 Tab 继续懒加载领域接口
- [x] 移除仪表盘运行监控 Tab
  - 运行监控由独立 DAG 页面承担
  - 仪表盘保留数据质量、资源消耗、数据源健康三个 Tab
- [x] 修正资源消耗来源费用口径
  - 来源费用构成优先按文章真实来源归因
  - RSS 子来源展示 `source_detail`，如 `36氪`
  - Reviewer 成本跟随文章来源，不再显示为独立 `review` 来源
- [x] 补充成本来源快照和历史兜底
  - `cost_logs` 新增 `source/source_detail/source_id`
  - 新成本记录写入时保存来源快照，统计优先使用显式字段
  - 历史成本无法 JOIN 文章时按 `ref_url` 域名兜底识别来源
- [x] 统一数据源健康 source_id 口径
  - `source_health.source_id` 统一使用 `config/sources.yaml` 的配置 id
  - RSS/arXiv/飞书采集结果在 `raw_metadata.source_id` 保留配置 id
  - Reviewer 阶段按配置 id 汇总通过率和平均分，避免展示名或分类名被过滤
- [x] 数据源健康展示统一使用数据源简称
  - `/api/sources/stats` 保留 `id` 作为稳定主键，同时返回 `name/type`
  - 仪表盘数据源健康图表和表格优先展示 `name`，不再直接展示 `rss_36kr` 等存储 id
- [x] 修正 source_health 同日覆盖问题
  - Collector 累加 `total_collected/failed`
  - Reviewer 累加 `approved/rejected`，`avg_score` 按 approved 数加权合并
  - 新增 007 迁移合并历史 `36氪`、`cs.AI/cs.CL/cs.LG` 健康记录
- [x] 修正多源定时采集竞争
  - 启动时按 cron 表达式分组注册采集任务，同一时间只启动一个 pipeline run
  - `run_pipeline(source_filter=...)` 支持多个 source id，组内由 Collector 并行采集
  - `pipeline.start/pipeline.skip` 日志补充 source filter 和 source 数量，便于排查
  - 修复每周数据源维护任务使用旧 DB 路径且未初始化连接的问题
- [x] 统一 period 日期窗口口径
  - `/api/sources/stats` 使用真实日期窗口，不再取最近 N 条健康记录
  - `/api/stats/consumption-detail` 使用 day=今天、week=近 7 个自然日、month=近 30 个自然日
  - `days=N` 查询窗口统一为含今天的 N 个自然日，成本汇总、运行状态与质量新鲜度比较同步修正
- [x] 资源消耗趋势窗口独立传参
  - `/api/stats/consumption-detail` 新增 `trend_window`，KPI 窗口继续由 `period` 控制
  - 默认趋势窗口：day=14d、week=12w、month=12m
  - `trend/source_trend/provider_trend` 使用同一个趋势窗口，避免选日时趋势只剩今天
- [ ] 统计服务层继续收口
  - 将 `quality/runtime/consumption` SQL 从 `src/db/operations.py` 逐步迁到更聚焦的统计服务文件
  - 每迁一个接口补一个契约测试
- [ ] 历史成本来源回填
  - 可选执行一次性脚本，将已有 `cost_logs` 的 `source/source_detail/source_id` 按 `articles` 和 URL 域名回填
  - 回填后统计接口仍保留 URL 兜底，兼容漏网历史数据
- [ ] API 错误码细分
  - 数据库异常目前仍归入 `50001`
  - 如需严格区分，可补 DB exception handler 映射到 `50002`

## 验证命令

- 已通过：`.venv/bin/python -m pytest tests/test_api_contracts.py -q`
- 已通过：`.venv/bin/python -m pytest tests/test_stats_consumption_detail.py -q`
- 已通过：`.venv/bin/python -m pytest -m "not integration and not e2e"`（77 passed）

说明：当前 shell 中 `uv` 不可用，使用项目 `.venv/bin/python` 执行测试。
