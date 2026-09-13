# 完整工作流：从变更意图到长期规范

本页以 v1.13.0 的默认 `spec-driven` 为基准。命令使用 `/opsx:...` 通用写法，Codex 对应名称见[命令图鉴](commands-reference.md)。实际路径、产物和依赖以当前 Schema 的 CLI 输出为准。

## 1. 在已有项目中确定一个小变更

无需先为整个系统补写 Spec。先选一个真正需要交付、能用一句话描述意图的变化，读取相关代码、测试和已有需求。现有 PRD、Issue、ADR 可以作为背景引用，逐次把本次涉及的行为整理成可测试规范。[采用指南](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/existing-projects.md)

### Explore：解决未知

`/opsx:explore` 用于调查、比较和澄清。它可以读取代码、搜索资料、画图；不实施功能，也没有必须交付的文档数量。与 mattpocock 的 grilling 相比，我理解它更强调开放探索，没有固定的分轮问题树。

**当前定义的一个差异：** 官方 Explore 入门页概括为不写任何产物；实际生成模板允许在用户确认具体范围后创建或更新 OpenSpec 文档，首次写入前需列明文件和动作并单独确认。可把它理解为默认先讨论、需要时再明确记录，不能把回答设计问题当成同意写入。[Explore 文档](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/explore.md)、[执行模板](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/explore.ts)

## 2. 选择计划的推进方式

### Propose：一次形成实施前产物

`/opsx:propose add-article-favorites` 先确认会影响范围、行为、兼容性或验收的重要歧义，再读取项目上下文和相关实现，创建 Change，按依赖逐份生成文档。

它只规划，完成后停下来供审阅；实际模板明确要求随后由用户发起 apply。没有初始化 OpenSpec 根目录时也会停止，提示先初始化。[Propose 定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/propose.ts)

### New、Continue、FF：控制生成粒度

这些入口需要另行启用：

- `new` 只建立变更骨架，展示第一份文档的指引。
- `continue` 每次取当前依赖已满足的第一类产物，生成后停止。对于 `specs`，一类产物可能对应多个文件。
- `ff` 是集中生成实施前产物的扩展入口；不是跳过研究、需求或验证的快捷键。当前模板仍含创建 Change 的步骤，已有同名变更时不要直接重建，可用 continue 逐步推进。

生成顺序来自 Schema。默认 proposal 完成后，specs 与 design 都可以开始；tasks 依赖这两者。因此“proposal → specs → design → tasks”是常见阅读顺序，真实依赖图存在分支。[Continue 模板](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/continue-change.ts)、[FF 模板](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/ff-change.ts)

### 不要为了凑文档而创造需求

默认 Schema 对 design 的说明是“满足列出的复杂性条件时才创建”：跨模块方案、重要数据模型变化、新依赖、安全或迁移复杂性，以及需要先作出的技术决定。

当前 propose/ff 允许依据产物指引跳过有条件的 design；不过 CLI 的文件存在状态仍可能显示 design 缺失、规划未全齐。手工跳过后应记录原因，结合 `instructions apply` 判断是否具备实施条件，不能把 `status` 的单个字段当作质量结论。

对于完全不改变可观察行为的重构、工具或文档变更，可在 Change 的 `.openspec.yaml` 中明确设置 `skip_specs: true`；此时不要再生成 Delta Spec。行为有变化时不能用它消除校验提示。[默认 Schema](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/schemas/spec-driven/schema.yaml)

## 3. 审阅四类信息是否各司其职

| 文档 | 审阅问题 | 常见问题 |
| --- | --- | --- |
| proposal | 为什么改？范围和受影响能力准确吗？ | 描述过于宽泛，混入不相关功能 |
| specs | 什么行为应成立？能举例验证吗？ | 把内部表结构写成用户要求 |
| design | 为什么选择此方案？风险和迁移怎样处理？ | 未决定的问题已经影响后续任务 |
| tasks | 每项完成后怎样证明？依赖顺序合理吗？ | 只有“完成后端”“优化体验”等空泛条目 |

需求变更可能反过来修改提案，设计变化也可能反过来影响需求边界。这个流程允许迭代，不能只向下生成文件而不检查相互一致。

