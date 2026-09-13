# mattpocock/skills 能力、产物与协作关系图

本文把 [`skills-analysis.md`](./skills-analysis.md) 中的六类能力、产物生命周期和五条协作流程整理为六张关系图。内容以 `mattpocock/skills` 当前 `main` 为准；箭头表示产物交接或明确标注的内部调用；相邻用户入口需要用户分别选择。

## 1. 六类能力地图

这张图回答“25 个正式 Skill 分别解决哪类问题”。六个分组是导航视图，不代表调用顺序或上游目录结构。

```mermaid
flowchart TB
    subgraph Navigation["导航与项目配置"]
        AskMatt["ask-matt"]
        Setup["setup-matt-pocock-skills"]
    end

    subgraph Discovery["需求澄清与方案探索"]
        GrillMe["grill-me"]
        GrillDocs["grill-with-docs"]
        Grilling["grilling"]
        Prototype["prototype"]
        Questionnaire["to-questionnaire"]
    end

    subgraph Governance["请求治理与规划拆分"]
        Triage["triage"]
        Wayfinder["wayfinder"]
        ToSpec["to-spec"]
        ToTickets["to-tickets"]
    end

    subgraph Delivery["实现、测试与审查"]
        Implement["implement"]
        TDD["tdd"]
        Diagnose["diagnosing-bugs"]
        Review["code-review"]
        Resolve["resolving-merge-conflicts"]
        Wizard["wizard"]
    end

    subgraph Architecture["领域知识与架构设计"]
        Domain["domain-modeling"]
        Design["codebase-design"]
        Improve["improve-codebase-architecture"]
    end

    subgraph Knowledge["知识获取与跨会话协作"]
        Research["research"]
        Handoff["handoff"]
        Teach["teach"]
        WriteSkills["writing-for-agents"]
        WaitWhat["wait-what"]
    end
```

每个正式 Skill 在图中恰好出现一次，能力范围只帮助读者选择入口。调用方式是单项属性，未作为一级分类，也不应从节点相邻关系推断自动调用。

## 2. 产物生命周期与主要读写关系

这张图回答“协作依靠哪些持久或临时产物接续”。实线标签中的 `C/U/R` 分别表示创建、更新和读取；为保持可读性，只画正文矩阵中的主要生产与消费关系。

```mermaid
flowchart LR
    subgraph ProjectConfig["项目级配置"]
        AgentConfig["AGENTS.md / CLAUDE.md"]
        TrackerConfig["docs/agents/issue-tracker.md"]
        DomainConfig["docs/agents/domain.md"]
        LabelConfig["docs/agents/triage-labels.md"]
    end

    subgraph DomainKnowledge["长期领域知识"]
        Context["CONTEXT.md"]
        ContextMap["CONTEXT-MAP.md（可选）"]
        ADR["docs/adr/NNNN-*.md"]
    end

    subgraph Planning["工作规划产物"]
        Spec["Spec Issue"]
        Tickets["Ticket Issues"]
        LocalTickets[".scratch/&lt;feature&gt;/issues/NN-&lt;ticket&gt;.md"]
    end

    subgraph DesignResearch["设计与研究产物"]
        ResearchDoc["Research Markdown"]
        PrototypeBranch["Prototype branch"]
        ArchitectureReport["Architecture HTML report"]
    end

    subgraph Session["临时会话产物"]
        HandoffDoc["OS 临时目录/handoff-*.md"]
    end

    subgraph Verification["实现与验证产物"]
        Tests["Tests"]
        Commits["Code commits"]
        ReviewReport["Code Review report"]
    end

    Setup["setup-matt-pocock-skills"] -->|"C/U 项目配置"| AgentConfig
    Setup -->|"C/U tracker 配置"| TrackerConfig
    Setup -->|"C/U 领域配置"| DomainConfig
    Setup -->|"C/U 标签映射（安装 triage 时）"| LabelConfig
    Domain["domain-modeling"] -->|"C/U 领域词汇"| Context
    Domain -->|"C 长期决策"| ADR
    ToSpec["to-spec"] -->|"C 需求基线"| Spec
    ToTickets["to-tickets"] -->|"C 远程票据"| Tickets
    ToTickets -->|"C 本地票据"| LocalTickets
    Research["research"] -->|"C 带引用事实"| ResearchDoc
    Wayfinder["wayfinder"] -->|"委派 research 子任务"| Research
    ResearchDoc -->|"Wayfinder 场景：保存并回链"| ResearchBranch["research/name 证据分支"]
    Prototype["prototype"] -->|"C/U 可重跑原型证据"| PrototypeBranch
    Improve["improve-codebase-architecture"] -->|"C 临时报告"| ArchitectureReport
    Handoff["handoff"] -->|"C 会话桥"| HandoffDoc
    TDD["tdd / diagnosing-bugs"] -->|"C/U 行为契约"| Tests
    Implement["implement"] -->|"C 已验证版本"| Commits
    Review["code-review"] -->|"C 双轴结论"| ReviewReport

    TrackerConfig -->|"R tracker 操作"| ToSpec
    DomainConfig -->|"R 知识位置"| Domain
    LabelConfig -->|"R label vocabulary / ready-for-agent 配置"| ToSpec
    LabelConfig -->|"R label vocabulary / ready-for-agent 配置"| ToTickets
    Context -->|"R 领域语言"| ToSpec
    ADR -->|"R 决策约束"| Implement
    Spec -->|"R 拆票输入"| ToTickets
    Tickets -->|"R/U 实现任务"| Implement
    LocalTickets -->|"R/U 实现任务"| Implement
    Tests -->|"R 反馈证据"| Review
    Spec -->|"R 规格轴"| Review
    ReviewReport -->|"R 修正依据"| Implement
    HandoffDoc -->|"R 状态与正式产物指针"| NewSession["新会话"]
```

