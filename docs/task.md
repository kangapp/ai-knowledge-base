# 当前任务拆解

更新时间：2026-06-02

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
- [x] 收紧 GitHub 数据源采集口径
  - GitHub Search 查询从宽泛全文词改为 `topic:` qualifier + 明确关键词 + 排除词
  - 移除 `skill` 等易引入噪音的宽泛词，降低壁纸、账号、卡片、NSFW 等非技术仓库进入分析的概率
  - `github_trending_velocity` 只过滤本源采集到的 repo，不再误过滤同批其它源
  - GitHub 增速计算不再依赖精确 N 天前快照，改用目标窗口前最近一次基线快照
- [x] 修复 GitHub Search 422
  - Search query 最多拼 5 个 include 条件，避免超过 GitHub `AND/OR/NOT` 操作符限制
  - `exclude_terms` 改为 API 返回后的本地过滤，保留噪音剔除能力
- [x] 修复 GitHub 数据源健康采集量为 0
  - GitHub Search 不支持对 `topic:` qualifier 使用 `OR`，旧查询会稳定返回 0
  - 改为最多 5 个单条件 Search 请求，合并去重后再应用 stars/forks/watchers 阈值
- [x] 新增 GitHub AI 开发工具数据源
  - 新增 `github_ai_devtools`，面向 Understand-Anything、GitNexus、probe 这类代码库理解/知识图谱/AI 开发工具仓库
  - 使用 `pushed` 90 天窗口和用途型关键词：`interactive knowledge graph`、`codebase knowledge graph`、`code understanding`、`codebase understanding`、`repository analysis`
- [x] 收紧 RSS 数据源采集口径
  - 英文关键词按词边界匹配，避免 `AI` 命中 `raises`、`chair` 等普通单词片段
  - 综合媒体 RSS 使用 `filter_scope: title`，避免长正文/推荐内容里偶然出现 AI 词导致误采集
  - 移除 `技术/科技/智能/Python/前端/technology` 等泛词，补充 `豆包/Kimi/通义/智谱/AI4S` 等强信号词
- [x] 修复 RSS 采集阻塞 pipeline
  - RSS feed 统一先用 `httpx.AsyncClient(timeout=30, follow_redirects=True)` 获取文本
  - `feedparser` 只解析已获取的文本，不再直接解析 URL，避免外部 feed 卡住事件循环
- [x] 稳定 Reviewer 四维评分裁决
  - Reviewer 输出解析阶段统一维度 key，兼容历史 `information_density` 并写回 `info_density`
  - `total_score` 由代码按四维分重算，不再信任模型输出总分
  - `approved/retry/discarded` 由代码按阈值裁决，低 AI 相关度内容强制丢弃
  - 质量统计兼容历史 `information_density`，避免信息密度均值被算成 0
- [x] 收紧费用统计账本口径
  - Analyzer/Reviewer 只要 LLM 返回 usage，就记录 `CostRecord`，解析失败和重试调用不再漏记
  - 文章入库时按 `ref_url` 汇总 Analyzer + Reviewer 成本，写入 `analysis_cost/analysis_tokens`
  - Reviewer 成本来源映射统一使用 `RawItem.raw_metadata.source_id`，避免 RSS/arXiv 落到展示名
  - 资源消耗预算读取 `config/agents.yaml budget.monthly`，趋势返回 `llm_calls` 并保留兼容字段 `articles`
- [x] 统一 period 日期窗口口径
  - `/api/sources/stats` 使用真实日期窗口，不再取最近 N 条健康记录
  - `/api/stats/consumption-detail` 使用 day=今天、week=近 7 个自然日、month=近 30 个自然日
  - `days=N` 查询窗口统一为含今天的 N 个自然日，成本汇总、运行状态与质量新鲜度比较同步修正
- [x] 资源消耗趋势窗口独立传参
  - `/api/stats/consumption-detail` 新增 `trend_window`，KPI 窗口继续由 `period` 控制
  - 默认趋势窗口：day=14d、week=12w、month=12m
  - `trend/source_trend/provider_trend` 使用同一个趋势窗口，避免选日时趋势只剩今天
- [x] 统一项目业务时间为北京时间
  - 新增 `src/core/time.py` 作为 Python 业务时间唯一入口
  - 采集、pipeline run、phase log、cost log、source health、GitHub 快照、静态站构建时间统一写入北京时间
  - 所有 API/仪表盘 SQL 日期窗口使用北京时间自然日，避免 UTC 日界导致选日数据为 0
- [x] 扩展数据模型可观测性
  - 新增 `collection_items`，记录每次 pipeline 中每条原始 item 的采集、去重、审核和入库状态
  - 新增 `pipeline_source_runs`，记录 run + source 级采集漏斗、成本、token 和失败数
  - `cost_logs` 补充 `status/error/latency_ms/attempt_no/prompt_name/prompt_version` 审计字段
  - `/api/sources/stats` 保留旧健康字段，同时返回 source-run 漏斗和成本字段，方便后续数据源健康 Tab 重构
- [x] MiniMax 默认模型升级到 M3
  - `config/llm.yaml` 注册模型改为 `MiniMax-M3`
  - `config/agents.yaml` 中所有 analyzer/reviewer primary model 统一改为 `MiniMax-M3`
  - 保持现有 provider、价格和 agent 输出 token 参数不变
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
- 已通过：`.venv/bin/python -m pytest tests/test_collector.py tests/test_database.py tests/test_pipeline_github.py -q`
- 已通过：`.venv/bin/python -m pytest -m "not integration and not e2e"`
- 已通过：`.venv/bin/pytest tests/test_collector.py -q`（10 passed）
- 已通过：`.venv/bin/python -m pytest tests/test_reviewer.py tests/test_stats_quality_detail.py tests/test_prompt_regression.py -q`
- 已通过：`.venv/bin/python -m pytest tests/test_analyzer.py tests/test_reviewer.py tests/test_cost_accounting.py tests/test_stats_consumption_detail.py -q`
- 已通过：`.venv/bin/python -m pytest -m "not integration and not e2e"`（93 passed）
- 已通过：`.venv/bin/pytest tests/test_config.py tests/test_llm_client.py tests/test_analyzer.py tests/test_reviewer.py tests/test_pipeline.py -q`（24 passed）
- 已通过：`.venv/bin/pytest tests/test_collector.py -q`（11 passed）
- 已通过：`.venv/bin/python -m pytest -m "not integration and not e2e"`（103 passed）
- 已通过：`.venv/bin/python -m pytest tests/test_database.py tests/test_cost_accounting.py tests/test_pipeline_observability.py tests/test_api_contracts.py tests/test_analyzer.py tests/test_reviewer.py tests/test_pipeline.py -q`（34 passed）

说明：当前 shell 中 `uv` 不可用，使用项目 `.venv/bin/python` 执行测试。
