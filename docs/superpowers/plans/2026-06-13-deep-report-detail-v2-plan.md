# Deep Report Detail V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将深度报告升级为面向采用决策的 V2 结构，展示架构、快速上手和部署流程图，提高 Coding 实用项目准入门槛，并安全重建后删除全部 V1 报告。

**Architecture:** `DeepReportOutput` 负责提供可校验、可绘图的结构化数据；日常 Pipeline 只生成 `report_version=2`。数据库允许同仓库同 commit 的 V1/V2 暂时并存，并用单行设置控制公开版本；批量重建完成后原子切换到 V2 并删除 V1。前端只渲染公开 V2，使用原生 HTML/CSS/SVG，不引入新依赖。

**Tech Stack:** Python 3.12、Pydantic v2、aiosqlite/SQLite、FastAPI、原生 JavaScript/CSS/SVG、pytest、uv

---

## 文件结构

- `src/deep_reports/models.py`：V2 报告模型及跨字段图关系校验。
- `src/deep_reports/analyzer.py`：V2 Schema 描述、解析和 JSON 修复提示。
- `prompts/deep_report.md`：采用决策型报告生成约束。
- `src/deep_reports/selector.py`：Coding 实用性分类、硬门槛和候选评分。
- `src/db/migrations/011_deep_report_v2.sql`：报告版本、公开版本设置和新版唯一约束。
- `src/db/operations.py`：版本化写入、公开版本查询、重建清理操作。
- `src/deep_reports/service.py`：日常 Pipeline 写入 V2 和 V2 Markdown 审计文本。
- `src/deep_reports/rebuild.py`：历史报告 dry-run、重建、失败重试、切换和静态站构建。
- `src/api/deep_reports.py`：继续暴露现有接口，查询逻辑由 DB 层限定公开版本。
- `src/site/static/js/deep-reports.js`：决策漏斗和结构化图形渲染。
- `src/site/static/css/style.css`：架构图、流程卡片和响应式布局。
- `src/site/templates/deep-report.html`：更新页面说明。
- `tests/test_deep_reports_*.py`：模型、候选、DB、Pipeline、重建和 API 测试。
- `tests/test_dashboard_frontend_contract.py`：V2 前端安全与渲染契约。
- `docs/*.md`：同步 API、数据模型、架构、代码地图和任务状态。

### Task 1: 定义并校验 V2 报告 Schema

**Files:**
- Modify: `src/deep_reports/models.py`
- Modify: `tests/test_deep_reports_analyzer.py`

- [ ] **Step 1: 将 analyzer 测试样例改为完整 V2 payload**

在 `tests/test_deep_reports_analyzer.py` 中让 `_valid_output_json()` 返回以下结构：

```python
{
    "title": "acme/agent-tool 深度报告",
    "summary": "面向开发者工作流的 Coding Agent。",
    "tech_stack": ["Python", "FastAPI"],
    "use_cases": ["仓库理解", "开发流程自动化"],
    "decision": {
        "recommendation": "适合需要可扩展 Coding Agent 的小型团队。",
        "reasons": ["入口清晰", "支持工作流编排"],
        "best_for": ["需要仓库级上下文的开发者"],
        "not_for": ["要求完全离线运行的团队"],
    },
    "architecture": {
        "pattern": "分层服务",
        "summary": "API 接收任务，Agent 编排层调用工具并返回结果。",
        "nodes": [
            {"id": "api", "label": "API", "role": "接收请求", "group": "interface"},
            {"id": "agent", "label": "Agent", "role": "编排任务", "group": "core"},
            {"id": "tools", "label": "Tools", "role": "执行开发工具", "group": "core"},
            {"id": "result", "label": "Result", "role": "输出结果", "group": "interface"},
        ],
        "edges": [
            {"source": "api", "target": "agent", "label": "任务"},
            {"source": "agent", "target": "tools", "label": "调用"},
            {"source": "tools", "target": "result", "label": "结果"},
        ],
    },
    "quick_start": {
        "prerequisites": ["Python 3.12", "模型 API Key"],
        "steps": [
            {"id": "install", "title": "安装", "description": "安装项目依赖"},
            {"id": "config", "title": "配置", "description": "设置模型密钥"},
            {"id": "run", "title": "启动", "description": "运行 CLI"},
        ],
        "expected_result": "CLI 返回代码分析结果。",
    },
    "deployment": {
        "prerequisites": ["可运行 Python 的主机"],
        "steps": [
            {"id": "prepare", "title": "准备环境", "description": "安装运行时"},
            {"id": "deploy", "title": "部署", "description": "安装依赖并配置服务"},
            {"id": "health", "title": "检查", "description": "验证服务可用"},
        ],
        "operations": ["监控模型调用失败", "定期更新依赖"],
    },
    "core_modules": [
        {"name": "API", "responsibility": "接收任务", "depends_on": ["Agent"]},
        {"name": "Agent", "responsibility": "编排工具", "depends_on": ["Tools"]},
    ],
    "runtime_data_flow": [
        {"id": "input", "title": "输入", "description": "用户提交开发任务"},
        {"id": "plan", "title": "规划", "description": "Agent 拆分任务"},
        {"id": "output", "title": "输出", "description": "返回执行结果"},
    ],
    "strengths": ["工作流边界清晰"],
    "limitations": ["依赖外部模型"],
    "actionable_takeaways": ["先用 CLI 验证核心工作流"],
    "source_evidence": [{"path": "src/main.py", "reason": "应用入口"}],
}
```