`CONTEXT-MAP.md` 没有固定创建者或更新者，因此只保留在生命周期分组中；它不是 Setup 自动生成物。Setup 仅在安装 `triage` 时创建 `triage-labels.md`，而 `to-spec`、`to-tickets` 声明需要这套 label vocabulary 和 `ready-for-agent` 配置；源代码没有定义文件缺失时的回退。Wayfinder 明确委派 Research 子任务，结果保存到研究分支并从决策任务回链；独立 research 则按仓库已有笔记约定保存。

## 3. 新功能开发与 Bug 修复

这张图并列展示两条交付路径：新功能先沉淀需求与规划，并由 `implement` 在内部驱动测试和审查；Bug 则由 `diagnosing-bugs` 自身完成反馈环、回归测试与修复，审查仅为可选质量门。所有实线边都以标签说明传递的产物。

```mermaid
flowchart LR
    subgraph Feature["新功能开发"]
        GrillDocs["grill-with-docs"] -->|"CONTEXT.md / ADR / 已确认需求"| ToSpec["to-spec"]
        ToSpec -->|"Spec"| ToTickets["to-tickets"]
        ToTickets -->|"Tickets"| SharedImplement["implement"]
        GrillDocs -.->|"可选：单会话小改的已确认需求"| SharedImplement
        SharedImplement -->|"内部驱动"| SharedTDD["tdd"]
        SharedTDD -->|"Tests + Code"| SharedImplement
        SharedImplement -->|"内部调用：固定点实现 diff"| SharedReview["code-review"]
        SharedReview -->|"Code Review report（双轴结论）"| SharedImplement
        SharedImplement -->|"修正"| Commit["Commit"]
    end

    subgraph Bugfix["Bug 修复"]
        Diagnose["diagnosing-bugs"] -->|"feedback loop / 最小复现 / 根因"| Fix["修复 Code + 合适 seam 上的回归测试"]
        Fix -.->|"可选：固定点修复 diff"| BugReview["code-review"]
        BugReview -->|"Code Review report，不产出 commit"| Fix
        Diagnose -.->|"可选：根因说明中的架构发现"| Improve["improve-codebase-architecture"]
    end
```

虚线是按范围或诊断结果选择的组合：小改可跳过正式 Spec/Tickets；Bug 修复后可选择 `code-review`，缺少正确 test seam 时也可把架构发现交给架构维护。缺少合适 seam 时记录限制并复跑原始反馈命令。Bug 路径不强制串入 `tdd` 或 `implement`，且 `code-review` 只报告固定点 diff 的双轴结论，不创建 commit。

## 4. 大型项目与外部请求治理

这张图回答两类“尚不能直接实现”的工作如何被治理：Wayfinder 消散大型项目的未知，Triage 将外部请求分流到明确状态。实线表示票据、评论、brief 或状态记录的传递，虚线只表示分析建议中的可选组合。

```mermaid
flowchart LR
    subgraph LargeProject["大型模糊项目｜Wayfinder"]
        Destination["destination"] -->|"destination / Map Issue"| Wayfinder["wayfinder"]
        Wayfinder -->|"Research 决策任务"| ResearchTicket["Research Ticket / AFK"]
        Wayfinder -->|"Prototype 决策任务"| PrototypeTicket["Prototype Ticket / HITL"]
        Wayfinder -->|"Grilling 决策任务"| GrillingTicket["Grilling Ticket / HITL"]
        Wayfinder -->|"解除决策阻塞的前置操作"| TaskTicket["Task Ticket"]
        ResearchTicket -->|"resolution comment / linked asset / decision"| Map["Map Issue：Decisions so far / frontier"]
        PrototypeTicket -->|"resolution comment / linked asset / decision"| Map
        GrillingTicket -->|"resolution comment / decision"| Map
        TaskTicket -->|"resolution comment / decision"| Map
        ResearchTicket -->|"明确委派：可并行"| Research["research 后台子任务"]
        Research -->|"Markdown / research 分支 / 证据指针"| ResearchTicket
        PrototypeTicket -->|"调用"| Prototype["prototype：可运行证据"]
        Map -->|"已确认决策与清晰路线"| ToSpec["to-spec"]
        ToSpec -->|"Spec Issue"| ToTickets["to-tickets"]
        ToTickets -->|"Ticket Issues"| ImplementLarge["implement"]
        Map -.->|"可选：缩小到单会话的明确工作"| ImplementLarge
    end

    subgraph ExternalRequest["外部请求治理｜Triage"]
        Incoming["Incoming Issue / external PR"] -->|"原始描述与现有 diff"| Triage["triage"]
        Triage -->|"Triage Notes / 补充问题"| NeedsInfo["needs-info"]
        NeedsInfo -->|"报告者回复"| NeedsTriage["needs-triage"]
        NeedsTriage -->|"更新后的请求"| Triage
        Triage -->|"Agent Brief"| ReadyAgent["ready-for-agent"]
        ReadyAgent -->|"agent-ready 请求"| ImplementExternal["implement / 继续既有 PR"]
        Triage -->|"Human Brief"| ReadyHuman["ready-for-human → 人类处理/合并"]
        Triage -->|"Close / out-of-scope record"| Wontfix["wontfix"]
    end
```

