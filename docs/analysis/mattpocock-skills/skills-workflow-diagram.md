# mattpocock/skills 能力、产物与协作关系图

本文把 [`skills-analysis.md`](./skills-analysis.md) 中已经审定的六类能力、产物生命周期和五条协作流程压缩为五张关系图。所有名称与关系固定到 `mattpocock/skills` 提交 `391a2701dd948f94f56a39f7533f8eea9a859c87`；箭头表示产物交接，不表示相邻 Skill 会自动互相调用。

## 1. 六类能力地图

这张图回答“21 个正式 Skill 分别解决哪类问题”。六个分组是导航视图，不代表调用顺序或上游目录结构。

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
        WriteSkills["writing-great-skills"]
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
    Prototype["prototype"] -->|"C/U 抛弃式证据"| PrototypeBranch
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

`CONTEXT-MAP.md` 没有固定创建者或更新者，因此只保留在生命周期分组中；它不是 Setup 自动生成物。Setup 仅在安装 `triage` 时创建 `triage-labels.md`，而 `to-spec`、`to-tickets` 声明需要这套 label vocabulary 和 `ready-for-agent` 配置；固定源码没有定义文件缺失时的回退。Research Markdown 与 Wayfinder Research Ticket 没有固定 C/U/R 关系，二者若组合只能作为可选路线。

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
        Diagnose["diagnosing-bugs"] -->|"feedback loop / 最小复现 / 根因"| Fix["Regression Test + 修复 Code"]
        Fix -.->|"可选：固定点修复 diff"| BugReview["code-review"]
        BugReview -->|"Code Review report，不产出 commit"| Fix
        Diagnose -.->|"可选：post-mortem 中的架构发现"| Improve["improve-codebase-architecture"]
    end
```

虚线是按范围或诊断结果选择的组合：小改可跳过正式 Spec/Tickets；Bug 修复后可选择 `code-review`，缺少正确 test seam 时也可把架构发现交给架构维护。Bug 路径不串入 `tdd` 或 `implement`，且 `code-review` 只报告固定点 diff 的双轴结论，不创建 commit。

## 4. 大型项目与外部请求治理

这张图回答两类“尚不能直接实现”的工作如何被治理：Wayfinder 消散大型项目的未知，Triage 将外部请求分流到明确状态。实线表示票据、评论、brief 或状态记录的传递，虚线只表示分析建议中的可选组合。

```mermaid
flowchart LR
    subgraph LargeProject["大型模糊项目｜Wayfinder"]
        Destination["destination"] -->|"destination / Map Issue"| Wayfinder["wayfinder"]
        Wayfinder -->|"Research Ticket"| ResearchTicket["Research Ticket"]
        Wayfinder -->|"Prototype Ticket"| PrototypeTicket["Prototype Ticket"]
        Wayfinder -->|"Grilling Ticket"| GrillingTicket["Grilling Ticket"]
        Wayfinder -->|"Task Ticket"| TaskTicket["Task Ticket"]
        ResearchTicket -->|"resolution comment / linked asset / decision"| Map["Map Issue：Decisions so far / frontier"]
        PrototypeTicket -->|"resolution comment / linked asset / decision"| Map
        GrillingTicket -->|"resolution comment / decision"| Map
        TaskTicket -->|"resolution comment / decision"| Map
        ResearchTicket -.->|"可选组合：研究问题"| Research["research → Research Markdown"]
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

Research Ticket 是 Wayfinder 的票据类型，图中没有把它画成对 `/research` 的固定调用；通往 `research` 的虚线明确是可选路线。Triage 处理外部原始 Issue/PR，`to-tickets` 生成的规划票据不再进入 Triage。

## 5. 架构维护与跨会话桥

这张图把架构维护的正式产物链与通用跨会话桥放在一起。架构链的实线标签写明报告、领域文档、模块设计和实现入口；handoff 只引用正式产物并传递状态，不取代任何业务流程。

```mermaid
flowchart LR
    Improve["improve-codebase-architecture"] -->|"Architecture HTML report"| Choose["用户选择候选"]
    Choose -->|"设计问题与证据"| Grilling["grilling"]
    Choose -->|"设计问题与证据"| Domain["domain-modeling"]
    Grilling -->|"已确认模块边界"| Design["codebase-design"]
    Domain -->|"CONTEXT.md / ADR"| Design
    Design -->|"深模块接口与 test seam"| Scale{"工作规模"}
    Scale -->|"单会话明确工作"| Implement["implement"]
    Scale -->|"多会话规划输入"| ToSpec["to-spec"]
    ToSpec -->|"Spec Issue"| ToTickets["to-tickets"]
    ToTickets -->|"Ticket Issues"| Implement

    AnySession["任意流程中的当前会话"] -->|"当前状态 / 下一目标 / 正式产物指针 / 未决项"| Handoff["handoff"]
    Handoff -->|"handoff Markdown"| NewSession["新会话"]
    NewSession -->|"正式产物指针 / 下一目标"| Resume["原流程下一节点"]
```

Architecture HTML report 与 handoff Markdown 都位于 OS 临时目录，但生命周期职责不同：前者帮助用户选择架构候选，后者只做会话间桥接。新会话读取 handoff 中的正式产物指针和下一目标后，再从原流程的下一节点继续。跨会话时应引用 Spec、ADR、Issue、commit 或 diff 等事实源，而不是把它们复制进 handoff。