- [ ] **Step 2: 添加跨字段失败测试**

新增参数化测试，分别验证：

```python
payload["architecture"]["nodes"][1]["id"] = "api"  # 重复节点 ID
payload["architecture"]["edges"][0]["target"] = "missing"  # 无效引用
payload["architecture"]["edges"][0] = {"source": "api", "target": "api", "label": "loop"}  # 自环
payload["quick_start"]["steps"] = payload["quick_start"]["steps"][:2]  # 少于 3 步
payload["deployment"]["steps"] *= 3  # 超过 8 步
```

每种情况都应让 `parse_deep_report_output()` 抛出 `ValueError`。

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_deep_reports_analyzer.py -q
```

Expected: FAIL，旧模型缺少 `decision`、`quick_start`、`deployment`、`nodes` 等字段。

- [ ] **Step 4: 实现最小 V2 模型**

在 `src/deep_reports/models.py` 中新增：

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator


class FlowStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    title: str
    description: str


class DeepReportFlow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prerequisites: list[str]
    steps: list[FlowStep] = Field(min_length=3, max_length=8)

    @model_validator(mode="after")
    def validate_unique_step_ids(self):
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("flow step ids must be unique")
        return self


class DeepReportQuickStart(DeepReportFlow):
    expected_result: str


class DeepReportDeployment(DeepReportFlow):
    operations: list[str]
```

同时新增 `DeepReportDecision`、`ArchitectureNode`、`ArchitectureEdge`、`CoreModule`，并把 `DeepReportArchitecture.components` 改为 `summary/nodes/edges`。`nodes` 使用 `Field(min_length=4, max_length=10)`。在 `DeepReportArchitecture.model_validator` 中校验节点 ID 唯一、边引用存在且禁止自环。最后按规格文件定义完整 `DeepReportOutput`，所有模型保持 `extra="forbid"`。

- [ ] **Step 5: 运行模型测试**

Run:

```bash
uv run pytest tests/test_deep_reports_analyzer.py -q
```

Expected: 与模型解析相关的测试 PASS；Prompt Schema 断言可能仍 FAIL，留给 Task 2。

- [ ] **Step 6: 提交**

```bash
git add src/deep_reports/models.py tests/test_deep_reports_analyzer.py
git commit -m "feat: define deep report v2 schema"
```

### Task 2: 更新 Prompt、Schema 描述和修复重试

**Files:**
- Modify: `src/deep_reports/analyzer.py`
- Modify: `prompts/deep_report.md`
- Modify: `tests/test_deep_reports_analyzer.py`
- Test: `tests/test_prompt_regression.py`

- [ ] **Step 1: 添加 V2 Prompt 契约断言**

在 `test_prompt_template_contains_required_placeholders()` 中断言渲染结果包含：

```python
assert "采用决策" in rendered
assert "快速上手" in rendered
assert "部署运行" in rendered
assert "节点数量 4-10" in rendered
assert "步骤数量 3-8" in rendered
assert "源码证据不用于前台展示" in rendered
assert '"recommendation"' in rendered
assert '"nodes"' in rendered
assert '"quick_start"' in rendered
assert '"deployment"' in rendered
```

- [ ] **Step 2: 运行定向测试确认失败**

Run:

```bash
uv run pytest tests/test_deep_reports_analyzer.py::test_prompt_template_contains_required_placeholders -q
```

Expected: FAIL，旧 Prompt 与 Schema 描述没有 V2 字段。

- [ ] **Step 3: 替换 `DEEP_REPORT_SCHEMA_DESC`**

在 `src/deep_reports/analyzer.py` 中用与 Task 1 完全一致的嵌套字段生成描述。不要手写另一套字段名；定义普通 dict 后调用 `json.dumps(schema_description, ensure_ascii=False)`。修复消息继续引用同一常量：

