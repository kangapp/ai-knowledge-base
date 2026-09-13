# 完整工作流与 Skill 配合

## 新功能：从想法到交付

### 1. `grill-with-docs`：把想法说清楚

它组合 `grilling` 与 `domain-modeling`：先把问题展开为有前后依赖的决策树，每轮一起询问前提已经明确的问题，并为每题给出建议。收到回答后重算下一轮；依赖本轮答案的问题放到后续轮次。

事实由后台子任务从代码、文档和环境中查证，只等待依赖这些事实的问题，其余问题继续问。产品与设计取舍交给用户；术语确定时立即更新 `CONTEXT.md`，符合长期决策条件时才创建 ADR。[grilling 定义](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/productivity/grilling/SKILL.md)

输出是共享理解、准确术语和已确认决策。前沿问题全部解决，并由用户确认理解一致后，才进入实施。

### 2. 必要时用 `prototype` 回答可运行问题

如果状态机必须操作后才能判断，逻辑分支生成一个可双击打开的 HTML：显示领域化状态、自由操作按钮和分场景引导步骤，不需要构建或服务器。UI 分支则在同一路由提供多种差异明显的方案，通过 URL 参数和浮动切换栏比较。

原型需要独立目录或会话时，用 `handoff` 带出问题，再带回结论。完成后将演示保存在 `prototype/<name>` 分支，在实施事项单留下指针；生产代码吸收已验证的决定，必要时提取独立纯逻辑模块。原型页面外壳留在证据分支。[原型及保存规则](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/prototype/SKILL.md)

### 3. `to-spec`：形成需求说明

多会话工作需要把对话综合成 Spec。它记录问题、方案、用户故事、实施与测试决策、范围边界；仍需确认测试切入点，但不重新访谈需求。通常不写容易过期的具体路径和代码；能精确表达已验证决策的原型片段可以作为例外保留。

### 4. `to-tickets`：拆成纵向任务

每张任务单应交付一项可验证行为，并写明被哪些任务阻塞。不要简单拆成“数据库、后端、前端、测试”四张水平任务。远程 Tracker 优先使用原生阻塞关系；本地模式每票一文件，存入 `.scratch/<feature>/issues/<NN>-<slug>.md`。

广泛机械重构是纵向切片的例外：先添加兼容的新形式，再分批迁移调用者，最后移除旧形式，即 expand–contract。[to-tickets 定义](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/to-tickets/SKILL.md)

### 5. `implement` + `tdd`：一次实现一张任务单

多会话工作通常每个实施 Ticket 用干净的新会话执行；单会话小改可继续当前上下文。`implement` 本身也接受 Spec 或一组 Tickets，这里逐票执行是 `ask-matt` 推荐路线。

先读取事项单、项目规则、术语和相关 ADR，再在已确认的测试切入点做红灯—绿灯循环：一个失败测试、最小实现、重复。预期结果来自需求、已知样例等独立依据，避免用与实现相同的计算重复断言。

**以执行正文为准：** 当前 `tdd/SKILL.md` 将重构放在审查阶段，红灯—绿灯的实现循环中不夹带重构；README 和 description 仍沿用 red-green-refactor 的概括。[TDD 正文](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/tdd/SKILL.md)

### 6. `code-review`：双轴收尾

规范轴检查仓库规则和 Fowler 代码气味基线，仓库明确规则优先，气味只作为判断提示；需求轴检查是否漏做、做错或超出 Spec。两个独立子任务并行审查，两类结论分开报告。`implement` 还要求定期运行类型检查、单文件测试，结束时运行完整测试套件，并提交当前分支。[审查定义](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/code-review/SKILL.md)

审查前要约定固定比较点，并检查实际 diff 是否包含本轮改动；当前 `code-review` 的三点比较命令只涵盖提交内容，详见图鉴的前置条件说明。

## Bug：先建立能看到问题的反馈循环

使用 `diagnosing-bugs`：

```text
能精确失败的一条命令
→ 稳定复现并缩小案例
→ 列出和排序假设
→ 一次验证一个假设
→ 修复并保留回归测试
→ 清理诊断代码并复盘
```

如果复盘发现根因是没有稳定测试切入点或模块耦合太深，修复完成后再把架构发现交给 `improve-codebase-architecture`。

