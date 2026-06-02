# GitHub Reviewer Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitHub AI tool repositories such as `Lum1104/Understand-Anything` pass through an appropriate repo-aware review path instead of being discarded by article-style depth criteria.

**Architecture:** Keep the existing pipeline shape unchanged: Collector -> Router -> Analyzer -> Aggregator -> Reviewer -> DB. Add a small review-context layer so reviewer can distinguish GitHub repos from articles, enrich GitHub review prompts with repo metadata, and use source-aware deterministic verdict thresholds. Do not add a new workflow node or database table for this change.

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph, FastAPI, SQLite, pytest, MiniMax-M3 through the existing OpenAI-compatible client.

---

## Current Root Cause

`Understand-Anything` was collected and analyzed successfully, but reviewer gave it low article-style depth scores:

- First observed review: `total=59`, `ai_relevance=30`, `content_depth=14`, `info_density=8`, `timeliness=7`, final verdict `discarded`.
- Second observed review: `total=55`, `ai_relevance=28`, `content_depth=13`, `info_density=7`, `timeliness=7`, final verdict `discarded`.

The current `_decide_verdict(total_score, ai_score, depth_score)` only approves when `total_score >= 80 and ai_score >= 30`. Scores from `60` to `79` become `retry`, not approved. Scores below `60` become discarded. That is reasonable for articles, but too harsh for GitHub repository cards where the available content is naturally README/repo metadata, not a deep article.

## File Structure

- Modify: `src/graph/state.py`
  - Add optional source/review context fields to `AnalyzedItem`, keeping compatibility with existing tests and persisted articles.
- Modify: `src/graph/analyzers/base.py`
  - Propagate `source`, `source_detail`, `source_id`, and selected GitHub metadata into `AnalyzedItem`.
- Modify: `src/graph/reviewer.py`
  - Add review context detection.
  - Load GitHub-specific prompt text.
  - Build richer reviewer input for GitHub repositories.
  - Split deterministic verdict policy by content kind.
- Create: `prompts/github_reviewer.md`
  - Repo-aware scoring rubric for AI GitHub tools.
- Modify: `prompts/reviewer.md`
  - Keep article/news/arXiv-oriented rubric, with a short note that GitHub repos use a different prompt.
- Modify: `tests/test_reviewer.py`
  - Add unit tests for source-aware verdict policy and GitHub prompt input.
- Modify: `tests/test_pipeline.py`
  - Add a small pipeline-style test that a GitHub AI devtool with `Understand-Anything`-like metadata can become approved.
- Modify: `docs/api.md`, `docs/codemap.md`, `docs/task.md`
  - Document the source-aware reviewer policy and current task state.

## Policy Design

### Content Kinds

Use deterministic local classification:

```python
def _review_kind(item: AnalyzedItem) -> str:
    if item.source == "github":
        return "github_repo"
    if item.source == "arxiv":
        return "paper"
    return "article"
```

This keeps behavior explicit and avoids asking the LLM to infer source type.

### GitHub Repo Verdict Thresholds

Use a separate deterministic policy:

```python
def _decide_github_verdict(total_score: int, ai_score: int, utility_score: int, signal_score: int) -> str:
    if ai_score < 25:
        return "discarded"
    if total_score >= 65 and ai_score >= 28 and utility_score >= 15:
        return "approved"
    if total_score >= 55 and ai_score >= 25:
        return "retry"
    return "discarded"
```

Rationale:

- GitHub tools should not need article-level `80+` scores to be displayed.
- A repo with strong AI relevance and practical developer utility should pass even if it lacks a deep blog-style writeup.
- `signal_score` is included in the rubric to reflect stars/topics/activity, but not required as a hard gate because niche new projects can still be useful.

### GitHub Reviewer Dimensions

For GitHub repos only, use four repo-specific dimensions while still normalizing to existing `ReviewedItem.dimensions` structure:

