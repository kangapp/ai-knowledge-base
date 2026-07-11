# mattpocock/skills 浏览器手册实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 mattpocock/skills 专题改为只描述上游 `main` 最新版、可从“分析”Tab 完整阅读的中文交互手册。

**Architecture:** Markdown 是唯一正文源，`topic.yaml` 声明页面顺序与输出路径；`SiteBuilder` 使用成熟 Markdown 渲染库和 Jinja2 统一模板生成专题 HTML。共享 CSS/JavaScript 提供详情抽屉、折叠、流程节点与锚点导航，正文在 JavaScript 失效时仍可读。

**Tech Stack:** Python 3.12、Jinja2、Markdown 渲染库、PyYAML、HTML5、原生 CSS/JavaScript、pytest。

## Global Constraints

- 只描述 `mattpocock/skills` 当前 `main` 最新提交，页脚记录提交哈希与核对日期，不展示历史版本对比。
- 通俗中文为主，英文术语只在首次出现时标注；Skill 名、文件名和标签保留原文。
- `index.html` 是专题总入口，全部内容必须能从网站内访问，不依赖本地编辑器。
- Markdown、配置、模板、共享资源和构建代码提交 Git；生成 HTML 只写入 `output/`。
- 文章收藏功能是全部文件与工作流示例的贯穿案例。
- 不修改其他分析专题的现有发布方式。

---

### Task 1: Markdown 专题构建能力

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/site/builder.py`
- Create: `src/site/templates/analysis-topic.html`
- Test: `tests/test_site_builder.py`

**Interfaces:**
- Consumes: `docs/analysis/<slug>/topic.yaml` 与其中声明的 Markdown 页面。
- Produces: `output/analysis/<slug>/<output>.html`，并让 `/analysis.html` 链接专题首页。

- [x] **Step 1: 写失败测试**

  构造含 `topic.yaml`、`README.md`、`usage-guide.md` 的临时专题，断言构建后生成 `index.html` 和 `usage-guide.html`，导航互链且正文 Markdown 已渲染。

- [x] **Step 2: 运行测试确认 RED**

  Run: `uv run pytest tests/test_site_builder.py::test_site_builder_renders_markdown_analysis_topic -q`

  Expected: 因当前构建器只复制文件、不会生成 HTML 而失败。

- [x] **Step 3: 最小实现**

  增加 Markdown 渲染依赖；在 `SiteBuilder` 中仅对存在 `topic.yaml` 的专题读取显式页面清单，渲染 Markdown 并套用 `analysis-topic.html`。保留无清单专题的原复制行为。

- [x] **Step 4: 运行测试确认 GREEN**

  Run: `uv run pytest tests/test_site_builder.py::test_site_builder_renders_markdown_analysis_topic -q`

  Expected: PASS。

### Task 2: 统一专题主题与交互

**Files:**
- Create: `src/site/static/css/analysis-topic.css`
- Create: `src/site/static/js/analysis-topic.js`
- Modify: `src/site/templates/analysis-topic.html`
- Test: `tests/test_site_builder.py`

**Interfaces:**
- Consumes: Markdown 生成的语义 HTML 与 `data-*` 增强标记。
- Produces: 统一导航、面包屑、目录、详情抽屉、折叠和流程节点交互。

- [x] **Step 1: 写失败的页面契约测试**

  断言专题页包含共享 CSS/JS、返回专题首页、上一页/下一页、抽屉容器、可访问关闭按钮和无脚本可读正文。

- [x] **Step 2: 运行测试确认 RED**

  Run: `uv run pytest tests/test_site_builder.py -k analysis_topic -q`

  Expected: 缺少主题与交互契约而失败。

- [x] **Step 3: 实现最小统一主题与渐进增强交互**

  卡片打开右侧抽屉；模板和示例使用 `<details>`；流程节点原地展开；Escape、遮罩、关闭按钮和焦点恢复可用。核心正文不得仅存在于 JavaScript 数据中。

- [x] **Step 4: 运行测试确认 GREEN**

  Run: `uv run pytest tests/test_site_builder.py -k analysis_topic -q`

  Expected: PASS。

### Task 3: 重写最新版中文内容

**Files:**
- Create: `docs/analysis/mattpocock-skills/topic.yaml`
- Create: `docs/analysis/mattpocock-skills/README.md`
- Create: `docs/analysis/mattpocock-skills/usage-guide.md`
- Create: `docs/analysis/mattpocock-skills/file-management.md`
- Create: `docs/analysis/mattpocock-skills/examples/article-favorites.md`
- Modify: `docs/analysis/mattpocock-skills/skills-analysis.md`
- Modify: `docs/analysis/mattpocock-skills/skills-workflow-diagram.md`
- Delete: `docs/analysis/mattpocock-skills/index.html`

**Interfaces:**
- Consumes: 上游 `main` 最新 `README.md`、插件清单与正式 Skill 源码。
- Produces: 首页、使用指南、文件管理、Skill 参考、流程图和贯穿案例六类浏览器页面。

- [x] **Step 1: 获取并记录唯一上游基准**

  读取上游 `main` 当前提交及正式 Skill 清单，正文只保留最新版口径。

- [x] **Step 2: 写专题入口和工作流**

  `README.md` 提供场景入口、三分钟主流程、术语速查和全部页面导航；`usage-guide.md` 覆盖新功能、Bug、外部请求、大型项目、架构维护与跨会话。

- [x] **Step 3: 写文件管理与贯穿案例**

  每种产物说明目的、记录逻辑、内容结构、创建/读取/更新者、是否提交、清理规则、正确示例与常见错误；案例统一使用文章收藏功能。

- [x] **Step 4: 更新 Skill 参考和关系图**

  以最新版正式 Skill 为边界，删除旧提交和旧数量口径；全部页面由 `topic.yaml` 导航互联。

- [x] **Step 5: 验证无旧版口径和断链**

  Run: `rg -n '391a270|21 个正式|固定版本|历史版本' docs/analysis/mattpocock-skills`

  Expected: 无输出。

### Task 4: 文档与回归验证

**Files:**
- Modify: `docs/codemap.md`
- Test: `tests/test_site_builder.py`

**Interfaces:**
- Consumes: 完成后的构建行为与专题目录。
- Produces: 与实现一致的模块说明和验证证据。

- [x] **Step 1: 更新 codemap**

  记录 `topic.yaml` Markdown 专题发布、模板和共享资源职责。

- [x] **Step 2: 运行专题与构建器测试**

  Run: `uv run pytest tests/test_site_builder.py -q`

  Expected: 全部通过。

- [x] **Step 3: 构建静态站并核对输出**

  Run: 使用现有 SiteBuilder 测试夹具或项目构建入口生成站点，并检查六个专题页面、导航、CSS、JavaScript 和锚点链接存在。

- [x] **Step 4: 运行常规测试**

  Run: `uv run pytest -m "not integration and not e2e"`

  Expected: 全部通过。

