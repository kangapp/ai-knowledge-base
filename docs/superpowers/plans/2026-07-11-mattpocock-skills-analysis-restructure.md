# mattpocock/skills 分析信息架构重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有 mattpocock/skills 专题从“情境工作流优先”重构为“能力图鉴优先”，让用户先认识 21 个正式 Skill，再理解中间产物及协作关系。

**Architecture:** 三个现有文件继续各司其职：Markdown 是完整说明书，Mermaid 文档是五张关系图，HTML 是交互阅读入口。三者共享六类能力、21 个 Skill、产物词汇和五条典型流程；调用方式与上游目录只作为属性或附录，不再主导导航。

**Tech Stack:** Markdown、Mermaid、HTML5、原生 CSS、原生 JavaScript、Python 标准库验证、Node.js 语法检查、Mermaid CLI 临时渲染、pytest。

## Global Constraints

- 上游事实固定为提交 `391a2701dd948f94f56a39f7533f8eea9a859c87`。
- 主图鉴只包含插件正式暴露的 21 个 Skill；每个 Skill 恰好归入一个能力类型。
- 六类能力及成员必须与设计文档完全一致。
- `user-invoked` / `model-invoked` 仅为 Skill 属性，不作为一级分类。
- 所有 Skill 详情链接使用固定 SHA，不使用 `blob/main`。
- “输出”和“中间产物”分开描述。
- 产物关系只记录固定源码可支持的事实；推断关系明确标注。
- Wayfinder 的 Research Ticket 不画成 `/research` 的确定调用边。
- Setup/Triage 前置张力如实保留，不发明回退行为。
- `misc`、`personal`、`in-progress`、`deprecated` 只放附录。
- 不修改站点构建逻辑、分析列表模板、测试文件或其他项目文档。
- 不新增仓库依赖；Mermaid CLI 只允许临时运行。

## File Structure

- Modify: `docs/analysis/mattpocock-skills/skills-analysis.md` — 完整 Skill、产物、矩阵和协作说明书。
- Modify: `docs/analysis/mattpocock-skills/skills-workflow-diagram.md` — 五张能力、产物和协作关系图。
- Modify: `docs/analysis/mattpocock-skills/index.html` — 能力图鉴优先的交互页面。

---

### Task 1: 重写完整 Skill 与产物说明书

**Files:**

- Modify: `docs/analysis/mattpocock-skills/skills-analysis.md`

**Interfaces:**

- Consumes: 固定上游源码 `/tmp/mattpocock-skills`；设计文档中的六类能力、统一 Skill 字段、产物目录树和五条流程。
- Produces: Task 2 和 Task 3 必须复用的能力分类、21 个 Skill 详情、产物词汇、C/U/R 关系和流程口径。

- [ ] **Step 1: 重排 Markdown 一级结构**

  按以下顺序重写，不保留旧的“情境入口优先”顺序：

  ```text
  1. 快速认识
  2. 六类能力地图
  3. 21 个正式 Skill 图鉴
  4. 文件与产物图鉴
  5. Skill × 产物矩阵
  6. 五条协作流程与跨会话桥
  7. 安装、调用属性与已知前置条件
  8. 非正式 Skill 附录
  9. 固定快照来源
  ```

- [ ] **Step 2: 写六类能力地图**

  使用设计文档确认的六类能力。分类表中 21 个 Skill 必须恰好出现一次；分类说明只解释能力范围，不提前展开流程。

- [ ] **Step 3: 写 21 个统一 Skill 条目**

  每个 Skill 使用三级标题并覆盖：核心作用、适用场景、调用方式、输入、执行动作、输出、中间产物、依赖、协作关系、使用边界、固定源码。名称由标题承担，因此每项共有 10 个描述字段和 1 个固定源码字段。

  每个 Skill 的固定源码链接使用：

  ```text
  https://github.com/mattpocock/skills/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/skills/<bucket>/<skill>/SKILL.md
  ```

