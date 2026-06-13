# 深度报告详情 V2 设计

日期：2026-06-13

## 背景

当前深度报告详情由概述、技术栈、架构、数据流、应用场景、优势、局限、建议和源码证据组成。多数内容是字符串数组，`architecture` 也只有 `pattern` 与 `components`，页面只能逐段罗列，无法表达组件关系、实际使用步骤和部署运行过程。

本次将深度报告从“源码信息清单”调整为“面向采用决策的技术尽调页”。主要读者是想快速判断一个项目是否值得采用的开发者。源码证据继续用于约束 LLM 结论，但不在详情页展示。

## 目标

- 详情页优先回答项目解决什么问题、适合谁、是否值得采用。
- 展示系统架构全景图、快速上手流程图和部署运行流程图。
- 让核心模块、运行时数据流、限制和建议能够支持采用决策。
- 候选仓库重点覆盖 Coding 与辅助 Coding 的实用项目。
- 提高深度报告准入门槛，减少仅因热度或宽泛 AI 标签入选的项目。
- 删除旧格式报告，并基于新版结构重新生成已有仓库报告。

## 非目标

- 不做源码浏览器或大段源码展示。
- 不做安全审计、性能测试或许可证审计。
- 不做报告版本对比。
- 不做架构图缩放、拖拽、编辑或复杂自动布局。
- 不引入 Mermaid 或新的前端图表依赖。
- 不把深度报告扩展成通用项目文档站。

## 方案选择

采用结构化决策报告：

- LLM 输出可验证的 Pydantic 结构。
- 架构关系和流程步骤直接使用结构化节点。
- 前端使用原生 HTML、CSS 和 SVG 渲染。
- 无效或不完整图数据降级为结构化卡片，不从自然语言推测关系。

不采用以下方案：

- Markdown + Mermaid：图语法和渲染稳定性不足，难以做严格校验。
- 二次 LLM 加工：增加成本和复杂度，且会引入新的不一致来源。

## 页面信息架构

采用“决策漏斗”顺序：

1. 采用结论与适用人群。
2. 解决的问题与典型场景。
3. 系统架构全景图。
4. 快速上手流程图。
5. 部署运行流程图。
6. 核心模块与运行时数据流。
7. 优势、限制和采用建议。

页面顶部先提供结论，后续图和技术细节用于解释结论。源码证据不渲染。

## 报告数据结构

`DeepReportOutput` 升级为以下 V2 结构。字段名是前后端契约，实施时不得另行改名。

### 基础信息

- `title: str`
- `summary: str`
- `tech_stack: list[str]`
- `use_cases: list[str]`

### 采用决策

`decision`：

- `recommendation: str`：一句话采用结论。
- `reasons: list[str]`：推荐或不推荐的主要原因。
- `best_for: list[str]`：最适合的人群或团队。
- `not_for: list[str]`：不适合的人群、阶段或约束条件。

### 系统架构

`architecture`：

- `pattern: str`
- `summary: str`
- `nodes: list[ArchitectureNode]`
- `edges: list[ArchitectureEdge]`

`ArchitectureNode`：

- `id: str`：报告内稳定且唯一的短 ID。
- `label: str`
- `role: str`
- `group: str | None`

`ArchitectureEdge`：

- `source: str`
- `target: str`
- `label: str`

约束：

- 节点数量为 4 至 10 个。
- 每条边的 `source` 和 `target` 必须引用已声明节点。
- 不允许自环。
- 只表达源码摘要包能够支持的组件和关系。

### 快速上手

`quick_start`：

- `prerequisites: list[str]`
- `steps: list[FlowStep]`
- `expected_result: str`

用于表达用户第一次使用项目的实际路径：安装或接入、配置、启动、输入、系统处理和获得结果。

### 部署运行

`deployment`：

- `prerequisites: list[str]`
- `steps: list[FlowStep]`
- `operations: list[str]`

用于表达环境准备、部署、服务启动、健康检查和持续运行。证据不足时应明确限制，不得补造部署方式。

`FlowStep`：

- `id: str`
- `title: str`
- `description: str`

约束：