- `ai_relevance` `(0-35)`: AI/LLM/Agent/MCP/RAG/code-understanding relevance.
- `developer_utility` `(0-30)`: whether the project solves a concrete developer workflow problem.
- `project_signal` `(0-20)`: stars, forks, topics, recent trend/source type, ecosystem signal.
- `content_clarity` `(0-15)`: whether the title/summary explain what it does clearly.

Store these dimensions under their explicit names for traceability. Update normalization to accept both article dimensions and GitHub dimensions.

The final total remains `0-100`.

## Task 1: Add Review Context to AnalyzedItem

**Files:**
- Modify: `src/graph/state.py`
- Modify: `src/graph/analyzers/base.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Write failing test for GitHub metadata on analyzed item**

Add this test to `tests/test_reviewer.py`:

```python
from src.graph.state import AnalyzedItem


def test_analyzed_item_accepts_review_context():
    item = AnalyzedItem(
        ref_url="https://github.com/Lum1104/Understand-Anything",
        title="Understand-Anything",
        summary="代码知识图谱工具",
        tags=["AI", "RAG", "Tool"],
        source="github",
        source_detail="Lum1104/Understand-Anything",
        source_id="github_ai_devtools",
        metadata={"stars": 49166, "forks": 4003, "language": "TypeScript"},
    )

    assert item.source == "github"
    assert item.source_id == "github_ai_devtools"
    assert item.metadata["stars"] == 49166
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/test_reviewer.py::test_analyzed_item_accepts_review_context -v
```

Expected: FAIL because `AnalyzedItem` does not yet define `source`, `source_detail`, `source_id`, or `metadata`.

- [ ] **Step 3: Add fields to `AnalyzedItem`**

In `src/graph/state.py`, update `AnalyzedItem`:

```python
class AnalyzedItem(BaseModel):
    """Analyzer 产出 — LLM 分析后的结构化结果"""
    ref_url: str
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list, max_length=3)
    language: Literal["zh", "en"] = "zh"
    retry_count: int = Field(default=0, ge=0)
    source: str = ""
    source_detail: str = ""
    source_id: str = ""
    metadata: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Propagate metadata from analyzer**

In `src/graph/analyzers/base.py`, when creating `AnalyzedItem`, pass:

```python
source=item.source,
source_detail=item.source_detail,
source_id=item.raw_metadata.get("source_id", item.source_detail or item.source),
metadata=item.raw_metadata,
```

Apply this to the success path and any fallback/default analyzed item path.

- [ ] **Step 5: Run test**

Run:

```bash
uv run pytest tests/test_reviewer.py::test_analyzed_item_accepts_review_context -v
```

Expected: PASS.

## Task 2: Add GitHub Review Prompt and Prompt Selection

**Files:**
- Create: `prompts/github_reviewer.md`
- Modify: `src/graph/reviewer.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Write failing test for GitHub prompt input**

Add this test to `tests/test_reviewer.py`:

```python
from src.graph.reviewer import build_reviewer_user_prompt
from src.graph.state import AnalyzedItem


def test_github_reviewer_prompt_includes_repo_signals():
    item = AnalyzedItem(
        ref_url="https://github.com/Lum1104/Understand-Anything",
        title="Understand-Anything - 代码交互式知识图谱工具",
        summary="将任意代码库转化为可探索、可搜索、可提问的交互式知识图谱。",
        tags=["AI", "Agent", "RAG"],
        source="github",
        source_detail="Lum1104/Understand-Anything",
        source_id="github_ai_devtools",
        metadata={
            "stars": 49166,
            "forks": 4003,
            "language": "TypeScript",
            "topics": ["codebase-analysis", "knowledge-graph", "codex", "claude-code"],
        },
    )

    prompt = build_reviewer_user_prompt(item)

    assert "内容类型: github_repo" in prompt
    assert "source_id: github_ai_devtools" in prompt
    assert "stars: 49166" in prompt
    assert "topics: codebase-analysis, knowledge-graph, codex, claude-code" in prompt