```python
{
    "decision": {
        "recommendation": "string",
        "reasons": ["string"],
        "best_for": ["string"],
        "not_for": ["string"],
    },
    "architecture": {
        "pattern": "string",
        "summary": "string",
        "nodes": [{"id": "string", "label": "string", "role": "string", "group": "string|null"}],
        "edges": [{"source": "node_id", "target": "node_id", "label": "string"}],
    },
}
```

- [ ] **Step 4: 重写 Prompt 约束**

`prompts/deep_report.md` 明确：

- 读者是评估项目是否值得采用的开发者。
- 优先识别 Coding Agent、代码理解、IDE/CLI、测试调试、代码审查、Skill、MCP 和开发自动化价值。
- `quick_start` 与 `deployment` 必须分开。
- 架构节点 4-10 个，流程步骤 3-8 个。
- 边只能引用已声明节点。
- 证据不足时在 `limitations` 说明，不补造部署方式。
- `source_evidence` 只用于约束可信度，不面向前台读者。
- 总长度仍不超过 5000 个中文字符。

- [ ] **Step 5: 运行 Analyzer 和 Prompt 回归**

Run:

```bash
uv run pytest tests/test_deep_reports_analyzer.py tests/test_prompt_regression.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/deep_reports/analyzer.py prompts/deep_report.md tests/test_deep_reports_analyzer.py
git commit -m "feat: generate decision-oriented deep reports"
```

### Task 3: 收紧 Coding 实用候选规则

**Files:**
- Modify: `src/deep_reports/selector.py`
- Modify: `tests/test_deep_reports_selector.py`

- [ ] **Step 1: 添加硬门槛测试**

在 `tests/test_deep_reports_selector.py` 添加：

```python
@pytest.mark.asyncio
async def test_selector_requires_approved_and_reviewer_score_85(db):
    assert await select_with(verdict="retry", score=95) is None
    assert await select_with(verdict="approved", score=84) is None


@pytest.mark.asyncio
async def test_selector_requires_coding_capability(db):
    candidate = await select_with(
        title="General Knowledge RAG",
        description="knowledge graph rag search assistant",
        tags=["RAG", "Knowledge"],
        score=95,
        stars=50_000,
    )
    assert candidate is None
```

按现有 fixture/helper 形态实现 `select_with` 等价测试，不新建生产抽象。

- [ ] **Step 2: 添加允许方向测试**

参数化覆盖：

```python
[
    "coding agent for repository changes",
    "IDE extension for code review",
    "CLI debugger and test generator",
    "MCP server for developer tools",
    "reusable skill for coding workflow",
    "repository understanding and context builder",
]
```

每个样例在 Reviewer 85+、候选分 85+ 时应入选。

- [ ] **Step 3: 运行 Selector 测试确认失败**

Run:

```bash
uv run pytest tests/test_deep_reports_selector.py -q
```

Expected: FAIL，旧逻辑允许 `retry`、Reviewer 低分和泛 RAG 项目。

- [ ] **Step 4: 实现分类命中和新评分**

在 `selector.py` 中：

```python
MIN_REVIEWER_SCORE = 85
MIN_CANDIDATE_SCORE = 85

CODING_CAPABILITY_TERMS = {
    "coding_agent": {"coding agent", "code agent", "software agent"},
    "code_understanding": {"code understanding", "repository analysis", "repo context"},
    "developer_interface": {"ide extension", "editor extension", "developer cli"},
    "quality": {"test generator", "debugger", "code review", "lint"},
    "mcp_skill": {"mcp server", "mcp tool", "coding skill", "developer skill"},
    "automation": {"developer workflow", "build automation", "release automation"},
}

EXCLUDED_ONLY_TERMS = {
    "knowledge base",
    "general rag",
    "chatbot",
    "model weights",
    "dataset",
    "benchmark",
}
```

新增 `_coding_capabilities(raw, analyzed) -> set[str]`。选择时先检查：

```python
if reviewed.verdict != "approved":
    continue
if reviewed.total_score < MIN_REVIEWER_SCORE:
    continue
capabilities = _coding_capabilities(raw, analyzed)
if not capabilities:
    continue
```

评分固定为：

```python
score_parts = {
    "coding": min(40 + max(len(capabilities) - 1, 0) * 5, 45),
    "reviewer": int(reviewed.total_score * 0.35),
    "source": 10 if source_key == "github_ai_devtools" else 5,
    "readiness": min(_readiness_hits(raw, analyzed) * 2, 10),
}
```

`_readiness_hits()` 只统计明确可用信号：安装说明、CLI/IDE 入口、配置示例、Docker/包管理发布、测试或演示。stars 不再直接计分，只保留在 metadata 供展示；这样热度无法推动项目过线。`metadata` 保存 `coding_capabilities` 和 `score_parts`。删除 `knowledge/graph/rag` 作为独立实用命中的能力。

