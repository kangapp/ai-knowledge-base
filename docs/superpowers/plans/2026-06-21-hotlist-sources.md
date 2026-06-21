# Hotlist Sources Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加 NewsNow 热榜采集能力，接入 AIHOT、掘金和知乎 AI 热榜，并修复 RSS 过滤顺序。

**Architecture:** 使用一个配置驱动的 `collect_hotlist()` 将 NewsNow 数据转换为 `RawItem(source="hotlist")`。Router 将 hotlist 复用到 RSS Analyzer，现有查重、审核、健康记录和入库流程保持不变。

**Tech Stack:** Python 3.12、httpx、Pydantic v2、pytest、现有 LangGraph 流水线

## Global Constraints

- 不新增第三方依赖。
- 不复制 TrendRadar GPL-3.0 代码。
- API 地址、平台 ID、域名和关键词全部来自 `config/sources.yaml`。
- 单源失败继续由现有 `collect_all()` 隔离。
- 热榜先过滤关键词，再限制 `max_items`。

---

### Task 1: Collector 行为

**Files:**
- Modify: `tests/test_collector.py`
- Modify: `src/graph/collector.py`

**Interfaces:**
- Produces: `async def collect_hotlist(source: SourceConfig) -> list[RawItem]`

- [ ] 写失败测试：覆盖字段映射、关键词过滤后限量、HTTPS/域名校验和异常状态。
- [ ] 运行 `tests/test_collector.py`，确认因 `collect_hotlist` 不存在或行为缺失而失败。
- [ ] 最小实现 `collect_hotlist()`，并将 `hotlist` 注册进 `COLLECTOR_MAP`。
- [ ] 修改 `collect_rss()`，遍历完整 entries，匹配后达到 `max_items` 即停止。
- [ ] 运行 `tests/test_collector.py`，确认通过。

### Task 2: 类型、路由和配置

**Files:**
- Modify: `tests/test_router.py`
- Modify: `tests/test_config.py`
- Modify: `src/graph/state.py`
- Modify: `src/graph/router.py`
- Modify: `config/sources.yaml`

**Interfaces:**
- Consumes: `RawItem(source="hotlist")`
- Produces: hotlist 条目进入 `routed_rss`

- [ ] 写失败测试：hotlist 路由至 RSS，项目配置包含三个启用源。
- [ ] 运行定向测试并确认失败。
- [ ] 扩展 `RawItem.source` 和 `ROUTE_MAP`，添加三个配置源。
- [ ] 运行定向测试并确认通过。

### Task 3: 文档同步

**Files:**
- Modify: `docs/structure.md`
- Modify: `docs/architecture.md`
- Modify: `docs/data-model.md`
- Modify: `docs/codemap.md`
- Modify: `docs/task.md`

- [ ] 记录 hotlist 类型、NewsNow 映射、安全校验、路由复用和首批数据源。
- [ ] 检查文档描述与代码配置一致。

### Task 4: 验证

**Files:**
- No production changes expected

- [ ] 运行 Collector、Router、Config 定向测试。
- [ ] 运行 `pytest -m "not integration and not e2e"`。
- [ ] 使用真实接口逐源执行 `collect_hotlist()`，打印源 ID、数量、标题和 URL。
- [ ] 对返回 URL 发起 HEAD/GET 抽样，确认可访问或可正常重定向。
- [ ] 运行 `git diff --check` 并检查最终 diff 只包含需求相关改动。