```

- [ ] **Step 2: Run failing test**

Run:

```bash
uv run pytest tests/test_reviewer.py::test_github_reviewer_prompt_includes_repo_signals -v
```

Expected: FAIL because `build_reviewer_user_prompt` does not exist.

- [ ] **Step 3: Create GitHub reviewer prompt**

Create `prompts/github_reviewer.md`:

```markdown
你是 AI 开源项目审核员。只根据用户给出的 GitHub 仓库标题、摘要、标签、URL 和仓库元数据评分。

评分维度：
- ai_relevance(0-35): 核心 AI/LLM/Agent/MCP/RAG/代码理解工具=30-35；AI 开发辅助或知识库工具=24-29；仅泛泛使用 AI 标签=10-23；无关=0-9。
- developer_utility(0-30): 明确解决开发者工作流痛点且可直接使用=22-30；用途清晰但细节一般=15-21；概念模糊或偏展示=5-14；无实用价值=0-4。
- project_signal(0-20): stars/forks/topics/source_id 显示强社区或趋势信号=15-20；有一定关注度或专业 topic=8-14；信号弱=0-7。
- content_clarity(0-15): 摘要清楚说明做什么、给谁用、如何接入=11-15；基本清楚=7-10；含糊=0-6。

强约束：
- dimensions 只能包含 ai_relevance、developer_utility、project_signal、content_clarity 四个 key。
- total_score 必须等于四个维度 score 之和。
- 如果 source_id 是 github_ai_devtools，且仓库围绕 AI 编程助手、代码理解、知识图谱、RAG、Agent 工具链，ai_relevance 通常不低于 28。
- GitHub repo 不要求具备文章式深度；请重点判断项目是否值得作为 AI 工具被收录。

输出 JSON:
{ "total_score": 78, "dimensions": { "ai_relevance": {"score": 32, "reason": "..."}, "developer_utility": {"score": 23, "reason": "..."}, "project_signal": {"score": 15, "reason": "..."}, "content_clarity": {"score": 8, "reason": "..."} }, "verdict": "approved"|"retry"|"discarded", "retry_feedback": null|{"suggestions": ["..."]} }
```

- [ ] **Step 4: Add prompt builder**

In `src/graph/reviewer.py`, add:

```python
def review_kind(item: AnalyzedItem) -> str:
    if item.source == "github":
        return "github_repo"
    if item.source == "arxiv":
        return "paper"
    return "article"


def build_reviewer_user_prompt(item: AnalyzedItem) -> str:
    kind = review_kind(item)
    if kind != "github_repo":
        return f"标题: {item.title}\n摘要: {item.summary}\n标签: {', '.join(item.tags)}\n来源: {item.ref_url}"

    metadata = item.metadata or {}
    topics = metadata.get("topics") or []
    topics_text = ", ".join(str(topic) for topic in topics[:12])
    return "\n".join([
        "内容类型: github_repo",
        f"标题: {item.title}",
        f"摘要: {item.summary}",
        f"标签: {', '.join(item.tags)}",
        f"来源: {item.ref_url}",
        f"source_id: {item.source_id}",
        f"repo: {item.source_detail}",
        f"stars: {metadata.get('stars', 0)}",
        f"forks: {metadata.get('forks', 0)}",
        f"language: {metadata.get('language', '')}",
        f"topics: {topics_text}",
    ])
```

- [ ] **Step 5: Add prompt loader selection**

In `src/graph/reviewer.py`, add:

```python
def _load_prompt_file(path: str, fallback: str) -> str:
    from pathlib import Path
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return fallback


def _load_reviewer_prompt_for_item(registry: LLMRegistry, item: AnalyzedItem) -> str:
    if review_kind(item) == "github_repo":
        return _load_prompt_file("prompts/github_reviewer.md", GITHUB_REVIEWER_FALLBACK_PROMPT)
    return _load_reviewer_prompt(registry)