- [ ] **Step 5: 运行 Selector 测试**

Run:

```bash
uv run pytest tests/test_deep_reports_selector.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/deep_reports/selector.py tests/test_deep_reports_selector.py
git commit -m "feat: tighten deep report candidate selection"
```

### Task 4: 增加报告版本和公开版本切换

**Files:**
- Create: `src/db/migrations/011_deep_report_v2.sql`
- Modify: `src/db/operations.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_deep_reports_db.py`

- [ ] **Step 1: 添加迁移和并存测试**

测试 schema version 为 11，并验证：

```python
columns = await db.fetch_all("PRAGMA table_info(deep_reports)")
assert "report_version" in {row["name"] for row in columns}

setting = await db.fetch_one(
    "SELECT public_version FROM deep_report_settings WHERE id = 1"
)
assert setting["public_version"] == 1
```

再保存相同 `repo_url + commit_sha` 的 V1 和 V2，断言得到两个不同 ID。

- [ ] **Step 2: 添加公开版本查询测试**

先插入 V1/V2 completed，设置公开版本 1，断言 list/latest/detail 只返回 V1；调用 `set_public_deep_report_version(db, 2)` 后只返回 V2。详情查询 V1 ID 在公开版本 2 时返回 `None`。

- [ ] **Step 3: 运行 DB 测试确认失败**

Run:

```bash
uv run pytest tests/test_database.py tests/test_deep_reports_db.py -q
```

Expected: FAIL，缺少 migration 011 和版本参数。

- [ ] **Step 4: 编写 SQLite 迁移**

`011_deep_report_v2.sql` 使用 SQLite 表重建：

```sql
ALTER TABLE deep_reports RENAME TO deep_reports_v1;

CREATE TABLE deep_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_url            TEXT NOT NULL,
    repo_name           TEXT NOT NULL,
    article_id          INTEGER REFERENCES articles(id),
    run_id              TEXT REFERENCES pipeline_runs(id),
    commit_sha          TEXT NOT NULL DEFAULT '',
    status              TEXT NOT NULL,
    candidate_score     INTEGER NOT NULL DEFAULT 0,
    trigger_reason      TEXT NOT NULL DEFAULT '',
    report_json         TEXT NOT NULL DEFAULT '{}',
    report_markdown     TEXT NOT NULL DEFAULT '',
    evidence_json       TEXT NOT NULL DEFAULT '[]',
    tech_stack_json     TEXT NOT NULL DEFAULT '{}',
    file_tree_summary   TEXT NOT NULL DEFAULT '',
    analysis_cost       REAL NOT NULL DEFAULT 0,
    analysis_tokens     INTEGER NOT NULL DEFAULT 0,
    error               TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now', '+8 hours')),
    report_version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(repo_url, commit_sha, report_version)
);

INSERT INTO deep_reports (
    id, repo_url, repo_name, article_id, run_id, commit_sha, status,
    candidate_score, trigger_reason, report_json, report_markdown,
    evidence_json, tech_stack_json, file_tree_summary, analysis_cost,
    analysis_tokens, error, created_at, updated_at, report_version
)
SELECT
    id, repo_url, repo_name, article_id, run_id, commit_sha, status,
    candidate_score, trigger_reason, report_json, report_markdown,
    evidence_json, tech_stack_json, file_tree_summary, analysis_cost,
    analysis_tokens, error, created_at, updated_at, 1
FROM deep_reports_v1;

DROP TABLE deep_reports_v1;

CREATE TABLE deep_report_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    public_version INTEGER NOT NULL
);
INSERT INTO deep_report_settings (id, public_version) VALUES (1, 1);

CREATE INDEX idx_deep_reports_status_created
    ON deep_reports(status, created_at DESC);
CREATE INDEX idx_deep_reports_repo_url
    ON deep_reports(repo_url);
CREATE INDEX idx_deep_reports_run_id
    ON deep_reports(run_id);
CREATE INDEX idx_deep_reports_public
    ON deep_reports(report_version, status, updated_at DESC);

INSERT OR REPLACE INTO schema_version (version) VALUES (11);
```

- [ ] **Step 5: 修改 DB operations**

给 `save_deep_report()` 增加关键字参数 `report_version: int = 2`，INSERT 和 fallback SELECT 都带上版本。冲突目标改为：

```sql
ON CONFLICT(repo_url, commit_sha, report_version) DO UPDATE SET
    repo_name=excluded.repo_name,
    article_id=excluded.article_id,
    run_id=excluded.run_id,
    status=excluded.status,
    candidate_score=excluded.candidate_score,
    trigger_reason=excluded.trigger_reason,
    report_json=excluded.report_json,
    report_markdown=excluded.report_markdown,
    evidence_json=excluded.evidence_json,
    tech_stack_json=excluded.tech_stack_json,
    file_tree_summary=excluded.file_tree_summary,
    analysis_cost=excluded.analysis_cost,
    analysis_tokens=excluded.analysis_tokens,
    error=excluded.error,
    updated_at=excluded.updated_at
WHERE NOT (deep_reports.status = 'completed' AND excluded.status = 'failed')
```

