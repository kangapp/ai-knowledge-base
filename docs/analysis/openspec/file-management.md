# 文件管理：让规范与实现一起演进

默认情况下，OpenSpec 的规划文件保存在代码仓库内。下面展示完整使用后的典型结构；初始化时不一定马上出现所有目录和文件。自定义 Schema、跳过规范的变更以及 Stores 会影响实际路径。

## 1. 目录地图

```text
your-project/
├── openspec/
│   ├── config.yaml
│   ├── specs/
│   │   └── article-favorites/
│   │       └── spec.md
│   ├── changes/
│   │   ├── add-article-favorites/
│   │   │   ├── .openspec.yaml
│   │   │   ├── proposal.md
│   │   │   ├── specs/article-favorites/spec.md
│   │   │   ├── design.md
│   │   │   └── tasks.md
│   │   └── archive/
│   │       └── YYYY-MM-DD-completed-change/
│   └── schemas/                  可选的项目自定义工作流
├── .agents/skills/openspec-*/    选择 Codex 时生成的 Skills
├── src/
└── tests/
```

一个 Capability 可采用平铺路径 `article-favorites`，也可沿用已有领域层级，例如 `reading/article-favorites`。修改已有能力时必须保持完整原路径，不能为了分类方便另建一个近似名字。[默认 Schema](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/schemas/spec-driven/schema.yaml)

## 2. 每类文件记录什么？

### 主规范：openspec/specs/

记录当前约定的行为，按能力组织 Requirement 与 Scenario。它是后续变更的基准；代码是否真正符合它，要由测试和审查确认。

典型结构为 `## Purpose`、`## Requirements`、`### Requirement: ...`、`#### Scenario: ...`。实现函数名、具体库和数据库字段通常不属于行为规范，应放在设计或代码里。

### 提案：proposal.md

说明为什么需要变化、改变什么、受影响能力和影响范围。Capabilities 分成 New 与 Modified：前者将创建新能力规范，后者使用现有能力的精确路径。先查 `openspec list --specs`，再读相关完整规范，避免重复定义。

### 增量规范：changes/<name>/specs/

描述本次相对主规范的变化。每个受影响能力有对应文件，不能把整个 Change 的所有行为混进一份无法归属的文档。

这是规划材料；完成同步后，主规范吸收其变化，Delta 原文随 Change 保留以便追溯。

### 设计：design.md

说明方案、选择依据、替代方案、风险，以及需要时的迁移安排。默认指引将它设为有条件产物；复杂度足够时才有必要展开。未解决的问题如果影响需求、方案或任务划分，必须先解决，不能用 Open Questions 标题推给实施。

### 任务：tasks.md

使用 `- [ ] 1.1 任务与验证方式` 格式。AI 从复选框恢复实施进度，完成后写成 `- [x]`。建议每项能在一个会话内完成，并按实际依赖排序。

它是默认 Schema 的实施清单，不会自动变成 GitHub Issues，也不会自动给每项任务分配独立工作树。

### 变更元数据：.openspec.yaml

记录本次使用的 Schema 等信息。例如：

```yaml
schema: spec-driven
created: 2026-09-13
```

纯文档或重构且没有规范层行为变化时，可额外加入 `skip_specs: true`。这个标记必须与“不存在 Delta Spec”一致；一边跳过一边保留 specs 文件会造成校验冲突。

### 归档：changes/archive/

保存完成或明确收尾的 Change 及其全部产物，包括元数据。常规名字是 `YYYY-MM-DD-<name>`；若 Change 名本身已有日期前缀，当前版本不会再叠加一个日期。

这些文件应随 Git 保存。归档不自动提交代码、关闭 Issue 或部署服务；项目需要自行约定这些动作与归档的先后。[官方概念](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/concepts.md)、[归档实现](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/templates/workflows/archive-change.ts)

## 3. Delta 的四种操作

| 操作 | 适用情况 | 必须注意 |
| --- | --- | --- |
| ADDED | 新增要求 | 不要用来重复已有的同名要求 |
| MODIFIED | 修改已有要求的行为 | 写出完整更新后的要求及所有应保留场景 |
| REMOVED | 删除要求 | 说明 Reason 与 Migration |
| RENAMED | 只改要求名字 | 用 FROM / TO；行为同时变化时配合 MODIFIED |

### 新能力的最小示例

```markdown
## Purpose

为知识库中的文章提供明确的后续阅读标记，使用户能够保存阅读意图，在刷新页面或重新访问同一服务时找回此前标记的内容，并与文章审核状态保持独立。

## ADDED Requirements

### Requirement: 收藏状态持久化
系统 SHALL 在刷新页面后保留文章的收藏状态。

#### Scenario: 刷新后仍已收藏
- **GIVEN** 用户已成功收藏文章 A
- **WHEN** 用户刷新页面
- **THEN** 文章 A 仍显示为已收藏
```

新能力最好从有实际含义的 Purpose 开始；严格校验会提示少于 50 个字符的 Purpose。新建主规范时归档会采用这个 Purpose，缺少它可能留下待补占位符。已有能力的 Purpose 不由 Delta 修改，应编辑主规范本身。

