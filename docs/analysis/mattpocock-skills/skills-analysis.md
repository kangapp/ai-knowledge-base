# mattpocock/skills 工作流与技能体系分析

## 1. 研究口径与结论摘要

本文是后续流程图与专题页面的事实和术语基线，不追踪上游仓库的浮动 `main` 分支。

- 研究日期：2026-07-10。
- 固定版本：`mattpocock/skills` 提交 `391a2701dd948f94f56a39f7533f8eea9a859c87`（该提交日期也是 2026-07-10）。
- 正式技能：以 [`.claude-plugin/plugin.json`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/.claude-plugin/plugin.json) 的 `skills` 数组为唯一清单，共 **21 个**；其中 **13 个 user-invoked**、**8 个 model-invoked**。
- 主要依据：[仓库 README](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/README.md)、[调用规则](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/.agents/invocation.md)、[`ask-matt`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/ask-matt/SKILL.md) 以及插件清单内各技能的 `SKILL.md`。

这里要区分两个统计口径：仓库把技能目录放进 `engineering`、`productivity`、`misc`、`personal`、`in-progress`、`deprecated` 六个桶，这是作者维护、试验和归档内容的物理视图；安装插件真正暴露哪些技能，则由 `plugin.json` 显式决定。两者不能互相替代。

**核心结论：目录树是维护视图，情境路由才是使用视图。** 使用者面对的不是“先选 engineering 还是 productivity”，而是“我现在是在澄清想法、诊断 Bug、分流外部请求、探索大项目、维护架构还是研究资料”。这六个业务入口之外，跨会话交接是任意节点可用的桥。`ask-matt` 正是正式技能之上的情境路由器。

因此，本文采用双层信息架构：

1. **使用层**：安装和 Setup、主流程、六个业务入口与跨会话桥、产物交接；回答“现在该走哪条路”。
2. **参考层**：21 个正式技能目录、非正式目录快照、事实与评价；回答“某个技能具体承诺什么、边界在哪里”。

## 2. 安装、Setup 与调用模型

### 2.1 安装与首次配置

安装命令是：

```bash
npx skills@latest add mattpocock/skills
```

安装器会让用户选择要安装的技能及目标 coding agent；上游 README 特别要求安装时选中 `/setup-matt-pocock-skills`。随后在目标仓库中由用户运行 `/setup-matt-pocock-skills`。它不是确定性脚本，而是“探测—展示—确认—写入”的提示驱动配置流程：

1. **仓库探测**：检查 Git remote、`.git/config`、根目录 `AGENTS.md`/`CLAUDE.md`、现有 `CONTEXT.md`/`CONTEXT-MAP.md`、ADR、`docs/agents/`、`.scratch/`、是否安装 `triage`，以及 monorepo 信号。
2. **Issue Tracker**：优先推荐探测到的托管平台；技能正文列出的直接选项是 GitHub、GitLab、本地 Markdown 和 Other。选 Other 时记录 Jira、Linear 等自定义工作流。选择写入 `docs/agents/issue-tracker.md`，供 `to-spec`、`to-tickets`、`triage`、`wayfinder` 和 `code-review` 等技能读取。
3. **Triage Labels**：仅在安装了 `triage` 时配置。默认保留五个状态角色名 `needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix`，也可映射到仓库已有标签；结果写入 `docs/agents/triage-labels.md`。
4. **Domain Docs**：绝大多数仓库默认单上下文，即根目录 `CONTEXT.md` 加 `docs/adr/`；只有探测到大型多包仓库信号时才提供 `CONTEXT-MAP.md` 指向多个上下文的方案。消费规则和布局写入 `docs/agents/domain.md`。
5. **确认和写入**：先展示 `## Agent skills` 配置块与两个配置文件草稿（`issue-tracker.md`、`domain.md`）；安装了 `triage` 时再加 `triage-labels.md`，共三个。得到用户确认后再写。如果已有 `CLAUDE.md` 就更新它，否则更新已有的 `AGENTS.md`；两者都没有时询问用户创建哪一个，不自行选择。