新增：

```python
async def get_public_deep_report_version(db: Database) -> int:
    row = await db.fetch_one(
        "SELECT public_version FROM deep_report_settings WHERE id = 1"
    )
    return int(row["public_version"])


async def set_public_deep_report_version(db: Database, version: int) -> None:
    await db.execute(
        "UPDATE deep_report_settings SET public_version = ? WHERE id = 1",
        (version,),
    )
    await db.commit()
```

`get_completed_deep_report`、`get_latest_deep_report`、`list_completed_deep_reports` 全部 join/cross query 当前公开版本。列表字段加入 `report_version`。

- [ ] **Step 6: 运行 DB 测试**

Run:

```bash
uv run pytest tests/test_database.py tests/test_deep_reports_db.py -q
```

Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add src/db/migrations/011_deep_report_v2.sql src/db/operations.py tests/test_database.py tests/test_deep_reports_db.py
git commit -m "feat: version deep report persistence"
```

### Task 5: 让日常 Pipeline 持久化 V2

**Files:**
- Modify: `src/deep_reports/service.py`
- Modify: `tests/test_deep_reports_pipeline.py`

- [ ] **Step 1: 更新 Pipeline 报告 fixture**

用 Task 1 的模型构造 `_report()`，并将成功测试新增：

```python
assert report_row["report_version"] == 2
assert json.loads(report_row["report_json"])["decision"]["recommendation"]
assert "## 采用结论" in report_row["report_markdown"]
assert "## 快速上手" in report_row["report_markdown"]
assert "## 部署运行" in report_row["report_markdown"]
```

失败报告也断言 `report_version == 2`。

- [ ] **Step 2: 运行 Pipeline 测试确认失败**

Run:

```bash
uv run pytest tests/test_deep_reports_pipeline.py -q
```

Expected: FAIL，旧 Markdown renderer 访问 `components/data_flow`。

- [ ] **Step 3: 更新 Markdown 审计文本**

`render_report_markdown()` 只作为数据库审计/降级文本，按 V2 字段输出：

```python
sections = [
    f"# {report.title}",
    "## 采用结论",
    report.decision.recommendation,
    "## 架构",
    report.architecture.summary,
    "## 快速上手",
    *(f"{index}. {step.title}: {step.description}"
      for index, step in enumerate(report.quick_start.steps, start=1)),
    "## 部署运行",
    *(f"{index}. {step.title}: {step.description}"
      for index, step in enumerate(report.deployment.steps, start=1)),
]
```

保留证据段用于内部审计，但前端不渲染。

- [ ] **Step 4: 显式写入 V2**

成功和失败的 `save_deep_report()` 调用都传 `report_version=2`。事件 payload 增加：

```python
{"report_id": report_id, "candidate_score": candidate.candidate_score, "report_version": 2}
```

- [ ] **Step 5: 运行 Pipeline 测试**

Run:

```bash
uv run pytest tests/test_deep_reports_pipeline.py -q
```

Expected: PASS。

- [ ] **Step 6: 提交**

```bash
git add src/deep_reports/service.py tests/test_deep_reports_pipeline.py
git commit -m "feat: persist deep report v2 from pipeline"
```

### Task 6: 实现历史报告重建与 V1 清理命令

**Files:**
- Create: `src/deep_reports/rebuild.py`
- Create: `tests/test_deep_reports_rebuild.py`
- Modify: `src/db/operations.py`

- [ ] **Step 1: 添加 dry-run 测试**

创建两个 V1 completed 报告，调用：

```python
result = await rebuild_deep_reports(
    db,
    registry=None,
    dry_run=True,
    max_reports=None,
    repo_url=None,
)
assert result.planned == 2
assert result.completed == 0
assert await get_public_deep_report_version(db) == 1
assert await count_version(db, 1) == 2
assert await count_version(db, 2) == 0
```

- [ ] **Step 2: 添加成功、部分失败和重试测试**

使用注入的 `clone_and_inspect_fn`、`analyze_fn`：

- 全成功：写入两个 V2，切换公开版本 2，删除全部 V1。
- 一个失败：写入该仓库的 V2 failed 记录，其余仓库继续；结束后仍切换 V2 并删除全部 V1；结果包含失败 URL。
- `repo_url=` 单仓库重试：从 V2 failed 记录恢复仓库元数据，只处理指定仓库，成功后覆盖该 V2 failed 记录为 completed。
- `max_reports=1`：只处理一条，未完整处理全部 V1 时不得自动切换公开版本。

- [ ] **Step 3: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_deep_reports_rebuild.py -q
```