Research 是 Wayfinder 明确委派后台研究的决策任务，可并行处理；其余决策任务每会话最多解决一张。HITL 表示需要真人参与，AFK 表示 agent 可独立处理。Triage 处理外部原始请求；外部 PR 只有在 tracker 配置开启该入口时才纳入，`to-tickets` 生成的实施票据不再进入 Triage。

## 5. 架构维护与跨会话桥

这张图把架构维护的正式产物链与跨环境交接桥放在一起。架构链的实线标签写明报告、领域文档、模块设计和实现入口；handoff 只引用正式产物并传递状态，不取代任何业务流程。

```mermaid
flowchart LR
    Scope["用户指定方向或近期变更热点"] -->|"先限定扫描范围"| Improve["improve-codebase-architecture"]
    Improve -->|"Architecture HTML report"| Choose["用户选择候选"]
    Choose -->|"设计问题与证据"| Grilling["grilling"]
    Choose -->|"设计问题与证据"| Domain["domain-modeling"]
    Grilling -->|"已确认模块边界"| Design["codebase-design"]
    Domain -->|"CONTEXT.md / ADR"| Design
    Design -->|"深模块接口与 test seam"| Scale{"工作规模"}
    Scale -->|"单会话明确工作"| Implement["implement"]
    Scale -->|"多会话规划输入"| ToSpec["to-spec"]
    ToSpec -->|"Spec Issue"| ToTickets["to-tickets"]
    ToTickets -->|"Ticket Issues"| Implement

    AnySession["换工具、目录、协作者或中途分出支线"] -->|"当前状态 / 下一目标 / 正式产物指针 / 未决项"| Handoff["handoff"]
    Handoff -->|"handoff Markdown"| NewSession["新会话"]
    NewSession -->|"正式产物指针 / 下一目标"| Resume["原流程下一节点"]
```

Architecture HTML report 与 handoff Markdown 都位于 OS 临时目录，但生命周期职责不同：前者帮助用户选择架构候选，后者只做需要迁移上下文的交接。新会话读取 handoff 中的正式产物指针和下一目标后，再从原流程的下一节点继续。跨会话时应引用 Spec、ADR、Issue、commit 或 diff 等事实源，而不是把它们复制进 handoff。

## 6. 阶段边界：上下文如何继续

从上往下判断，首个适用项优先。清空和压缩是宿主会话操作，不属于正式 Skill；图中的顺序来自上游路由器，实际操作能力随宿主而异。

```mermaid
flowchart TB
    Boundary["一个阶段已经完成"] --> ContinueQ{"仍需完整推理或空间足够？"}
    ContinueQ -->|"是"| Continue["继续当前会话"]
    ContinueQ -->|"否"| ClearQ{"已有上下文与下一任务无关？"}
    ClearQ -->|"是"| Clear["清空，从自包含任务重新开始"]
    ClearQ -->|"否"| TravelQ{"要迁移工具、目录或协作者？"}
    TravelQ -->|"是"| Handoff["handoff：携带文件与事实源指针"]
    TravelQ -->|"否"| AgentQ{"任务范围明确，可独立完成？"}
    AgentQ -->|"是"| Agent["派给后台子任务"]
    AgentQ -->|"否"| Compact["压缩：明确下一阶段需要保留什么"]
```

阶段中途优先继续，或分出可独立完成的工作；中途支线需要迁移时可用 handoff。压缩意味着用摘要替代原始讨论，应在阶段边界进行。[阶段边界原文](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/ask-matt/PHASE-BOUNDARIES.md)

以上图表按 2026-09-13 核对的提交 `3cca18b368ae95cdbdebbff572ccafa662551015` 绘制。能力清单、条件性读写和调用来源见 [Skill 图鉴](skills-analysis.md)；Wayfinder 的实线研究委派见 [执行定义](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/wayfinder/SKILL.md)。
