# mattpocock/skills 工作流与产物关系图

本文把 [`skills-analysis.md`](./skills-analysis.md) 的结论压缩为五张可独立阅读的关系图。所有数量与关系固定到 `mattpocock/skills` 提交 `391a2701dd948f94f56a39f7533f8eea9a859c87`；箭头表达推荐路线或实际组合关系，不表示一个 user-invoked 技能能自动调用另一个 user-invoked 技能。

## 1. 六类情境入口

`ask-matt` 根据当前工作情境推荐入口；它只负责给出路线，仍由用户显式启动下一项 user-invoked 技能。

```mermaid
flowchart LR
    New["新需求"] -->|"ask-matt 推荐"| Grill["grill-with-docs"]
    Bug["Bug"] -->|"ask-matt 推荐"| Diagnose["diagnosing-bugs"]
    External["外部 Issue / PR"] -->|"ask-matt 推荐"| Triage["triage"]
    Huge["巨大模糊工作"] -->|"ask-matt 推荐"| Wayfinder["wayfinder"]
    Architecture["架构维护"] -->|"ask-matt 推荐"| Improve["improve-codebase-architecture"]
    Study["研究"] -->|"ask-matt 推荐"| Research["research"]
```

路由按输入行一一对应：新需求进入澄清主链，Bug 先建立可执行反馈环，外部请求先分流，巨大工作先消除未知，架构维护先扫描候选，研究先产出带引用的事实材料。

## 2. Idea-to-ship 主流程

Setup 是仓库级首次前置。前期讨论、Spec 和 Tickets 尽量保留在同一未压缩上下文；进入实施后，每张 Ticket 都在干净上下文中重新启动一次 `implement`。

```mermaid
flowchart LR
    Setup["Setup<br/>首次仓库配置"] --> Grill["grill-with-docs<br/>同一 idea 会话"]
    Grill --> NeedPrototype{"有问题必须用<br/>可运行原型回答？"}

    NeedPrototype -->|"是"| Out["handoff<br/>转入原型会话"]
    Out --> Prototype["prototype<br/>抛弃式证据"]
    Prototype --> Back["handoff<br/>结论回原 idea 会话"]
    NeedPrototype -->|"否"| Size{"能否在单会话完成？"}
    Back --> Size

    Size -->|"小改动"| Start["启动 implement"]
    Size -->|"多会话工作"| Spec["to-spec<br/>同一未压缩上下文"]
    Spec --> Tickets["to-tickets<br/>声明 blocking edges"]
    Tickets --> Fresh["领取一张可执行 Ticket<br/>清理上下文"]
    Fresh --> Start

    subgraph Implement["Implement 内部执行与收尾"]
        direction LR
        Start --> Slice["内部 TDD<br/>red → green 垂直切片"]
        Slice --> Review["结束前 Code Review<br/>Standards + Spec"]
        Review --> Commit["Commit"]
    end

    Commit --> More{"还有已解锁 Ticket？"}
    More -->|"是：新会话"| Fresh
    More -->|"否"| Done["本轮交付完成"]
```

图中的 TDD 是 `implement` 内部反馈环，不是与 `implement` 平级的必经用户命令；`code-review` 也是其提交前的收尾门。二者仍可被单独调用。

## 3. User-invoked 与 Model-invoked 调用依赖

仅绘制固定源码中明确存在的组合边。左侧技能可编排右侧技能；图中没有画出的相邻主流程步骤（例如 `to-spec → to-tickets`）是用户下一步启动关系，不是自动调用依赖。

