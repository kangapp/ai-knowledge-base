# mattpocock/skills 使用手册

这套 Skills 把软件开发中的澄清、决策、实现和验证变成可组合的协作方法。按问题选择入口：简单明确的工作可以直接实施，跨会话工作再用需求说明和任务单保存上下文。

> 核对日期：2026-09-13；上游 `main` 提交：[3cca18b](https://github.com/mattpocock/skills/tree/3cca18b368ae95cdbdebbff572ccafa662551015)（提交日期 2026-09-04）；插件版本：`1.2.3`。正式范围以该提交的插件清单为准，共 **25 个 Skill**。行为以各 `SKILL.md` 及其引用文件为准；本手册的理解与建议会单独标明。

## 我现在该从哪里开始？

| 你的情况 | 推荐入口 | 接下来通常进入 |
| --- | --- | --- |
| 不知道应该用哪个 Skill | `ask-matt` | 它只推荐路线，不代替你执行 |
| 有一个新功能想法 | `grill-with-docs` | `to-spec` 或小改直接 `implement` |
| 软件出现难以定位的问题 | `diagnosing-bugs` | 回归测试、修复、审查 |
| 收到外部 Bug 或功能请求 | `triage` | `ready-for-agent` 后交给 `implement` |
| 工作太大，一个会话想不清楚 | `wayfinder` | 调查清楚后进入 `to-spec` |
| 想主动改善代码架构 | `improve-codebase-architecture` | 选定候选后进入澄清和实施流程 |
| 答案掌握在另一位同事或专家手里 | `to-questionnaire` | 生成问卷，收到回答后继续澄清或写 Spec |
| 正卡在 Git 合并或 rebase 冲突中 | `resolving-merge-conflicts` | 追溯双方意图、验证并完成当前操作 |
| 流程中有必须由人完成的操作 | `wizard` | 生成交互式 Bash 向导供人运行 |
| 没听懂 AI 刚才在说什么 | `wait-what` | 补上必要背景，重新解释上一条消息 |

## 三分钟理解主工作流

```text
新想法
→ grill-with-docs：按轮次解决当前可回答的问题，同时维护项目术语和重要决策
→ to-spec：把已讨论清楚的内容整理成需求说明
→ to-tickets：拆成互相标明依赖关系的小任务
→ implement：通常每张任务单开启干净会话
  ↳ 内部使用 tdd：在已确认的测试切入点，一次完成一个红灯—绿灯循环
  ↳ 内部使用 code-review：分别检查项目规范和需求完成度
→ 提交代码
```

小改动可以从 `grill-with-docs` 直接进入 `implement`。多会话工作应先创建需求说明和任务单，让新会话从持久记录重新建立上下文。

上面的箭头表示工作交接。`grill-with-docs`、`to-spec`、`to-tickets`、`implement` 都需要用户显式选择；前一个 Skill 不会自动启动下一个。`tdd`、`code-review` 等通用方法则可由模型按需使用。[上游调用规则](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/.agents/invocation.md)

## 通俗术语速查

| 原词 | 通俗中文 | 它回答的问题 |
| --- | --- | --- |
| Issue | 事项单 | 有什么事情需要跟踪？ |
| Spec | 需求说明 | 最终要做成什么样？ |
| Implementation ticket | 实施任务 | 这一小步交付什么可验证行为？ |
| Decision ticket | 决策任务 | 哪个问题必须先查清或决定？用于 Wayfinder |
| Frontier | 当前可推进项 | 哪些问题的前提已明确，或哪些任务的阻塞已解除？ |
| ADR | 技术决策记录 | 为什么选择这个长期方案？ |
| `CONTEXT.md` | 项目术语表 | 项目里的词准确指什么？ |
| Agent Brief | AI 执行说明 | 新会话需要知道什么才能开工？ |
| Triage | 事项分诊 | 应补信息、交给 AI、交给人还是拒绝？ |
| Blocker | 前置阻塞 | 哪项任务不完成，当前任务就不能开始？ |
| Seam | 测试切入点 | 通过哪个稳定接口验证行为？ |
| Prototype | 验证性原型 | 这个设计运行起来是否可行？ |
| Handoff | 可携带的工作交接单 | 换工具、目录、协作者或分出支线时怎样继续？ |
| Diff | 代码改动对比 | 相比基准点具体改了什么？ |

## 深入阅读

- [完整工作流](usage-guide.md)：了解各 Skill 在新功能、Bug、外部请求和大型工作中怎样配合。
- [文件管理](file-management.md)：了解每类文件记录什么、由谁维护、是否提交，以及常见错误。
- [Skill 图鉴](skills-analysis.md)：查阅每个正式 Skill 的输入、输出、依赖和边界。
- [关系图](skills-workflow-diagram.md)：通过图理解 Skill 和产物如何交接。
- [文章收藏案例](examples/article-favorites.md)：从一个具体功能看完整信息生命周期。

## 使用前配置

先选择一种安装方式。

Claude Code 官方插件：

```bash
claude plugins install mattpocock-skills
```

这是托管的只读技能包。需要自己修改 Skill，或使用 Codex 等其他 agent 时，使用文件安装方式：

```bash
npx skills@latest add mattpocock/skills
```

选择目标 agent、需要的 Skill 和 `setup-matt-pocock-skills`；之后可用 `npx skills update` 主动更新文件。避免同一环境同时安装两套重复 Skill。核对时上游仍未提供原生 Codex 插件。[安装说明](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/README.md)

每个仓库第一次使用工程流程时，运行一次 `setup-matt-pocock-skills`。手册后文用 Skill 名称标识入口；Claude Code 通常写作 `/to-spec`，Codex 显式调用写作 `$to-spec`。实际隐式调用权限见[Skill 图鉴](skills-analysis.md)。

Setup 支持 GitHub、GitLab、本地 Markdown，以及用户描述操作流程的其他 Tracker。仅安装 `triage` 时配置标签；通常直接采用单领域布局，有 monorepo 信号才讨论多领域布局。[Setup 定义](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/setup-matt-pocock-skills/SKILL.md)

**本手册示例项目 `ai-knowledge-base` 的既有配置**如下，这是项目选择，不是所有用户的默认配置：

- GitHub Issues 管理需求和任务。
- 默认五类分诊标签。
- `AGENTS.md` 作为项目规则入口。
- 根目录 `CONTEXT.md` 与 `docs/adr/` 作为单领域文档布局，按需创建。

## 我的理解与使用建议

以下是本手册的实践判断，供选择工作方式时参考。

1. **把 Skill 当作可组合的方法。** 先判断缺的是事实、决策、实现还是验证，再选择工具；没有必要为了完成一个小改动走完全部入口。
2. **把决策依据留下来。** 术语表、ADR、研究引用和可重跑的原型各有职责。后续会话需要知道结论为什么成立，不能只接收一句总结。
3. **按依赖组织人与 AI 的协作。** AI 查事实，人决定取舍；同一轮问前提已经满足的问题，后台研究处理能独立完成的资料工作。
4. **按下一阶段需要管理上下文。** 先考虑继续当前会话，再判断清空、交接、子任务或压缩。保留完整推理与腾出上下文空间之间需要取舍。

这些判断主要来自 [ask-matt](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/ask-matt/SKILL.md)、[grilling](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/grilling/SKILL.md) 和 [prototype](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/prototype/SKILL.md) 的职责划分；各方法的具体边界以图鉴中的原文为准。
