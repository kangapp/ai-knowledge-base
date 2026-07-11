# mattpocock/skills：Skill 与产物说明书

本文以 `mattpocock/skills` 当前 `main` 为准。正式 Skill 以 `.claude-plugin/plugin.json` 为边界；核对日期与提交哈希只用于让读者验证资料来源。

## 1. 快速认识

这套仓库把工程工作拆成 **21 个正式 Skill、6 类能力**。推荐阅读顺序是：先用能力地图找到 Skill，再查单项输入输出，然后看产物如何被创建、更新和读取，最后沿五条流程理解协作。

- **Skill 是过程单元**：接收对话、代码、Issue、文件或配置，执行一套可复用纪律。
- **产物是协作契约**：文件、Issue、分支、测试、提交或报告让不同 Skill 和会话接续工作。
- **调用方式只是属性**：13 个 user-invoked Skill 只能由人显式输入；8 个 model-invoked Skill 可由模型自动选择，也可由人输入。
- **目录只是维护视图**：`engineering`、`productivity` 等物理目录不作为本文的一级能力分类。

## 2. 六类能力地图

| 能力类型 | 正式 Skill | 能力范围 |
| --- | --- | --- |
| 导航与项目配置 | `ask-matt`、`setup-matt-pocock-skills` | 选择合适入口，建立 Issue Tracker、标签与领域文档配置 |
| 需求澄清与方案探索 | `grill-me`、`grill-with-docs`、`grilling`、`prototype` | 澄清模糊需求，以对话或可运行原型回答设计问题 |
| 请求治理与规划拆分 | `triage`、`wayfinder`、`to-spec`、`to-tickets` | 治理外部请求，探索大型工作，形成 Spec 与 Tickets |
| 实现、测试与审查 | `implement`、`tdd`、`diagnosing-bugs`、`code-review` | 实现代码，建立反馈环，诊断问题，检查规格与质量 |
| 领域知识与架构设计 | `domain-modeling`、`codebase-design`、`improve-codebase-architecture` | 维护领域语言，设计深模块，发现架构改进机会 |
| 知识获取与跨会话协作 | `research`、`handoff`、`teach`、`writing-great-skills` | 调研、跨会话传递、持续教学与 Skill 编写方法 |

上表中 21 个 Skill 各出现一次；能力范围只用于导航，不表示自动调用链。

## 3. 21 个正式 Skill 图鉴

“输出”指 Skill 结束时交付的正式结果；“中间产物”指过程中创建、更新或传递、可供后续继续使用的信息载体。

### `ask-matt`

- **核心作用**：按当前情境推荐 Skill 或流程；**适用场景**：不确定从哪个入口开始；**调用方式**：用户显式 `/ask-matt`。
- **输入**：当前问题、代码库有无、工作规模；**执行动作**：区分主流程、入口、维护与独立工具并给出路线；**输出**：推荐路线。
- **中间产物**：无；**依赖**：仓库 Skill 与调用规则知识；**协作关系**：位于所有流程之前，指向 Setup 或具体入口；**使用边界**：只路由，不执行另一个 user-invoked Skill。
- **源代码**：[ask-matt](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/ask-matt/SKILL.md)

### `setup-matt-pocock-skills`

- **核心作用**：为工程 Skill 建立仓库级配置；**适用场景**：每个仓库首次使用工程流程；**调用方式**：用户显式 `/setup-matt-pocock-skills`。
- **输入**：remote、仓库结构、现有 agent/domain 文件、已安装 Skill 与用户选择；**执行动作**：探测、展示草稿、逐节确认后写入；**输出**：可被工程 Skill 消费的项目配置。
- **中间产物**：`AGENTS.md`/`CLAUDE.md` 配置块及 `docs/agents/*.md` 草稿；**依赖**：Git/文件探测与用户确认；**协作关系**：为 `triage`、`wayfinder`、`to-spec`、`to-tickets`、领域相关 Skill 提供前置；**使用边界**：不同时新建两种 agent 文件，未安装 `triage` 时跳过标签配置。
- **源代码**：[setup-matt-pocock-skills](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/setup-matt-pocock-skills/SKILL.md)

### `grill-me`

- **核心作用**：用持续访谈澄清通用计划或设计；**适用场景**：没有代码库的方案讨论；**调用方式**：用户显式 `/grill-me`。
- **输入**：计划、设计与逐题回答；**执行动作**：运行 `grilling`；**输出**：共享理解与已解决决策树。
- **中间产物**：对话中的问题与答案；**依赖**：`grilling`；**协作关系**：通用澄清入口；**使用边界**：无状态，不写领域文档，确认前不实施。
- **源代码**：[grill-me](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/grill-me/SKILL.md)