README 的快速说明把 Issue Tracker 举例为 GitHub、Linear 或本地文件，而固定提交中的 Setup 技能正文列出 GitHub、GitLab、本地 Markdown、Other。本文以技能正文描述实际分支，并把 Linear 视作 Other 可承载的自定义工作流；这一处文案差异也说明阅读时必须固定提交并核对执行文件。

### 2.2 user-invoked 与 model-invoked

| 维度 | user-invoked | model-invoked |
| --- | --- | --- |
| 谁能触发 | 只有人类显式输入技能名 | 模型可按任务自动选择，人类也可显式输入 |
| frontmatter | `disable-model-invocation: true` | 省略 `disable-model-invocation` |
| `description` 的读者 | 人类，简短说明斜杠命令用途 | 模型，包含可触发自动选择的情境描述 |
| 主要职责 | 编排流程、设置人工决策门、发布或推进工作 | 提供可复用纪律、参考词汇或可嵌入的执行环 |
| 成本 | 不常驻模型上下文，但用户要记得它存在，形成认知负担 | 描述常驻上下文，增加上下文负担，但减少人工记忆和选择成本 |
| 组合规则 | **可以组合 model-invoked 技能** | 可以由用户直接调用，也可被模型或 user-invoked 流程采用 |
| 硬边界 | **不能自动调用另一个 user-invoked 技能** | 不受这条“人类唯一入口”边界限制 |

这条边界决定了如何阅读流程图：例如 `/to-tickets` 的末尾建议逐票运行 `/implement`，两者都是 user-invoked，因此它表达的是下一步应由用户启动，而不是 `to-tickets` 在当前执行中自动嵌套 `implement`。相反，`implement` 可以把 model-invoked 的 `tdd` 和 `code-review` 组合进自己的工作。

当 user-invoked 技能增多到难以记忆时，`ask-matt` 用一个显式入口承担索引职责；它给出路线，但不代替用户触发路线中的下一个 user-invoked 技能。

## 3. 主工作流、六个业务入口与跨会话桥

### 3.1 Idea-to-ship 主链

完整主链统一写作：

```text
setup → grill-with-docs → [handoff → prototype → handoff]? →
to-spec → to-tickets → implement → tdd → code-review → commit
```

各段含义如下：

1. `setup` 是首次工程流程的仓库级前置配置，不是每项工作都重复运行。
2. `grill-with-docs` 通过 `grilling` 逐问澄清决策，并用 `domain-modeling` 即时维护 `CONTEXT.md` 和必要的 ADR。
3. 如果某个设计问题无法只靠谈话解决，先用 `handoff` 把当前讨论交给新会话，在新会话用 `prototype` 制作可运行的抛弃式答案，再用 `handoff` 把结论带回原始 idea 会话。方括号内是可选支线。
4. **单会话小改动**不需要为了形式制造 Spec 和 Tickets：从 `grill-with-docs` 直接进入 `implement`，留在同一上下文完成。
5. **多会话工作**才从同一上下文依次运行 `to-spec` 和 `to-tickets`。前者把已经讨论清楚的内容发布为 Spec issue，后者拆成声明 blocking edges 的 tracer-bullet tickets。
6. 每个 ticket 用新的上下文启动一次 `implement`；`implement` 在预先确认的 seam 上驱动 `tdd` 的 red-green 垂直切片，定期运行类型检查和局部测试，结束时运行完整测试，再以 `code-review` 分别检查 Standards 与 Spec，最后提交。

`ask-matt` 还给出一条上下文卫生规则：从 grilling 到产出 tickets 的步骤应尽量保留在一个未压缩的上下文中，使后续产物继承同一套决策；接近模型的有效推理窗口时，用 `handoff` 转入新会话。进入逐票实现后则反过来，每张 ticket 使用干净上下文，避免旧任务污染新任务。

### 3.2 六个业务入口与跨会话桥