```mermaid
flowchart LR
    subgraph User["User-invoked｜必须由人类显式启动"]
        GrillDocs["grill-with-docs"]
        GrillMe["grill-me"]
        Triage["triage"]
        Wayfinder["wayfinder"]
        Improve["improve-codebase-architecture"]
        Implement["implement"]
    end

    subgraph Model["Model-invoked｜模型可自动选择，用户也可显式调用"]
        Grilling["grilling"]
        Domain["domain-modeling"]
        Design["codebase-design"]
        Prototype["prototype"]
        TDD["tdd"]
        Review["code-review"]
    end

    GrillDocs --> Grilling
    GrillDocs --> Domain
    GrillMe --> Grilling
    Triage -->|"需要补全请求时"| Grilling
    Triage -->|"需要补全请求时"| Domain
    Wayfinder --> Grilling
    Wayfinder --> Domain
    Wayfinder -->|"prototype 类型调查票"| Prototype
    Improve --> Design
    Improve --> Grilling
    Improve --> Domain
    Implement --> TDD
    Implement --> Review
```

`ask-matt` 未作为调用源画入：它只推荐 user-invoked 路线，不能替用户启动这些路线。

## 4. 稳定产物交接

这张图展示多会话主链中的持久交接物。原型、研究和 handoff 是按需证据或跨上下文桥，不取代这些正式产物。

```mermaid
flowchart LR
    Setup["setup-matt-pocock-skills"]

    subgraph Config["Setup 配置｜仓库级长期约定"]
        Tracker["docs/agents/<br/>issue-tracker.md"]
        Labels["docs/agents/<br/>triage-labels.md<br/>仅安装 triage 时"]
        DomainConfig["docs/agents/<br/>domain.md"]
    end

    subgraph Language["领域语言与决策"]
        Glossary["CONTEXT.md<br/>Glossary"]
        ADR["docs/adr/*.md<br/>达到三项门槛才创建"]
    end

    Spec["Spec issue<br/>需求基线"]
    Tickets["Tracer-bullet tickets<br/>+ blocking edges"]
    Build["Code + Tests<br/>逐票可执行行为"]
    Review["Code Review<br/>Standards + Spec 报告"]
    Commit["Commit<br/>持久版本边界"]

    Setup --> Tracker
    Setup --> Labels
    Setup --> DomainConfig
    DomainConfig --> Glossary
    DomainConfig --> ADR
    Glossary --> Spec
    ADR --> Spec
    Tracker --> Spec
    Labels --> Spec
    Spec --> Tickets
    Tracker --> Tickets
    Labels --> Tickets
    Tickets --> Build
    Glossary --> Build
    ADR --> Build
    Build --> Review
    Spec --> Review
    Tracker --> Review
    Review --> Commit
```

Spec 与 Tickets 只服务多会话工作；单会话小改可在 `grill-with-docs` 后直接实施，但仍应读取领域文档，并以 Tests、Review 和 Commit 收尾。

## 5. 正式暴露与目录状态分层

正式边界只由固定提交的 `plugin.json` 决定；目录桶是维护快照，不能用目录存在替代发布状态。

```mermaid
flowchart LR
    Snapshot["固定提交<br/>391a2701…"]

    Snapshot --> Manifest["plugin.json<br/>正式暴露 21 个"]
    Manifest --> User["User-invoked<br/>13 个"]
    Manifest --> Model["Model-invoked<br/>8 个"]

    Snapshot --> Tree["skills/ 目录快照<br/>39 个直接技能目录"]
    Tree --> Published["进入正式清单<br/>21 个"]

    Tree --> Unpublished["未正式暴露分支<br/>7 个"]
    Unpublished --> Misc["misc<br/>4 个零散可用技能"]
    Unpublished --> Personal["personal<br/>2 个个人环境技能"]
    Unpublished --> EngineeringOne["engineering<br/>1 个目录存在但未暴露<br/>不推断原因"]

    Tree --> Developing["开发中分支<br/>in-progress：7 个"]
    Tree --> Deprecated["废弃分支<br/>deprecated：4 个"]
```

`engineering`、`productivity`、`misc`、`personal`、`in-progress`、`deprecated` 六桶合计 39 个目录；其中正式清单覆盖 21 个，其余 18 个分别处于未正式暴露、开发中或废弃分支。
