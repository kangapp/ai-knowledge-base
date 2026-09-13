# mattpocock/skills：Skill 与产物说明书

本文以 `mattpocock/skills` 当前 `main` 为准。正式 Skill 以 `.claude-plugin/plugin.json` 为边界；核对日期与提交哈希只用于让读者验证资料来源。

## 1. 快速认识

这套仓库把工程工作拆成 **25 个正式 Skill、6 类能力**。推荐阅读顺序是：先用能力地图找到 Skill，再查单项输入输出，然后看产物如何被创建、更新和读取，最后沿五条流程理解协作。

- **Skill 是过程单元**：接收对话、代码、Issue、文件或配置，执行一套可复用纪律。
- **产物是协作契约**：文件、Issue、分支、测试、提交或报告让不同 Skill 和会话接续工作。
- **调用方式只是属性**：14 个 user-invoked Skill 只能由人显式输入；11 个 model-invoked Skill 可由模型自动选择，也可由人输入。
- **目录只是维护视图**：`engineering`、`productivity` 等物理目录不作为本文的一级能力分类。

## 2. 六类能力地图

| 能力类型 | 正式 Skill | 能力范围 |
| --- | --- | --- |
| 导航与项目配置 | `ask-matt`、`setup-matt-pocock-skills` | 选择合适入口，建立 Issue Tracker、标签与领域文档配置 |
| 需求澄清与方案探索 | `grill-me`、`grill-with-docs`、`grilling`、`prototype`、`to-questionnaire` | 澄清模糊需求，以对话或可运行原型回答设计问题 |
| 请求治理与规划拆分 | `triage`、`wayfinder`、`to-spec`、`to-tickets` | 治理外部请求，探索大型工作，形成 Spec 与 Tickets |
| 实现、测试与审查 | `implement`、`tdd`、`diagnosing-bugs`、`code-review`、`resolving-merge-conflicts`、`wizard` | 实现代码，建立反馈环，诊断问题，检查规格与质量、解决合并冲突、引导人工步骤 |
| 领域知识与架构设计 | `domain-modeling`、`codebase-design`、`improve-codebase-architecture` | 维护领域语言，设计深模块，发现架构改进机会 |
| 知识获取与跨会话协作 | `research`、`handoff`、`teach`、`writing-for-agents`、`wait-what` | 调研、跨环境交接、持续教学、Agent 文档编写与表达修正 |

上表中 25 个 Skill 各出现一次；能力范围只用于导航，不表示自动调用链。

## 3. 25 个正式 Skill 图鉴

“输出”指 Skill 结束时交付的正式结果；“中间产物”指过程中创建、更新或传递、可供后续继续使用的信息载体。

### `ask-matt`

- **核心作用**：按当前情境推荐 Skill 或流程；**适用场景**：不确定从哪个入口开始；**调用方式**：用户显式 `/ask-matt`。
- **输入**：当前问题、工作目录有无、工作规模与阶段边界；**执行动作**：区分主流程、入口、维护与独立工具并给出路线；**输出**：推荐路线。
- **中间产物**：无；**依赖**：仓库 Skill 与调用规则知识；**协作关系**：位于所有流程之前，指向 Setup 或具体入口；**使用边界**：只路由，不执行另一个 user-invoked Skill。
- **源代码**：[ask-matt](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/ask-matt/SKILL.md)

### `setup-matt-pocock-skills`

- **核心作用**：为工程 Skill 建立仓库级配置；**适用场景**：每个仓库首次使用工程流程；**调用方式**：用户显式 `/setup-matt-pocock-skills`。
- **输入**：remote、仓库结构、现有 agent/domain 文件、已安装 Skill 与用户选择；**执行动作**：探测、展示草稿、逐节确认后写入；**输出**：可被工程 Skill 消费的项目配置。
- **中间产物**：`AGENTS.md`/`CLAUDE.md` 配置块及 `docs/agents/*.md` 草稿；**依赖**：Git/文件探测与用户确认；**协作关系**：为 `triage`、`wayfinder`、`to-spec`、`to-tickets`、领域相关 Skill 提供前置；**使用边界**：不同时新建两种 agent 文件，未安装 `triage` 时跳过标签配置。
- **源代码**：[setup-matt-pocock-skills](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/setup-matt-pocock-skills/SKILL.md)

### `grill-me`

- **核心作用**：用持续访谈澄清通用计划或设计；**适用场景**：没有工作目录的方案讨论；**调用方式**：用户显式 `/grill-me`。
- **输入**：计划、设计与分轮回答；**执行动作**：运行 `grilling`；**输出**：共享理解与已解决决策树。
- **中间产物**：对话中的问题与答案；**依赖**：`grilling`；**协作关系**：通用澄清入口；**使用边界**：无状态，不写领域文档，确认前不实施。
- **源代码**：[grill-me](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/grill-me/SKILL.md)