| 起始情境 | 入口与局部路径 | 产物 | 回到主链的位置 |
| --- | --- | --- | --- |
| 新需求 | `grill-with-docs`：通过 `grilling` 逐问澄清，并用 `domain-modeling` 维护领域文档 | 共享理解、更新后的 `CONTEXT.md` 和必要 ADR | 单会话小改回到 `implement`；多会话工作回到 `to-spec` |
| Bug 或性能回归 | `diagnosing-bugs`：建立能捕获用户精确症状的 tight feedback loop，再最小化、列 3–5 个可证伪假设、逐项探测、先写回归测试后修复 | 最小复现、修复、回归测试、清理和 post-mortem | 该技能已经包含修复和回归测试，因此通常在 `code-review → commit` 收尾；若发现没有正确测试 seam，修复后转入架构维护入口，再从 `grill-with-docs` 回主链 |
| 外部 Issue/PR | `triage`：读取 tracker、验证主张、必要时组合 `grilling` 与 `domain-modeling`，在人类确认下改变状态 | category/state 标签、triage notes 或 agent brief；PR 还验证现有 diff | `ready-for-agent` 的新工作回到 `implement`；已有 PR 可按 brief 处理 diff 后进入 `code-review`；`ready-for-human` 交给人类，不强行进入自动实现 |
| 超大、模糊、单会话装不下的工作 | `wayfinder`：先定义 destination，再建立 map、调查 tickets、blocking edges 与 frontier；每个会话只解决一张票 | 决策地图、已关闭的决策票、逐步消散的 fog of war | 路线清楚后回到 `to-spec`；若实际范围足够小，可直接回到 `implement` |
| 架构维护 | `improve-codebase-architecture`：用 `codebase-design` 词汇扫描 deepening opportunities，生成临时 HTML 候选报告，由用户选一个再 grilling | 带 before/after 可视化的临时报告、被选中的架构想法与设计决策 | 候选想法回到 `grill-with-docs`，随后按规模走小改或 Spec/Tickets 分支 |
| 研究 | `research`：后台 agent 针对高信任的一手资料调查并写带引用的 Markdown | research Markdown，作为事实输入而非决策替代品 | 把研究文件带入 `grill-with-docs`，由人类和模型共同作取舍，再走主链 |
| 跨会话交接 | `handoff`：把当前对话压缩为 OS 临时目录中的 Markdown，引用而不复制既有 Spec、ADR、issue、commit、diff，并脱敏 | handoff Markdown 与 suggested skills | 新会话从被中断的主链节点继续；若为 prototype 支线，结论回到原 idea 线程并在 `to-spec` 前合流 |

表中前六行是业务入口；“跨会话交接”不是第七个业务入口，而是任意节点可用的桥。这里的 `/compact` 是 agent 的内建能力，不在 21 个正式技能中。它让同一对话继续但允许早期内容被摘要；`handoff` 则是有意开启新会话的桥。前者适合阶段边界，后者适合上下文已满或需要并行支线的情况。

## 4. 产物交接契约

这套系统的可组合性不只来自技能名，更来自稳定产物。下表把每个关键产物视为生产者与消费者之间的契约。