我的建议是审阅少量关键问题：正常行为是什么、哪种失败最不能接受、哪些内容明确不做、采用方案是否尊重项目边界。任务应写明自身验证方式；只有跨多项任务的系统验证才单列一项。[写规范指南](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/writing-specs.md)、[任务产物定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/schemas/spec-driven/schema.yaml)

## 4. Apply：从持久文件恢复并实施

`/opsx:apply <name>` 先读取状态与动态指引，再读取返回的所有上下文文件。根据 `tasks.md` 中未勾选项逐项实施，完成后及时勾选。

它不是一次性生成代码的命令：可以中途暂停，下次继续同一 Change。发生阻塞、设计问题或超出范围的工作时应指出并澄清；部分完成、推迟或缩小范围不能标成完成。默认工作流没有强制规定 TDD，具体测试方式由任务、项目约定和所选工程方法决定。[Apply 定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/apply-change.ts)

### 计划改变时怎样继续？

使用 `/opsx:update <name>` 协调**已有**规划文档：既可把新决定写入，也可检查文件间矛盾。当前模板要求逐份说明修改并确认；它不改代码，也不创建缺失产物。

之后检查任务的完成状态：新验收要求若未实施，应有未勾选任务或明确的新工作项，再发起 apply。否则旧的全勾选列表会让实现被误认为已经完成。这是本专题的操作建议。

如果只是细化原来的同一意图，更新当前 Change；如果目的已经变成另一件事，另建 Change，让历史仍能解释每次变化。[Update 定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/update-change.ts)

## 5. 分层验证

### 文档结构：Validate

终端运行：

```bash
openspec validate add-article-favorites --type change --strict
```

它检查规范和变更的可解析结构与规则，例如 Delta、Requirement、Scenario 等；严格模式会提升校验要求。它不执行你的产品测试，也不能判断代码是否满足业务语义。

### 实现对齐：Verify

启用后使用 `/opsx:verify <name>`，让 AI 检查三件事：

- 完整性：任务、需求和场景是否都有覆盖。
- 正确性：实现是否符合需求意图和边界。
- 一致性：实现是否体现设计、符合项目模式。

报告区分 CRITICAL、WARNING、SUGGESTION。这是 AI 辅助审查，不是独立执行的强制发布闸门；归档也不以存在一份 verify 报告为必要条件。[Verify 定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/verify-change.ts)

### 产品行为：测试与真实验收

执行任务中约定的测试和项目要求的检查。浏览器操作、接口响应、持久化结果或部署健康分别提供相应证据。我的建议是把“哪个场景由哪个测试或操作验证”写入任务，方便下一次复核。

## 6. Sync 与 Archive：同步和归档是两个动作

`/opsx:sync <name>` 将 Delta 合入主规范，Change 仍保留在活动目录。适合先审阅规范合并、分阶段维护规范；若提前同步，团队要知道相应实现的完成状态，避免把尚未交付的行为误认成已经上线。

`/opsx:archive <name>` 检查产物和任务，比较 Delta 与主规范，展示变化并提供同步选择。若选择同步，当前模板要求在当前流程完成合并、重新比较所有相关能力，确认没有遗漏之后才移动 Change；不能让同步在后台仍运行时就移动它。[归档模板](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/archive-change.ts)

因此“归档会更新规范”有前提：存在 Delta，而且选择并完成了同步。用户也可以选择不做同步；文档或任务未完成时，AI 工作流会警告并请求确认后继续。不要把归档成功等同于规范已同步或任务已交付。

终端 `openspec archive <name>` 则执行 CLI 的结构化校验、规范合并与文件移动，和 AI 工作流的语义合并不是同一个实现。完整 Delta 对两者都更可靠。[CLI 生命周期](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/cli.md)

## 7. 并行变更与长期维护

独立意图可以分成多个 Change，命令中显式指定名字。Change 文件夹只隔离规划材料，**不会自动隔离代码工作区**；多人实施仍需 Git 分支或工作树。

多个 Change 改同一 Capability 时，归档前检查重叠要求。可选的 bulk-archive 会查看冲突与实现证据，安排合并并报告结果；不能把时间先后直接当作正确的业务覆盖顺序。[批量归档定义](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/bulk-archive-change.ts)

我的建议是让规范、代码和任务的更新一起进入可审阅提交或 PR，并保留相关 Issue 链接。跨会话时从 Change 恢复；跨仓库需要共同规划时再使用[文件管理](file-management.md)中的 Stores Beta。
