# 命令图鉴：入口、产物与边界

本页核对 v1.13.0 的正式工作流清单，共 **12 个**，其中默认 core 6 个、自选扩展 6 个。终端 CLI 是支撑工作流的工具，不与这 12 个入口混计。仓库内其他辅助模板也不自动属于正式工作流集合。[Profile 清单](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/profiles.ts)

## 1. 输入在哪里？

| 场所或工具 | 示例 | 用途 |
| --- | --- | --- |
| 终端 | `openspec init` | 安装项目入口、查询、校验、结构化操作 |
| Claude Code | `/opsx:propose` | 让 AI 执行规划工作流 |
| Cursor / Copilot IDE | `/opsx-propose` | 同一工作流的工具特定写法 |
| Codex | `$openspec-propose` | 显式选择生成的 Skill |
| Amazon Q | `@opsx-propose` | 选择 Prompt 库入口 |

以初始化提示和工具实际发现的入口为准。不同工具不仅前缀不同，Skill 名称本身也有变化。[工具调用表](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/supported-tools.md)

## 2. 全部工作流与 Codex 对照

| 通用入口 | Codex Skill | 安装范围 | 主要结果 |
| --- | --- | --- | --- |
| `/opsx:propose` | `$openspec-propose` | core | 新 Change 与实施前产物 |
| `/opsx:explore` | `$openspec-explore` | core | 理解、选项与决策 |
| `/opsx:apply` | `$openspec-apply-change` | core | 实现与任务进度 |
| `/opsx:update` | `$openspec-update-change` | core | 协调已有规划文档 |
| `/opsx:sync` | `$openspec-sync-specs` | core | 更新主规范，保留活动 Change |
| `/opsx:archive` | `$openspec-archive-change` | core | 同步评估与归档 |
| `/opsx:new` | `$openspec-new-change` | 扩展 | 新 Change 骨架 |
| `/opsx:continue` | `$openspec-continue-change` | 扩展 | 下一类就绪产物 |
| `/opsx:ff` | `$openspec-ff-change` | 扩展 | 批量补齐实施前产物 |
| `/opsx:verify` | `$openspec-verify-change` | 扩展 | 实现对齐报告 |
| `/opsx:bulk-archive` | `$openspec-bulk-archive-change` | 扩展 | 多项变更的合并与归档 |
| `/opsx:onboard` | `$openspec-onboard` | 扩展 | 带讲解的真实完整练习 |

名称来自[官方工作流模板](https://github.com/Fission-AI/OpenSpec/tree/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows)。启用扩展：在终端执行 `openspec config profile` 选择工作流，再运行 `openspec update`。选择 archive 或 bulk-archive 的自定义集合会补入它们依赖的 sync。

## 3. 默认工作流详解

### `propose`：建立可审阅的计划

**输入：** 一个 kebab-case 变更名或自然语言需求。

先读取项目上下文和相关实现，再创建 Change；按 Schema 的传递依赖集合生成实施前所需产物。默认通常为 proposal、specs、design、tasks，design 可按其条件说明省略。

**边界：** 只规划，展示产物后结束，等待后续实施请求。需要影响验收的重要信息时先澄清，不能在 tasks 中用含糊的“再研究一下”代替应完成的前期调查。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/propose.ts)

### `explore`：调查与比较

**输入：** 问题、想法、备选方案或某个 Change 的上下文。

允许读代码、查事实、画图、沿多个方向讨论；没有固定步骤或必须输出的文件。

**边界：** 不实施功能。当前模板允许经明确确认后写入范围内的规划产物；入门说明仍把它概括为纯对话，具体差异见[完整工作流](usage-guide.md)。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/explore.ts)

### `apply`：实施未完成任务

**输入：** 选定的 Change，以及 CLI 返回的状态、上下文文件和任务。

逐项实现并更新复选框，可从中断位置继续。实际步骤读取 `instructions apply` 的 blocked、ready 或 all_done 状态。

**边界：** 完成意味着指定行为已实现，不能擅自收缩需求或把推迟项勾选。默认定义没有自动保证 TDD、测试覆盖率或部署成功。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/apply-change.ts)

### `update`：修订并协调已有计划

**输入：** 新决定，或“检查这些文档是否一致”。

读取已有产物，在任意方向消除矛盾。例如设计改变可能需要改任务，也可能要回头修订提案。按当前模板逐份展示修改并取得确认。

**边界：** 不改代码、不创建缺失产物；后续需要 continue 或 apply。与终端 `openspec update` 刷新工具入口完全不同。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/update-change.ts)

### `sync`：合并规范增量

**输入：** 选定 Change 中具体存在的 Delta Spec 和对应主规范。

由 AI 理解并合并新增、修改、删除和重命名，保留无关内容。读取 CLI 返回的实际路径与 specs 规则，完成后报告哪些能力改变。

**边界：** 会改主规范；Change 仍处于活动状态。适合单独审阅规范合并，日常小变更也可在 archive 中处理。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/sync-specs.ts)

