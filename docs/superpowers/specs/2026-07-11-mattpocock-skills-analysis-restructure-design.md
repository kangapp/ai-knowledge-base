# mattpocock/skills 分析信息架构重构设计

## 目标

重构 `docs/analysis/mattpocock-skills/` 的信息架构，让第一次接触该仓库的用户依次理解：

1. 有哪些正式 Skill，各自解决什么问题。
2. 单个 Skill 接收什么输入、执行什么动作、产生什么输出。
3. Skill 会创建或更新哪些中间文件、Issue、分支和报告。
4. 这些产物的内部结构、保存位置、生命周期与消费者。
5. Skill 如何通过产物协作成完整工作流。

当前专题以情境入口和 Idea-to-ship 工作流开场，读者在尚未认识 Skill 时就需要理解多个名称和依赖关系。本次重构将主叙事改为：

```text
认识 Skill → 理解输入输出 → 理解中间产物 → 理解 Skill 协作
```

研究事实继续固定到上游提交 `391a2701dd948f94f56a39f7533f8eea9a859c87`，不更新事实范围，不增加新的正式 Skill。

## 信息架构选择

采用“能力图鉴型”结构，不再以调用方式、目录桶或工作阶段作为一级分类。

- 能力类型负责帮助用户找到 Skill。
- `user-invoked` / `model-invoked` 是 Skill 属性。
- `engineering` / `productivity` 是上游目录属性。
- `misc` / `personal` / `in-progress` / `deprecated` 是附录中的维护状态。
- 工作流用于解释已经介绍过的 Skill 如何协作，放在 Skill 与产物图鉴之后。

## 六类能力与 21 个正式 Skill

每个正式 Skill 在主目录中只出现一次，避免重复分类。

| 能力类型 | Skill | 能力范围 |
|---|---|---|
| 导航与项目配置 | `ask-matt`、`setup-matt-pocock-skills` | 选择 Skill，建立 Issue Tracker、标签和领域文档配置 |
| 需求澄清与方案探索 | `grill-me`、`grill-with-docs`、`grilling`、`prototype` | 澄清模糊需求，用对话或可运行原型回答设计问题 |
| 请求治理与规划拆分 | `triage`、`wayfinder`、`to-spec`、`to-tickets` | 治理外部请求，探索大型工作，形成 Spec 与 Tickets |
| 实现、测试与审查 | `implement`、`tdd`、`diagnosing-bugs`、`code-review` | 实现代码，建立反馈环，修复问题，检查规格和代码质量 |
| 领域知识与架构设计 | `domain-modeling`、`codebase-design`、`improve-codebase-architecture` | 维护领域语言，设计深模块，发现架构改进机会 |
| 知识获取与跨会话协作 | `research`、`handoff`、`teach`、`writing-great-skills` | 调研、跨会话传递、持续教学和 Skill 编写方法 |

## Skill 图鉴

21 个 Skill 使用统一的数据结构，用户可以横向比较。

| 字段 | 说明 |
|---|---|
| 名称 | Skill 的正式名称 |
| 核心作用 | 一句话说明解决的问题 |
| 适用场景 | 用户何时应使用它 |
| 调用方式 | 用户主动或模型自动 |
| 输入 | 对话、代码、Issue、Spec、文件或配置 |
| 执行动作 | 读取、访谈、分析、写入、测试或审查 |
| 输出 | Skill 完成后的正式结果 |
| 中间产物 | 过程中创建、更新或传递的文件和状态 |
| 依赖 | 必需的配置、文件、工具或其他 Skill |
| 协作关系 | 通常从哪里来，下一步交给谁 |
| 使用边界 | 明确不负责的事情 |
| 固定源码 | 固定 SHA 对应的 `SKILL.md` |

HTML 默认展示名称、核心作用、适用场景、调用方式、输出和中间产物；点击后在详情抽屉展示其余字段。正文表格或分节说明必须覆盖全部字段。

“输出”和“中间产物”必须分开：输出是 Skill 结束时交付的结果；中间产物是后续 Skill 会读取、继续维护或用来跨会话传递的信息载体。

## 文件与产物图鉴

产物按生命周期分组：

```text
项目级配置
├── AGENTS.md / CLAUDE.md
└── docs/agents/
    ├── issue-tracker.md
    ├── domain.md
    └── triage-labels.md       # 安装 triage 时产生

长期领域知识
├── CONTEXT.md
├── CONTEXT-MAP.md             # 多上下文项目可选
└── docs/adr/
    └── NNNN-*.md

工作规划产物
├── Spec Issue
├── Ticket Issues
└── .scratch/<feature>/issues/
    └── NN-<ticket>.md

设计与研究产物
├── Research Markdown
├── Prototype branch
└── Architecture HTML report

临时会话产物
└── OS 临时目录/
    └── handoff-*.md

实现与验证产物
├── Tests
├── Code commits
└── Code Review report
```

