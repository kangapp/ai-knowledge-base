# mattpocock/skills 使用手册

这套 Skills 把软件开发拆成可以反复执行的协作流程：先把问题说清楚，再把决定写下来，随后拆成可验证的小任务，最后通过测试和审查交付。

> 本手册以 `mattpocock/skills` 的 `main` 当前内容为准。核对日期：2026-07-11；上游提交：`391a2701dd948f94f56a39f7533f8eea9a859c87`。

## 我现在该从哪里开始？

| 你的情况 | 推荐入口 | 接下来通常进入 |
| --- | --- | --- |
| 不知道应该用哪个 Skill | `ask-matt` | 它只推荐路线，不代替你执行 |
| 有一个新功能想法 | `grill-with-docs` | `to-spec` 或小改直接 `implement` |
| 软件出现难以定位的问题 | `diagnosing-bugs` | 回归测试、修复、审查 |
| 收到外部 Bug 或功能请求 | `triage` | `ready-for-agent` 后交给 `implement` |
| 工作太大，一个会话想不清楚 | `wayfinder` | 调查清楚后进入 `to-spec` |
| 想主动改善代码架构 | `improve-codebase-architecture` | 选定候选后进入澄清和实施流程 |

## 三分钟理解主工作流

```text
新想法
→ grill-with-docs：逐个解决需求问题，同时维护项目术语和重要决策
→ to-spec：把已讨论清楚的内容整理成需求说明
→ to-tickets：拆成互相标明依赖关系的小任务
→ implement：一次实现一张任务单
→ tdd：先写失败测试，再写最小实现
→ code-review：分别检查项目规范和需求完成度
→ 提交代码
```

小改动可以从 `grill-with-docs` 直接进入 `implement`。多会话工作应先创建需求说明和任务单，让新会话从持久记录重新建立上下文。

## 通俗术语速查

| 原词 | 通俗中文 | 它回答的问题 |
| --- | --- | --- |
| Issue | 事项单 | 有什么事情需要跟踪？ |
| Spec | 需求说明 | 最终要做成什么样？ |
| Ticket | 实施任务 | 这一小步具体做什么？ |
| ADR | 技术决策记录 | 为什么选择这个长期方案？ |
| `CONTEXT.md` | 项目术语表 | 项目里的词准确指什么？ |
| Agent Brief | AI 执行说明 | 新会话需要知道什么才能开工？ |
| Triage | 事项分诊 | 应补信息、交给 AI、交给人还是拒绝？ |
| Blocker | 前置阻塞 | 哪项任务不完成，当前任务就不能开始？ |
| Seam | 测试切入点 | 通过哪个稳定接口验证行为？ |
| Prototype | 验证性原型 | 这个设计运行起来是否可行？ |
| Handoff | 工作交接单 | 换会话后怎样继续？ |
| Diff | 代码改动对比 | 相比基准点具体改了什么？ |

## 深入阅读

- [完整工作流](usage-guide.md)：了解各 Skill 在新功能、Bug、外部请求和大型工作中怎样配合。
- [文件管理](file-management.md)：了解每类文件记录什么、由谁维护、是否提交，以及常见错误。
- [Skill 图鉴](skills-analysis.md)：查阅每个正式 Skill 的输入、输出、依赖和边界。
- [关系图](skills-workflow-diagram.md)：通过图理解 Skill 和产物如何交接。
- [文章收藏案例](examples/article-favorites.md)：从一个具体功能看完整信息生命周期。

## 使用前配置

每个仓库第一次使用工程流程时，运行一次 `setup-matt-pocock-skills`。当前项目已经配置为：

- GitHub Issues 管理需求和任务。
- 默认五类分诊标签。
- `AGENTS.md` 作为项目规则入口。
- 根目录 `CONTEXT.md` 与 `docs/adr/` 作为单领域文档布局，按需创建。