### `grill-with-docs`

- **核心作用**：澄清工程计划并同步固化领域语言和决策；**适用场景**：有工作目录、需要保留领域知识的功能或架构讨论；**调用方式**：用户显式 `/grill-with-docs`。
- **输入**：计划、代码事实、领域文档与用户决策；**执行动作**：组合 `grilling` 和 `domain-modeling`；**输出**：共享理解、更新后的领域文档。
- **中间产物**：`CONTEXT.md`、必要 ADR、对话决策；**依赖**：`grilling`、`domain-modeling`；**协作关系**：新功能主链起点，可交给 `to-spec` 或小改的 `implement`；**使用边界**：负责澄清与记录，不实施计划。
- **源代码**：[grill-with-docs](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/grill-with-docs/SKILL.md)

### `grilling`

- **核心作用**：按决策依赖分轮压力测试计划、决定或想法；**适用场景**：需要消除设计分歧或未决项；**调用方式**：模型自动或用户显式。
- **输入**：计划、可查事实和用户回答；**执行动作**：每轮问完前提已满足的 frontier 问题并给推荐答案；事实调查派给后台子任务，不阻塞无依赖的问题；**输出**：共享理解。
- **中间产物**：对话中的决策树；**依赖**：用户参与、可访问环境与后台子任务能力；**协作关系**：被 `grill-me`、`grill-with-docs`、`triage`、`wayfinder` 等复用；**使用边界**：不替用户作决策；前沿清空且用户确认共享理解后才可行动。
- **源代码**：[grilling](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/grilling/SKILL.md)

### `prototype`

- **核心作用**：用抛弃式可运行代码回答一个设计问题；**适用场景**：状态/逻辑需可交互 HTML 验证，或 UI 必须看见多个差异方案；**调用方式**：模型自动或用户显式。
- **输入**：单一设计问题与现有项目约定；**执行动作**：做单文件逻辑 HTML（状态面板、自由操作、场景引导）或同一路由多种 UI，记录结论并保存证据分支；**输出**：可运行原型与已验证决策。
- **中间产物**：Prototype branch、问题/答案和返回原线程的 context pointer；**依赖**：项目运行方式、路由与 Git；**协作关系**：由 grilling 支线进入，结论回到原想法/Spec；**使用边界**：默认无持久化、测试或抽象；演示保存在独立分支供重跑，已验证纯逻辑可提取到正式模块，HTML 外壳不进入生产。
- **源代码**：[prototype](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/prototype/SKILL.md)

### `triage`

- **核心作用**：把外部 Issue/PR 推进到明确类别与状态；**适用场景**：维护者处理未经治理的请求；**调用方式**：用户显式 `/triage`。
- **输入**：外部 Issue/PR、tracker 状态、标签映射和维护者指示；**执行动作**：分类、验证、补问、写 notes/brief，经人确认后变更状态；**输出**：`needs-info`、`ready-for-agent`、`ready-for-human` 或 `wontfix` 结果。
- **中间产物**：Triage Notes、Agent/Human Brief、标签和评论；**依赖**：Issue Tracker、Triage Labels，必要时 `grilling`/`domain-modeling`；**协作关系**：agent-ready 请求交给 `implement`；**使用边界**：外部 PR 需 tracker 配置开启；类别为 bug/enhancement，状态为五类分诊角色；`to-tickets` 产出的票不再 triage，发布的评论/Issue 带 AI 声明。
- **源代码**：[triage](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/triage/SKILL.md)

### `wayfinder`

- **核心作用**：把超大模糊工作变成共享决策地图；**适用场景**：目的地已知但单会话看不清路线；**调用方式**：用户显式 `/wayfinder`。
- **输入**：destination、tracker 配置、领域知识和用户决策；**执行动作**：创建 Map 与子票、连接阻塞边、除 Research 外每会话认领并解决至多一张决策任务，Research 由后台子任务并行处理、更新 frontier；**输出**：逐步消散 fog of war 的决策地图。
- **中间产物**：Map Issue、四类 Decision tickets、resolution comments、Decisions so far、研究证据分支；**依赖**：Issue Tracker、`grilling`、`domain-modeling`、`research`、`prototype`；**协作关系**：路线清晰后交给 `to-spec` 或小范围 `implement`；**使用边界**：默认产出决策；建图后明确分派 `research` 子任务并保存 `research/<name>` 分支指针，Task 仅完成阻塞决策的前置操作。
- **源代码**：[wayfinder](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/wayfinder/SKILL.md)

### `to-spec`