| 产物 | 主要生产者 | 主要消费者 | 生命周期与交接语义 |
| --- | --- | --- | --- |
| `docs/agents/issue-tracker.md` | `setup-matt-pocock-skills` | `to-spec`、`to-tickets`、`triage`、`wayfinder`、`code-review` | 仓库级长期配置；切换 tracker 或重建配置时更新，记录 issue、阻塞关系、查询等平台操作 |
| `docs/agents/triage-labels.md` | `setup-matt-pocock-skills`，仅安装 `triage` 时生成 | `triage`、`to-spec`、`to-tickets` | 仓库级角色到实际标签字符串的映射；复用现有标签，避免重复创建 |
| `docs/agents/domain.md` | `setup-matt-pocock-skills` | 所有需要读取或维护领域文档的工程技能 | 仓库级长期配置；声明 single-context 或 multi-context 布局及消费规则 |
| `CONTEXT.md` | `domain-modeling`；常由 `grill-with-docs`、`triage`、`wayfinder`、架构 grilling 驱动 | 规划、实现、测试、诊断、评审和架构扫描 | 活的领域术语表；术语一旦澄清就即时更新，只放领域语言，不放实现细节、Spec 或工作草稿 |
| `docs/adr/*.md` | `domain-modeling` 在难逆转、缺少上下文会令人意外且确有权衡时创建 | 后续 grilling、Spec、实现、诊断、架构与 review | 长期决策记录；防止后续会话重新争论已定取舍，只有达到三项门槛才生成 |
| Spec issue | `to-spec` | `to-tickets`、`implement`、`code-review` | 多会话工作的需求基线；从既有讨论综合并发布，标为 `ready-for-agent`，不再额外 triage |
| tracer-bullet tickets + blocking edges | `to-tickets` | 每次新的 `implement` 会话、tracker frontier 查询 | 每张票是单会话可完成的端到端切片；本地 tracker 用逐票文件和文本依赖，真实 tracker 优先用原生 blocking links；阻塞解除后可领取 |
| prototype branch | `prototype` | 原 idea/Spec/implementation issue | 主分支之外的抛弃式证据快照；保留问题、结论和分支指针，主分支只吸收已验证决策，不吸收演示性代码 |
| handoff Markdown | `handoff` | 新会话 | 临时跨上下文桥；存放在 OS 临时目录，脱敏并以指针引用已有正式产物，不把同一事实复制成第二来源 |
| research Markdown | `research` | `grill-with-docs`、`wayfinder` 或其他决策会话 | 仓库中的带一手来源引用的研究快照；提供事实输入，不能代替人类决策和领域建模 |
| tests | `tdd`、`diagnosing-bugs` | 实现反馈环、`code-review`、CI、未来回归验证 | 长期可执行的行为契约；通过确认过的 public seam 验证外部行为，随实现保留 |
| code-review report | `code-review` | 实现者和人类审阅者 | 固定点到 `HEAD` 的阶段性质量门；Standards 与 Spec 两个轴并列报告，不合并重排 |
| commit | `implement` 的最终步骤 | 后续 ticket、PR、review、发布流程 | 一个实现单元的持久版本边界；在测试与双轴 review 后产生，并为后续 diff 提供固定点 |

固定快照存在一个未决一致性问题：Setup 在未安装 `triage` 时明确跳过标签配置，不生成 `triage-labels.md`；但 `to-spec` 与 `to-tickets` 又声明 triage label vocabulary 应已提供，并分别要求把 Spec 或 tickets 标为 `ready-for-agent`。源码没有说明这种情况下的回退行为。因此，完整多会话主链在进入 `to-spec → to-tickets` 前存在此前置张力；本文只记录它，不推断如何补齐标签词汇。

## 5. 21 个正式技能目录

调用方式中的“用户”表示必须由人类显式启动；“模型/用户”表示模型可自动选择，人类也可显式启动。依赖列既包括被组合的技能，也包括必须存在的配置、文档或外部能力。