正文可使用中文，但保留 OpenSpec 的英文结构标题与 SHALL/MUST 关键字，Scenario 必须是四级标题。要求正文要表达可观察结果，每条新增或修改要求至少有一个场景。[默认规范指引](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/schemas/spec-driven/schema.yaml)、[多语言约定](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/multi-language.md)

### 修改、删除与重命名

修改时先从主规范复制完整 Requirement 块，再修改其中的行为和场景。CLI 合并会用 MODIFIED 内容替换原要求；如果只写新增的一个场景，原有场景可能丢失。AI sync 能理解语义，也不应成为省略规范的理由。

重命名的形式为：

```markdown
## RENAMED Requirements

- FROM: `### Requirement: 保存文章`
- TO: `### Requirement: 收藏文章`
```

若删除的是一个能力最后的要求，CLI 归档需要在变更元数据中显式声明 `retire_capabilities: true`，并检查主规范是否含有不宜丢失的附加内容。它会删除空下来的主规范文件，而不是保留没有要求的能力。[规范编写指南](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/writing-specs.md)

## 4. 配置、规则与 Schema 的区别

### 项目配置：config.yaml

下面是适用于本知识库语境的**示例配置**，不表示已经写入或启用：

```yaml
schema: spec-driven
context: |
  产物正文使用简体中文，保留 OpenSpec 结构标题和 SHALL/MUST。
  这是个人 AI 知识库；不增加多用户、登录或权限系统。
  项目规则见 AGENTS.md，API 约定见 docs/api.md。
rules:
  specs:
    - 描述可观察行为，至少覆盖一个重要异常或边界场景。
  tasks:
    - 每项任务写明可执行的验证方式。
operations:
  apply:
    guidance:
      - 先运行相关测试，再执行项目要求的完整检查。
```

`context` 提供项目事实和约束；`rules` 针对特定产物；`operations.apply/archive.guidance` 提供操作建议。三者都不是能自动强制执行的测试或权限系统，真正需要阻止合并的条件应落实到项目检查。

这些输入用于约束生成，不应机械复制进每份产物。推荐引用既有规则，避免把容易变化的项目细节维护在多个地方。[自定义配置](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/customization.md)

### 自定义 Schema

需要额外的研究、审查或验收产物时，再考虑从默认定义派生：

```bash
openspec schema fork spec-driven team-workflow
openspec schema validate team-workflow
openspec schema which team-workflow
```

副本位于 `openspec/schemas/team-workflow/`，包含 `schema.yaml` 和模板。Schema 中的 `requires` 定义依赖，`generates` 定义输出，`apply.requires` 定义实施前需要的产物，`apply.tracks` 指向进度文件。

Schema 名称选择优先级为：命令的 `--schema`、Change 元数据、项目配置、默认 `spec-driven`。同名 Schema 的文件查找则另按项目、用户目录、包内定义解析；可用 `schema which` 核对实际来源。

## 5. 工具入口怎样维护？

`openspec init/update` 按 AI 工具生成 Skills、命令文件或两者。Codex 当前使用 `.agents/skills/`；Claude Code 可使用 `.claude/skills/` 与 `.claude/commands/opsx/`。应检查提交 diff，按团队约定保存需要共享的入口。

升级包和刷新项目入口是两个动作：

```bash
npm install -g @fission-ai/openspec@latest
openspec update
```

后者在每个已采用 OpenSpec 的项目中运行。它会依据当前 Profile 更新入口，**不会替你重写业务 Spec 或修订某个 Change**；修订 Change 是对话中的 `/opsx:update`。工具生成内容需要长期定制时，优先通过配置与 Schema 表达。[工具适配](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/supported-tools.md)

## 6. Stores：规划跨越代码仓库时

Stores 在当前版本属于 **Beta**。它是一个独立的规划 Git 仓库，保留相同 `openspec/` 结构，并增加身份文件 `.openspec-store/store.yaml`。每台机器按名字注册后，用 `--store <id>` 选择它。

```bash
openspec store setup team-plans --path ~/openspec/team-plans
openspec new change add-article-favorites --store team-plans
openspec status --change add-article-favorites --store team-plans
```

可以让 Web、API 等多个仓库围绕同一份规划工作。Git 的克隆、提交、拉取和推送仍由团队负责，OpenSpec 不会自动替你同步远程仓库。

根目录选择优先考虑显式 `--store`；其次是最近的本地 OpenSpec 规划根，或只有配置指针的项目所声明的 `store:`；没有这些时才考虑全局 `defaultStore`。已有本地规划目录时，项目指针不会覆盖它。

因此，涉及 Store 时读取 CLI 返回的 `root.path`、`planningHome`、`changeRoot` 和具体产物路径，不要把所有写入都假定在当前代码仓库。来自被引用 Store 的资料只是相关背景，不能据此推断本次写入目标。[Stores 指南](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/stores-beta/user-guide.md)、[根目录与路径契约](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/agent-contract.md)

## 7. 长期维护的判断

我的建议是：主规范随交付更新，历史变更保留解释，测试持续验证行为；技术决策需要跨多次变更长期有效时，再引用项目 ADR。不要把历史设计整份复制成当前规范，也不要为了采用工具一次性回填全部系统。