- **核心作用**：把已经讨论清楚的内容综合成可执行 Spec；**适用场景**：多会话工作进入正式规划；**调用方式**：用户显式 `/to-spec`。
- **输入**：当前完整对话、代码库理解和领域文档；**执行动作**：综合问题、方案、用户故事及实施/测试决策，确认测试 seams 后发布；**输出**：带 `ready-for-agent` 的 Spec Issue。
- **中间产物**：Spec 草稿与 seam 确认；**依赖**：Issue Tracker、Triage Labels、领域术语；**协作关系**：承接 grilling/wayfinder，交给 `to-tickets`；**使用边界**：不重新访谈需求；不写具体路径或普通代码，表达已验证决策的原型片段可精简内联。
- **源代码**：[to-spec](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/to-spec/SKILL.md)

### `to-tickets`

- **核心作用**：把计划拆成单会话 tracer-bullet tickets；**适用场景**：Spec 或计划需分阶段实现；**调用方式**：用户显式 `/to-tickets`。
- **输入**：Spec、plan、issue 或当前讨论；**执行动作**：设计端到端切片、确认粒度与 blocking edges、发布到 tracker；**输出**：带依赖关系和 `ready-for-agent` 的 Ticket Issues。
- **中间产物**：票据草稿；本地 tracker 为 `.scratch/<feature>/issues/NN-<ticket>.md`；**依赖**：Issue Tracker、Triage Labels 与阻塞能力；**协作关系**：每票由新的 `implement` 会话消费；**使用边界**：不修改/关闭 parent，wide refactor 用 expand-contract，发布前必须经用户确认。
- **源代码**：[to-tickets](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/to-tickets/SKILL.md)

### `implement`

- **核心作用**：实现明确的 Spec 或 Tickets，并以测试、审查和提交收尾；**适用场景**：Spec/Ticket 已足够可执行；**调用方式**：用户显式 `/implement`。
- **输入**：Ticket、Spec 或明确工作说明；**执行动作**：理解范围，在确认 seam 上驱动 `tdd`，运行反馈命令，以 `code-review` 收尾并提交；**输出**：已验证实现和 Code commit。
- **中间产物**：Tests、Code、测试输出、Code Review report；**依赖**：`tdd`、`code-review`、项目测试/类型检查；**协作关系**：承接 agent-ready 工作，逐票完成主链；**使用边界**：不得跳过预定 seam、完整测试或提交前双轴审查。
- **源代码**：[implement](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/implement/SKILL.md)

### `tdd`

- **核心作用**：以 red → green 垂直切片实现外部行为；**适用场景**：功能或修复有已确认 public seam；**调用方式**：模型自动或用户显式。
- **输入**：一个行为、确认过的 seam、领域文档；**执行动作**：先写一个失败测试，再写最小实现使其通过并重复；**输出**：通过的行为切片。
- **中间产物**：失败后转绿并保留的 Tests 与 Code；**依赖**：测试工具、`CONTEXT.md`/ADR；**协作关系**：由 `implement` 驱动，也可独立使用；**使用边界**：预期结果使用独立依据；不测试实现细节、不横向批量铺测试、不在未确认 seam 上开始；重构在审查阶段进行。
- **源代码**：[tdd](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/tdd/SKILL.md)

### `diagnosing-bugs`

- **核心作用**：用紧反馈环诊断困难 Bug/性能回归并验证修复；**适用场景**：错误、失败、变慢、间歇性问题；**调用方式**：模型自动或用户显式。
- **输入**：用户精确症状、环境、代码与历史状态；**执行动作**：建立 red-capable 命令、复现并最小化、排序可证伪假设、单变量探测、在合适 seam 先回归测试后修复、清理并记录根因；**输出**：根因说明和已验证修复。
- **中间产物**：最小复现、反馈命令、临时 instrumentation、Regression Test；**依赖**：可运行环境、`CONTEXT.md`/ADR；**协作关系**：修复后交给 review/commit，无正确 seam 时把发现交给架构维护；**使用边界**：先脱敏命令、输出和捕获材料；没有已运行且能捕获精确症状的紧红灯命令，不进入假设阶段；缺少正确 seam 时记录限制。
- **源代码**：[diagnosing-bugs](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/diagnosing-bugs/SKILL.md)

### `code-review`

- **核心作用**：从固定点对 diff 做 Standards 与 Spec 双轴审查；**适用场景**：实现收尾或独立检查分支/PR；**调用方式**：模型自动或用户显式。
- **输入**：可解析 fixed point、`HEAD` diff、仓库 standards 与可选 Spec；**执行动作**：两个独立并行审查分别核对标准/气味和规格忠实度；**输出**：并排的双轴 Code Review report。
- **中间产物**：两个 sub-agent 报告；**依赖**：Git、Issue Tracker/Spec、标准文件与并行 agent 能力；**协作关系**：`implement` 提交前质量门；**使用边界**：缺 fixed point 先问、空 diff 停止、无 Spec 明示跳过该轴、两轴不合并重排。
- **源代码**：[code-review](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/code-review/SKILL.md)

