# 热榜数据源接入设计

## 目标

在不引入 TrendRadar 代码和依赖的前提下，为现有采集流水线增加 NewsNow 热榜数据源，并修正 RSS 采集“先截断、后过滤”导致漏采的问题。

首批接入：

- AIHOT：AI 聚合资讯
- 稀土掘金热榜：补充当前已失效的掘金 RSS
- 知乎 AI 热榜：补充 AI 社会关注度信号

## 架构

新增 `hotlist` 数据源类型和单一 `collect_hotlist()` Collector。每个配置条目对应一个 NewsNow 平台 ID，通过统一接口获取数据，转换为现有 `RawItem` 后复用 RSS Analyzer、Reviewer、URL 去重、健康记录和入库流程。

不增加独立 Hotlist Analyzer。热榜条目仍是文章型内容，单独增加 Analyzer 和 Prompt 会扩大维护面，当前没有必要。

## 配置

每个热榜源使用现有 `SourceConfig`：

```yaml
- id: hotlist_aihot
  name: AIHOT
  type: hotlist
  enabled: true
  priority: 2
  cron: "0 */2 * * *"
  max_items: 10
  config:
    api_url: "https://newsnow.busiyi.world/api/s"
    platform_id: "aihot"
    expected_domain: "virxact.com"
    filter_keywords: [AI, LLM, Agent, RAG, MCP, OpenAI, Anthropic]
    filter_scope: title_summary
```

`expected_domain` 校验 NewsNow 返回的文章 URL 必须为 HTTPS，且主机名等于该域名或其子域名。知乎、掘金可配置固定域名；AIHOT 是聚合源，文章链接会指向多个站点，因此不配置固定域名，只校验 HTTPS。

## 数据映射

NewsNow 响应中的字段映射为：

- `url` → `RawItem.url`
- `title` → `RawItem.title`
- `pubDate` → `RawItem.published_at`
- `extra.hover` → `RawItem.description`
- 平台名称 → `RawItem.source_detail`
- `source` 固定为 `hotlist`
- `id`、榜单排名、`extra.info`、平台 ID、接口更新时间、配置 source ID → `raw_metadata`

缺少标题或 URL 的条目直接跳过。关键词过滤完成后再应用 `max_items`。

## 路由与分析

`RawItem.source` 增加 `hotlist`。Router 将其路由到 `routed_rss`，因此后续复用 `rss_analyzer` 和文章型 Reviewer。数据库 `articles.source` 保存 `hotlist`，`source_id` 仍保存配置 ID。

## 错误与安全

- HTTP 非 2xx、非 JSON、响应状态不是 `success/cache`：抛出异常，由现有单源故障隔离和健康记录处理。
- URL 非 HTTPS：跳过该条。
- 配置了 `expected_domain` 且域名不匹配：跳过该条。
- 公共 NewsNow 服务只作为可替换上游；`api_url` 必须来自配置，不在 Collector 内硬编码业务配置。
- 不复制 TrendRadar GPL-3.0 代码；仅依据公开接口自行实现。

## RSS 修复

RSS Collector 遍历全部 feed 条目，先完成关键词过滤，再在匹配数量达到 `max_items` 时停止，避免前 N 条不匹配导致后续有效文章被漏掉。

## 验证

- 单元测试覆盖热榜字段映射、关键词过滤、先过滤后限量、无效 URL、域名校验、异常状态和路由复用。
- 配置测试覆盖三个首批数据源。
- 使用真实 NewsNow 接口逐源采集，确认返回 `RawItem`、URL 可用、关键词过滤生效。
- 运行非 integration/e2e 全量测试和 `git diff --check`。