| 技能 | 调用方式 | 核心输入 | 核心输出 | 关键依赖 | 流程位置 | 边界 |
| --- | --- | --- | --- | --- | --- | --- |
| [`ask-matt`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/ask-matt/SKILL.md) | 用户：`/ask-matt` | 用户当前情境、工作规模、是否有代码库 | 推荐的 skill 或 flow | 21 项技能的路由知识、调用规则 | 总路由器；工程流前先检查 Setup | 只给路线，不执行另一个 user-invoked 技能；无代码库的澄清转 `grill-me` |
| [`diagnosing-bugs`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/diagnosing-bugs/SKILL.md) | 模型/用户 | Bug、异常、失败、性能回归及可访问环境 | tight feedback loop、最小复现、已验证修复、回归测试、post-mortem | `CONTEXT.md`、相关 ADR、可运行测试/脚本/浏览器/trace | Bug 入口，结束后 review/commit；无测试 seam 时转架构维护 | 未得到已运行且能捕获精确症状的红灯命令前不进入假设；只处理可验证的困难故障 |
| [`grill-with-docs`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/grill-with-docs/SKILL.md) | 用户：`/grill-with-docs` | 有代码库的计划或设计 | 共享理解、更新后的术语表和必要 ADR | `grilling`、`domain-modeling`、代码与已有领域文档 | 主链起点 | 逐问澄清，不实施计划；无代码库时用 `grill-me` |
| [`triage`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/triage/SKILL.md) | 用户：`/triage` | 外部 issue/PR、tracker 状态、维护者指示 | category/state、验证结果、notes 或 durable brief | Issue Tracker、Triage Labels、领域文档；必要时 `grilling`、`domain-modeling` | 外部请求入口，产出 agent-ready 工作后接 `implement` | 只 triage 外来原始请求；`to-tickets` 生成的票已经 ready，不再 triage；状态变化经过维护者决策门 |
| [`improve-codebase-architecture`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/improve-codebase-architecture/SKILL.md) | 用户：`/improve-codebase-architecture` | 代码库、`CONTEXT.md`、相关 ADR | OS 临时目录中的视觉 HTML 候选报告；选择后形成设计问题 | `codebase-design`、代码探索能力、`grilling`、`domain-modeling` | 架构维护入口，选题后接 `grill-with-docs` | 扫描阶段不先提具体 interface；报告不落仓库；不能无视 ADR 冲突 |
| [`setup-matt-pocock-skills`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/setup-matt-pocock-skills/SKILL.md) | 用户：`/setup-matt-pocock-skills` | 仓库结构、remote、现有 agent/domain 文件、用户选择 | `docs/agents/*.md` 与既有 `CLAUDE.md`/`AGENTS.md` 中的配置块 | Git 与文件探测；用户逐节确认 | 首次工程流程前置 | 提示驱动而非脚本；不同时新建两种 agent 指令文件；Triage 配置只在技能已安装时生成 |
| [`tdd`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/tdd/SKILL.md) | 模型/用户 | 已确认的 public seam、一个具体外部行为 | 一次一个 red-green 垂直切片及可保留测试 | `CONTEXT.md`、ADR、测试工具、用户预先确认 seam | `implement` 内部反馈环，也可独立使用 | 不在未确认 seam 上写测试；不测试实现细节；不横向批量写测试；refactor 留给 review 阶段 |
| [`to-spec`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/to-spec/SKILL.md) | 用户：`/to-spec` | 当前完整对话和代码库理解 | 发布到 tracker、带 `ready-for-agent` 的 Spec issue | Issue Tracker、Triage Labels、领域术语、用户确认测试 seams | 多会话分支：grilling 后、tickets 前 | 不重新访谈，只综合已有信息；通常不写具体文件路径或代码；原型决策片段是有限例外 |
| [`to-tickets`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/to-tickets/SKILL.md) | 用户：`/to-tickets` | 已有 Spec、plan、issue 或当前讨论 | 获用户批准的 tracer-bullet tickets 与 blocking edges | Issue Tracker、Triage Labels、领域术语、tracker 阻塞能力 | Spec 后、逐票 `implement` 前 | 票必须是单会话端到端切片；wide refactor 用 expand–contract；不修改或关闭 parent issue；发布前由用户确认粒度和依赖 |
| [`wayfinder`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/wayfinder/SKILL.md) | 用户：`/wayfinder` | 超大、模糊、路线尚不可见的 destination | map issue、调查 tickets、blocking frontier、逐票决策 | Issue Tracker、`grilling`、`domain-modeling`；按票型使用 `research`/`prototype` | 超大工作入口，清雾后接 `to-spec` 或小范围 `implement` | 默认产出决策而非 destination deliverables；一次会话最多解决一张票；HITL 票不能由 agent 冒充人类回答 |
| [`implement`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/implement/SKILL.md) | 用户：`/implement` | 一张 ticket、Spec 或明确工作说明 | 实现、测试结果、review、commit | `tdd`、`code-review`、类型检查和测试命令 | 主链执行段 | 在预先确认的 seams 上测试；局部反馈常跑、全量测试收尾；提交前必须 review |
| [`prototype`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/prototype/SKILL.md) | 模型/用户 | 一个需要可运行答案的逻辑/状态或 UI 设计问题 | 可运行 CLI 或同一路由多种 UI；throwaway branch、结论与 context pointer | 现有项目运行方式和路由约定 | grilling 与 Spec 之间的可选支线，也可单独探索 | 从第一天即标记抛弃；默认无持久化、测试、抽象和 polish；主分支只保留被验证的决策 |
| [`research`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/research/SKILL.md) | 模型/用户 | 需要查证的一项问题 | 仓库中带逐项引用的单一 Markdown | 后台 agent、高信任一手来源、仓库既有笔记约定 | 研究入口，结果带回 grilling；也可成为 wayfinder research 票 | 只做阅读和事实归档，不用二手文章替代来源，不代替决策或实现 |
| [`domain-modeling`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/domain-modeling/SKILL.md) | 模型/用户 | 模糊、重载或冲突的领域术语，具体边界场景，难逆决策 | 即时更新的 `CONTEXT.md`、达到门槛的 ADR | single/multi-context 布局、用户决策、代码事实 | 贯穿 grilling、triage、wayfinder 和架构工作的词汇层 | 仅“读取术语表”不算调用；`CONTEXT.md` 只做 glossary；ADR 必须同时满足难逆、意外、真实权衡 |
| [`codebase-design`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/codebase-design/SKILL.md) | 模型/用户 | module/interface/seam 的设计或重构问题 | deep-module 统一词汇、候选 interface 与 seam 评价 | 当前调用关系和可变 adapter 事实；需要时 design-it-twice agent | 架构与 TDD 下方的设计词汇层 | 使用 module、interface、depth、seam、adapter、leverage、locality 的精确词义；只有一个 adapter 时不凭空制造 seam |
| [`code-review`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/code-review/SKILL.md) | 模型/用户 | 用户给定 fixed point、`HEAD` diff、Spec、仓库 standards | 并排的 Standards report 与 Spec report | 可解析 Git fixed point、Issue Tracker、标准文件、两个并行 sub-agents | `implement` 收尾，也可独立 review 分支/PR | fixed point 缺失时先问；空 diff 立即停止；两个轴不合并重排；无 Spec 时明确跳过 Spec 轴 |
| [`grill-me`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/grill-me/SKILL.md) | 用户：`/grill-me` | 无代码库的计划或设计 | 直到共享理解为止的决策树 | `grilling` | 主工程流之外的通用澄清入口 | 无状态、不写 `CONTEXT.md`；确认共享理解前不实施 |
| [`grilling`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/grilling/SKILL.md) | 模型/用户 | 待压力测试的计划、设计及用户答复 | 逐分支解决的决策与共享理解 | 代码库可查事实、用户对决策的回答 | `grill-me`、`grill-with-docs`、triage、wayfinder 的可复用原语 | 每次只问一个问题并给推荐答案；事实自行查，决策等用户答；不实施计划 |
| [`handoff`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/handoff/SKILL.md) | 用户：`/handoff` | 当前对话、下一会话目标、已有正式产物指针 | OS 临时目录中的脱敏 handoff Markdown 与 suggested skills | 对 Spec、ADR、issue、commit、diff 等既有产物的引用 | 任意阶段跨会话；prototype 支线的双向桥 | 不在原会话继续，不把已有产物全文复制一遍，不落当前 workspace，不携带敏感信息 |
| [`teach`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/teach/SKILL.md) | 用户：`/teach` | 学习主题、学习动机、现有学习记录和可信资源 | `MISSION.md`、`RESOURCES.md`、HTML lessons/reference、assets、learning records | 当前目录作为状态化教学 workspace、一手资料、用户反馈 | 独立的多会话教学流 | 课程必须服务 mission 和最近发展区；知识依赖可信资料；可复用资产不重复内联；不属于工程交付主链 |
| [`writing-great-skills`](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/writing-great-skills/SKILL.md) | 用户：`/writing-great-skills` | 待编写、修改或评估的 skill | 关于可预测调用、信息层级、拆分、裁剪和 leading words 的规范 | 同目录 `GLOSSARY.md` 及被编辑技能 | 独立参考层 | 重点是过程可预测而非输出一致；用户调用与模型调用的成本不可混淆；每个含义保持单一事实源 |