### `domain-modeling`

- **核心作用**：建立并持续校准项目统一领域语言；**适用场景**：术语模糊、重载、边界冲突或决策需要固化；**调用方式**：模型自动或用户显式。
- **输入**：领域术语、边界场景、代码事实和用户决策；**执行动作**：挑战定义、用反例压力测试、即时更新 glossary，达到门槛才写 ADR；**输出**：清晰领域模型。
- **中间产物**：`CONTEXT.md`、可选 `CONTEXT-MAP.md`、`docs/adr/NNNN-*.md`；**依赖**：`docs/agents/domain.md` 与用户裁决；**协作关系**：贯穿 grilling、triage、wayfinder、架构工作；**使用边界**：仅被动读取 glossary 不算调用；`CONTEXT.md` 不放实现细节；ADR 必须同时具备难逆、意外和真实权衡。
- **源代码**：[domain-modeling](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/domain-modeling/SKILL.md)

### `codebase-design`

- **核心作用**：提供 deep module、interface 与 seam 的统一设计纪律；**适用场景**：模块边界、抽象、adapter 或可测试性设计；**调用方式**：模型自动或用户显式。
- **输入**：调用关系、行为、变化轴与候选接口；**执行动作**：以 module/interface/depth/seam/adapter/leverage/locality 评价设计，必要时 design-it-twice；**输出**：深模块接口与测试 seam 设计。
- **中间产物**：候选接口、边界方案与比较；**依赖**：现有代码事实；**协作关系**：为 `tdd` 和架构扫描提供词汇，选定设计回主开发流程；**使用边界**：只有一个 adapter 时不凭空制造 seam，不把浅包装当深模块。
- **源代码**：[codebase-design](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/codebase-design/SKILL.md)

### `improve-codebase-architecture`

- **核心作用**：扫描代码库并可视化 deepening opportunities；**适用场景**：周期性架构维护或缺少测试 seam；**调用方式**：用户显式 `/improve-codebase-architecture`。
- **输入**：用户指定方向或近期提交热点、代码库、`CONTEXT.md`、相关 ADR；**执行动作**：先确定高价值扫描范围，再用 `codebase-design` 词汇探索候选，生成 HTML，由用户选择后 grilling；**输出**：Architecture HTML report 与选定架构问题。
- **中间产物**：OS 临时目录中的报告、候选列表与设计对话；**依赖**：`codebase-design`、代码探索、`grilling`/`domain-modeling`；**协作关系**：选题后经领域/边界澄清回主开发流程；**使用边界**：扫描时不先定具体 interface，报告不落仓库，不绕过 ADR 冲突。
- **源代码**：[improve-codebase-architecture](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/improve-codebase-architecture/SKILL.md)

### `research`

- **核心作用**：针对一个问题查阅高信任一手资料并固化引用；**适用场景**：决策前需要外部事实；**调用方式**：模型自动或用户显式。
- **输入**：清晰研究问题、仓库笔记约定；**执行动作**：后台 agent 搜索、筛选 primary sources、逐项引用并写文件；**输出**：仓库内单一 Research Markdown。
- **中间产物**：来源列表、检索笔记和引用；**依赖**：后台 agent、网络/资料访问；**协作关系**：结果可带入 `grill-with-docs` 或其他决策会话；**使用边界**：只做事实调研，不以二手摘要替代一手来源，不代替决策或实现；Wayfinder 的 Research Ticket 已明确通过它执行，独立使用时则按仓库约定存放笔记，不强制研究分支。
- **源代码**：[research](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/research/SKILL.md)

### `handoff`

- **核心作用**：把当前会话压缩成新会话可接续的文档；**适用场景**：换工具、目录、协作者，或阶段中途分出支线；**调用方式**：用户显式 `/handoff`。
- **输入**：当前对话、下一会话目标和正式产物指针；**执行动作**：总结、引用既有产物、建议 Skill、脱敏并写入临时目录；**输出**：handoff Markdown。
- **中间产物**：无；**依赖**：OS 临时目录与现有 Spec/ADR/Issue/commit/diff 指针；**协作关系**：需要携带上下文到其他环境时的桥；同环境容量不足时先按阶段边界决策树选择；**使用边界**：不复制已有正式产物，不写当前 workspace，不携带敏感信息；生成文件不会自动启动下一会话或终止当前会话。
- **源代码**：[handoff](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/handoff/SKILL.md)

### `teach`

- **核心作用**：在当前目录维护多会话教学工作区；**适用场景**：持续学习一个概念或技能；**调用方式**：用户显式 `/teach`。
- **输入**：主题、mission、学习记录、可信资源与反馈；**执行动作**：确定最近发展区，制作短 lesson、reference、练习和学习记录；**输出**：状态化教学工作区与 HTML lessons。
- **中间产物**：`MISSION.md`、`RESOURCES.md`、`NOTES.md`、`lessons/`、`reference/`、`assets/`、`learning-records/`；**依赖**：当前目录、一手资源和用户反馈；**协作关系**：独立多会话教学流；**使用边界**：每课服务 mission，mission 变更先确认，不属于工程交付链。
- **源代码**：[teach](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/teach/SKILL.md)

