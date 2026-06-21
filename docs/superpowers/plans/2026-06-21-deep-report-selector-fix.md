# Deep Report Selector Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the brittle keyword-based Deep Report candidate gate with structured GitHub project classification, calibrated eligibility rules, and observable rejection diagnostics.

**Architecture:** GitHub Analyzer emits an optional `project_type` classification on `AnalyzedItem`. The Selector treats `coding_tool` plus Reviewer dimensions as hard eligibility rules, computes a score only to rank eligible candidates, and returns a compact diagnostic summary consumed by the Deep Report service events.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, SQLite/aiosqlite, existing LangGraph pipeline and structured event logging.

## Global Constraints

- Keep `project_type` optional on `AnalyzedItem`; non-GitHub analyzers and historical data must remain valid.
- Accept only the exact project types: `coding_tool`, `ai_infrastructure`, `framework`, `research`, `dataset`, `benchmark`, `resource_collection`, `other`.
- Missing or unknown `project_type` fails closed as `project_type_missing`; do not fall back to keyword detection.
- Eligibility requires approved verdict, Reviewer total ≥85, valid GitHub repo URL, `coding_tool`, `ai_relevance` ≥28, `developer_utility` ≥24, and no completed report in the last 7 days.
- Candidate score is `round(total_score * 0.7 + developer_utility * 0.6 + source_bonus)`, with source bonus 5 only for `github_ai_devtools`.
- Candidate score ranks eligible candidates and is not an eligibility threshold.
- Each reviewed item contributes to at most one rejection reason, evaluated in eligibility order.
- Do not change clone, inspection, report analysis, persistence, public API, or report version behavior.
- Do not add dependencies.

---

### Task 1: Add Structured GitHub Project Classification

**Files:**
- Modify: `src/graph/state.py`
- Modify: `src/graph/analyzers/base.py`
- Modify: `prompts/github_analyzer.md`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_prompt_regression.py`

**Interfaces:**
- Produces: `AnalyzedItem.project_type: str | None`
- Produces: `GITHUB_PROJECT_TYPES: tuple[str, ...]`
- Consumes: existing `parse_and_validate(raw, ref_url, source_item)` and common analyzer schema rendering.

- [ ] **Step 1: Add failing parser and prompt contract tests**

Add tests equivalent to:

```python
def test_parse_and_validate_preserves_project_type():
    raw = json.dumps({
        "title": "Goose",
        "summary": "可执行、编辑和测试代码的 Coding Agent",
        "tags": ["Agent"],
        "language": "zh",
        "project_type": "coding_tool",
    })

    result = parse_and_validate(raw, ref_url="https://github.com/aaif-goose/goose")

    assert result.project_type == "coding_tool"


def test_analyzed_item_allows_missing_project_type():
    item = AnalyzedItem(
        ref_url="https://example.com/article",
        title="Article",
        summary="Summary",
    )

    assert item.project_type is None


def test_github_prompt_defines_project_type_contract():
    content = (PROJECT_ROOT / "prompts/github_analyzer.md").read_text()

    for value in (
        "coding_tool",
        "ai_infrastructure",
        "framework",
        "research",
        "dataset",
        "benchmark",
        "resource_collection",
        "other",
    ):
        assert value in content
    assert "主要交付物" in content
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_analyzer.py::test_parse_and_validate_preserves_project_type \
  tests/test_analyzer.py::test_analyzed_item_allows_missing_project_type \
  tests/test_prompt_regression.py::test_github_prompt_defines_project_type_contract -q
```

Expected: failures because `project_type` and the prompt contract do not exist.

- [ ] **Step 3: Implement the minimal model and schema changes**

In `src/graph/state.py`, define:

```python
PROJECT_TYPES = (
    "coding_tool",
    "ai_infrastructure",
    "framework",
    "research",
    "dataset",
    "benchmark",
    "resource_collection",
    "other",
)


class AnalyzedItem(BaseModel):
    ...
    project_type: str | None = None
```

Keep the field optional rather than using a strict `Literal`, because unknown model output must reach the Selector and be reported as `project_type_missing` instead of causing Analyzer retries.

In `src/graph/analyzers/base.py`, extend `ANALYZED_SCHEMA_DESC` with the optional field:

```python
ANALYZED_SCHEMA_DESC = (
    '{"title": "string", "summary": "100-200字中文", '
    '"tags": ["标签1", "标签2"], "language": "zh|en", '
    '"project_type": "GitHub only: coding_tool|ai_infrastructure|framework|'
    'research|dataset|benchmark|resource_collection|other"}'
)
```

In `prompts/github_analyzer.md`, require one exact enum value and include these boundaries:

```text
project_type 必须根据仓库的主要交付物选择：
- coding_tool：直接服务于编码、代码理解/生成、测试、调试、IDE/CLI、开发自动化或 Coding Agent
- ai_infrastructure：通用 LLM 网关、向量库、Agent/RAG 平台或模型服务
- framework：通用编程、ML、深度学习或应用框架
- research：论文、研究实现或模型权重
- dataset：数据集或数据集构建
- benchmark：benchmark、leaderboard、evaluation suite 或 testbed
- resource_collection：awesome list、课程、教程、知识库或资源合集
- other：其他

