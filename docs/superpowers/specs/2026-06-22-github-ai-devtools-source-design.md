# GitHub AI 开发工具数据源优化设计

日期：2026-06-22

## 背景

Deep Reports 当前只接受 `project_type=coding_tool` 的高质量 GitHub 项目。生产数据表明，`github_ai_devtools` 现有关键词集中在代码库理解、知识图谱和仓库分析，采集结果包含较多通用框架、AI 基础设施、教程资源和安全 writeup，真正的 AI Coding Tool 命中不足。

## 目标

- 提高 Coding Agent、AI 编程助手、代码生成、代码审查、测试生成和 IDE 工具的采集比例。
- 在 GitHub API 请求数量、调度频率和 `max_items` 不变的前提下减少明显噪声。
- 不放宽 Deep Report 的审核分数、项目类型或开发者实用性门槛。

## 方案

仅修改 `config/sources.yaml` 中 `github_ai_devtools` 的配置：

1. 将五个查询关键词改为覆盖主要 Coding Tool 形态的用途型短语：
   - `coding agent`
   - `AI coding assistant`
   - `code generation`
   - `AI code review`
   - `AI IDE`
2. 扩充本地排除词，过滤课程、教程、题库、writeup 和资源合集等明显非工具项目。
3. 保持以下配置不变：
   - `lookback_type: pushed`
   - `lookback_days: 90`
   - `min_stars: 100`
   - `max_items: 10`
   - 每 6 小时运行一次

不新增采集器分支、关键词评分器或额外依赖。现有 GitHub Collector 已支持多关键词独立查询、结果合并去重、本地排除和优先选择数据库中未出现的仓库。

## 数据流

配置关键词 → GitHub Search 五次独立查询 → URL 合并去重 → 排除词及星标阈值过滤 → 优先返回未入库项目 → Analyzer 分类 → Reviewer 审核 → Deep Report Selector。

## 验证

- 更新配置契约测试，确保关键词和排除词符合设计。
- 运行配置及 GitHub Collector 单元测试。
- 运行非 integration/e2e 测试，确认没有影响其他数据源和流水线。
- 部署后通过 `pipeline_source_runs`、`collection_items` 和 `deep.selector_skipped` 观察实际命中；本次不以单轮必然生成报告为成功条件。

## 成功标准

- GitHub API 查询仍为五条合法的独立 Search 请求。
- 配置能直接召回 Coding Agent、编程助手、代码生成、代码审查和 AI IDE 项目。
- 明显课程、教程、writeup、awesome list 和面试题仓库在进入 Analyzer 前被过滤。
- Deep Report 的质量门槛保持不变。

## 非目标

- 不保证每轮采集都生成深度报告。
- 不调整 Reviewer、Analyzer 分类或 Deep Report Selector。
- 不增加 GitHub API 请求数量和新的数据源。