### `writing-for-agents`

- **核心作用**：编写供 Agent 消费的文档；**适用场景**：编辑 Skill、`AGENTS.md`/`CLAUDE.md` 或被指针引用的文档；**调用方式**：模型自动或用户显式。
- **输入**：待编辑文档、读者和触发场景；**执行动作**：设计 context pointers、信息层级和可验证完成条件，裁剪重复、无效和过期内容；**输出**：更清晰、可预测的 Agent 文档。
- **中间产物**：文档改动；**依赖**：编写 Skill 时进一步读取同目录 `SKILL-MECHANICS.md`；**协作关系**：通用编写参考；**使用边界**：兼顾模型上下文负担与人的选择负担；环境已能直接回答的内容只在查找代价高时缓存进文档。
- **源代码**：[writing-for-agents](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/writing-for-agents/SKILL.md)

### `resolving-merge-conflicts`

- **核心作用**：完成正在进行的 merge/rebase；**适用场景**：已有冲突；**调用方式**：模型自动或用户显式。
- **输入**：冲突块、双方提交及关联 PR/Issue；**执行动作**：追溯双方原始意图，逐块解决，运行项目检查并完成操作；**输出**：已完成的合并或变基。
- **中间产物**：冲突修复、检查结果和 Git 提交；**依赖**：Git 与项目检查；**协作关系**：独立工具；**使用边界**：尽量保留双方意图，不兼容时依据合并目标说明取舍；不发明新行为，上游要求完成操作而非 `--abort`。
- **源代码**：[resolving-merge-conflicts](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/resolving-merge-conflicts/SKILL.md)

### `wizard`

- **核心作用**：生成人工步骤的交互式 Bash 向导；**适用场景**：必须由人完成的服务开通、凭据配置、第三方界面操作、迁移或切换；**调用方式**：模型自动或用户显式。
- **输入**：环境、目标状态、步骤和需采集的值；**执行动作**：确认阶段与写入位置，复制模板并仅编写阶段，静态校验；**输出**：可执行向导和运行方法。
- **中间产物**：scratch 或 `scripts/` 下的脚本；**依赖**：`template.sh`、Bash，按需使用 `gh`；**协作关系**：流程被人工步骤阻塞时使用；**使用边界**：AI 能直接完成的工作应直接完成；不改模板库，不由 AI 端到端运行。凭据隐藏输入，不可逆步骤前确认；进度按阶段数显示。
- **源代码**：[wizard](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/wizard/SKILL.md)

### `to-questionnaire`

- **核心作用**：向掌握缺失信息的人收集输入；**适用场景**：用户不能独自回答的决策问题；**调用方式**：用户显式。
- **输入**：收件人的角色、掌握的信息，以及用户需要拿回的事实或决定；**执行动作**：询问收件人和回收目标，然后按重要性编排问题；**输出**：当前目录的 `to-questionnaire-<slug>.md`。
- **中间产物**：问卷草稿和回答位置；**依赖**：用户明确用途；**协作关系**：回答可回流到澄清或 Spec；**使用边界**：访谈围绕“给谁、要什么”，生成问卷不等于替用户发送，也不代填答案。
- **源代码**：[to-questionnaire](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/to-questionnaire/SKILL.md)

### `wait-what`

- **核心作用**：重新解释刚才没有讲清楚的消息；**适用场景**：用户跟不上表达或缺少背景；**调用方式**：用户显式。
- **输入**：上一条消息和领域词汇；**执行动作**：补必要背景、简化表达；**输出**：重新组织的解释。
- **中间产物**：无；**依赖**：已有 `CONTEXT.md`，多领域时经 `CONTEXT-MAP.md` 定位；**协作关系**：可在任意对话中使用；**使用边界**：修复当次表达，不保证之后自动简洁；上游正文指定 ASD-STE100 简化技术英语，中文项目可依语言约定适配。
- **源代码**：[wait-what](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/wait-what/SKILL.md)

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
├── Implementation Ticket Issues
├── Wayfinder Map + Decision tickets
└── .scratch/<feature>/{spec.md,issues/NN-<ticket>.md}
设计与研究产物
├── Research Markdown
├── prototype/<name> 与 research/<name> 证据分支
└── Architecture HTML report
临时会话产物
├── OS 临时目录/handoff-*.md
├── to-questionnaire-<slug>.md
└── Wizard Bash script
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
| `docs/adr/NNNN-*.md` | `docs/adr/` 或 domain 配置指定位置 | `domain-modeling` | 无固定更新者 | 后续领域建模、规划、实现、诊断、审查与架构工作 | 编号/标题、上下文、决策、备选与后果 | 长期决策记录，替代关系按项目约定维护；仅在难逆、缺上下文会意外且存在真实权衡时创建 |

