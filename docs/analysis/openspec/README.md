# OpenSpec 使用手册与专题分析

OpenSpec 把一次软件变更组织成可审查的提案、行为规范、设计和任务，并在完成后将规范变化合入长期记录。它让人和 AI 在动手前对齐目标，也让下一次工作能从文件恢复理解。

> 核对日期：2026-09-13；GitHub 最新发布版与 npm 最新版均为 **v1.13.0**。本专题固定到上游提交 [9d4e597](https://github.com/Fission-AI/OpenSpec/tree/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461)（2026-09-09），与该版本发布提交一致。主要依据官方文档、默认 Schema 和实际生成的工作流模板；个人判断会明确标注。[版本说明](https://github.com/Fission-AI/OpenSpec/releases/tag/v1.13.0)

## 我现在该从哪里开始？

| 你的情况 | 推荐入口 | 预期结果 |
| --- | --- | --- |
| 对需求、方案或现有代码还不确定 | `/opsx:explore` | 查明事实、比较方案、明确边界 |
| 已经知道要改什么，希望形成完整计划 | `/opsx:propose` | 创建 Change 和实施前需要的文档 |
| 想逐份审阅文档再继续 | `/opsx:new` + `/opsx:continue` | 每次推进一个产物，需启用扩展工作流 |
| 计划清楚，开始或继续实现 | `/opsx:apply` | 按任务实施，保存完成状态 |
| 实施中改变了设计或验收条件 | `/opsx:update` | 协调已有文档，再回到实现 |
| 检查实现是否符合计划 | `/opsx:verify` | 完整性、正确性、一致性报告，需启用 |
| 已完成，准备保存这次变更 | `/opsx:archive` | 评估规范同步并归档变更 |
| 已有大型项目，还没有任何 Spec | 从一个真实小变更开始 | 逐次积累规范，无须先补全文档 |

这里使用官方通用写法 `/opsx:...`。**它们输入在 AI 对话框中**；Codex 使用对应 Skill 名称，例如 `$openspec-propose`、`$openspec-apply-change`，并非把所有命令机械换成同一个前缀。完整对应见[命令图鉴](commands-reference.md)。[官方调用说明](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/how-commands-work.md)

## 三分钟理解它的核心

```text
openspec/specs/：当前已经约定的行为
        ↓ 阅读现有规范和代码
openspec/changes/<name>/：这一次准备改变什么
        ├─ proposal.md：为什么改、范围是什么
        ├─ specs/：相对现有规范的变化
        ├─ design.md：怎样实现、为什么这样选择
        └─ tasks.md：具体实施与验证项
        ↓ apply 实现，测试和审查
sync / archive：把规范变化合入主规范，保存变更历史
        ↓
下一次变更从更新后的 specs/ 出发
```

最关键的区分是：**主规范记录当前约定，Change 保存本次变化，代码和测试提供实现证据。** 归档只是文件生命周期的一步；它本身不能证明产品已通过测试或已部署。[概念说明](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/concepts.md)

## 安装与第一次使用

OpenSpec CLI 需要 Node.js **20.19.0 或更新版本**。在终端执行：

```bash
npm install -g @fission-ai/openspec@latest
cd your-project
openspec init
openspec --version
```

`init` 为选择的 AI 工具生成入口文件和项目配置；它不会替你启动一个新的 AI 助手。随后在该项目的 AI 对话中输入：

```text
/opsx:explore 我想给文章列表增加收藏功能，先明确行为和项目约束
/opsx:propose add-article-favorites
```

审阅生成的文档后，再发起 `/opsx:apply add-article-favorites`。完成验证后使用 `/opsx:archive add-article-favorites`。上述每行代表一次交互，不是一次粘贴后全部自动执行。[入门指南](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/getting-started.md)

### Codex 的具体入口

新项目只配置 Codex，并设置中文产物，可以执行：

```bash
openspec init --tools codex --language "简体中文"
```

然后在对话中使用：

```text
$openspec-explore
$openspec-propose add-article-favorites
$openspec-apply-change add-article-favorites
$openspec-archive-change add-article-favorites
```

当前 OpenSpec 为 Codex 写入项目的 `.agents/skills/openspec-*/SKILL.md`，采用 Skills 入口，不生成 Codex 自定义 Prompt。已存在配置时，应合并修改 `context` 中的语言约定。[工具适配](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/supported-tools.md)、[多语言配置](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/multi-language.md)

### 默认与扩展工作流

默认 `core` 包含 **6 个**工作流：`propose`、`explore`、`apply`、`update`、`sync`、`archive`。另有 **6 个**可选择的扩展工作流：`new`、`continue`、`ff`、`verify`、`bulk-archive`、`onboard`。

需要逐步生成或实施审查时，在终端运行 `openspec config profile`，选择所需工作流，再到项目运行 `openspec update`。Profile 决定安装哪些入口；Schema 决定产物与依赖，两者职责不同。[正式工作流清单](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/src/core/profiles.ts)

## 通俗术语速查

| 术语 | 中文理解 | 例子 |
| --- | --- | --- |
| Spec | 可验证的行为规范 | 收藏后刷新仍保留 |
| Capability | 一组相关行为 | `article-favorites` |
| Requirement | 一项明确要求 | 可以取消收藏 |
| Scenario | 要求成立的具体场景 | 在收藏筛选页取消一篇文章 |
| Change | 有单一意图的一次变更 | `add-article-favorites` |
| Artifact | 变更中的文档产物 | 提案、设计、任务、Delta Spec |
| Delta Spec | 相对主规范的变化 | 新增、修改、删除、重命名要求 |
| Schema | 产物种类与依赖定义 | 默认 `spec-driven` |
| Profile | 安装的工作流入口集合 | `core` 或自选工作流 |
| Store | 独立的规划仓库 | 多个代码仓库共同使用的需求记录，Beta |

## 与 mattpocock Skills 怎样比较？

以下是本专题的理解：两者都在减少 AI 开发中的信息丢失，但重心不同。

| 关注点 | OpenSpec | mattpocock Skills |
| --- | --- | --- |
| 核心组织方式 | 围绕 Change 和规范增量组织工作 | 按问题组合澄清、决策、实施、审查方法 |
| 长期记忆 | 主规范、变更文档和归档 | 术语、ADR、Spec、任务单、研究或原型证据 |
| 拆分与跟踪 | 默认一份 `tasks.md` | 支持 Tracker 中的独立 Ticket 和依赖 |
| 实施质量 | apply 依任务执行，verify 对照产物 | TDD、诊断、双轴 code-review 等具体方法 |
| 扩展方式 | 配置、Schema、工具适配、Stores | 增加或组合 Skill，选择项目工作约定 |

我的建议是：需要持续维护“产品应当怎样工作”时，优先考虑 OpenSpec；需要改善“如何澄清、如何测试、如何审查”时，mattpocock 的方法很有价值。两者可以配合，但先确定哪个地方保存需求、哪个地方跟踪完成状态，避免复制出两套互相冲突的 Spec 和任务表。[mattpocock 专题](/analysis/mattpocock-skills/index.html)

对本知识库，更合适的试点是一个边界清楚的功能，而不是立即迁移所有 GitHub Issues。仓库目前的 Issues、项目规则和领域文档约定继续作为既有输入；此专题只展示采用 OpenSpec 的方法，没有给项目安装或启用它。

## 我的理解与使用建议

1. **价值在于持续维护行为约定。** 文档生成很容易；每次实现后把变化准确合回主规范，才会形成可信的项目记忆。
2. **根据不确定性选择粒度。** 需求明确时用 propose；需要讨论时先 explore；需要逐份审阅时选择 continue。小修正不必制造完整仪式。
3. **把文档完成与功能完成分开判断。** 文件存在、任务勾选、结构校验、测试通过、上线成功是不同证据，不能互相替代。
4. **先采用默认结构，再按真实需要扩展。** 单仓库通常够用本地 `openspec/`；跨仓库确有共同规划需要时再评估 Stores Beta。[既有项目采用指南](https://github.com/Fission-AI/OpenSpec/blob/9d4e5974e5c0d9a09b9c6c1e1eb0975e80ec4461/docs/existing-projects.md)

## 深入阅读

- [完整工作流](usage-guide.md)：从探索、计划到实施、同步和归档。
- [文件管理](file-management.md)：各类文件、Delta 写法、配置和长期维护。
- [命令图鉴](commands-reference.md)：12 个工作流、Codex 映射和常用 CLI。
- [关系图](workflow-diagrams.md)：生命周期、产物依赖、验证边界和组合方式。
- [文章收藏案例](examples/article-favorites.md)：与 mattpocock 专题使用同一功能进行对照。