每种产物说明以下信息：

| 字段 | 说明 |
|---|---|
| 名称 | 文件、Issue、分支或报告 |
| 路径/位置 | 实际保存位置或平台 |
| 创建者 | 首次创建它的 Skill |
| 更新者 | 会继续修改它的 Skill |
| 消费者 | 会读取它的后续 Skill |
| 内部结构 | 主要章节、字段或关系 |
| 生命周期 | 长期、阶段性、临时或一次性 |
| 作用 | 在协作链中解决的问题 |

增加一张 `Skill × 产物` 矩阵，使用以下关系标记：

- `C`：创建（Create）
- `U`：更新（Update）
- `R`：读取（Read）

矩阵只记录固定源码能够支持的关系；推断关系必须明确标注，不与源码事实混写。

## Skill 协作流程

协作图的连线必须标明传递的产物，不只绘制 Skill 名称之间的箭头。

### 新功能开发

```text
grill-with-docs
  → CONTEXT.md / ADR / 已确认需求
to-spec
  → Spec Issue
to-tickets
  → 带阻塞关系的 Tickets
implement
  → tdd：Tests + Code
  → code-review：Standards / Spec 审查结论
  → Commit
```

### Bug 修复

```text
diagnosing-bugs
  → 最小复现 / 反馈命令 / 根因
tdd
  → 失败的回归测试
implement
  → 修复代码
code-review
```

### 大型模糊项目

```text
wayfinder
  → Map Issue
  → Research Ticket / Prototype Ticket / Grilling Ticket
  → Decisions
to-spec → to-tickets → implement
```

Wayfinder 的 Research Ticket 是票据类型，不能画成源码明确调用 `/research`。如果展示二者的可能组合，必须标为可选路线或分析建议。

### 外部请求治理

```text
Incoming Issue / PR
  → triage
  → needs-info：Triage Notes
  → ready-for-agent：Agent Brief
  → ready-for-human：Human Brief
  → wontfix：Close / Out-of-scope record
```

### 架构维护

```text
improve-codebase-architecture
  → Architecture HTML report
grilling + domain-modeling
  → 已确认模块边界 / CONTEXT.md / ADR
codebase-design
  → 深模块接口与测试 Seam
  → 主开发流程
```

`handoff` 是任意流程可用的跨会话桥，不作为第六条业务流程：

```text
任意会话 → handoff Markdown → 新会话
```

## 页面结构

专题统一使用以下阅读顺序：

1. 快速认识：21 个正式 Skill、6 类能力和阅读顺序。
2. 能力地图：六类能力及包含的 Skill。
3. Skill 图鉴：21 张统一格式卡片与详情。
4. 文件与产物图鉴：真实目录树、内部结构和生命周期。
5. Skill × 产物矩阵：C/U/R 关系。
6. Skill 协作流程：五条典型流程与跨会话桥。
7. 安装与调用参考：安装、Setup、调用属性和已知前置张力。
8. 非正式 Skill 附录：非推广、开发中和废弃内容。

仓库评价、固定快照、调用模型和目录状态继续保留，但不再作为开场主叙事。

## 三个文件的职责

- `skills-analysis.md`：完整说明书，覆盖 Skill、产物、矩阵和协作说明。
- `skills-workflow-diagram.md`：能力地图、产物关系和五条协作流程，不重复展开仓库评价。
- `index.html`：交互阅读入口，默认突出能力地图与 Skill 图鉴，详情抽屉展示完整 Skill 卡片和相关产物。

不修改站点构建逻辑、分析列表模板或其他项目文档。

## 验证标准

1. 21 个正式 Skill 恰好归入一个能力类型，分类总数为 21。
2. 每个 Skill 覆盖统一详情结构中的全部字段。
3. 所有被提及的中间产物都有位置、创建者、更新者、消费者、内部结构、生命周期和作用。
4. `Skill × 产物` 矩阵的 C/U/R 关系可追溯到固定 SHA 源码。
5. 五条协作流程的连线都标明传递的产物。
6. `user-invoked` / `model-invoked` 只作为属性，不作为一级分类。
7. HTML 能按能力类型浏览 Skill，详情抽屉支持鼠标与键盘，移动端布局可读。
8. 五张协作/关系 Mermaid 图实际解析和渲染成功。
9. 上游 Setup/Triage 前置张力继续如实保留，不发明源码未定义的回退行为。
10. 固定源码链接继续使用提交 `391a2701dd948f94f56a39f7533f8eea9a859c87`。
11. 现有站点构建测试和常规测试通过。

## 不在本次范围内

- 修改或重新解释上游 Skill 行为。
- 安装、运行或更新上游 Skill。
- 将非正式目录中的 Skill 提升到主图鉴。
- 修改本项目站点的分析页发现机制。
- 新增搜索 API、数据库表或前端依赖。