### 4.4 工作规划产物

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| Spec Issue | 配置的 Issue Tracker | `to-spec` | 无固定更新者 | `to-tickets`、`implement`、`code-review` | 背景/目标、范围与非目标、行为、领域词汇、模块/seams、验收与测试策略 | 阶段性需求基线；将完整对话压缩成 agent-ready 规格 |
| Ticket Issues | 真实 tracker 的子/关联 Issue | `to-tickets` | 无固定更新者 | 独立 `implement` 会话、frontier 查询 | 单会话 tracer bullet、验收、上下文、测试 seam、blocking edges、parent 指针 | 阶段性；阻塞解除后可领取，完成后关闭 |
| `.scratch/<feature>/issues/NN-<ticket>.md` | 本地 Markdown tracker | `to-tickets` | 无固定更新者 | 独立 `implement` 会话、人工 blockers-first 调度 | 与 Ticket Issue 等价的正文，加文本化依赖与状态 | 阶段性；本地 tracker 的逐票实体，功能完成后可清理 |

### 4.5 设计、研究与跨会话产物

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| Research Markdown | 仓库内，按既有研究/笔记约定选择文件名 | `research` | 无固定更新者 | grilling 或其他决策会话 | 研究问题、结论、逐项 primary-source 引用与来源链接 | 阶段性事实快照；独立使用时不强制提交；Wayfinder 指定保存在研究分支并回链决策任务 |
| Prototype branch | Git 的隔离抛弃式分支 | `prototype` | `prototype` | 原 idea/Spec/implementation 会话 | 单文件逻辑 HTML 或同一路由 UI 变体、问题/答案、分支指针 | 留存可重跑证据；演示外壳不合入主分支，已验证纯逻辑可提取 |
| Architecture HTML report | OS 临时目录中的 HTML | `improve-codebase-architecture` | 无固定更新者 | 用户、后续 grilling/架构设计 | 候选 deepening opportunity、before/after 视觉、证据、收益与 ADR 冲突提示 | 一次性临时报告；帮助选题，不作为仓库长期文档 |
| handoff Markdown | OS 临时目录，通常 `handoff-*.md` | `handoff` | 无固定更新者 | 新会话 | 当前状态、下一目标、未决项、正式产物指针、suggested skills；敏感信息已脱敏 | 临时跨会话桥；引用而不复制事实源 |

### 4.6 实现与验证产物

| 产物 | 路径/位置 | 创建者 | 更新者 | 消费者 | 内部结构 | 生命周期与作用 |
| --- | --- | --- | --- | --- | --- | --- |
| Tests | 项目既有测试目录 | `tdd`、`diagnosing-bugs` | `tdd`、`implement` | 实现反馈环、`code-review`、CI、未来回归 | 从 public seam 表达外部行为；诊断时包含最小回归场景 | 长期可执行契约；先红后绿证明行为 |
| Code commits | Git 历史 | `implement` | 无固定更新者 | 后续 Ticket/PR/review/发布 | 聚焦实现 diff、测试与说明；固定 SHA/父提交形成边界 | 长期版本记录；测试和双轴 review 后产生 |
| Code Review report | 当前会话/agent 输出 | `code-review` | 无固定更新者 | 实现者和人类审阅者 | Standards report 与 Spec report 并排，各自含按严重度定位的发现；无 Spec 时注明跳过 | 阶段性一次性质量门；不改写成单一混合排序 |

## 5. Skill × 产物矩阵

这里按主要职责列出读写和交接关系。条件性动作写明条件；流程中的建议路线与 Skill 内部调用分别描述。