按主要交付物分类，不因 topics 或偶然出现的关键词改变类型。
```

- [ ] **Step 4: Run analyzer and prompt tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_analyzer.py tests/test_prompt_regression.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/graph/state.py src/graph/analyzers/base.py prompts/github_analyzer.md tests/test_analyzer.py tests/test_prompt_regression.py
git commit -m "feat: classify GitHub analyzer projects"
```

---

### Task 2: Replace Keyword Eligibility with Structured Selector Rules

**Files:**
- Modify: `src/deep_reports/models.py`
- Modify: `src/deep_reports/selector.py`
- Rewrite focused fixtures/assertions in: `tests/test_deep_reports_selector.py`

**Interfaces:**
- Produces: `DeepReportSelection` with `candidate: DeepReportCandidate | None` and `diagnostics: dict`
- Produces: `select_deep_report_candidate(...) -> DeepReportSelection`
- Consumes: `AnalyzedItem.project_type`, `ReviewedItem.dimensions`, and `Database`.

- [ ] **Step 1: Add failing production-sample eligibility tests**

Create focused fixtures that explicitly model production outcomes:

```python
@pytest.mark.parametrize(
    ("repo", "reviewer_score", "ai_score", "utility_score"),
    [
        ("aaif-goose/goose", 93, 33, 27),
        ("upstash/context7", 95, 34, 28),
        ("rtk-ai/rtk", 92, 33, 27),
        ("DietrichGebert/ponytail", 87, 32, 24),
    ],
)
async def test_selector_accepts_production_coding_tools(
    db, repo, reviewer_score, ai_score, utility_score
):
    url = f"https://github.com/{repo}"
    result = await select_deep_report_candidate(
        db,
        [_raw(url, source_id="github_trending_hot")],
        [_analyzed(url, project_type="coding_tool")],
        [_reviewed(
            url,
            score=reviewer_score,
            dimensions={
                "ai_relevance": {"score": ai_score},
                "developer_utility": {"score": utility_score},
            },
        )],
    )

    assert result.candidate is not None
    assert result.candidate.repo_name == repo
```

Add parameterized rejection tests for every non-coding project type, missing/unknown type, each score threshold, invalid URL, non-GitHub source, and recent report.

- [ ] **Step 2: Run selector tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_deep_reports_selector.py -q
```

Expected: failures because the selector still returns a candidate directly and uses keyword capability gates.

- [ ] **Step 3: Add the selection result model**

In `src/deep_reports/models.py`:

```python
class DeepReportSelection(BaseModel):
    candidate: DeepReportCandidate | None = None
    diagnostics: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Implement ordered eligibility and dimension parsing**

In `src/deep_reports/selector.py`, remove the capability vocabulary and `_coding_capabilities()` eligibility path. Add:

```python
MIN_REVIEWER_SCORE = 85
MIN_AI_RELEVANCE_SCORE = 28
MIN_DEVELOPER_UTILITY_SCORE = 24
VALID_PROJECT_TYPES = set(PROJECT_TYPES)


def _dimension_score(reviewed: ReviewedItem, name: str) -> int:
    value = reviewed.dimensions.get(name, {})
    if not isinstance(value, dict):
        return 0
    try:
        return int(value.get("score", 0))
    except (TypeError, ValueError):
        return 0
```

Initialize diagnostics with every fixed rejection key. Process each item in this exact order:

```python
if reviewed.verdict != "approved": reject("not_approved")
elif reviewed.total_score < 85: reject("reviewer_score")
elif raw is None or analyzed is None or raw.source != "github": reject("not_github")
elif _repo_info(raw.url) is None: reject("invalid_repo_url")
elif analyzed.project_type not in VALID_PROJECT_TYPES: reject("project_type_missing")
elif analyzed.project_type != "coding_tool": reject("project_type")
elif ai_relevance < 28: reject("ai_relevance")
elif developer_utility < 24: reject("developer_utility")
elif await self._has_recent_report(repo_url): reject("recent_report")
else: eligible
```

Increment `approved_github` after valid GitHub URL resolution and before project type checks. Increment `eligible` only after all checks pass.

- [ ] **Step 5: Implement ranking-only candidate score**

Use:

```python
source_bonus = 5 if source_key == "github_ai_devtools" else 0
candidate_score = round(
    reviewed.total_score * 0.7
    + developer_utility * 0.6
    + source_bonus
)
```

Store `project_type`, `ai_relevance`, `developer_utility`, and score parts in candidate metadata. Return the first maximum so ties preserve input order.