- 每条流程包含 3 至 8 个步骤。
- 步骤 ID 在所属流程内唯一。
- 步骤顺序以数组顺序为准，不额外维护连线。

### 技术细节

- `core_modules: list[CoreModule]`
- `runtime_data_flow: list[FlowStep]`
- `strengths: list[str]`
- `limitations: list[str]`
- `actionable_takeaways: list[str]`

`CoreModule`：

- `name: str`
- `responsibility: str`
- `depends_on: list[str]`

`depends_on` 使用模块名称，不要求与架构节点一一对应。它用于文字解释，不用于绘图。

### 源码证据

`source_evidence` 继续保留：

- `path: str`
- `reason: str`

Prompt 继续要求证据路径只能来自源码摘要包。API 详情可继续返回该字段，页面不渲染。数据库已有 `evidence_json` 不删除。

## Prompt 约束

新版 Prompt 必须：

- 明确报告读者是评估项目采用价值的开发者。
- 优先提炼真实可用能力，而非复述 README 宣传语。
- 分开输出快速上手与部署运行流程。
- 仅基于提供的源码摘要包生成节点、关系和步骤。
- 对安装、运行、部署证据不足的项目，在 `limitations` 中说明。
- 限制数组和图节点规模，避免输出冗长清单。
- 保留全部字段必填和 `extra="forbid"` 校验。
- 继续使用 JSON 修复重试机制。

## 前端渲染

详情页继续由 `deep-report.html` 静态外壳和 `deep-reports.js` 请求 API。

### 采用结论

顶部展示：

- 一句话结论。
- 候选分。
- 推荐理由。
- 适合与不适合人群。
- 仓库、Commit 和更新时间。

### 架构图

- 使用 SVG 绘制有限规模的节点和连线。
- 桌面端优先横向分层，移动端改为纵向排列。
- 节点展示名称和职责。
- 连线标签可省略空值。
- 数据校验失败时改为架构节点卡片列表。

第一版使用简单、确定性的分层布局，不实现通用图布局算法。

### 快速上手与部署运行

- 使用 HTML/CSS 有序流程卡片。
- 桌面端允许横向展示，移动端自然切换为纵向。
- 每步展示标题和简短说明。
- 前置条件和预期结果分别展示。
- 空流程不输出空 section。

### 技术细节

- 核心模块使用职责卡片。
- 运行时数据流使用有序步骤。
- 应用场景、优势、限制和建议使用短列表。
- 页面不展示“源码证据”区块。

### 安全与降级

- 所有 LLM 文本继续进行 HTML 转义。
- 外部链接只允许 `http` 和 `https`。
- 图节点 ID 不直接作为 HTML。
- 不完整的单个 section 独立隐藏或降级，不影响其余报告。
- 不再把旧格式报告作为长期兼容目标。

## 候选筛选

深度报告只选择高价值 Coding 或辅助 Coding 项目。

### 硬门槛

- `reviewed.verdict == "approved"`。
- Reviewer 总分至少 85。
- 综合 `candidate_score` 至少 85。
- 必须命中至少一类 Coding 实用能力。

### 可入选方向

- 代码生成、补全和修改。
- 代码理解、仓库分析和上下文构建。
- Coding Agent 和开发工作流 Agent。
- IDE、编辑器插件和开发者 CLI。
- 测试生成、调试、代码审查和质量工具。
- 对 Coding 有直接帮助的 Skill、MCP Server 或 MCP 工具。
- 构建、发布、文档、自动化等明确服务于软件开发的工具。

### 排除方向

- 泛知识库、泛 RAG 或通用搜索，且没有明确 Coding 用途。
- 纯聊天机器人或角色应用。
- 纯论文、模型权重、数据集或 benchmark。
- 仅因 stars、趋势热度或宽泛 AI 标签得分高的项目。
- 只有概念演示、缺少可执行入口或实用工作流的项目。

### 评分调整

- 将 Coding 能力由宽泛关键词加分改为明确分类命中。
- Skill 和 MCP 仅在描述出直接开发用途时计入。
- 热度只作为低权重加分，不能弥补 Coding 能力缺失。
- `retry` 项目不再进入深度报告候选池。
- 每轮 Pipeline 仍最多生成一篇报告。
- 同仓库近期去重规则继续保留。