```

Define `GITHUB_REVIEWER_FALLBACK_PROMPT` as the same text as `prompts/github_reviewer.md` to keep startup fail-soft behavior consistent with current reviewer.

- [ ] **Step 6: Use prompt builder in reviewer loop**

Replace in `reviewer_node()`:

```python
system_prompt = _load_reviewer_prompt(registry)
...
user_prompt = f"标题: {item.title}\n摘要: {item.summary}\n标签: {', '.join(item.tags)}\n来源: {item.ref_url}"
```

With:

```python
system_prompt = _load_reviewer_prompt_for_item(registry, item)
user_prompt = build_reviewer_user_prompt(item)
```

- [ ] **Step 7: Run test**

Run:

```bash
uv run pytest tests/test_reviewer.py::test_github_reviewer_prompt_includes_repo_signals -v
```

Expected: PASS.

## Task 3: Add Source-Aware Verdict Normalization

**Files:**
- Modify: `src/graph/reviewer.py`
- Test: `tests/test_reviewer.py`

- [ ] **Step 1: Write failing tests for GitHub policy**

Add to `tests/test_reviewer.py`:

```python
from src.graph.reviewer import parse_reviewer_output


def test_parse_github_review_approves_under_repo_policy():
    raw = """
    {
      "review_kind": "github_repo",
      "total_score": 70,
      "dimensions": {
        "ai_relevance": {"score": 30, "reason": "AI code knowledge graph tool"},
        "developer_utility": {"score": 18, "reason": "solves codebase understanding"},
        "project_signal": {"score": 14, "reason": "strong stars and topics"},
        "content_clarity": {"score": 8, "reason": "clear summary"}
      },
      "verdict": "discarded",
      "retry_feedback": null
    }
    """

    result = parse_reviewer_output(raw, review_kind="github_repo")

    assert result.total_score == 70
    assert result.verdict == "approved"


def test_parse_github_review_retries_when_useful_but_thin():
    raw = """
    {
      "review_kind": "github_repo",
      "total_score": 58,
      "dimensions": {
        "ai_relevance": {"score": 28, "reason": "AI devtool"},
        "developer_utility": {"score": 14, "reason": "useful but thin"},
        "project_signal": {"score": 10, "reason": "some stars"},
        "content_clarity": {"score": 6, "reason": "basic summary"}
      },
      "verdict": "discarded",
      "retry_feedback": {"suggestions": ["补充技术细节"]}
    }
    """

    result = parse_reviewer_output(raw, review_kind="github_repo")

    assert result.total_score == 58
    assert result.verdict == "retry"
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
uv run pytest tests/test_reviewer.py::test_parse_github_review_approves_under_repo_policy tests/test_reviewer.py::test_parse_github_review_retries_when_useful_but_thin -v
```

Expected: FAIL because `parse_reviewer_output()` does not accept `review_kind` and does not support GitHub dimensions.

- [ ] **Step 3: Add GitHub dimension limits**

In `src/graph/reviewer.py`, add:

```python
ARTICLE_DIMENSION_LIMITS = {
    "ai_relevance": 40,
    "content_depth": 30,
    "info_density": 15,
    "timeliness": 15,
}