- [ ] **Step 4: 写文件与产物图鉴**

  按生命周期解释以下产物：

  ```text
  AGENTS.md / CLAUDE.md
  docs/agents/issue-tracker.md
  docs/agents/domain.md
  docs/agents/triage-labels.md
  CONTEXT.md
  CONTEXT-MAP.md
  docs/adr/NNNN-*.md
  Spec Issue
  Ticket Issues
  .scratch/<feature>/issues/NN-<ticket>.md
  Research Markdown
  Prototype branch
  Architecture HTML report
  handoff Markdown
  Tests
  Code commits
  Code Review report
  ```

  每项说明位置、创建者、更新者、消费者、内部结构、生命周期和作用。不存在更新者时明确写“无固定更新者”，不能虚构。

- [ ] **Step 5: 写 Skill × 产物矩阵**

  矩阵使用 `C`、`U`、`R`，至少覆盖项目配置、领域文档、ADR、Spec、Tickets、Research Markdown、Prototype branch、Architecture report、Handoff、Tests/Code、Review report。表后给出符号图例和证据边界。

- [ ] **Step 6: 写五条协作流程**

  依次写新功能、Bug 修复、大型模糊项目、外部请求治理、架构维护。每一步都写成 `Skill → 传递产物 → Skill/结果`；`handoff` 单独说明为任意流程可用的桥。

- [ ] **Step 7: 写参考与附录**

  将安装命令、Setup、调用属性、Setup/Triage 张力、目录状态和非正式 Skill 移到后部。保留固定快照来源，但不再写大篇幅仓库评价。