### `archive`：核对同步状态并保存历史

**输入：** 一次准备收尾的 Change。

检查文档和任务，评估是否需要同步。选择同步时，必须完成合并并核对所有 Delta 对应能力后再移动文件。

**边界：** 未完成项是警告与确认点，不是自动阻断所有归档的闸门；也可以明确选择不做同步。最终摘要应说明同步状态，不能一概写“规范已更新”。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/archive-change.ts)

## 4. 扩展工作流详解

### `new`：先创建骨架

创建变更目录与元数据，查询产物状态并展示首个产物的指引；不直接把所有文档写完。适合希望分步骤决定内容的工作。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/new-change.ts)

### `continue`：每次推进一类产物

从状态结果取第一个 ready 产物，读取指引与已完成依赖，生成后停下。它推进的是规划，继续写代码应使用 apply。Schema 中 specs 的一个产物可能展开成多个能力文件。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/continue-change.ts)

### `ff`：集中补齐计划

按依赖生成实施前需要的产物，可处理条件性省略。它与 propose 的快速规划能力有重叠，新用户优先使用默认 propose。当前 ff 模板仍包含创建 Change 的步骤，已有同名变更时不宜照抄该步骤重建，可用 continue 推进已有产物。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/ff-change.ts)

### `verify`：对照计划寻找实现证据

检查完整性、正确性和一致性，给出分级问题与代码位置。缺少某类产物时说明检查限制；不能凭任务全勾选就认定所有场景都已覆盖。它不会替代项目测试。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/verify-change.ts)

### `bulk-archive`：批量收尾

选择多个 Change，检查完成度与规范冲突，再依据真实实现判断如何合并。适合多个独立变更一起收尾；同名要求发生相互矛盾的变化时，需要明确处理，不能简单覆盖。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/bulk-archive-change.ts)

### `onboard`：通过真实小任务学习

在实际项目中选择一个小改动，带讲解走完探索、产物、实施和归档。它可能修改真实代码和规划文件，因此不同于只展示演示文本的教程。[定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/onboard.ts)

## 5. 常用终端 CLI

### 配置与浏览

| 命令 | 用途 |
| --- | --- |
| `openspec init` | 初始化项目与工具入口 |
| `openspec update` | 根据当前 CLI 和 Profile 刷新工具入口 |
| `openspec config profile` | 选择全局工作流集合 |
| `openspec list` | 列出活动 Change |
| `openspec list --specs` | 列出主规范能力 |
| `openspec show <id> --type spec` | 查看指定主规范，包括场景 |
| `openspec view` | 查看终端仪表盘 |
| `openspec context --json` | 确认当前规划根及相关上下文 |

没有 `--specs` 的 list 返回活动变更，不是现有产品能力。相同名字可同时属于 Change 和 Spec，使用 `--type change/spec` 消除歧义。

### 状态、指引与校验

```bash
openspec new change add-article-favorites
openspec status --change add-article-favorites --json
openspec instructions specs --change add-article-favorites --json
openspec instructions apply --change add-article-favorites --json
openspec validate add-article-favorites --type change --strict
openspec validate --all --strict
openspec validate --archived
```

`instructions` 返回让 AI 工作所需的模板、依赖和约束，不会自行生成完整业务文档。最后一条只检查归档中的任务是否仍有未完成项；它不重放已归档的 Delta。

### 终端归档与 Schema

人在终端可运行 `openspec archive <name>`，按提示归档。已经决定执行且无人能回答终端提示的脚本使用 `openspec archive <name> --yes`；这会修改规范并移动文件，不能当作预览。

`--skip-specs` 只跳过这一次 CLI 归档的规范更新；变更本来就不改变规范时，应在元数据使用 `skip_specs: true` 表明意图。两者不是同一种状态。

自定义工作流常用 `openspec schema fork`、`schema validate`、`schema which`。它们管理 Schema；Spec 校验仍使用普通 validate。[CLI 参考](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/cli.md)

## 6. 状态字段不要混读

| 表面状态 | 能说明什么 | 不能说明什么 |
| --- | --- | --- |
| artifact: done | 匹配的产物文件存在 | 文档内容完整正确 |
| isPlanningComplete | 非跳过的规划产物已存在 | 产品实施完成 |
| apply: all_done | 追踪任务已全部勾选 | 测试、代码审查、部署均通过 |
| validate 成功 | 满足相应文档校验规则 | 代码实现了规范语义 |
| archive 成功 | 已完成相应归档操作 | 当前运行服务具备新功能 |

v1.13.0 增加了 apply 缺少 Delta 且未声明 skip_specs 的警告：即使任务存在、实施状态 ready，变更仍可能通不过 validate。自动化应读取当前 JSON 契约，不能照抄旧文档中的示意对象；例如 validate 当前返回 `items` 与 `summary`，status 的旧字段 `isComplete` 是规划完成的兼容别名。[Agent 契约](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/agent-contract.md)、[v1.13.0 发布说明](https://github.com/Fission-AI/OpenSpec/releases/tag/v1.13.0)