## 历史报告重建

旧格式报告最终全部删除，并重新生成新版报告。

### 执行方式

提供一次性管理命令，不把批量重建混入日常 Pipeline：

1. 读取当前 completed 旧报告的仓库清单。
2. 支持 `dry-run` 输出待处理仓库和预估数量。
3. 逐仓库执行 clone、inspect、summarize 和新版 analyze。
4. 新版报告生成成功后写入 `report_version = 2`，但重建期间公开 API 仍只读取 V1。
5. 任务结束时执行一次版本切换：公开 API 改为只读取 V2，并删除全部 V1。
6. 输出失败仓库清单，支持指定仓库重试。

### 一致性与失败处理

- 不在任务开始时直接清空 `deep_reports`，避免重建中途线上页面全空。
- 单仓库失败不阻断其余仓库。
- 重建失败的仓库最终不保留旧格式报告，符合“删除旧报告”的要求。
- 清理阶段必须可重复执行。
- 批量任务受全局预算熔断约束，并允许设置本次任务最大报告数或成本上限。
- 全部清理完成后触发一次静态站构建。

### 版本识别

为避免通过字段猜测版本，在 `deep_reports` 表增加 `report_version`，新版写入 `2`，旧记录迁移后默认为 `1`。应用配置增加当前公开报告版本，默认值在迁移完成前为 `1`；批量重建成功收尾时切换为 `2`。列表、latest 和详情 API 始终只查询当前公开版本，避免同一阶段混用两种结构。

## API

沿用现有接口：

- `GET /api/deep-reports`
- `GET /api/deep-reports/latest`
- `GET /api/deep-reports/{id}`

调整：

- 列表继续只返回摘要字段。
- 详情返回新版 `report_json`。
- 返回 `report_version`，便于前端明确选择渲染器。
- 历史重建和清理完成后，公开 API 中不再出现 V1 报告。
- 源码证据可以继续存在于详情 API，但前端不展示。

## 测试策略

### Selector

- `retry` 不入选。
- Reviewer 分数低于 85 不入选。
- 候选分低于 85 不入选。
- 缺少 Coding 硬匹配不入选。
- Coding Agent、IDE/CLI、测试调试、Skill 和 MCP 项目可入选。
- 泛知识库、纯聊天和纯论文模型项目不入选。
- 热度不能单独推动项目过线。

### Analyzer 与 Prompt

- V2 全部必填字段可解析。
- 缺少嵌套字段、额外字段、重复节点 ID、无效边引用和步骤超限均被拒绝。
- Prompt 回归测试验证快速上手、部署流程和证据约束。
- JSON 修复重试继续记录所有调用成本。

### 数据库与重建

- `report_version` 迁移和读写正确。
- V2 报告可正常 upsert。
- `dry-run` 不修改数据库。
- 单仓库失败不阻断批量任务。
- 清理后不存在 V1 报告。
- 重试成功后只保留 V2。

### API 与前端

- 列表和详情返回 `report_version`。
- 详情页按 V2 字段渲染采用结论、架构图和两类流程图。
- 源码证据不出现在 DOM。
- 无效图数据降级为卡片。
- 空 section 不渲染。
- 所有文本继续转义，外链继续校验。
- 桌面和移动端均无页面级横向溢出。

## 验收标准

- 新报告不再表现为简单字段罗列。
- 用户无需阅读源码证据即可理解项目价值、架构、使用和部署过程。
- 每篇有效报告至少包含采用结论、架构图、快速上手流程和部署运行流程。
- 两个 85 门槛和 Coding 硬匹配均生效。
- 旧报告完成批量重建和清理，公开页面只展示 V2。
- Prompt 回归、Selector、Analyzer、数据库、API 和前端契约测试全部通过。
- 项目相关文档同步更新。

## 文档更新

实施时同步维护：

- `docs/architecture.md`
- `docs/data-model.md`
- `docs/api.md`
- `docs/codemap.md`
- `docs/task.md`
- `docs/bug-progress.md`，仅在实施中出现值得记录的新问题时更新。