## 6. 非正式目录状态快照

固定提交中，六个目录桶的直接子目录数量如下：

| 目录桶 | 快照数量 | 含义 |
| --- | ---: | --- |
| `engineering` | 17 | 日常工程技能的维护目录；其中 16 项进入正式插件清单 |
| `productivity` | 5 | 通用工作流技能；5 项全部进入正式插件清单 |
| `misc` | 4 | 零散但可用的技能，不在正式插件清单 |
| `personal` | 2 | 与作者个人环境绑定，桶说明明确称未推广到插件 |
| `in-progress` | 7 | 正在形成中的技能，不在正式插件清单 |
| `deprecated` | 4 | 已弃用的历史技能，不在正式插件清单 |

六桶合计 39 个目录，正式插件暴露 21 个。这个差值不应被简化成“18 个都未完成”：`misc`、`personal`、`in-progress`、`deprecated` 分别表达不同状态，而插件清单才是正式暴露边界。

`skills/engineering/resolving-merge-conflicts/` 存在于 `engineering` 桶，却未出现在 `plugin.json` 的正式清单中。这个快照只能证明“目录存在、插件未暴露”；没有足够证据判断是遗漏、暂缓发布、兼容性考虑还是其他原因，因此不作原因推断。

## 7. 设计评价

### 7.1 可直接从固定源码确认的事实