### `grill-with-docs`

- **核心作用**：澄清工程计划并同步固化领域语言和决策；**适用场景**：有代码库的功能或架构讨论；**调用方式**：用户显式 `/grill-with-docs`。
- **输入**：计划、代码事实、领域文档与用户决策；**执行动作**：组合 `grilling` 和 `domain-modeling`；**输出**：共享理解、更新后的领域文档。
- **中间产物**：`CONTEXT.md`、必要 ADR、对话决策；**依赖**：`grilling`、`domain-modeling`；**协作关系**：新功能主链起点，可交给 `to-spec` 或小改的 `implement`；**使用边界**：负责澄清与记录，不实施计划。
- **源代码**：[grill-with-docs](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/grill-with-docs/SKILL.md)

### `grilling`

- **核心作用**：逐分支、逐问题压力测试计划；**适用场景**：需要消除设计分歧或未决项；**调用方式**：模型自动或用户显式。
- **输入**：计划、可查事实和用户回答；**执行动作**：事实自行查证，决策每次只问一题并给推荐答案；**输出**：共享理解。
- **中间产物**：对话中的决策树；**依赖**：用户参与和可访问代码库；**协作关系**：被 `grill-me`、`grill-with-docs`、`triage`、`wayfinder` 等复用；**使用边界**：不替用户作决策，不实施计划。
- **源代码**：[grilling](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/grilling/SKILL.md)

### `prototype`

- **核心作用**：用抛弃式可运行代码回答一个设计问题；**适用场景**：状态/逻辑需 CLI 验证，或 UI 必须看见多个差异方案；**调用方式**：模型自动或用户显式。
- **输入**：单一设计问题与现有项目约定；**执行动作**：建立隔离分支，做最小 CLI 或同一路由多种 UI，记录结论；**输出**：可运行原型与已验证决策。
- **中间产物**：Prototype branch、问题/答案和返回原线程的 context pointer；**依赖**：项目运行方式、路由与 Git；**协作关系**：由 grilling 支线进入，结论回到原想法/Spec；**使用边界**：代码从第一天即抛弃，默认不做持久化、测试、抽象或 polish。
- **源代码**：[prototype](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/prototype/SKILL.md)

### `triage`

- **核心作用**：把外部 Issue/PR 推进到明确类别与状态；**适用场景**：维护者处理未经治理的请求；**调用方式**：用户显式 `/triage`。
- **输入**：外部 Issue/PR、tracker 状态、标签映射和维护者指示；**执行动作**：分类、验证、补问、写 notes/brief，经人确认后变更状态；**输出**：`needs-info`、`ready-for-agent`、`ready-for-human` 或 `wontfix` 结果。
- **中间产物**：Triage Notes、Agent/Human Brief、标签和评论；**依赖**：Issue Tracker、Triage Labels，必要时 `grilling`/`domain-modeling`；**协作关系**：agent-ready 请求交给 `implement`；**使用边界**：仅治理外来原始请求，`to-tickets` 产出的票不再 triage，所有发布内容带 AI 声明。
- **源代码**：[triage](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/triage/SKILL.md)

### `wayfinder`

- **核心作用**：把超大模糊工作变成共享决策地图；**适用场景**：目的地已知但单会话看不清路线；**调用方式**：用户显式 `/wayfinder`。
- **输入**：destination、tracker 配置、领域知识和用户决策；**执行动作**：创建 Map 与子票、连接阻塞边、每会话认领并解决至多一票、更新 frontier；**输出**：逐步消散 fog of war 的决策地图。
- **中间产物**：Map Issue、Research/Prototype/Grilling/Task Tickets、resolution comments、Decisions so far；**依赖**：Issue Tracker、`grilling`、`domain-modeling`；**协作关系**：路线清晰后交给 `to-spec` 或小范围 `implement`；**使用边界**：默认产出决策而非目的地交付物；Research Ticket 是票据类型，不等于源码明确调用 `research`，二者组合只能标作可选路线。
- **源代码**：[wayfinder](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/wayfinder/SKILL.md)

### `to-spec`

- **核心作用**：把已经讨论清楚的内容综合成可执行 Spec；**适用场景**：多会话工作进入正式规划；**调用方式**：用户显式 `/to-spec`。
- **输入**：当前完整对话、代码库理解和领域文档；**执行动作**：综合目标、范围、行为与测试 seams，确认后发布；**输出**：带 `ready-for-agent` 的 Spec Issue。
- **中间产物**：Spec 草稿与 seam 确认；**依赖**：Issue Tracker、Triage Labels、领域术语；**协作关系**：承接 grilling/wayfinder，交给 `to-tickets`；**使用边界**：不重新访谈，通常不写具体实现文件或代码。
- **源代码**：[to-spec](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/to-spec/SKILL.md)

