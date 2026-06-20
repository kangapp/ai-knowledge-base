# Article Detail Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将文章列表改为“快速扫描 + 详情抽屉”，同时保留可分享的独立详情页，并让两种详情形态复用同一套安全渲染逻辑。

**Architecture:** `/api/articles/{id}` 返回文章、标准化四维评分和关联的公开深度报告摘要。`article-detail.js` 负责请求、DOM 安全渲染、抽屉交互和独立页初始化；首页只提供抽屉容器，独立页只提供详情容器。列表仍保留 `/article.html?id=...` 链接，普通点击由抽屉接管，修饰键和新窗口行为不受影响。

**Tech Stack:** Python 3.12、FastAPI、aiosqlite、Jinja2、原生 JavaScript、CSS、pytest

## Global Constraints

- 始终使用中文界面文案。
- 不新增第三方依赖。
- 只展示公开版本且 `status='completed'` 的深度报告。
- 所有 API 数据通过 DOM API 和 `textContent` 渲染，不直接拼接未转义 HTML。
- 列表负责扫描，详情负责解释，深度报告负责深入。

---

### Task 1: 扩展文章详情 API

**Files:**
- Modify: `src/db/operations.py`
- Modify: `src/api/routes.py`
- Test: `tests/test_api_contracts.py`

**Interfaces:**
- Produces: `operations.get_article_detail(db: Database, article_id: int) -> dict | None`
- API adds: `dimensions: dict` and `deep_report: dict | None`

- [x] 写 API 契约测试：详情返回标准化四维评分、标签和公开深度报告摘要。
- [x] 运行目标测试，确认因字段缺失而失败。
- [x] 实现最小 SQL 查询与 JSON 标准化。
- [x] 运行 API 契约测试，确认通过。

### Task 2: 建立共享详情渲染器

**Files:**
- Create: `src/site/static/js/article-detail.js`
- Modify: `src/site/templates/base.html`
- Modify: `src/site/templates/article.html`
- Test: `tests/test_site_builder.py`

**Interfaces:**
- Produces: `window.ArticleDetail.mountPage(container)`、`openDrawer(articleId)`、`closeDrawer()`
- Consumes: `GET /api/articles/{id}`

- [x] 写静态契约测试：共享脚本被加载，独立页不再内联拼接 API 字段，并包含详情挂载点。
- [x] 运行目标测试，确认失败。
- [x] 用 DOM API 实现标题、摘要、原始简介、标签、时间、评分维度、原文和深度报告入口。
- [x] 实现加载、无 ID、404、网络错误状态。
- [x] 运行目标测试，确认通过。

### Task 3: 首页详情抽屉与列表信息分层

**Files:**
- Modify: `src/site/templates/index.html`
- Modify: `src/site/static/js/app.js`
- Modify: `src/site/static/css/style.css`
- Modify: `src/site/builder.py`
- Test: `tests/test_site_builder.py`

**Interfaces:**
- Article links keep canonical href: `/article.html?id={id}`
- Normal click opens drawer; modified click follows the link.

- [x] 写失败测试：首页有抽屉容器、文章链接标识和较短的 `list_summary`。
- [x] 运行目标测试，确认失败。
- [x] 增加抽屉结构、焦点恢复、遮罩/关闭按钮/Escape 关闭和移动端样式。
- [x] 列表摘要限制为 120 字并使用三行截断，详情仍读取完整 API 摘要。
- [x] 运行站点构建测试，确认通过。

### Task 4: 文档与完整验证

**Files:**
- Modify: `docs/api.md`
- Modify: `docs/architecture.md`
- Modify: `docs/codemap.md`

- [x] 更新文章详情 API 字段和前端渲染策略。
- [x] 运行文章详情相关测试。
- [x] 运行非 integration/e2e 全量测试。
- [x] 构建静态站并用浏览器验证桌面与移动端抽屉、独立详情页及错误状态。
- [x] 检查 diff，确认没有无关改动。