1. **组合性**：调用模型把编排型 user-invoked 与可复用 model-invoked 分开；前者可以组合后者，但不能自动触发另一个 user-invoked 技能。`ask-matt` 用路由器缓解大量显式命令的记忆压力。
2. **人工决策门**：Setup 写文件前展示草稿；grilling 每次只问一个决策；`to-spec` 要确认测试 seams；`to-tickets` 要确认粒度和 blocking edges；triage 先向维护者推荐再改变状态；架构扫描先展示候选再设计。
3. **上下文卫生**：idea、grilling、Spec、tickets 尽量处于同一上下文；每张 implementation ticket 则清空上下文重新开始；跨窗口用 handoff 引用正式产物，阶段边界才考虑 compact。
4. **Issue Tracker 抽象**：Setup 用 `docs/agents/issue-tracker.md` 把 GitHub、GitLab、本地 Markdown 或其他 tracker 的物理操作隔离在配置中；Spec、tickets、triage、wayfinder 和 review 读取它。
5. **领域语言**：`CONTEXT.md` 被严格限定为 glossary；`domain-modeling` 主动挑战词义和边界，并只在三项条件同时成立时创建 ADR；工程技能读取这些文档保持命名一致。
6. **反馈环**：TDD 要求预先确认 seam、red before green 和单个垂直切片；Bug 诊断把已运行、红灯能力、确定、快速、agent 可执行的命令当作进入假设阶段的硬门；实现末尾再用双轴 review。
7. **使用成本**：user-invoked 不增加模型的 description 上下文负担，却增加人的认知负担；model-invoked 恰好相反。多会话链还要求用户理解何时发布 Spec、拆票、清上下文和重新启动 `implement`。
8. **版本漂移**：正式边界由一个固定提交的 `plugin.json` 决定，目录数量和 README 文案不能替代它；同一提交中 README 的 Issue Tracker 示例与 Setup 正文选项已经存在轻微差异。
9. **标签配置前置张力**：Setup 未安装 `triage` 时不生成标签词汇文件，但 `to-spec` 与 `to-tickets` 要求该词汇并应用 `ready-for-agent`；固定源码未定义回退行为。
10. **工具能力假设**：技能正文假设环境可能具备 Git、issue tracker CLI/原生 blocking links、并行或后台 sub-agent、浏览器或 headless browser、测试与类型检查、打开本地 HTML、临时目录等能力；各 agent 平台不一定全部等价提供。

### 7.2 分析判断