### `to-tickets`

- **核心作用**：把计划拆成单会话 tracer-bullet tickets；**适用场景**：Spec 或计划需分阶段实现；**调用方式**：用户显式 `/to-tickets`。
- **输入**：Spec、plan、issue 或当前讨论；**执行动作**：设计端到端切片、确认粒度与 blocking edges、发布到 tracker；**输出**：带依赖关系和 `ready-for-agent` 的 Ticket Issues。
- **中间产物**：票据草稿；本地 tracker 为 `.scratch/<feature>/issues/NN-<ticket>.md`；**依赖**：Issue Tracker、Triage Labels 与阻塞能力；**协作关系**：每票由新的 `implement` 会话消费；**使用边界**：不修改/关闭 parent，wide refactor 用 expand-contract，发布前必须经用户确认。
- **源代码**：[to-tickets](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/to-tickets/SKILL.md)

### `implement`

- **核心作用**：完成一张明确票据并以测试、审查和提交收尾；**适用场景**：Spec/Ticket 已足够可执行；**调用方式**：用户显式 `/implement`。
- **输入**：Ticket、Spec 或明确工作说明；**执行动作**：理解范围，在确认 seam 上驱动 `tdd`，运行反馈命令，以 `code-review` 收尾并提交；**输出**：已验证实现和 Code commit。
- **中间产物**：Tests、Code、测试输出、Code Review report；**依赖**：`tdd`、`code-review`、项目测试/类型检查；**协作关系**：承接 agent-ready 工作，逐票完成主链；**使用边界**：不得跳过预定 seam、完整测试或提交前双轴审查。
- **源代码**：[implement](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/implement/SKILL.md)

### `tdd`

- **核心作用**：以 red-green-refactor 垂直切片实现外部行为；**适用场景**：功能或修复有已确认 public seam；**调用方式**：模型自动或用户显式。
- **输入**：一个行为、确认过的 seam、领域文档；**执行动作**：先写一个失败测试，再写最小实现使其通过并重复；**输出**：通过的行为切片。
- **中间产物**：失败后转绿并保留的 Tests 与 Code；**依赖**：测试工具、`CONTEXT.md`/ADR；**协作关系**：由 `implement` 驱动，也可独立使用；**使用边界**：不测试实现细节、不横向批量铺测试、不在未确认 seam 上开始。
- **源代码**：[tdd](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/tdd/SKILL.md)

### `diagnosing-bugs`

- **核心作用**：用紧反馈环诊断困难 Bug/性能回归并验证修复；**适用场景**：错误、失败、变慢、间歇性问题；**调用方式**：模型自动或用户显式。
- **输入**：用户精确症状、环境、代码与历史状态；**执行动作**：建立 red-capable 命令、复现并最小化、排序可证伪假设、单变量探测、先回归测试后修复、清理复盘；**输出**：根因、已验证修复与 post-mortem。
- **中间产物**：最小复现、反馈命令、临时 instrumentation、Regression Test；**依赖**：可运行环境、`CONTEXT.md`/ADR；**协作关系**：修复后交给 review/commit，无正确 seam 时把发现交给架构维护；**使用边界**：没有已运行且捕获精确症状的紧红灯命令，不进入假设阶段。
- **源代码**：[diagnosing-bugs](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/diagnosing-bugs/SKILL.md)

### `code-review`

- **核心作用**：从固定点对 diff 做 Standards 与 Spec 双轴审查；**适用场景**：实现收尾或独立检查分支/PR；**调用方式**：模型自动或用户显式。
- **输入**：可解析 fixed point、`HEAD` diff、仓库 standards 与可选 Spec；**执行动作**：两个独立并行审查分别核对标准/气味和规格忠实度；**输出**：并排的双轴 Code Review report。
- **中间产物**：两个 sub-agent 报告；**依赖**：Git、Issue Tracker/Spec、标准文件与并行 agent 能力；**协作关系**：`implement` 提交前质量门；**使用边界**：缺 fixed point 先问、空 diff 停止、无 Spec 明示跳过该轴、两轴不合并重排。
- **源代码**：[code-review](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/code-review/SKILL.md)

### `domain-modeling`