| Skill | 主要读取 | 创建、更新或交付 | 交接边界 |
| --- | --- | --- | --- |
| `ask-matt` | 当前情境和上游路线 | 路线建议 | 不代为执行其他用户入口 |
| `setup-matt-pocock-skills` | 现有项目配置和 remote | Agent 配置块、tracker/domain/条件性标签文档 | 通用配置前置 |
| `grill-me` | 计划与回答 | 对话中的共享理解 | 不写本地领域文档 |
| `grill-with-docs` | 计划、事实、领域文档 | 共享理解、术语、必要 ADR | 内部组合 grilling 和领域建模 |
| `grilling` | 已决前提和后台调查结果 | 下一轮问题、最终共享理解 | 用户作决策，确认后才能行动 |
| `prototype` | 一个设计问题和运行约定 | HTML/UI 原型、证据分支、事项单指针 | 原型外壳留在证据分支 |
| `triage` | 外部原始请求、tracker、标签 | Notes、Brief、评论、状态，按需更新领域文档 | 不处理已拆好的实施票 |
| `wayfinder` | Map、前沿、相关决策任务 | Map 索引、子任务、答案评论、证据指针 | Research 明确委派后台研究 |
| `to-spec` | 当前对话、领域词汇、已确认 seams | Spec；本地模式为 spec.md | 通常无路径/代码，决策型原型片段例外 |
| `to-tickets` | Spec、计划或讨论 | 一票一文件/Issue、blocking edges | 不修改或关闭 parent |
| `implement` | Spec/Tickets、项目规则 | 实现、验证结果、当前分支提交 | 内部使用 tdd 和 code-review |
| `tdd` | 行为与确认过的公开接口 | 逐个红转绿的测试与实现 | 重构放在审查阶段 |
| `diagnosing-bugs` | 精确症状与可运行环境 | 反馈命令、最小复现、修复与适当的回归测试 | 无合适 seam 时写明限制 |
| `code-review` | 固定点 diff、标准、Spec | 分开的 Standards / Spec 报告 | 本身不改代码或提交 |
| `domain-modeling` | 术语、场景、代码和已有 ADR | CONTEXT.md、必要 ADR | 被动读取术语不算主动建模 |
| `codebase-design` | 模块形状、调用与变化 | 接口/seam 的设计判断与候选比较 | 不固定创建某类文件 |
| `improve-codebase-architecture` | 指定范围或近期热点、领域文档 | 临时 HTML 候选报告和后续设计讨论 | 用户选题后再深入设计 |
| `research` | 研究问题、一手来源 | 带引用 Markdown | 保存位置遵守仓库约定 |
| `handoff` | 对话、下一目标、正式产物指针 | OS 临时目录交接文档 | 不复制源材料或启动下一会话 |
| `teach` | 目标、资源、学习记录 | 教学工作区、HTML lessons、学习记录 | 独立学习流程 |
| `writing-for-agents` | 待编辑文档及触发需求 | Agent 文档改进 | 不固定创建新的文件层级 |
| `resolving-merge-conflicts` | 冲突及双方原始意图 | 冲突修复、检查、完成 merge/rebase | 只处理当前合并目标 |
| `wizard` | 人工流程与配置中需要的值 | 可执行 Bash 向导 | 运行时才采集值，用户执行 |
| `to-questionnaire` | 收件人和信息缺口 | 当前目录问卷 | 回答由收件人提供 |
| `wait-what` | 上一条消息与领域词汇 | 重新解释 | 不创建持久文件 |

Map 与实施 Tickets 都可能物理存为 Issue，但完成条件不同。Wayfinder 对 Research 的后台委派是源码明确要求；独立 `research` 的 Markdown 不必然关联 Wayfinder，也不自动成为 Spec。`prototype` 向 implementation issue 写入结论/指针，不代表它能实施该任务。

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
4. 若没有正确 test seam：`diagnosing-bugs` → 根因说明中的架构发现 → `improve-codebase-architecture`，但先完成可验证修复。

### 6.3 大型模糊项目

1. `wayfinder` → destination / Map Issue → Research、Prototype、Grilling 或 Task 决策任务。
2. 一张 frontier Ticket → resolution comment / linked asset / decision → Map Issue 的 Decisions so far 与新 frontier。
3. Map 完成 → 已确认决策与清晰路线 → `to-spec`（范围已缩小到单会话时可到 `implement`）。
4. `to-spec` → Spec Issue → `to-tickets` → Ticket Issues → `implement`。

Research 是决策任务的一种类型。Wayfinder 建图后明确为 Research 任务启动后台子任务，使用 `research` 保存带引用结果，并从任务链接到 `research/<name>` 分支；这是“每会话最多解决一票”规则的例外。

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

`handoff` 是需要跨工具、目录、协作者迁移上下文，或中途分出支线时的桥：

```text
需要迁移的上下文 → handoff Markdown（状态、指针、未决项、suggested skills）→ 目标会话
```

它也可为独立目录中的 prototype 支线做双向桥。只是上下文容量不足时，先按“继续 → 清空 → 交接 → 后台子任务 → 压缩”的顺序判断；完整决策树见[完整工作流](usage-guide.md)。

## 7. 安装、调用属性与已知前置条件

### 7.1 安装与 Setup

Claude Code 可选择官方托管插件 `claude plugins install mattpocock-skills`；需要可编辑文件，或使用 Codex 等其他 agent 时，选择 `npx skills@latest add mattpocock/skills`。文件安装可用 `npx skills update` 主动更新；同一环境不要重复安装两套。Setup 的具体步骤见[快速入门](README.md)。

Setup 执行正文支持 GitHub、GitLab、本地 Markdown 和自定义 Other。Linear 等 Tracker 通过描述实际操作流程配置，不能把 README 的示例理解成内置专用适配器。