Expected: FAIL，模块不存在。

- [ ] **Step 4: 增加重建 DB helpers**

在 `operations.py` 新增：

```python
async def list_deep_reports_for_rebuild(
    db: Database,
    *,
    repo_url: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    conditions = ["report_version = 1", "status = 'completed'"]
    params: list = []
    if repo_url:
        conditions = ["repo_url = ?", "((report_version = 1 AND status = 'completed') OR (report_version = 2 AND status = 'failed'))"]
        params.append(repo_url)
    sql = "SELECT * FROM deep_reports WHERE " + " AND ".join(conditions) + " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = await db.fetch_all(sql, tuple(params))
    return [_deep_report_row(row) for row in rows]


async def delete_deep_reports_by_version(db: Database, version: int) -> None:
    await db.execute("DELETE FROM deep_reports WHERE report_version = ?", (version,))
    await db.commit()
```

列表只读取 `report_version=1 AND status='completed'`，按 ID 排序。

- [ ] **Step 5: 实现重建编排**

`src/deep_reports/rebuild.py` 定义 `RebuildResult(planned, completed, failed, switched)`，并实现以下签名：

`rebuild_deep_reports(db, registry, *, dry_run, max_reports, repo_url, max_cost=None, clone_and_inspect_fn=clone_and_inspect, analyze_fn=analyze_deep_report) -> RebuildResult`

函数体按以下确定顺序实现，不增加额外抽象：

1. 调用 `list_deep_reports_for_rebuild()` 获取计划列表；`dry_run` 直接返回数量且不创建 run。
2. 使用 `run_id_bj("deep_rebuild")` 创建 run_id，并调用 `start_pipeline_run(db, run_id, "deep_report_rebuild")`。
3. 对每行构造 `DeepReportCandidate`，保留 `candidate_score/trigger_reason/article_id`。
4. 重新 clone 当前仓库、构建源码包并调用 V2 Analyzer。
5. 每次调用后以新 run_id 写入 cost log。
6. 成功时以 `status="completed", report_version=2` 保存。
7. 失败时以 `status="failed", report_version=2` 保存错误和可用源码包，加入 `failed`。
8. 累计成本达到 `max_cost` 时停止，并禁止自动切换。
9. 满足完整运行条件时，在一个事务内切换公开版本并删除 V1。
10. 正常结束调用 `end_pipeline_run(db, run_id, "completed", summary_json)`；编排级异常调用 `end_pipeline_run(db, run_id, "failed", str(exc))` 后重新抛出。

只有在“未设置 `max_reports`、未设置单仓库过滤、未触发成本上限”时才调用 `switch_public_deep_reports_to_v2(db)`。该函数直接使用 `db._conn` 执行 `BEGIN`、更新设置、删除 V1、`COMMIT`；异常时 `ROLLBACK` 后重新抛出。此处集中使用底层连接是为了保证切换与删除原子完成，不扩展通用 Database API。V2 failed 记录保留，供 `--repo` 重试。

- [ ] **Step 6: 增加命令行入口**

同文件使用 `argparse` 支持：

```bash
uv run python -m src.deep_reports.rebuild --dry-run
uv run python -m src.deep_reports.rebuild --max-reports 5 --max-cost 1.5
uv run python -m src.deep_reports.rebuild --repo https://github.com/org/repo
uv run python -m src.deep_reports.rebuild
```

CLI 加载 `config/llm.yaml`、`config/agents.yaml`、`data/kb.db`，初始化 `LLMRegistry`。完整切换后直接实例化 `SiteBuilder` 执行一次 `build()`。

- [ ] **Step 7: 运行重建测试**

Run:

```bash
uv run pytest tests/test_deep_reports_rebuild.py tests/test_deep_reports_db.py -q
```

Expected: PASS。

- [ ] **Step 8: 提交**

```bash
git add src/deep_reports/rebuild.py src/db/operations.py tests/test_deep_reports_rebuild.py
git commit -m "feat: rebuild and switch deep report versions"
```

### Task 7: 更新公开 API 的 V2 契约

**Files:**
- Modify: `tests/test_deep_reports_api.py`
- Modify: `src/api/deep_reports.py` only if routing changes are required

- [ ] **Step 1: 更新 API fixture**

`_save_report()` 默认传 `report_version=2`，并使用完整 V2 `report_json`。fixture 初始化后将公开版本设为 2。

- [ ] **Step 2: 添加版本隔离断言**

创建 V1 和 V2 报告，公开版本设为 2：