- **核心作用**：建立并持续校准项目统一领域语言；**适用场景**：术语模糊、重载、边界冲突或决策需要固化；**调用方式**：模型自动或用户显式。
- **输入**：领域术语、边界场景、代码事实和用户决策；**执行动作**：挑战定义、用反例压力测试、即时更新 glossary，达到门槛才写 ADR；**输出**：清晰领域模型。
- **中间产物**：`CONTEXT.md`、可选 `CONTEXT-MAP.md`、`docs/adr/NNNN-*.md`；**依赖**：`docs/agents/domain.md` 与用户裁决；**协作关系**：贯穿 grilling、triage、wayfinder、架构工作；**使用边界**：仅被动读取 glossary 不算调用；`CONTEXT.md` 不放实现细节；ADR 必须同时具备难逆、意外和真实权衡。
- **源代码**：[domain-modeling](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/domain-modeling/SKILL.md)

### `codebase-design`

- **核心作用**：提供 deep module、interface 与 seam 的统一设计纪律；**适用场景**：模块边界、抽象、adapter 或可测试性设计；**调用方式**：模型自动或用户显式。
- **输入**：调用关系、行为、变化轴与候选接口；**执行动作**：以 module/interface/depth/seam/adapter/leverage/locality 评价设计，必要时 design-it-twice；**输出**：深模块接口与测试 seam 设计。
- **中间产物**：候选接口、边界方案与比较；**依赖**：现有代码事实；**协作关系**：为 `tdd` 和架构扫描提供词汇，选定设计回主开发流程；**使用边界**：只有一个 adapter 时不凭空制造 seam，不把浅包装当深模块。
- **源代码**：[codebase-design](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/codebase-design/SKILL.md)

### `improve-codebase-architecture`

- **核心作用**：扫描代码库并可视化 deepening opportunities；**适用场景**：周期性架构维护或缺少测试 seam；**调用方式**：用户显式 `/improve-codebase-architecture`。
- **输入**：代码库、`CONTEXT.md`、相关 ADR；**执行动作**：用 `codebase-design` 词汇探索候选，生成 HTML，由用户选择后 grilling；**输出**：Architecture HTML report 与选定架构问题。
- **中间产物**：OS 临时目录中的报告、候选列表与设计对话；**依赖**：`codebase-design`、代码探索、`grilling`/`domain-modeling`；**协作关系**：选题后经领域/边界澄清回主开发流程；**使用边界**：扫描时不先定具体 interface，报告不落仓库，不绕过 ADR 冲突。
- **源代码**：[improve-codebase-architecture](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/improve-codebase-architecture/SKILL.md)

### `research`

- **核心作用**：针对一个问题查阅高信任一手资料并固化引用；**适用场景**：决策前需要外部事实；**调用方式**：模型自动或用户显式。
- **输入**：清晰研究问题、仓库笔记约定；**执行动作**：后台 agent 搜索、筛选 primary sources、逐项引用并写文件；**输出**：仓库内单一 Research Markdown。
- **中间产物**：来源列表、检索笔记和引用；**依赖**：后台 agent、网络/资料访问；**协作关系**：结果可带入 `grill-with-docs` 或其他决策会话；**使用边界**：只做事实调研，不以二手摘要替代一手来源，不代替决策或实现；与 Wayfinder Research Ticket 的结合不是固定调用事实。
- **源代码**：[research](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/engineering/research/SKILL.md)

### `handoff`

- **核心作用**：把当前会话压缩成新会话可接续的文档；**适用场景**：上下文将满、需要分支或换会话；**调用方式**：用户显式 `/handoff`。
- **输入**：当前对话、下一会话目标和正式产物指针；**执行动作**：总结、引用既有产物、建议 Skill、脱敏并写入临时目录；**输出**：handoff Markdown。
- **中间产物**：无；**依赖**：OS 临时目录与现有 Spec/ADR/Issue/commit/diff 指针；**协作关系**：任意流程、任意节点到新会话的桥；**使用边界**：不在原会话继续，不复制已有正式产物，不写当前 workspace，不携带敏感信息。
- **源代码**：[handoff](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/handoff/SKILL.md)

### `teach`

- **核心作用**：在当前目录维护多会话教学工作区；**适用场景**：持续学习一个概念或技能；**调用方式**：用户显式 `/teach`。
- **输入**：主题、mission、学习记录、可信资源与反馈；**执行动作**：确定最近发展区，制作短 lesson、reference、练习和学习记录；**输出**：状态化教学工作区与 HTML lessons。
- **中间产物**：`MISSION.md`、`RESOURCES.md`、`NOTES.md`、`lessons/`、`reference/`、`assets/`、`learning-records/`；**依赖**：当前目录、一手资源和用户反馈；**协作关系**：独立多会话教学流；**使用边界**：每课服务 mission，mission 变更先确认，不属于工程交付链。
- **源代码**：[teach](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/teach/SKILL.md)