### 7.2 调用属性

| 属性 | user-invoked（14 项） | model-invoked（11 项） |
| --- | --- | --- |
| 触发者 | 用户显式选择 | 模型按场景选择，或用户显式选择 |
| Claude Code 元数据 | SKILL.md 中 disable-model-invocation: true | 省略该字段 |
| Codex 元数据 | agents/openai.yaml 中 policy.allow_implicit_invocation: false | 省略该 policy 限制 |
| 描述职责 | 给人选择入口 | 告诉模型何时适用 |
| 调用边界 | 其他 Skill 不能代为启动用户入口 | 可由编排 Skill 复用 |

每个 Skill 都有 `agents/openai.yaml` 保存显示名称和简介；两个宿主的权限字段需要一致。通常在 Claude Code 用 `/skill-name`，在 Codex 用 `$skill-name` 显式选择。这里描述上游的元数据约定，具体安装器和宿主仍需正确识别这些文件。[调用规则](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/.agents/invocation.md)

用户入口共 14 项：`ask-matt`、`setup-matt-pocock-skills`、`grill-me`、`grill-with-docs`、`triage`、`wayfinder`、`to-spec`、`to-tickets`、`implement`、`improve-codebase-architecture`、`handoff`、`teach`、`to-questionnaire`、`wait-what`。其余 11 项均可由模型或用户选择，包括 `writing-for-agents`。

### 7.3 执行前需要核实的边界

以下是按当前源码发现的衔接问题，不是额外增加的上游规则。

- **标签配置**：Setup 未安装 `triage` 时不生成 `triage-labels.md`，但 `to-spec`、`to-tickets` 仍要求标签词汇及 `ready-for-agent`。源码没有定义缺失时的完整回退，使用前应检查项目配置。
- **未提交改动的审查**：`implement` 要求审查后提交，`code-review` 却使用 `git diff <fixed-point>...HEAD`。这条命令不会包含工作区/暂存区中的未提交修改，也不会包含未跟踪文件。执行时应明确本轮修改是否进入比较范围，必要时由实际工作流补充相应 diff；不要把空的已提交 diff 当成本轮审查完成。
- **TDD 阶段划分**：README/description 仍使用 red-green-refactor 的概括，而 `tdd/SKILL.md` 明确将重构放在审查阶段。本文的操作说明以正文为准。

[Setup](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/setup-matt-pocock-skills/SKILL.md)、[implement](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/implement/SKILL.md)、[code-review](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/code-review/SKILL.md) 和 [tdd](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/tdd/SKILL.md) 提供上述核对依据。

### 7.4 环境能力

各路径可能需要 Git、Tracker API/CLI、阻塞关系、后台子任务、浏览器、本地 HTML、Bash，以及项目测试/类型检查命令。Skill 元数据兼容多个宿主，不等于每个宿主都具备完全相同的工具；缺失能力时要明确实际替代方案。

## 8. 正式与非正式范围

当前提交共有 **37 个 `SKILL.md`**，插件清单收录 **25 项**。正式与否按清单判断，不按目录名称猜测。

| 目录桶 | Skill 数量 | 当前状态 |
| --- | ---: | --- |
| `engineering` | 18 | 全部进入插件，包括 resolving-merge-conflicts 和 wizard |
| `productivity` | 7 | 全部进入插件 |
| `misc` | 4 | 作者保留但很少使用的工具，不进入插件 |
| `in-progress` | 8 | 公开 Beta，按项试用；不进入插件，可能变更或移除 |
| `deprecated` | 0 | 当前为空；personal 目录已不存在 |

Beta 包含 `loop-me`、`writing-beats`、`writing-fragments`、`writing-shape`、`claude-handoff`、`setup-ts-deep-modules`、`implement-spec` 和 `retro`。其中 `retro` 仍是设计笔记占位，尚不可用；不能把 Beta 一律视为完成品。确实需要试用时可按名称安装：

```bash
npx skills@latest add mattpocock/skills --skill=<name>
```

特别注意：Beta `implement-spec` 与正式 `implement` 是不同 Skill，本手册的正式交付流程不包含它。[Beta 目录说明](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/in-progress/README.md)

## 9. 核对来源

- 核对日期：2026-09-13；上游提交：`3cca18b368ae95cdbdebbff572ccafa662551015`；提交日期：2026-09-04；插件版本：`1.2.3`。
- [README](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/README.md)：安装与整体定位。
- [插件清单](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/.claude-plugin/plugin.json)：25 个正式 Skill 的范围。
- [调用规则](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/.agents/invocation.md)：调用权限与元数据；核对时同时检查各 Skill 的 agents/openai.yaml。
- 25 个正式 `SKILL.md` 的固定提交链接逐项列在第 3 节；运行规则有分歧时优先读执行正文和它引用的材料。
