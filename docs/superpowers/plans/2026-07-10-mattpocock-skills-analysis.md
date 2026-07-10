# mattpocock/skills 专题分析实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `docs/analysis/mattpocock-skills/` 生成可发布的中文专题，详细解释 `mattpocock/skills` 的安装、调用模型、技能工作流、产物关系与信息架构。

**Architecture:** 采用“工作流主导、技能目录辅助”的双层信息架构。Markdown 正文负责完整论证，独立 Mermaid 文档负责关系图，单文件 HTML 负责情境路由、技能矩阵和交互式详情；三者共享同一上游快照与技能口径，但不引入生成脚本或运行时依赖。

**Tech Stack:** Markdown、Mermaid、HTML5、原生 CSS、原生 JavaScript、Python 标准库验证、现有 pytest 站点构建测试。

## Global Constraints

- 上游快照固定为 `391a2701dd948f94f56a39f7533f8eea9a859c87`，日期为 `2026-07-10`。
- 正式技能以 `.claude-plugin/plugin.json` 为准：21 个，其中用户调用 13 个、模型调用 8 个。
- 事实只引用上游 README、插件清单、`.agents/*.md`、`SKILL.md`、CHANGELOG 和同仓库一手资料。
- 不安装或运行上游技能，不修改本项目 `AGENTS.md`、站点构建逻辑和分析列表模板。
- 不新增依赖；HTML 必须自包含，移动端可读，并支持鼠标和键盘操作详情抽屉。
- `misc`、`personal`、`in-progress`、`deprecated` 只作为状态区说明，不混入正式技能推荐。

## File Structure

- Create: `docs/analysis/mattpocock-skills/skills-analysis.md` — 完整中文分析、技能目录、评价与来源索引。
- Create: `docs/analysis/mattpocock-skills/skills-workflow-diagram.md` — 五张 Mermaid 关系图及简短阅读说明。
- Create: `docs/analysis/mattpocock-skills/index.html` — 自包含交互式专题页，站点通过现有 `*/index.html` 规则自动发布。

---

### Task 1: 编写完整分析正文

**Files:**

- Create: `docs/analysis/mattpocock-skills/skills-analysis.md`

**Interfaces:**

- Consumes: 设计说明中的双层信息架构；上游提交 `391a270` 的 README、插件清单、调用规则、`ask-matt` 和各正式 `SKILL.md`。
- Produces: 后续 Mermaid 与 HTML 使用的统一术语、21 个正式技能口径、主流程、情境入口和产物定义。

- [ ] **Step 1: 写研究口径与结论摘要**

  创建文件并写明：固定提交与日期、正式技能统计、目录桶与插件暴露的区别，以及核心结论“目录树是维护视图，情境路由才是使用视图”。链接至少覆盖：仓库 README、`.claude-plugin/plugin.json`、`.agents/invocation.md`、`ask-matt/SKILL.md`。

- [ ] **Step 2: 写安装、Setup 与调用模型**

  包含准确命令：

  ```bash
  npx skills@latest add mattpocock/skills
  ```

  解释安装时选择 `/setup-matt-pocock-skills`，以及 Setup 对仓库探测、Issue Tracker、Triage Labels、Domain Docs 的配置流程。用表格对比 user-invoked 与 model-invoked，明确“用户调用技能可以组合模型调用技能；用户调用技能不能自动调用另一个用户调用技能”。

- [ ] **Step 3: 写主工作流、六个业务入口与跨会话桥**

  主链必须覆盖：

  ```text
  setup → grill-with-docs → [handoff → prototype → handoff]? →
  to-spec → to-tickets → implement → tdd → code-review → commit
  ```

  解释单会话小改动可从 `grill-with-docs` 直接进入 `implement`；多会话工作才生成 Spec 与 Tickets。六个业务入口分别覆盖新需求、Bug、外部 Issue/PR、超大模糊工作、架构维护、研究，并标明各自回到主链的位置；跨会话交接作为任意节点可用的桥单独说明。

- [ ] **Step 4: 写产物交接和正式技能目录**

  先用表格解释以下产物的生产者、消费者和生命周期：

  ```text
  docs/agents/issue-tracker.md
  docs/agents/triage-labels.md
  docs/agents/domain.md
  CONTEXT.md
  docs/adr/*.md
  Spec issue
  tracer-bullet tickets + blocking edges
  prototype branch / handoff Markdown / research Markdown
  tests / code-review report / commit
  ```

  再为插件清单中的 21 个技能逐项列出：调用方式、核心输入、核心输出、依赖、流程位置、边界。技能名必须完整覆盖：

  ```text
  ask-matt, diagnosing-bugs, grill-with-docs, triage,
  improve-codebase-architecture, setup-matt-pocock-skills, tdd,
  to-spec, to-tickets, wayfinder, implement, prototype, research,
  domain-modeling, codebase-design, code-review, grill-me, grilling,
  handoff, teach, writing-great-skills
  ```

