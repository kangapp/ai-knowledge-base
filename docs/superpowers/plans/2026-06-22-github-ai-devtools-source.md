# GitHub AI 开发工具数据源优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提高 `github_ai_devtools` 对 AI Coding Tool 的召回率，并在采集阶段过滤明显非工具仓库。

**Architecture:** 复用现有 GitHub Collector 的五条独立查询、合并去重和本地排除能力，仅修改数据源配置及其契约测试。Reviewer、Analyzer 和 Deep Report Selector 均不改动。

**Tech Stack:** YAML、Python 3.12、pytest、Pydantic v2

## Global Constraints

- GitHub 查询数量保持五条。
- `lookback_type: pushed`、`lookback_days: 90`、`min_stars: 100`、`max_items: 10` 和 cron 保持不变。
- 不新增依赖、采集器分支或评分逻辑。
- Deep Report 质量门槛保持不变。

---

### Task 1: 更新 AI 开发工具数据源配置

**Files:**
- Modify: `tests/test_config.py`
- Modify: `config/sources.yaml`
- Modify: `docs/codemap.md`
- Modify: `docs/task.md`

**Interfaces:**
- Consumes: `load_sources_config(Path("config/sources.yaml"))`
- Produces: 五个用途型 GitHub Search 关键词及本地噪声排除词。

- [ ] **Step 1: 写失败的配置契约测试**

将 `test_project_sources_include_github_ai_devtools` 的关键词断言改为：

```python
assert source.config["keywords"] == [
    "coding agent",
    "AI coding assistant",
    "code generation",
    "AI code review",
    "AI IDE",
]
assert {
    "tutorial",
    "course",
    "awesome",
    "interview",
    "writeup",
    "write-ups",
}.issubset(set(source.config["exclude_terms"]))
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `uv run pytest tests/test_config.py::test_project_sources_include_github_ai_devtools -q`

Expected: FAIL，旧关键词与新预期不一致。

- [ ] **Step 3: 最小修改配置和引用文档**

将 `github_ai_devtools.config.keywords` 改为测试中的五个短语，并把六个噪声词加入 `exclude_terms`。同步更新 `docs/codemap.md` 的数据源说明，以及 `docs/task.md` 的任务记录。

- [ ] **Step 4: 运行定向测试**

Run: `uv run pytest tests/test_config.py::test_project_sources_include_github_ai_devtools tests/test_collector.py -q`

Expected: PASS。

- [ ] **Step 5: 运行完整 CI 测试集**

Run: `uv run pytest -m "not integration and not e2e"`

Expected: 全部通过，0 failures。

- [ ] **Step 6: 检查改动并提交**

Run: `git diff --check && git status --short`

Expected: 无空白错误，仅包含本任务文件。

Commit:

```bash
git add config/sources.yaml tests/test_config.py docs/codemap.md docs/task.md docs/superpowers/plans/2026-06-22-github-ai-devtools-source.md
git commit -m "fix: improve AI coding tool source queries"
```