命令、日志和抓取的请求先脱敏，凭据通过环境变量保留在环境中；只展示与症状有关的输出。如果没有合适的测试切入点，明确记录这个限制，并继续用原始反馈命令验证修复。[诊断定义](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/diagnosing-bugs/SKILL.md)

## 外部请求：先分诊，再实施

`triage` 只治理未经整理的外部事项，不处理 `to-tickets` 已生成的任务。它读取完整 Issue、代码事实、术语和历史拒绝记录，然后建议：

- `needs-info`：信息不足，提出具体补充问题。
- `ready-for-agent`：内容完整，附上 Agent Brief 后交给 `implement`。
- `ready-for-human`：需要人工权限、判断或操作。
- `wontfix`：已实现、重复或明确不在范围内。

## 大型模糊工作：用 `wayfinder` 消除未知

Wayfinder 创建 Map Issue 和若干 **Decision tickets（决策任务）**。地图只做索引，详细答案留在子任务中；它默认规划通往目标的路线。只有明确问题才能建票，尚无法准确表述的问题暂存在 `Not yet specified`；超出目的地范围的内容放在 `Out of scope`。

Research 决策任务由后台子任务使用 `research` 并行处理，结果保存在 `research/<name>` 分支，并从任务链接过去。Prototype 与 Grilling 任务需要真人参与；Task 用来完成阻塞决策的前置操作。除研究任务外，每个会话最多解决一张决策任务。[Wayfinder 定义](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/wayfinder/SKILL.md)

地图清晰后进入 `to-spec → to-tickets → implement`；如果已经缩小成单会话任务，可以直接进入 `implement`。

## 架构维护

`improve-codebase-architecture` 优先检查用户指定方向，否则从近期提交找出经常变化的部分，再读取领域术语和 ADR，生成临时 HTML 候选报告。用户选定候选后，通过 `grilling` 澄清设计、`domain-modeling` 维护术语和决策、`codebase-design` 比较模块接口，最终回到主流程。

## 跨会话原则

在阶段完成的边界，按下面顺序判断，第一个适用项优先：

| 判断 | 做法 | 原因 |
| --- | --- | --- |
| 后续仍需要完整推理，或剩余空间足够？ | 继续当前会话 | 保留原始讨论，避免摘要损失 |
| 当前上下文与下一项工作无关？ | 清空上下文，从任务单重新开始 | 适合相互独立的实施任务 |
| 要换工具、目录、协作者，或在阶段中途分出支线？ | `handoff` | 生成可以随工作迁移的 Markdown |
| 工作范围明确，能独立完成？ | 后台子任务 | 返回结果，主会话继续 |
| 同环境内仍需相关上下文和用户参与，但空间不足？ | 在阶段边界压缩 | 告诉摘要下一阶段要做什么 |

澄清、Spec 和拆票尽量保持连续上下文；Handoff 只引用已有 Issue、ADR、提交和文件。`clear`、`compact` 是上游路线中的会话操作，不属于这 25 个 Skill，具体能力和语法取决于宿主工具。上游约 150k tokens 的 smart zone 是经验估计，不是通用模型限制。[阶段边界决策树](https://github.com/mattpocock/skills/blob/3cca18b368ae95cdbdebbff572ccafa662551015/skills/engineering/ask-matt/PHASE-BOUNDARIES.md)

## 需要额外输入时

- `to-questionnaire`：先明确问卷给谁、要拿回哪些事实或决定，再生成问卷；它不会要求你回答只有收件人才知道的内容。
- `wizard`：把必须由人完成的步骤变成交互式 Bash 向导，展示阶段进度；生成后供用户运行，适合操作权限或第三方界面成为阻塞时。
- `wait-what`：修复一次没有讲明白的表达，补上背景并使用已有领域词汇。上游正文指定简化技术英语，中文项目可按自己的语言约定改写此要求。

这些工具的输入、输出和源代码见 [Skill 图鉴](skills-analysis.md)。

## 常见误用

- 模糊需求直接 `implement`：实现过程会替用户暗自做决定。
- 把 `to-tickets` 生成的任务再次 `triage`：重复治理已经明确的工作。
- 把所有测试一次写完：测试了想象中的结构，而不是逐步发现的行为。
- 把原型合入主分支：把验证工具误当成生产实现。
- 用 `CONTEXT.md` 记录数据库字段和函数名：把术语表污染成实现笔记。