- [ ] **Step 6: Run selector tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_deep_reports_selector.py -q
```

Expected: all selector tests pass, including production samples and one-reason diagnostics.

- [ ] **Step 7: Commit**

```bash
git add src/deep_reports/models.py src/deep_reports/selector.py tests/test_deep_reports_selector.py
git commit -m "fix: restore deep report candidate selection"
```

---

### Task 3: Expose Selector Diagnostics in Pipeline Events

**Files:**
- Modify: `src/deep_reports/service.py`
- Modify: `tests/test_deep_reports_pipeline.py`

**Interfaces:**
- Consumes: `select_deep_report_candidate(...) -> DeepReportSelection`
- Produces events: `deep.selector_skipped`, `deep.selector_done`
- Preserves: `run_deep_report_stage(...) -> DeepReportStageResult`

- [ ] **Step 1: Add failing event payload tests**

Update the no-candidate test to assert:

```python
event = await db.fetch_one(
    "SELECT payload FROM pipeline_events WHERE event = 'deep.selector_skipped'"
)
payload = json.loads(event["payload"])
assert payload["reviewed_total"] == 1
assert payload["eligible"] == 0
assert payload["rejected"]["not_github"] == 1
```

Update the success/clone-failure path to assert a `deep.selector_done` event appears before `deep.clone_start`, with:

```python
assert payload["candidate_score"] == expected_score
assert payload["project_type"] == "coding_tool"
assert payload["diagnostics"]["eligible"] == 1
```

Update monkeypatched selector functions to return `DeepReportSelection` rather than a bare candidate.

- [ ] **Step 2: Run pipeline tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_deep_reports_pipeline.py::test_deep_report_stage_skips_when_no_candidate \
  tests/test_deep_reports_pipeline.py::test_deep_report_stage_clone_failure_persists_failed_row_and_event -q
```

Expected: failures because event payloads and `deep.selector_done` do not exist.

- [ ] **Step 3: Implement service event integration**

Change selection handling to:

```python
selection = await select_deep_report_candidate(...)
candidate = selection.candidate
if candidate is None:
    await record_pipeline_event(
        ...,
        event="deep.selector_skipped",
        status="skipped",
        message="没有满足条件的深度报告候选",
        payload=selection.diagnostics,
    )
    return DeepReportStageResult(status="skipped", message="no candidate")

await record_pipeline_event(
    ...,
    event="deep.selector_done",
    level="success",
    status="done",
    source_id=candidate.source_id,
    source="github",
    source_detail=candidate.source_detail,
    ref_url=candidate.repo_url,
    title=candidate.title,
    message="已选择深度报告候选",
    payload={
        "candidate_score": candidate.candidate_score,
        "project_type": candidate.metadata.get("project_type"),
        "diagnostics": selection.diagnostics,
    },
)
```

- [ ] **Step 4: Run full Deep Report pipeline tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_deep_reports_pipeline.py -q
```

Expected: all tests pass with updated event sequences.

- [ ] **Step 5: Commit**

```bash
git add src/deep_reports/service.py tests/test_deep_reports_pipeline.py
git commit -m "feat: explain deep report candidate decisions"
```

---

### Task 4: Update Documentation and Run Regression Verification

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/codemap.md`
- Modify: `docs/task.md`
- Modify: `docs/bug-progress.md`

**Interfaces:**
- Documents: `project_type` classification, eligibility thresholds, ranking formula, and selector diagnostic events.
- Verifies: all affected analyzer, selector, pipeline, database, API, and prompt contracts.

- [ ] **Step 1: Update architecture and code map**

Replace references to keyword capability evidence and dual 85-point thresholds with:

```text
GitHub Analyzer classifies the repository's primary deliverable as project_type.
Deep Reports accepts only coding_tool projects whose Reviewer total is at least
85, ai_relevance at least 28, and developer_utility at least 24. Candidate score
only ranks eligible projects. Selector events expose aggregate rejection reasons.
```

- [ ] **Step 2: Record the production bug and completed task**

In `docs/bug-progress.md`, record:

- No automatic report after 2026-06-12.
- 123 `deep.selector_skipped` events.
- 27 of 29 approved GitHub projects rejected by English phrase matching.
- Root cause: mismatch between Chinese analyzer output/short descriptions and exact English vocabulary, compounded by an unreachable second score gate.
- Fix: structured project type, Reviewer dimension thresholds, ranking-only score, diagnostics.

In `docs/task.md`, add the completed repair and exact verification counts after running tests.

- [ ] **Step 3: Run targeted regression suites**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_deep_reports_selector.py \
  tests/test_deep_reports_pipeline.py \
  tests/test_analyzer.py \
  tests/test_prompt_regression.py -q
```

Expected: all pass.

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_deep_reports_analyzer.py \
  tests/test_deep_reports_db.py \
  tests/test_deep_reports_api.py \
  tests/test_repo_inspector.py -q
```

Expected: all pass.

- [ ] **Step 4: Run repository checks**

Run:

```bash
git diff --check
.venv/bin/python -m pytest -m "not integration and not e2e" -q
```

Expected: no diff errors and all non-integration/e2e tests pass.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture.md docs/codemap.md docs/task.md docs/bug-progress.md
git commit -m "docs: document deep report selector repair"
```