GITHUB_DIMENSION_LIMITS = {
    "ai_relevance": 35,
    "developer_utility": 30,
    "project_signal": 20,
    "content_clarity": 15,
}
```

Keep `DIMENSION_ALIASES` for article compatibility.

- [ ] **Step 4: Update parser signatures**

Change:

```python
def parse_reviewer_output(raw: str) -> ReviewedItem:
```

To:

```python
def parse_reviewer_output(raw: str, review_kind: str = "article") -> ReviewedItem:
```

Pass `review_kind` through to `_normalize_review(data, review_kind)`.

- [ ] **Step 5: Add source-aware normalization**

Change `_normalize_review` to choose dimension limits:

```python
def _normalize_review(data: dict, review_kind: str = "article") -> ReviewedItem:
    dimension_limits = GITHUB_DIMENSION_LIMITS if review_kind == "github_repo" else ARTICLE_DIMENSION_LIMITS
    raw_dimensions = data.get("dimensions") or {}
    normalized_dimensions = {}
    for raw_key, value in raw_dimensions.items():
        key = DIMENSION_ALIASES.get(raw_key, raw_key)
        if key in dimension_limits and key not in normalized_dimensions:
            normalized_dimensions[key] = _normalize_dimension(key, value, dimension_limits)

    missing = [key for key in dimension_limits if key not in normalized_dimensions]
    if missing:
        raise ValueError(f"Reviewer output missing dimensions: {', '.join(missing)}")

    total_score = sum(item["score"] for item in normalized_dimensions.values())
    ai_score = normalized_dimensions["ai_relevance"]["score"]

    if review_kind == "github_repo":
        verdict = _decide_github_verdict(
            total_score,
            ai_score,
            normalized_dimensions["developer_utility"]["score"],
            normalized_dimensions["project_signal"]["score"],
        )
    else:
        verdict = _decide_article_verdict(
            total_score,
            ai_score,
            normalized_dimensions["content_depth"]["score"],
        )

    retry_feedback = None
    if verdict == "retry":
        retry_feedback = data.get("retry_feedback") or {"suggestions": ["补充 AI 相关性和技术细节证据后重新分析"]}

    return ReviewedItem.model_validate({
        "ref_url": data.get("ref_url"),
        "total_score": total_score,
        "dimensions": normalized_dimensions,
        "verdict": verdict,
        "retry_feedback": retry_feedback,
    })
```

- [ ] **Step 6: Update `_normalize_dimension` signature**

Change:

```python
def _normalize_dimension(name: str, value: dict) -> dict:
    max_score = DIMENSION_LIMITS[name]
```

To:

```python
def _normalize_dimension(name: str, value: dict, dimension_limits: dict[str, int]) -> dict:
    max_score = dimension_limits[name]
```

- [ ] **Step 7: Rename article policy and add GitHub policy**

Replace `_decide_verdict` with:

```python
def _decide_article_verdict(total_score: int, ai_score: int, depth_score: int) -> str:
    if ai_score < 20:
        return "discarded"
    if total_score >= 80 and ai_score >= 30:
        return "approved"
    if total_score >= 60 and ai_score >= 25 and depth_score >= 15:
        return "retry"
    return "discarded"


def _decide_github_verdict(total_score: int, ai_score: int, utility_score: int, signal_score: int) -> str:
    if ai_score < 25:
        return "discarded"
    if total_score >= 65 and ai_score >= 28 and utility_score >= 15:
        return "approved"
    if total_score >= 55 and ai_score >= 25:
        return "retry"
    return "discarded"
```

- [ ] **Step 8: Pass review kind during reviewer parsing**

In `reviewer_node()`:

```python
kind = review_kind(item)
...
reviewed = parse_reviewer_output(content, review_kind=kind)
```

- [ ] **Step 9: Run targeted tests**

Run:

```bash
uv run pytest tests/test_reviewer.py -v
```

Expected: all reviewer tests pass.

## Task 4: Add Regression Case for Understand-Anything-Like Repo

**Files:**
- Modify: `tests/test_reviewer.py`

- [ ] **Step 1: Add regression test**

Add:

```python
def test_understand_anything_like_repo_is_approved_with_repo_policy():
    raw = """
    {
      "total_score": 72,
      "dimensions": {
        "ai_relevance": {
          "score": 31,
          "reason": "围绕代码知识图谱、AI 编程助手和 RAG 式问答，属于 AI 开发者工具"
        },
        "developer_utility": {
          "score": 20,
          "reason": "帮助开发者理解大型代码库结构、依赖和上下文"
        },
        "project_signal": {
          "score": 14,
          "reason": "高 star，topics 命中 codebase-analysis、knowledge-graph、codex、claude-code"
        },
        "content_clarity": {
          "score": 7,
          "reason": "摘要清楚说明功能，但技术实现细节有限"
        }
      },
      "verdict": "discarded",
      "retry_feedback": null
    }
    """

    result = parse_reviewer_output(raw, review_kind="github_repo")

    assert result.verdict == "approved"
    assert result.total_score == 72
