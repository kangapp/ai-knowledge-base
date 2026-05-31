# 当前任务拆解

更新时间：2026-05-31

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
- [ ] 统计服务层继续收口
  - 将 `quality/runtime/consumption` SQL 从 `src/db/operations.py` 逐步迁到更聚焦的统计服务文件
  - 每迁一个接口补一个契约测试
- [ ] API 错误码细分
  - 数据库异常目前仍归入 `50001`
  - 如需严格区分，可补 DB exception handler 映射到 `50002`

## 验证命令

- 已通过：`.venv/bin/python -m pytest tests/test_api_contracts.py -q`
- 已通过：`.venv/bin/python -m pytest tests/test_stats_consumption_detail.py -q`
- 待全量确认：`.venv/bin/python -m pytest -m "not integration and not e2e"`

说明：当前 shell 中 `uv` 不可用，使用项目 `.venv/bin/python` 执行测试。