### `writing-great-skills`

- **核心作用**：提供可预测 Skill 的编写与裁剪规范；**适用场景**：编写、修改或评估 Skill；**调用方式**：用户显式 `/writing-great-skills`。
- **输入**：待处理 Skill 与调用需求；**执行动作**：检查 invocation、description、信息层级、拆分、单一事实源、leading words 与 failure modes；**输出**：Skill 设计/编辑规范或改进结论。
- **中间产物**：被编辑 Skill 与检查笔记；**依赖**：同目录 `GLOSSARY.md`；**协作关系**：独立参考能力；**使用边界**：追求过程可预测，不承诺输出逐字一致，不混淆 context load 与 cognitive load。
- **源代码**：[writing-great-skills](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/productivity/writing-great-skills/SKILL.md)

## 4. 文件与产物图鉴

### 4.1 生命周期目录树

```text
项目级配置
├── AGENTS.md / CLAUDE.md
└── docs/agents/{issue-tracker.md,domain.md,triage-labels.md}
长期领域知识
├── CONTEXT.md
├── CONTEXT-MAP.md
└── docs/adr/NNNN-*.md
工作规划产物
├── Spec Issue
├── Ticket Issues
└── .scratch/<feature>/issues/NN-<ticket>.md
设计与研究产物
├── Research Markdown
├── Prototype branch
└── Architecture HTML report
临时会话产物
└── OS 临时目录/handoff-*.md
实现与验证产物
├── Tests
├── Code commits
└── Code Review report
```

### 4.2 项目级配置

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| `AGENTS.md` / `CLAUDE.md` | 仓库根目录，二选一或更新既有文件 | `setup-matt-pocock-skills`（若两者皆无，由用户选择） | `setup-matt-pocock-skills` | 工程 Skill/agent | `## Agent skills` 配置块，指向 tracker 与 domain 配置 | 仓库级长期；让 agent 知道配置入口 |
| `docs/agents/issue-tracker.md` | 仓库内固定路径 | `setup-matt-pocock-skills` | `setup-matt-pocock-skills`（重新配置时） | `to-spec`、`to-tickets`、`triage`、`wayfinder`、`code-review` | tracker 类型；创建/读取/更新/关闭 Issue；标签、子票、阻塞、查询与 Wayfinding 操作 | 仓库级长期；隔离平台差异 |
| `docs/agents/domain.md` | 仓库内固定路径 | `setup-matt-pocock-skills` | `setup-matt-pocock-skills`（布局调整时） | 读取或维护领域文档的工程 Skill | single/multi-context 布局、上下文路径、ADR 路径与消费规则 | 仓库级长期；定位领域知识 |
| `docs/agents/triage-labels.md` | 仓库内固定路径；仅安装 `triage` 时创建 | `setup-matt-pocock-skills` | `setup-matt-pocock-skills`（映射调整时） | `triage`、`to-spec`、`to-tickets` | category/state 角色到真实 label 的映射 | 仓库级长期；统一请求状态词汇 |

### 4.3 长期领域知识

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| `CONTEXT.md` | 单上下文项目根目录，或各上下文根 | `domain-modeling`（常由组合流程驱动） | `domain-modeling` | grilling、规划、实现、TDD、诊断、审查、架构扫描 | 严格的领域 glossary：术语、定义、边界与关系 | 长期且持续演化；跨会话压缩统一语言，不承载实现细节或 Spec |
| `CONTEXT-MAP.md` | 大型多包项目根目录，可选；Setup 只配置其位置 | 无固定创建者 | 无固定更新者 | 需要选择上下文的工程 Skill | 子上下文名称、范围与对应 `CONTEXT.md` 指针 | 长期；多上下文导航，普通仓库不使用 |
| `docs/adr/NNNN-*.md` | `docs/adr/` 或 domain 配置指定位置 | `domain-modeling` | 无固定更新者 | 后续领域建模、规划、实现、诊断、审查与架构工作 | 编号/标题、上下文、决策、备选与后果 | 长期不可变记录；仅在难逆、缺上下文会意外且存在真实权衡时创建 |