- [ ] **Step 8: 验证 Markdown 结构**

  Run:

  ```bash
  uv run python - <<'PY'
  from pathlib import Path
  import re
  text = Path('docs/analysis/mattpocock-skills/skills-analysis.md').read_text()
  skills = {
      'ask-matt', 'setup-matt-pocock-skills', 'grill-me', 'grill-with-docs',
      'grilling', 'prototype', 'triage', 'wayfinder', 'to-spec', 'to-tickets',
      'implement', 'tdd', 'diagnosing-bugs', 'code-review', 'domain-modeling',
      'codebase-design', 'improve-codebase-architecture', 'research', 'handoff',
      'teach', 'writing-great-skills',
  }
  headings = set(re.findall(r'^### `([^`]+)`$', text, re.M))
  assert headings == skills, (skills - headings, headings - skills)
  for skill in skills:
      block = re.search(rf'^### `{re.escape(skill)}`$(.*?)(?=^### `|^## |\Z)', text, re.M | re.S)
      assert block
      for label in ('核心作用','适用场景','调用方式','输入','执行动作','输出','中间产物','依赖','协作关系','使用边界','固定源码'):
          assert f'**{label}**' in block.group(1), (skill, label)
  assert 'Skill × 产物矩阵' in text
  assert all(name in text for name in ('新功能开发','Bug 修复','大型模糊项目','外部请求治理','架构维护'))
  assert 'blob/main' not in text
  print('Markdown: 21 skills with 11 fields, artifacts, matrix and five flows')
  PY
  ! rg -n '[T]BD|[T]ODO|待[补]充|待[确]认' docs/analysis/mattpocock-skills/skills-analysis.md
  ```

  Expected: 输出 `Markdown: 21 skills with 11 fields, artifacts, matrix and five flows`，占位符扫描无输出。

- [ ] **Step 9: Commit**

  ```bash
  git add docs/analysis/mattpocock-skills/skills-analysis.md
  git commit -m "docs: restructure skills analysis handbook"
  ```

### Task 2: 重绘能力、产物与协作关系图

**Files:**

- Modify: `docs/analysis/mattpocock-skills/skills-workflow-diagram.md`

**Interfaces:**

- Consumes: Task 1 的六类能力、产物名称、C/U/R 关系和五条流程。
- Produces: 五张可独立渲染的 Mermaid 图；Task 3 的 HTML 流程区复用相同关系。

- [ ] **Step 1: 删除旧的状态分层与调用依赖主图**

  不再用 user/model 调用方式或正式/非正式目录状态占据 Mermaid 主图；这些内容留在正文属性和附录。

- [ ] **Step 2: 绘制五张图**

  精确使用五个 Mermaid 围栏：

  1. 六类能力地图：六个 subgraph，21 个 Skill 恰好出现一次。
  2. 产物生命周期图：项目配置、长期知识、规划、设计研究、临时会话、实现验证六组产物，以及主要生产/消费关系。
  3. 新功能与 Bug 修复：两个独立 subgraph，共享实现、测试和审查节点；边标签写传递产物。
  4. 大型项目与外部请求治理：Wayfinder 和 Triage 两个 subgraph；Research Ticket 不画成 `/research` 调用。
  5. 架构维护与跨会话桥：Architecture report、领域文档、模块设计与 handoff Markdown。

- [ ] **Step 3: 为每张图补阅读说明**

  每张图前后用 2–4 句话解释：图解决什么问题、实线表示什么、哪些边是可选组合。正文不重复 Skill 详情。

- [ ] **Step 4: 验证五张图实际渲染**

  Run:

  ```bash
  tmpdir=$(mktemp -d)
  uv run python - "$tmpdir" <<'PY'
  from pathlib import Path
  import re, sys
  text = Path('docs/analysis/mattpocock-skills/skills-workflow-diagram.md').read_text()
  blocks = re.findall(r'```mermaid\n(.*?)```', text, re.S)
  assert len(blocks) == 5
  out = Path(sys.argv[1])
  for index, block in enumerate(blocks, 1):
      (out / f'diagram-{index}.mmd').write_text(block)
  print(out)
  PY
  for input in "$tmpdir"/*.mmd; do
    npx -y @mermaid-js/mermaid-cli -i "$input" -o "${input%.mmd}.svg"
  done
  test "$(find "$tmpdir" -name 'diagram-*.svg' -type f -size +0c | wc -l | tr -d ' ')" = 5
  rm -rf "$tmpdir"
  ```

  Expected: 五个非空 SVG，命令退出码为 0；仓库无新增依赖或渲染产物。

- [ ] **Step 5: Commit**

  ```bash
  git add docs/analysis/mattpocock-skills/skills-workflow-diagram.md
  git commit -m "docs: redraw skills and artifact relationships"
  ```

### Task 3: 重构能力图鉴型交互页面

**Files:**

- Modify: `docs/analysis/mattpocock-skills/index.html`

**Interfaces:**

- Consumes: Task 1 的六类能力、21 个 Skill 详情、产物图鉴和矩阵；Task 2 的五条协作关系。
- Produces: 站点发布的交互页面，不依赖外部运行时资源。

- [ ] **Step 1: 重排八个页面分区**

  使用以下顺序和标题：快速认识、能力地图、Skill 图鉴、文件与产物图鉴、Skill × 产物矩阵、Skill 协作流程、安装与调用参考、非正式 Skill 附录。

- [ ] **Step 2: 实现能力地图与筛选**

  六类能力使用真实 `<button>`。点击能力后只显示该类 Skill 卡片，并更新当前筛选的 `aria-pressed`；提供“全部”按钮恢复 21 项。筛选不得修改 URL、请求网络或依赖框架。

- [ ] **Step 3: 重构 21 个 Skill 数据**

  每条 `skillDetails` 包含：`title`、`ability`、`purpose`、`scenarios`、`invocation`、`input`、`actions`、`output`、`intermediates`、`requires`、`collaboration`、`boundary`、`source`。

  `source` 必须指向固定 SHA。页面默认卡片展示 purpose、scenarios、invocation、output、intermediates；详情抽屉展示全部字段。

- [ ] **Step 4: 实现文件与产物图鉴**

  展示生命周期目录树和产物详情。每项包含位置、创建者、更新者、消费者、内部结构、生命周期和作用；可用展开卡片，不复用 Skill 抽屉状态。

- [ ] **Step 5: 实现 Skill × 产物矩阵**

  桌面展示表格，移动端允许矩阵区域横向滚动。首列固定 Skill 名，单元格只显示 C/U/R 或空值；表格提供图例和可访问标题。

- [ ] **Step 6: 实现五条协作流程**

  使用 HTML/CSS 流程卡，边或步骤文字明确写出传递产物。`handoff` 以跨会话桥单独展示，不作为第六条业务流程。

- [ ] **Step 7: 保留并适配可访问性**

  保留详情抽屉的 Escape、遮罩、关闭按钮、Tab/Shift+Tab 焦点循环、关闭后焦点恢复和滚动锁。新增筛选按钮必须支持键盘，焦点轮廓保持不透明 `#2563eb`。

- [ ] **Step 8: 验证 HTML 结构、数据与脚本**

  Run:

  ```bash
  uv run python - <<'PY'
  from pathlib import Path
  import re
  text = Path('docs/analysis/mattpocock-skills/index.html').read_text()
  assert text.count('<section') == 8
  abilities = re.findall(r'data-ability-filter="([^"]+)"', text)
  assert set(abilities) >= {'all','navigation','discovery','planning','delivery','architecture','knowledge'}
  skills = set(re.findall(r'^\s{6}"([a-z][a-z0-9-]+)": \{', text, re.M))
  assert len(skills) == 21
  for skill in skills:
      block = re.search(rf'^\s{{6}}"{re.escape(skill)}": \{{(.*?)^\s{{6}}\}}', text, re.M | re.S)
      assert block
      for field in ('title','ability','purpose','scenarios','invocation','input','actions','output','intermediates','requires','collaboration','boundary','source'):
          assert re.search(rf'^\s{{8}}{field}:', block.group(1), re.M), (skill, field)
  assert text.count('/blob/391a2701dd948f94f56a39f7533f8eea9a859c87/') >= 21
  assert 'blob/main' not in text
  assert 'aria-pressed' in text and 'data-artifact-matrix' in text
  for token in ('Escape','Tab','lastTrigger.focus()','@media (max-width: 760px)'):
      assert token in text
  print('HTML: 8 sections, 6 filters, 21x13 skill data, matrix and accessible drawer')
  PY
  uv run python - <<'PY' | node --check -
  from pathlib import Path
  import re
  scripts = re.findall(r'<script>(.*?)</script>', Path('docs/analysis/mattpocock-skills/index.html').read_text(), re.S)
  assert len(scripts) == 1
  print(scripts[0])
  PY
  ```

  Expected: 输出 HTML 成功摘要；Node 语法检查退出码为 0。

- [ ] **Step 9: 浏览器验证**

  用临时服务器打开页面，检查：六类筛选与“全部”、21 张卡片、详情抽屉完整字段、产物展开、矩阵横向滚动、五条流程、1280px 与 740px 布局、鼠标与键盘焦点行为、控制台无 JavaScript 错误。

  Run:

  ```bash
  uv run python -m http.server 8765 --directory docs/analysis/mattpocock-skills
  ```

  Expected: `http://localhost:8765/index.html` 返回 200；验证结束后停止服务器并确认端口无监听。

- [ ] **Step 10: Commit**

  ```bash
  git add docs/analysis/mattpocock-skills/index.html
  git commit -m "docs: restructure interactive skills handbook"
  ```

### Task 4: 全专题一致性与发布回归验证

**Files:**

- Verify: `docs/analysis/mattpocock-skills/skills-analysis.md`
- Verify: `docs/analysis/mattpocock-skills/skills-workflow-diagram.md`
- Verify: `docs/analysis/mattpocock-skills/index.html`
- Test: `tests/test_site_builder.py`

**Interfaces:**

- Consumes: Tasks 1–3 的最终产物。
- Produces: 跨文件一致性、Mermaid、浏览器、站点发现和测试证据；不修改生产文件。

- [ ] **Step 1: 检查三文件统一口径**

  编写临时 Python 断言，从三文件提取六类能力与 21 个 Skill，确认分类成员一致；检查五条流程名称、固定 SHA、Setup/Triage 张力和非正式附录均存在。

- [ ] **Step 2: 检查 Markdown、HTML 与 Mermaid**

  Run:

  ```bash
  git diff --check
  ! rg -n '[T]BD|[T]ODO|待[补]充|待[确]认|blob/main' docs/analysis/mattpocock-skills
  ```

  Expected: 两条命令均退出码为 0，无错误输出。

- [ ] **Step 3: 运行站点构建测试**

  Run:

  ```bash
  uv run pytest tests/test_site_builder.py -q
  ```

  Expected: 全部通过。

- [ ] **Step 4: 运行完整常规测试**

  Run:

  ```bash
  uv run pytest -m "not integration and not e2e"
  ```

  Expected: 0 failures。

- [ ] **Step 5: 检查提交和工作树**

  Run:

  ```bash
  git status --short
  git log -5 --oneline
  ```

  Expected: 工作树干净；最近提交包含计划和三个专题重构提交。