```

- [ ] **Step 2: Run regression test**

Run:

```bash
uv run pytest tests/test_reviewer.py::test_understand_anything_like_repo_is_approved_with_repo_policy -v
```

Expected: PASS after Task 3.

## Task 5: Preserve Existing Article Behavior

**Files:**
- Modify: `tests/test_reviewer.py`

- [ ] **Step 1: Add article policy guard test**

Add:

```python
def test_article_policy_still_discards_shallow_article():
    raw = """
    {
      "total_score": 59,
      "dimensions": {
        "ai_relevance": {"score": 30, "reason": "AI related"},
        "content_depth": {"score": 14, "reason": "thin"},
        "info_density": {"score": 8, "reason": "normal"},
        "timeliness": {"score": 7, "reason": "recent"}
      },
      "verdict": "approved",
      "retry_feedback": null
    }
    """

    result = parse_reviewer_output(raw)

    assert result.verdict == "discarded"
```

- [ ] **Step 2: Run guard test**

Run:

```bash
uv run pytest tests/test_reviewer.py::test_article_policy_still_discards_shallow_article -v
```

Expected: PASS.

## Task 6: Pipeline-Level Source Context Test

**Files:**
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Add a pipeline test for GitHub source context**

Add a test that constructs a `PipelineState` with a GitHub routed item and mocked analyzer/reviewer result. The key assertion is that `AnalyzedItem.source == "github"` and `source_id == "github_ai_devtools"` survive into reviewer prompt construction.

```python
from src.graph.reviewer import build_reviewer_user_prompt
from src.graph.state import AnalyzedItem


def test_github_review_prompt_uses_source_context_from_analyzed_item():
    analyzed = AnalyzedItem(
        ref_url="https://github.com/Lum1104/Understand-Anything",
        title="Understand-Anything",
        summary="代码知识图谱工具",
        tags=["AI", "RAG", "Tool"],
        source="github",
        source_detail="Lum1104/Understand-Anything",
        source_id="github_ai_devtools",
        metadata={"stars": 49166, "topics": ["knowledge-graph", "codex"]},
    )

    prompt = build_reviewer_user_prompt(analyzed)

    assert "内容类型: github_repo" in prompt
    assert "source_id: github_ai_devtools" in prompt
```

- [ ] **Step 2: Run pipeline test**

Run:

```bash
uv run pytest tests/test_pipeline.py::test_github_review_prompt_uses_source_context_from_analyzed_item -v
```

Expected: PASS.

## Task 7: Update Documentation

**Files:**
- Modify: `docs/codemap.md`
- Modify: `docs/task.md`
- Modify: `docs/api.md`

- [ ] **Step 1: Update `docs/codemap.md`**

Add under graph/reviewer responsibilities:

```markdown
- `src/graph/reviewer.py`: 内容审核与系统裁决。普通文章/arXiv 使用 `prompts/reviewer.md` 和文章型四维评分；GitHub repo 使用 `prompts/github_reviewer.md` 和 repo-aware 四维评分，避免 AI 开源工具被文章深度标准误伤。
```

- [ ] **Step 2: Update `docs/task.md`**

Add a new task entry:

```markdown
## 当前任务：GitHub repo 审核策略分流

优先级：P0
状态：进行中