### 4.4 工作规划产物

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| Spec Issue | 配置的 Issue Tracker | `to-spec` | 无固定更新者 | `to-tickets`、`implement`、`code-review` | 背景/目标、范围与非目标、行为、领域词汇、模块/seams、验收与测试策略 | 阶段性需求基线；将完整对话压缩成 agent-ready 规格 |
| Ticket Issues | 真实 tracker 的子/关联 Issue | `to-tickets` | 无固定更新者 | 独立 `implement` 会话、frontier 查询 | 单会话 tracer bullet、验收、上下文、测试 seam、blocking edges、parent 指针 | 阶段性；阻塞解除后可领取，完成后关闭 |
| `.scratch/<feature>/issues/NN-<ticket>.md` | 本地 Markdown tracker | `to-tickets` | 无固定更新者 | 独立 `implement` 会话、人工 blockers-first 调度 | 与 Ticket Issue 等价的正文，加文本化依赖与状态 | 阶段性；本地 tracker 的逐票实体，功能完成后可清理 |

### 4.5 设计、研究与跨会话产物

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| Research Markdown | 仓库内，按既有研究/笔记约定选择文件名 | `research` | 无固定更新者 | grilling 或其他决策会话 | 研究问题、结论、逐项 primary-source 引用与来源链接 | 阶段性事实快照；提供证据，不替代决策 |
| Prototype branch | Git 的隔离抛弃式分支 | `prototype` | `prototype` | 原 idea/Spec/implementation 会话 | 可运行 CLI 或同一路由 UI 变体、问题/答案、分支指针 | 临时；保留决策证据，代码不合入主分支 |
| Architecture HTML report | OS 临时目录中的 HTML | `improve-codebase-architecture` | 无固定更新者 | 用户、后续 grilling/架构设计 | 候选 deepening opportunity、before/after 视觉、证据、收益与 ADR 冲突提示 | 一次性临时报告；帮助选题，不作为仓库长期文档 |
| handoff Markdown | OS 临时目录，通常 `handoff-*.md` | `handoff` | 无固定更新者 | 新会话 | 当前状态、下一目标、未决项、正式产物指针、suggested skills；敏感信息已脱敏 | 临时跨会话桥；引用而不复制事实源 |

### 4.6 实现与验证产物

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| Tests | 项目既有测试目录 | `tdd`、`diagnosing-bugs` | `tdd`、`implement` | 实现反馈环、`code-review`、CI、未来回归 | 从 public seam 表达外部行为；诊断时包含最小回归场景 | 长期可执行契约；先红后绿证明行为 |
| Code commits | Git 历史 | `implement` | 无固定更新者 | 后续 Ticket/PR/review/发布 | 聚焦实现 diff、测试与说明；固定 SHA/父提交形成边界 | 长期版本记录；测试和双轴 review 后产生 |
| Code Review report | 当前会话/agent 输出 | `code-review` | 无固定更新者 | 实现者和人类审阅者 | Standards report 与 Spec report 并排，各自含按严重度定位的发现；无 Spec 时注明跳过 | 阶段性一次性质量门；不改写成单一混合排序 |

## 5. Skill × 产物矩阵

只列源代码能直接支持的关系；空白表示没有明确的创建、更新或读取关系，而不是证明 Skill 永远不会接触该产物。

