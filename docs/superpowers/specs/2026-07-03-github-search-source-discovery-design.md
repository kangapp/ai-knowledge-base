# GitHub 搜索发现器设计

## 目标

新增一个“找源的源”：定期在 GitHub 搜索 AI 知识库、AI 雷达、LLM/Agent 资讯聚合类项目，从这些项目里提取潜在 RSS、站点或 GitHub owner，写入现有数据源治理候选池。

它不产出文章，不进入首页，不进入 `data.json`，只推动现有闭环：

```text
GitHub 搜索 -> 候选源 -> trial -> active / rejected
```

## 非目标

- 不新增一套治理状态。
- 不把搜索到的 repo 当正常内容展示。
- 不做复杂 LLM 判断。
- 不自动启用候选源。

## 发现输入

第一版使用固定关键词，数量保持小：

- `ai knowledge base`
- `ai radar`
- `llm radar`
- `agent radar`
- `awesome ai tools`
- `ai newsletter`
- `llm news`

每个关键词最多取前 10 个 repo，按 stars 排序。后续只有命中太少时再扩关键词。

## 提取规则

对每个 repo：

1. 读取 GitHub repo 元数据里的 homepage。
2. 读取 README。
3. 从 homepage 和 README 中提取：
   - RSS/Atom 链接。
   - 普通站点链接。
   - GitHub owner。

候选源类型沿用现有 `SourceConfig`：

- RSS 链接 -> `type=rss`
- GitHub owner -> `type=github`

站点链接第一版只尝试常见 feed 路径，例如 `/feed`、`/rss.xml`、`/atom.xml`；验证失败就跳过。

## 写入规则

发现结果只写：

- `discovered_sources`
- `source_registry(status='candidate', enabled=0)`

`source_registry.config_json` 中增加轻量来源信息：

```json
{
  "discovered_by": "github_search",
  "discovery_query": "ai radar",
  "discovery_repo": "owner/repo"
}
```

重复判断复用现有 URL/source id 去重逻辑。

## 健康页展示

数据源健康页在候选/试运行源上展示发现来源：

- 发现方式：`GitHub Search`
- 关键词：例如 `ai radar`
- 来源 repo：例如 `owner/repo`

不改变正式源的核心表格，只补充候选源可解释性。

## 调度

复用现有发现调度。每周运行两次，避免间隔太长；每次仍限制关键词和 repo 数量，避免 GitHub API 消耗和候选池膨胀。

## 验收

- GitHub 搜索结果不会进入文章表和首页。
- 新发现源进入 `candidate`，后续可被现有逻辑提升为 `trial`。
- 重复运行不会重复写入相同候选源。
- 数据源健康页能看到候选源来自 GitHub 搜索及其关键词。
- 发现失败只记录 warning，不影响正常 pipeline。