1. **组合性的优势与摩擦**：小技能加稳定产物比一套包办式流程更容易替换局部步骤，也让失败位置更可见；代价是用户必须理解调用边界。流程图若把 user-invoked 箭头画成自动调用，会制造错误预期。
2. **人工门控提升对齐但降低无人值守程度**：关键不可逆节点都让人确认，适合强调工程控制权的定位；对完全 AFK 的批处理场景，这些停点会转化为延迟。它是有意的产品取舍，而不是缺陷。
3. **上下文策略很成熟，但依赖执行纪律**：前期保留上下文、实施逐票清空的分段，能同时保护决策连续性和实现专注度；如果 tracker ticket、Spec 或 handoff 写得不够耐久，新会话会失去隐含理由。
4. **Issue Tracker 是最重要的可移植 seam 之一**：以 Markdown 配置描述平台操作，能让上层流程保持稳定；但真实平台的 blocking、child issue、assignee claim、标签权限差异很大，“Other” tracker 的自由文本质量会直接决定自动化可靠性。
5. **领域语言是跨会话压缩层**：glossary 和 ADR 不只是文档，更是在不同 agent 会话间降低解释成本的编码方式。严格禁止把实现细节塞进 `CONTEXT.md`，有助于避免它退化为第二份易过期 Spec。
6. **反馈环覆盖了正确性，但成本集中在 seam 选择**：TDD、诊断和 review 都把可执行证据放在主观判断之前；真正困难之处是找到能代表用户行为的 public seam。系统正确地把“没有好 seam”视为架构发现，而不是勉强写一个浅层测试。
7. **总体使用成本不低**：首次 Setup、领域文档、tracker 约定、逐票上下文和多个显式命令需要学习。对小改动允许 grilling 后直达 implement，是防止流程税失控的关键逃生口。
8. **版本与能力差异需要显式降级**：阅读浮动主分支会让正式技能数量和语义漂移；不支持后台 agent、原生 blocking 或本地 HTML 打开的环境也需要替代方案。专题展示应标出证据提交和能力前提，不把理想路径描述成所有平台都已实现的事实。

## 8. 对本项目的结构借鉴

对本项目的价值在信息组织和交接契约，不在照搬技能正文，也不在替换现有 `AGENTS.md`。可借鉴五点：

1. **情境路由**：在模块目录之外提供“采集异常、分析质量、Prompt 回归、API 展示、部署故障”等使用者能直接识别的入口，让入口指向已有项目文档和命令。
2. **产物契约**：为采集结果、分析结果、Reviewer 评分、数据库记录、静态站输出明确生产者、消费者、格式和生命周期，使流水线节点通过可验证产物交接。
3. **稳定性标签**：区分正式、试验中、个人/环境特定、已弃用能力；目录位置只服务维护，正式暴露由单独清单或索引控制。
4. **证据快照**：专题分析记录来源仓库、完整提交 SHA、研究日期和精确文件链接；面对上游变化时新增快照或明确更新，而不是悄悄改写历史结论。
5. **主流程与例外分离**：保持 Collector → LangGraph → Reviewer → 入库 → 静态站/API 的主链简洁，把 Bug、外部资料研究、架构维护和跨会话交接作为可回流的例外入口单独表达。

现有 `AGENTS.md` 已承担项目边界、编码规则、文档写回和验证命令的权威职责，应继续保留为约束层。上述结构可以作为它指向的导航与产物说明补充，**不建议直接替换现有 `AGENTS.md`**。

## 9. 一手资料索引

- [仓库 README](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/README.md)：安装、Setup 入口与整体定位。
- [插件清单](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/.claude-plugin/plugin.json)：21 个正式技能的唯一边界。
- [调用规则](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/.agents/invocation.md)：user-invoked 与 model-invoked 的判定和组合边界。
- [Setup](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/setup-matt-pocock-skills/SKILL.md)、[to-spec](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/to-spec/SKILL.md)、[to-tickets](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/to-tickets/SKILL.md)：标签配置前置张力的直接证据。
- 其余 18 个正式技能的逐项固定源码链接见第 5 节技能表；该表合计覆盖全部 21 个 `SKILL.md`。