- [ ] **Step 5: 写非正式状态、设计评价与本项目借鉴**

  记录六个目录桶的快照数量：engineering 17、productivity 5、misc 4、personal 2、in-progress 7、deprecated 4；说明正式插件清单未包含 `resolving-merge-conflicts`，但不武断判断原因。评价分开写“事实”和“分析判断”，至少覆盖组合性、人工决策门、上下文卫生、Issue Tracker 抽象、领域语言、反馈环、使用成本、版本漂移和工具能力假设。

  对本项目只提出结构借鉴：情境路由、产物契约、稳定性标签、证据快照、主流程与例外分离；不建议直接替换现有 `AGENTS.md`。

- [ ] **Step 6: 检查 Markdown 基础完整性**

  Run:

  ```bash
  test -s docs/analysis/mattpocock-skills/skills-analysis.md
  rg -n '[T]BD|[T]ODO|待补充|待确认' docs/analysis/mattpocock-skills/skills-analysis.md
  ```

  Expected: 第一条退出码为 0；第二条无输出、退出码为 1。

- [ ] **Step 7: Commit**

  ```bash
  git add docs/analysis/mattpocock-skills/skills-analysis.md
  git commit -m "docs: analyze mattpocock skills workflow"
  ```

### Task 2: 绘制工作流与产物关系图

**Files:**

- Create: `docs/analysis/mattpocock-skills/skills-workflow-diagram.md`

**Interfaces:**

- Consumes: Task 1 确立的情境、主流程、调用模式、产物与发布状态口径。
- Produces: 五张可独立阅读的 Mermaid 图，HTML 可按相同关系重新组织卡片。

- [ ] **Step 1: 写图表说明与情境路由图**

  图中使用六个入口节点：新需求、Bug、外部 Issue/PR、巨大模糊工作、架构维护、研究；分别连到 `grill-with-docs`、`diagnosing-bugs`、`triage`、`wayfinder`、`improve-codebase-architecture`、`research`。

- [ ] **Step 2: 写主流程图**

  使用带条件分支的 `flowchart LR` 表达 Setup 前置、Prototype 可选支路、单/多会话分支、逐 Ticket 清理上下文、Implement 内部 TDD 和结束前 Code Review。不要把 `tdd` 画成与 `implement` 平级的必经用户命令。

- [ ] **Step 3: 写调用依赖图**

  用两个 subgraph 区分 User-invoked 与 Model-invoked；只绘制实际存在的组合边，例如 `grill-with-docs → grilling/domain-modeling`、`implement → tdd/code-review`、`improve-codebase-architecture → codebase-design/grilling/domain-modeling`。

- [ ] **Step 4: 写产物交接图与状态分层图**

  产物图从 Setup 配置开始，经过 Glossary/ADR、Spec、Tickets、Code/Tests、Review/Commit。状态图明确插件正式暴露 21 个，另将非推广、开发中和废弃桶放在独立分支。