```python
assert body["data"]["items"][0]["report_version"] == 2
assert latest["data"]["report_version"] == 2
assert detail["data"]["report_json"]["decision"]["recommendation"]
assert client.get(f"/api/deep-reports/{v1_id}").status_code == 404
```

源码证据仍可存在于详情 JSON，不在 API 层删除。

- [ ] **Step 3: 运行 API 测试**

Run:

```bash
uv run pytest tests/test_deep_reports_api.py -q
```

Expected: PASS；若 FAIL，应只修改 DB query 或最小路由契约，不在 API 中重复版本判断。

- [ ] **Step 4: 提交**

```bash
git add tests/test_deep_reports_api.py src/api/deep_reports.py
git commit -m "test: enforce public deep report version"
```

### Task 8: 重构详情页为决策漏斗和流程图

**Files:**
- Modify: `src/site/static/js/deep-reports.js`
- Modify: `src/site/static/css/style.css`
- Modify: `src/site/templates/deep-report.html`
- Modify: `tests/test_dashboard_frontend_contract.py`

- [ ] **Step 1: 将前端契约测试改为 V2**

删除对 `report.data_flow`、`architecture.components`、`renderEvidenceItems()` 和 Markdown fallback 的长期兼容断言，新增：

```python
assert "report.decision" in script
assert "report.architecture" in script
assert "report.quick_start" in script
assert "report.deployment" in script
assert "report.core_modules" in script
assert "report.runtime_data_flow" in script
assert "function renderArchitectureDiagram" in script
assert "function renderFlow" in script
assert "source_evidence" not in render_structured_report_block
assert "report_version" in script
assert ".deep-architecture-diagram" in styles
assert ".deep-flow" in styles
assert "@media (max-width: 700px)" in styles
```

保留 `escapeHtml`、`safeHttpUrl`、严格正整数 ID 和 envelope 错误处理断言。

- [ ] **Step 2: 运行前端契约测试确认失败**

Run:

```bash
uv run pytest tests/test_dashboard_frontend_contract.py -q
```

Expected: FAIL，页面仍是 V1 罗列。

- [ ] **Step 3: 增加 V2 归一化 helpers**

在 `deep-reports.js` 中新增：

```javascript
function normalizeFlow(value) {
    const flow = asObject(value);
    const steps = Array.isArray(flow.steps)
        ? flow.steps.map(asObject).filter(step => asString(step.id) && asString(step.title))
        : [];
    return {
        prerequisites: asStringList(flow.prerequisites),
        steps,
        expectedResult: asString(flow.expected_result),
        operations: asStringList(flow.operations),
    };
}
```

架构归一化只接受 plain object、唯一节点 ID、引用存在且非自环的边。无效边丢弃；节点不足时走卡片降级。

- [ ] **Step 4: 实现页面顺序**

`renderStructuredReport()` 按以下顺序拼接：

```javascript
renderDecision(report.decision)
renderUseCases(report.use_cases)
renderArchitectureDiagram(report.architecture)
renderFlow("快速上手", report.quick_start, "expected_result")
renderFlow("部署运行", report.deployment, "operations")
renderCoreModules(report.core_modules)
renderFlow("运行时数据流", { steps: report.runtime_data_flow })
renderAdoptionNotes(report.strengths, report.limitations, report.actionable_takeaways)
```

当 `item.report_version !== 2` 时显示“报告正在升级，请稍后查看”，不再渲染 V1 Markdown。

- [ ] **Step 5: 实现简单 SVG 架构图**

`renderArchitectureDiagram()` 同时生成 SVG 和节点卡片容器，使用确定性分层：

- 按节点数组顺序分配列。
- 桌面端 viewBox 横向布局。
- 每个节点使用 `<g><rect/><text/></g>`。
- 边使用 `<line marker-end="url(#arrow)">`。
- 所有 label/role/edge 文本先 `escapeHtml()`。
- 4 个以下有效节点时只输出 `.deep-architecture-cards`，不画 SVG。

不要实现拖拽、缩放或通用图布局。

- [ ] **Step 6: 增加响应式 CSS**

新增：

```css
.deep-decision-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.deep-architecture-diagram { width: 100%; overflow-x: auto; }
.deep-architecture-diagram svg { display: block; min-width: 720px; width: 100%; }
.deep-architecture-cards { display: none; }
.deep-flow { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; }
.deep-flow-step { position: relative; min-width: 0; }
.deep-module-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; }
```

在 700px media query 中让决策区和流程单列，并使用以下确定规则：

```css
.deep-architecture-diagram { display: none; }
.deep-architecture-cards { display: grid; gap: 0.75rem; }
```

因此桌面展示 SVG，移动端展示同一批节点的职责卡片，页面本身不产生横向溢出。