- [ ] 为 GitHub repo 增加 reviewer 上下文和 repo 元数据输入
- [ ] 增加 `prompts/github_reviewer.md`
- [ ] 将 GitHub repo 系统裁决从文章阈值切换到 repo-aware 阈值
- [ ] 增加 `Understand-Anything` 类 repo 回归测试
- [ ] VPS 触发 pipeline 验证 `github_ai_devtools` 通过率恢复
```

- [ ] **Step 3: Update `docs/api.md`**

If dashboard/source health docs mention `approved/retry/discarded`, add:

```markdown
GitHub repo 的审核策略与普通文章不同：系统会按 repo-aware 维度裁决，因此 `approved/retry/discarded` 的来源健康统计不能直接与 RSS 新闻按同一内容深度标准比较。
```

## Task 8: Verification

**Files:**
- No source edits unless tests expose a bug.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
uv run pytest tests/test_reviewer.py tests/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 2: Run non-integration suite**

Run:

```bash
uv run pytest -m "not integration and not e2e"
```

Expected: PASS.

- [ ] **Step 3: Commit locally**

Run:

```bash
git status --short
git add src/graph/state.py src/graph/analyzers/base.py src/graph/reviewer.py prompts/github_reviewer.md prompts/reviewer.md tests/test_reviewer.py tests/test_pipeline.py docs/codemap.md docs/task.md docs/api.md docs/superpowers/plans/2026-06-02-github-reviewer-policy-plan.md
git commit -m "refine github reviewer policy"
```

Expected: commit succeeds.

- [ ] **Step 4: Push**

Run:

```bash
git push
```

Expected: push succeeds.

- [ ] **Step 5: VPS deployment check**

After deployment reaches VPS, run:

```bash
ssh -i ~/.ssh/vps_deploy_key admin@8.134.176.187 'cd /opt/ai-knowledge-base && git rev-parse --short HEAD && docker compose ps'
```

Expected:

- VPS commit matches pushed commit.
- pipeline and web containers are up.

- [ ] **Step 6: Trigger source-limited pipeline**

Prefer source-limited trigger if supported; otherwise trigger the full pipeline:

```bash
ssh -i ~/.ssh/vps_deploy_key admin@8.134.176.187 'cd /opt/ai-knowledge-base && docker exec ai-knowledge-base-pipeline-1 sh -lc "uv run python - <<'\''PY'\''
import httpx
r = httpx.post(\"http://127.0.0.1:8000/api/pipeline/run\", timeout=20)
print(r.status_code)
print(r.text)
PY"'
```

Expected: `200` with queued status.

- [ ] **Step 7: Verify `Understand-Anything` no longer discarded on new runs**

Run:

```bash
ssh -i ~/.ssh/vps_deploy_key admin@8.134.176.187 'cd /opt/ai-knowledge-base && docker exec ai-knowledge-base-pipeline-1 sh -lc "uv run python - <<'\''PY'\''
import sqlite3, json
conn = sqlite3.connect(\"data/kb.db\")
conn.row_factory = sqlite3.Row
url = \"https://github.com/Lum1104/Understand-Anything\"
print(json.dumps([dict(r) for r in conn.execute(\"select run_id,status,reason,article_id,updated_at from collection_items where url=? order by updated_at desc limit 5\", (url,)).fetchall()], ensure_ascii=False, default=str))
print(json.dumps([dict(r) for r in conn.execute(\"select id,status,score,title from articles where url=? order by id desc limit 5\", (url,)).fetchall()], ensure_ascii=False, default=str))
PY"'
```

Expected after a new run that includes the repo:

- Latest `collection_items.status` is `inserted` or at minimum `reviewed_retry`, not `reviewed_discarded`.
- If `inserted`, `articles` has a row for the URL.

## Risks and Follow-Ups

- This change can increase GitHub approvals. Watch `github_ai_devtools` and `github_trending_hot` approved counts for one or two runs.
- Reviewer latency remains high because calls are still serial. This plan intentionally does not add concurrency; handle that as a separate performance task.
- Existing `retry` semantics are confusing because retry rows can be saved to `articles` but not counted as inserted. A follow-up should make dashboard labels clearer.

## Self-Review

- Spec coverage: Covers why `Understand-Anything` was filtered, adds repo-aware input, prompt, deterministic policy, regression tests, docs, and VPS verification.
- Placeholder scan: No TBD/TODO placeholders. Every task has exact files and commands.
- Type consistency: `review_kind`, `build_reviewer_user_prompt`, `parse_reviewer_output(..., review_kind=...)`, and `AnalyzedItem` fields are introduced before use.