- [ ] **Step 5: 校验 Mermaid 围栏成对**

  Run:

  ```bash
  python - <<'PY'
  from pathlib import Path
  text = Path('docs/analysis/mattpocock-skills/skills-workflow-diagram.md').read_text()
  assert text.count('```mermaid') == 5
  assert text.count('```') == 10
  print('5 Mermaid diagrams, fences balanced')
  PY
  ```

  Expected: `5 Mermaid diagrams, fences balanced`。

- [ ] **Step 6: Commit**

  ```bash
  git add docs/analysis/mattpocock-skills/skills-workflow-diagram.md
  git commit -m "docs: diagram mattpocock skills workflows"
  ```

### Task 3: 构建交互式专题页面

**Files:**

- Create: `docs/analysis/mattpocock-skills/index.html`

**Interfaces:**

- Consumes: Task 1 的术语、技能清单和摘要；Task 2 的情境、流程、依赖与产物关系。
- Produces: 可被 `_html_title()` 发现并由现有站点复制到 `/analysis/mattpocock-skills/index.html` 的自包含页面。

- [ ] **Step 1: 写语义化 HTML 外壳和响应式样式**

  `<title>` 使用 `mattpocock/skills 使用工作流分析`。页面包含 `header`、八个编号 `section`、右侧 `dialog` 风格详情抽屉和遮罩。复用现有分析页的 `--ink`、`--blue`、`--green`、`--amber` 色义；桌面宽度不超过 1200px，`@media (max-width: 760px)` 下网格改单列、抽屉占满可用宽度。

- [ ] **Step 2: 写八个内容分区**

  分区顺序固定为：项目定位与快照、情境入口、端到端主流程、调用模型、产物交接链、正式技能矩阵、非正式状态区、关键判断与本项目借鉴。主流程用 HTML/CSS 卡片和箭头表达，不依赖 Mermaid CDN。

- [ ] **Step 3: 写 21 个技能详情数据**

  在脚本中的 `skillDetails` 对象为每个正式技能提供：`title`、`summary`、`invocation`、`input`、`output`、`requires`、`previous`、`next`、`source`。`source` 必须是对应 GitHub `blob/391a2701dd948f94f56a39f7533f8eea9a859c87/.../SKILL.md` 的 HTTPS 链接。

- [ ] **Step 4: 实现详情抽屉交互**

  所有可点击卡片使用真实 `<button type="button" data-detail="...">` 或可聚焦等价结构。点击和 Enter/Space 打开详情；关闭按钮、遮罩点击和 Escape 关闭；打开时保存触发元素并在关闭后恢复焦点。抽屉使用 `role="dialog"`、`aria-modal="true"`、`aria-labelledby`，隐藏时设置 `hidden`。

- [ ] **Step 5: 校验 HTML 结构与技能完整性**

  Run:

  ```bash
  python - <<'PY'
  from html.parser import HTMLParser
  from pathlib import Path
  import re

  path = Path('docs/analysis/mattpocock-skills/index.html')
  text = path.read_text()
  HTMLParser().feed(text)
  assert '<title>mattpocock/skills 使用工作流分析</title>' in text
  assert text.count('<section') == 8
  names = {
      'ask-matt', 'diagnosing-bugs', 'grill-with-docs', 'triage',
      'improve-codebase-architecture', 'setup-matt-pocock-skills', 'tdd',
      'to-spec', 'to-tickets', 'wayfinder', 'implement', 'prototype',
      'research', 'domain-modeling', 'codebase-design', 'code-review',
      'grill-me', 'grilling', 'handoff', 'teach', 'writing-great-skills',
  }
  keys = set(re.findall(r'^\s{6}"([a-z][a-z0-9-]+)": \{', text, re.M))
  assert keys == names, (names - keys, keys - names)
  for token in ('aria-modal="true"', 'Escape', 'lastTrigger.focus()', '@media (max-width: 760px)'):
      assert token in text
  print('HTML structure and 21 skill records verified')
  PY
  ```

  Expected: `HTML structure and 21 skill records verified`。

- [ ] **Step 6: Commit**

  ```bash
  git add docs/analysis/mattpocock-skills/index.html
  git commit -m "docs: add interactive mattpocock skills analysis"
  ```

### Task 4: 完成发布与内容验证

**Files:**

- Verify: `docs/analysis/mattpocock-skills/skills-analysis.md`
- Verify: `docs/analysis/mattpocock-skills/skills-workflow-diagram.md`
- Verify: `docs/analysis/mattpocock-skills/index.html`
- Test: `tests/test_site_builder.py`

**Interfaces:**

- Consumes: Tasks 1–3 的完整专题。
- Produces: 内容、HTML、发布发现和回归测试证据；不新增生产文件。

- [ ] **Step 1: 运行占位符、空白与链接静态检查**

  Run:

  ```bash
  git diff --check HEAD~3..HEAD
  rg -n '[T]BD|[T]ODO|待补充|待确认' docs/analysis/mattpocock-skills || true
  rg -o 'https://github.com/mattpocock/skills[^)" ]*' docs/analysis/mattpocock-skills | sort -u
  ```

  Expected: 前两条没有错误输出；第三条列出一手资料链接，且没有二手来源域名。

- [ ] **Step 2: 验证站点能发现专题标题与 URL**

  Run:

  ```bash
  uv run pytest tests/test_site_builder.py -q
  ```

  Expected: `tests/test_site_builder.py` 全部通过。

- [ ] **Step 3: 浏览器级检查静态页面**

  用本地静态服务器打开页面，检查桌面和 760px 以下布局、21 个技能按钮、详情抽屉的鼠标/键盘打开关闭、焦点恢复和 GitHub 源码链接。

  Run:

  ```bash
  python -m http.server 8765 --directory docs/analysis/mattpocock-skills
  ```

  Expected: `http://localhost:8765/index.html` 返回 200，控制台无 JavaScript 错误。

- [ ] **Step 4: 最终仓库检查**

  Run:

  ```bash
  git status --short
  git log -4 --oneline
  ```

  Expected: 工作树干净；最近提交包含设计和三个专题任务提交。