| Skill | AGENTS.md / CLAUDE.md | docs/agents/issue-tracker.md | docs/agents/domain.md | docs/agents/triage-labels.md | CONTEXT.md | CONTEXT-MAP.md | docs/adr/NNNN-*.md | Spec Issue | Ticket Issues | .scratch/&lt;feature&gt;/issues/NN-&lt;ticket&gt;.md | Research Markdown | Prototype branch | Architecture HTML report | handoff Markdown | Tests | Code commits | Code Review report |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ask-matt` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `setup-matt-pocock-skills` | C/U | C/U | C/U | C/U | R | R | R |  |  |  |  |  |  |  |  |  |  |
| `grill-me` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `grill-with-docs` |  |  | R |  | C/U/R | R | C/R |  |  |  |  |  |  |  |  |  |  |
| `grilling` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `prototype` |  |  |  |  |  |  |  |  | U |  |  | C/U |  |  |  |  |  |
| `triage` |  | R | R | R | U/R | R | C/R |  |  |  |  |  |  |  |  | R |  |
| `wayfinder` |  | R | R |  | U/R | R | C/R |  | C/U/R |  |  |  |  |  |  |  |  |
| `to-spec` |  | R | R | R | R | R | R | C |  |  |  | R |  |  |  |  |  |
| `to-tickets` |  | R | R | R | R | R |  | R | C | C |  |  |  |  |  |  |  |
| `implement` | R | R | R | R | R | R | R | R | R/U | R/U |  |  |  |  | C/U/R | C | R |
| `tdd` |  |  |  |  | R | R | R |  |  |  |  |  |  |  | C/U/R |  |  |
| `diagnosing-bugs` |  |  |  |  | R | R | R |  |  |  |  |  |  |  | C/U/R | R |  |
| `code-review` | R | R | R | R | R | R | R | R | R | R |  |  |  |  | R | R | C |
| `domain-modeling` |  |  | R |  | C/U/R | R | C/R |  |  |  |  |  |  |  | R | R |  |
| `codebase-design` |  |  |  |  | R | R | R |  |  |  |  |  |  |  | R | R |  |
| `improve-codebase-architecture` |  |  |  |  | R | R | R |  |  |  |  |  | C |  | R | R |  |
| `research` |  |  |  |  |  |  |  |  |  |  | C |  |  |  |  |  |  |
| `handoff` |  |  |  |  |  |  | R | R | R | R |  |  |  | C | R | R |  |
| `teach` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| `writing-great-skills` |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |

图例：`C` = Create（创建），`U` = Update（更新），`R` = Read（读取）。同一格可包含多种关系。

证据边界：矩阵不把流程建议自动升级为调用事实。例如 Wayfinder 的 Research Ticket 会创建“linked Markdown summary”，但源码没有明确规定它调用 `research`，因此 `wayfinder × Research Markdown` 留空；若实践中组合两者，应标注为可选路线。`to-spec` 也没有固定读取 Research Markdown，研究结果只有进入当前对话后才可能成为可选输入。`prototype × Tickets` 的 `U` 只表示源码要求把原型分支指针和结论写回 implementation issue，不表示读取或处理 `to-tickets` 产出的规划票。`handoff` 明确读取/引用 ADR、Spec、Issue/Ticket、commit/diff，但不会更新它们。Triage 对领域文档/ADR 的创建更新来自其主动领域建模分支，而非每次 triage 都发生；其处理的是外部原始 Issue/PR，不是本矩阵的规划 Tickets。

## 6. 五条协作流程与跨会话桥

箭头两侧都是人工可识别的交接；两个 user-invoked Skill 相邻不代表前者能自动调用后者。

### 6.1 新功能开发

1. `grill-with-docs` → `CONTEXT.md` / ADR / 已确认需求 → `to-spec`（小型单会话改动可直接交给 `implement`）。
2. `to-spec` → Spec → `to-tickets`。
3. `to-tickets` → Tickets → 每票新的 `implement` 会话。
4. `implement` 内部驱动 `tdd` → Tests + Code。
5. `implement` 内部调用 `code-review` → Code Review report（从固定点对实现 diff 做 Standards / Spec 双轴审查）。
6. `implement` 按审查结论修正 → Commit。

### 6.2 Bug 修复

1. `diagnosing-bugs` → feedback loop / 最小复现 / 根因。
2. `diagnosing-bugs` → Regression Test + 修复 Code。
3. 可选 `code-review`（固定点 diff 双轴审查）→ Code Review report；它不产出 commit。
4. 若没有正确 test seam：`diagnosing-bugs` → post-mortem 中的架构发现 → `improve-codebase-architecture`，但先完成可验证修复。

### 6.3 大型模糊项目

1. `wayfinder` → destination / Map Issue → Research、Prototype、Grilling 或 Task Tickets。
2. 一张 frontier Ticket → resolution comment / linked asset / decision → Map Issue 的 Decisions so far 与新 frontier。
3. Map 完成 → 已确认决策与清晰路线 → `to-spec`（范围已缩小到单会话时可到 `implement`）。
4. `to-spec` → Spec Issue → `to-tickets` → Ticket Issues → `implement`。

Research Ticket 是 Wayfinder 的票据类型；将它交给 `research` 产出 Research Markdown 是合理的**可选组合建议**，不是源代码规定的自动调用。

### 6.4 外部请求治理

1. Incoming Issue / external PR → 原始描述与现有 diff → `triage`。
2. `triage` → Triage Notes / 补充问题 → `needs-info`，报告者回复后回到 `needs-triage`。
3. `triage` → Agent Brief → `ready-for-agent` → `implement` 或对既有 PR 继续处理。
4. `triage` → Human Brief → `ready-for-human` → 人类处理/合并。
5. `triage` → Close / out-of-scope record → `wontfix`。

### 6.5 架构维护

1. `improve-codebase-architecture` → Architecture HTML report → 用户选择候选。
2. 选中候选 → 设计问题与证据 → `grilling` + `domain-modeling`。
3. `grilling` + `domain-modeling` → 已确认模块边界 / `CONTEXT.md` / ADR → `codebase-design`。
4. `codebase-design` → 深模块接口与 test seam → 按规模回到 `implement` 或 `to-spec → to-tickets → implement`。

### 6.6 跨会话桥

`handoff` 不构成第六条业务流程，而是任意流程可用的桥：

```text
任意会话 → handoff Markdown（状态、指针、未决项、suggested skills）→ 新会话
```

它也可为 prototype 支线做双向桥：原 idea 会话 → handoff → prototype 会话 → handoff/结论指针 → 原主链的新会话。

## 7. 安装、调用属性与已知前置条件

### 7.1 安装与 Setup

```bash
npx skills@latest add mattpocock/skills
```

安装器中选择需要的 Skill 和目标 coding agent，并确保选择 `/setup-matt-pocock-skills`；随后在目标仓库运行它。Setup 会探测 remote、agent 文件、领域文档、ADR、`.scratch/`、monorepo 信号与 `triage` 是否安装，先展示草稿，确认后才写入。

Issue Tracker 的固定 Skill 正文选项是 GitHub、GitLab、本地 Markdown和 Other；README 快速说明举例 GitHub、Linear 或本地文件。本文以执行 Skill 为准，将 Linear 视为 Other 可描述的自定义 tracker。

### 7.2 调用属性

| 属性 | user-invoked | model-invoked |
| --- | --- | --- |
| 触发者 | 仅人类显式输入名称 | 模型自动或人类显式输入 |
| frontmatter | `disable-model-invocation: true` | 省略该字段 |
| description | 人类浏览用一句话 | 模型可见，包含触发分支 |
| 组合边界 | 可组合 model-invoked，但不能自动调用另一个 user-invoked | 可由编排 Skill 复用 |
| 成本 | 零 description 上下文负担，增加人的记忆负担 | 增加上下文负担，减少人工选择负担 |

用户调用共 13 项：`ask-matt`、`setup-matt-pocock-skills`、`grill-me`、`grill-with-docs`、`triage`、`wayfinder`、`to-spec`、`to-tickets`、`implement`、`improve-codebase-architecture`、`handoff`、`teach`、`writing-great-skills`。其余 8 项为模型/用户均可调用。

### 7.3 Setup/Triage 前置张力

源代码存在一个不能自行补齐的前置张力：Setup 在未安装 `triage` 时明确不生成 `docs/agents/triage-labels.md`；但 `to-spec` 与 `to-tickets` 又要求 triage label vocabulary 已提供，并要给 Spec/Tickets 应用 `ready-for-agent`。源码没有定义未安装 `triage` 时的回退标签来源，因此本文只记录张力，不虚构默认映射或跳过规则。

### 7.4 已知能力前提

各路径可能假设 Git、Issue Tracker API/CLI、原生 blocking links、并行或后台 agent、浏览器/headless browser、测试与类型检查命令、本地 HTML 打开能力和 OS 临时目录。不同 agent 平台的能力并不必然等价；缺失时需由实际执行环境明确替代方案。

## 8. 非正式 Skill 附录

当前提交包含 39 个 Skill 目录，插件正式暴露 21 个；剩余目录不能统称为“未完成”。

| 目录桶 | 数量 | 状态与正式边界 |
| --- | ---: | --- |
| `engineering` | 17 | 日常工程目录；16 项进入插件，`resolving-merge-conflicts` 未暴露 |
| `productivity` | 5 | 5 项全部正式暴露 |
| `misc` | 4 | 零散可用内容，未进入插件 |
| `personal` | 2 | 作者个人环境内容，未推广到插件 |
| `in-progress` | 7 | 开发中，未进入插件 |
| `deprecated` | 4 | 已弃用，未进入插件 |

`engineering/resolving-merge-conflicts` 的目录存在但不在 `plugin.json`；当前源码不足以解释原因，不推断为遗漏或即将发布。`misc`、`personal`、`in-progress`、`deprecated` 也不提升为本文正式 Skill。

## 9. 核对来源

- 研究日期：2026-07-11；上游提交：`391a2701dd948f94f56a39f7533f8eea9a859c87`。
- [README](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/README.md)：安装、Setup 入口、整体定位与调用分组。
- [插件清单](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/.claude-plugin/plugin.json)：21 个正式 Skill 的唯一清单。
- [调用规则](https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/.agents/invocation.md)：user/model-invoked 判定、依赖表达与被动/主动领域工作边界。
- 21 个正式 `SKILL.md` 的源代码链接逐项列在第 3 节。