- [ ] **Step 7: 更新详情模板说明**

将副标题改为：

```html
<p class="page-subtitle">从采用结论、系统架构、快速上手和部署运行四个层面评估项目。</p>
```

- [ ] **Step 8: 运行前端契约测试**

Run:

```bash
uv run pytest tests/test_dashboard_frontend_contract.py -q
```

Expected: PASS。

- [ ] **Step 9: 构建并浏览器验证**

启动应用并调用现有构建接口：

```bash
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
curl -X POST http://127.0.0.1:8000/api/pipeline/build
```

第一条命令在持续 PTY 会话中运行，第二条在另一个命令调用中执行；验证结束后停止服务。

用 Browser 打开已知本地站点，验证：

- 桌面端采用结论、架构、快速上手、部署和技术细节顺序正确。
- 390px 宽度无页面级横向滚动。
- 源码证据不在 DOM。
- 无效边数据降级但页面其余部分可用。

- [ ] **Step 10: 提交**

```bash
git add src/site/static/js/deep-reports.js src/site/static/css/style.css src/site/templates/deep-report.html tests/test_dashboard_frontend_contract.py
git commit -m "feat: render deep report decision flows"
```

### Task 9: 文档同步与完整验收

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/data-model.md`
- Modify: `docs/api.md`
- Modify: `docs/codemap.md`
- Modify: `docs/task.md`
- Modify: `docs/structure.md` only if the new rebuild module is included in the tree

- [ ] **Step 1: 更新数据模型**

`docs/data-model.md` 记录：

- schema version 11。
- `report_version`。
- `UNIQUE(repo_url, commit_sha, report_version)`。
- `deep_report_settings` 单行公开版本。
- V1/V2 临时并存与最终清理口径。

- [ ] **Step 2: 更新 API 和架构**

`docs/api.md` 记录公开 API 只返回当前 `public_version` 的 completed 报告，并返回 `report_version`。

`docs/architecture.md` 记录：

- V2 决策报告数据流。
- 两个 85 硬门槛和 Coding 能力硬匹配。
- 批量重建、版本切换和 V1 清理。
- 原生 SVG/HTML 流程图渲染。

- [ ] **Step 3: 更新代码地图和任务状态**

`docs/codemap.md` 增加 `src/deep_reports/rebuild.py` 入口；更新 selector、models、service 和前端职责。`docs/task.md` 增加本次任务清单，完成后逐项勾选。若 `docs/structure.md` 包含完整目录树，加入 `rebuild.py`。

- [ ] **Step 4: 运行深度报告测试集**

Run:

```bash
uv run pytest \
  tests/test_deep_reports_analyzer.py \
  tests/test_deep_reports_selector.py \
  tests/test_deep_reports_db.py \
  tests/test_deep_reports_pipeline.py \
  tests/test_deep_reports_rebuild.py \
  tests/test_deep_reports_api.py \
  tests/test_dashboard_frontend_contract.py \
  tests/test_prompt_regression.py -q
```

Expected: PASS。

- [ ] **Step 5: 运行 CI 测试集**

Run:

```bash
uv run pytest -m "not integration and not e2e"
```

Expected: PASS。

- [ ] **Step 6: 检查 diff**

Run:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` 无输出；状态只包含本任务预期文件。

- [ ] **Step 7: 提交文档**

```bash
git add docs/architecture.md docs/data-model.md docs/api.md docs/codemap.md docs/task.md docs/structure.md
git commit -m "docs: document deep report v2"
```

## 生产执行顺序

代码部署并完成 migration 011 后：

1. 预览待重建报告：

```bash
docker compose exec pipeline uv run python -m src.deep_reports.rebuild --dry-run
```

2. 执行完整重建：

```bash
docker compose exec pipeline uv run python -m src.deep_reports.rebuild
```

3. 命令成功输出应包含：

```text
planned=<N> completed=<M> failed=<K> switched=true
```

4. 若有失败仓库，修复上游问题后逐个重试：

```bash
docker compose exec pipeline uv run python -m src.deep_reports.rebuild --repo https://github.com/org/repo
```

5. 验证公开版本和旧报告清理：

```bash
docker compose exec pipeline uv run python -c "
import asyncio
from src.core.database import Database
async def main():
    db = Database('data/kb.db', 'src/db/migrations')
    await db.initialize()
    setting = await db.fetch_one('SELECT public_version FROM deep_report_settings WHERE id = 1')
    old = await db.fetch_one('SELECT COUNT(*) AS c FROM deep_reports WHERE report_version = 1')
    print({'public_version': setting['public_version'], 'v1_count': old['c']})
    await db.close()
asyncio.run(main())
"
```

Expected:

```text
{'public_version': 2, 'v1_count': 0}
```
