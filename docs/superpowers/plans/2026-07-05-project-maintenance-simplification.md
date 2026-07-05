# Project Maintenance Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变现有业务行为、API 契约、数据表和部署方式的前提下，校准文档、降低 `src/main.py` 与 `src/db/operations.py` 的维护负担，并为 Analyzer 增加最小可控并发。

**Architecture:** 本计划只做渐进式整理：先修正文档漂移，再迁移纯函数，最后按职责拆分 DB 操作并保留 `src/db/operations.py` 兼容 re-export。行为变化只限 Analyzer 支持有限并发，默认保守，且保持输入输出顺序稳定。

**Tech Stack:** Python 3.12、FastAPI、LangGraph、SQLite、aiosqlite、pytest、uv。

## Global Constraints

- 始终使用中文回复和中文文档说明。
- 先读相关代码和文档，再改代码；不确定时先说明假设。
- 简单优先，只做本计划列出的事，不写 speculative 代码。
- 精准改动，只触碰完成任务必须改的文件。
- 不新增依赖。
- 不改变 API 响应信封、错误码、数据库 schema、迁移策略、部署流程。
- 非 `db/` 模块不直接写 SQL；数据库读写仍走 `src/db/operations.py` 暴露的函数或其 re-export。
- 配置从 `config/*.yaml` 或统一配置模块读取，不在业务函数里直接读环境变量。
- 日志走 `logging`，不要用 `print()`。
- 不提交 `.env`、`data/`、`output/`。

## Assumptions

- 当前需求是维护性优化，不是新增产品能力。
- `src/db/operations.py` 在第一轮拆分后继续作为兼容入口，避免一次性修改全仓 import。
- Analyzer 并发是唯一允许的行为级优化；默认值保持保守，防止 LLM Provider 压力突然变大。
- 文档若与代码冲突，以代码为准，并修正文档。

## Success Criteria

- README、`docs/codemap.md`、必要时 `docs/structure.md` 与当前代码结构一致。
- `src/main.py` 至少移出纯辅助函数，保留顶层编排职责。
- `src/db/operations.py` 不再承载全部 SQL 实现，只保留 re-export 兼容层。
- 既有测试通过：`uv run pytest -m "not integration and not e2e"`。
- Analyzer 并发测试证明输出顺序稳定，且默认配置不改变现有行为。

---

### Task 1: 文档校准

**Files:**
- Modify: `README.md`
- Modify: `docs/codemap.md`
- Modify if needed: `docs/structure.md`

**Interfaces:**
- Consumes: 当前代码实际结构。
- Produces: 与代码一致的项目说明，供后续任务和新人阅读。

- [ ] **Step 1: 核对旧描述**

Run:

```bash
rg -n "skip_if_running|自动删除|src/db/articles.py|src/db/queries.py|src/core/database.py|operations.py|Deep Reports|source governance|pipeline lock|排队" README.md docs/codemap.md docs/structure.md
```

Expected:

```text
输出所有疑似过期或需要确认的描述位置。
```

- [ ] **Step 2: 更新 README 当前架构**

Edit `README.md` so it states these current facts:

```markdown
- pipeline 重叠触发时通过进程内 `asyncio.Lock` 排队，并记录 `pipeline.queued`，不是静默跳过。
- 数据源治理使用 `source_registry`、candidate、trial、active、degraded、quarantined、rejected/disabled 状态流转。
- 数据库操作当前以 `src/db/operations.py` 为统一兼容入口。
- Deep Reports 是 Reviewer/入库后的图外后置阶段，失败不影响主 pipeline。
- DAG 和 dashboard 基于 `pipeline_events`、`pipeline_source_runs`、`collection_items`、`cost_logs` 做观测。
```

- [ ] **Step 3: 更新 codemap 当前结构**

Edit `docs/codemap.md` so the DB section names the current source of truth:

```markdown
- `src/core/database.py`
  - SQLite 连接、迁移执行、基础 fetch/execute/backup API。

- `src/db/operations.py`
  - 数据库操作兼容入口。
  - 当前承载文章、统计、pipeline、成本和 deep report 查询；后续维护性优化会按职责拆分实现文件，但外部调用仍优先从这里导入。
```

- [ ] **Step 4: 验证文档没有明显旧结构残留**

Run:

```bash
rg -n "skip_if_running|自动删除数据源|src/db/articles.py|src/db/queries.py" README.md docs/codemap.md docs/structure.md
```

Expected:

```text
No matches.
```

- [ ] **Step 5: 跑轻量契约测试**

Run:

```bash
uv run pytest tests/test_api_contracts.py tests/test_deploy_workflow.py -q
```

Expected:

```text
所有测试通过。
```

---

### Task 2: 抽出 pipeline 纯辅助函数

**Files:**
- Create: `src/services/pipeline_helpers.py`
- Modify: `src/main.py`
- Create: `tests/test_pipeline_helpers.py`

**Interfaces:**
- Consumes: `RawItem`、`AnalyzedItem`、`ReviewedItem`、`CostRecord` 等现有模型。
- Produces:
  - `filter_sources(sources, source_filter)`
  - `group_enabled_sources_by_cron(sources) -> dict[str, list[str]]`
  - `source_filter_label(source_filter) -> str`
  - `source_filter_count(source_filter) -> int | None`
  - `apply_github_velocity_filter(raw_items, source, trending_urls) -> list`
  - `build_cost_source_map(items) -> dict[str, tuple[str, str, str]]`
  - `summarize_item_costs(cost_records) -> dict[str, tuple[float, int]]`
  - `source_identity(item) -> tuple[str, str, str]`
  - `build_pipeline_source_summaries(...) -> list[dict]`
  - `prepare_retry_review_items(retry_reviewed, analyzed_items, raw_items) -> list`
  - `merge_retry_review_result(all_reviewed, all_costs, retry_result) -> list[ReviewedItem]`

- [ ] **Step 1: 写失败测试**

Create `tests/test_pipeline_helpers.py`:

```python
from types import SimpleNamespace

from src.graph.state import CostRecord, ReviewedItem
from src.services.pipeline_helpers import (
    build_pipeline_source_summaries,
    merge_retry_review_result,
    source_filter_count,
    source_filter_label,
    summarize_item_costs,
)


def test_source_filter_label_and_count():
    assert source_filter_label(None) == "all"
    assert source_filter_count(None) is None
    assert source_filter_label("rss_36kr") == "rss_36kr"
    assert source_filter_count("rss_36kr") == 1
    assert source_filter_label(["a", "b"]) == "a,b"
    assert source_filter_count(["a", "b"]) == 2


def test_summarize_item_costs_ignores_records_without_ref_url():
    records = [
        CostRecord(agent="rss", provider="p", model="m", tokens_in=10, tokens_out=5, cost=0.01, ref_url="u1"),
        CostRecord(agent="reviewer", provider="p", model="m", tokens_in=2, tokens_out=3, cost=0.02, ref_url="u1"),
        CostRecord(agent="reviewer", provider="p", model="m", tokens_in=2, tokens_out=3, cost=0.02, ref_url=""),
    ]

    assert summarize_item_costs(records) == {"u1": (0.03, 20)}


def test_build_pipeline_source_summaries_counts_funnel():
    raw = SimpleNamespace(
        url="https://example.com/a",
        source="rss",
        source_detail="Example",
        raw_metadata={"source_id": "rss_example"},
    )
    analyzed = SimpleNamespace(ref_url=raw.url)
    reviewed = SimpleNamespace(ref_url=raw.url, verdict="approved")
    cost = CostRecord(
        agent="rss",
        provider="p",
        model="m",
        tokens_in=10,
        tokens_out=5,
        cost=0.01,
        ref_url=raw.url,
        source="rss",
        source_detail="Example",
        source_id="rss_example",
    )

    summaries = build_pipeline_source_summaries(
        run_id="run1",
        raw_items=[raw],
        new_items=[raw],
        analyzed_items=[analyzed],
        reviewed_items=[reviewed],
        cost_records=[cost],
        inserted_urls={raw.url},
        active_sources=[],
    )

    assert summaries == [{
        "run_id": "run1",
        "source_id": "rss_example",
        "source": "rss",
        "source_detail": "Example",
        "collected": 1,
        "new_items": 1,
        "dedup_skipped": 0,
        "analyzed": 1,
        "analysis_failed": 0,
        "approved": 1,
        "retry": 0,
        "discarded": 0,
        "inserted": 1,
        "failed": 0,
        "cost": 0.01,
        "tokens": 15,
        "filtered_items": 0,
        "request_success_rate": 1.0,
        "insert_rate": 1.0,
    }]


def test_merge_retry_review_result_replaces_existing_review():
    first = ReviewedItem(ref_url="u1", total_score=60, dimensions={}, verdict="retry")
    replacement = ReviewedItem(ref_url="u1", total_score=85, dimensions={}, verdict="approved")
    costs = []

    result = merge_retry_review_result([first], costs, {"reviewed_items": [replacement], "cost_records": ["c1"]})

    assert result == [replacement]
    assert costs == ["c1"]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```bash
uv run pytest tests/test_pipeline_helpers.py -q
```

Expected:

```text
FAIL，原因是 `src.services.pipeline_helpers` 不存在。
```

- [ ] **Step 3: 创建最小实现**

Create `src/services/pipeline_helpers.py` by moving the equivalent private helpers from `src/main.py` and renaming them without the leading underscore:

```python
from . import __name__ as _services_package_name


def filter_sources(sources, source_filter):
    if source_filter is None:
        return sources
    if isinstance(source_filter, str):
        source_ids = {source_filter}
    else:
        source_ids = set(source_filter)
    return [source for source in sources if source.id in source_ids]


def group_enabled_sources_by_cron(sources) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for source in sources:
        if not source.enabled:
            continue
        groups.setdefault(source.cron, []).append(source.id)
    return groups


def source_filter_label(source_filter) -> str:
    if source_filter is None:
        return "all"
    if isinstance(source_filter, str):
        return source_filter
    return ",".join(source_filter)


def source_filter_count(source_filter) -> int | None:
    if source_filter is None:
        return None
    if isinstance(source_filter, str):
        return 1
    return len(source_filter)
```

Then move these existing functions unchanged from `src/main.py` into the same file and only remove the leading underscore from each function name:

```python
apply_github_velocity_filter
build_cost_source_map
summarize_item_costs
source_identity
build_pipeline_source_summaries
prepare_retry_review_items
merge_retry_review_result
```

Remove this line if an editor inserts it:

```python
from . import __name__ as _services_package_name
```

- [ ] **Step 4: 更新 main import 和调用点**

Modify `src/main.py` imports:

```python
from .services.pipeline_helpers import (
    apply_github_velocity_filter,
    build_cost_source_map,
    build_pipeline_source_summaries,
    group_enabled_sources_by_cron,
    merge_retry_review_result,
    prepare_retry_review_items,
    source_filter_count,
    source_filter_label,
    source_identity,
    summarize_item_costs,
)
```

Replace call sites:

```python
_group_enabled_sources_by_cron(...) -> group_enabled_sources_by_cron(...)
_source_filter_label(...) -> source_filter_label(...)
_source_filter_count(...) -> source_filter_count(...)
_apply_github_velocity_filter(...) -> apply_github_velocity_filter(...)
_build_cost_source_map(...) -> build_cost_source_map(...)
_summarize_item_costs(...) -> summarize_item_costs(...)
_source_identity(...) -> source_identity(...)
_build_pipeline_source_summaries(...) -> build_pipeline_source_summaries(...)
_prepare_retry_review_items(...) -> prepare_retry_review_items(...)
_merge_retry_review_result(...) -> merge_retry_review_result(...)
```

Delete the moved helper definitions from `src/main.py`.

- [ ] **Step 5: 跑测试**

Run:

```bash
uv run pytest tests/test_pipeline_helpers.py tests/test_pipeline.py tests/test_pipeline_observability.py -q
```

Expected:

```text
所有测试通过。
```

---

### Task 3: 拆分 DB 操作实现并保留兼容入口

**Files:**
- Create: `src/db/articles.py`
- Create: `src/db/pipeline_ops.py`
- Create: `src/db/costs.py`
- Create: `src/db/deep_report_ops.py`
- Modify: `src/db/operations.py`
- Existing tests only.

**Interfaces:**
- Consumes: 现有 `src/db/operations.py` 函数。
- Produces: `src/db/operations.py` 继续 re-export 原函数名，外部 import 不需要改。

- [ ] **Step 1: 建立函数归属清单**

Run:

```bash
rg -n "^async def |^def " src/db/operations.py
```

Expected:

```text
列出所有函数，按 articles / pipeline_ops / costs / deep_report_ops / keep in operations 分类。
```

- [ ] **Step 2: 先迁移文章相关函数**

Move these functions from `src/db/operations.py` to `src/db/articles.py`:

```python
save_article
save_tags
batch_check_existing_urls
get_article_detail
```

Also move their private helpers only if exclusively used by article functions:

```python
_decode_json_field
```

Update `src/db/operations.py`:

```python
from .articles import (
    batch_check_existing_urls,
    get_article_detail,
    save_article,
    save_tags,
)
```

- [ ] **Step 3: 验证文章/API 契约**

Run:

```bash
uv run pytest tests/test_api_contracts.py tests/test_site_builder.py -q
```

Expected:

```text
所有测试通过。
```

- [ ] **Step 4: 迁移 pipeline 观测相关函数**

Move these functions to `src/db/pipeline_ops.py`:

```python
start_pipeline_run
end_pipeline_run
record_pipeline_event
record_collection_item
upsert_pipeline_source_run
```

Update `src/db/operations.py`:

```python
from .pipeline_ops import (
    end_pipeline_run,
    record_collection_item,
    record_pipeline_event,
    start_pipeline_run,
    upsert_pipeline_source_run,
)
```

- [ ] **Step 5: 验证 pipeline 观测**

Run:

```bash
uv run pytest tests/test_pipeline.py tests/test_pipeline_observability.py tests/test_source_health_records.py -q
```

Expected:

```text
所有测试通过。
```

- [ ] **Step 6: 迁移成本相关函数**

Move these functions to `src/db/costs.py`:

```python
save_cost_log
get_today_llm_spend
```

If cost summary query functions are present in `operations.py`, move them together only when tests identify them as cost-only functions.

Update `src/db/operations.py`:

```python
from .costs import (
    get_today_llm_spend,
    save_cost_log,
)
```

- [ ] **Step 7: 验证成本统计**

Run:

```bash
uv run pytest tests/test_cost_accounting.py tests/test_stats_consumption_detail.py tests/test_budget.py -q
```

Expected:

```text
所有测试通过。
```

- [ ] **Step 8: 迁移 Deep Reports DB 函数**

Move Deep Reports functions to `src/db/deep_report_ops.py`. Identify them with:

```bash
rg -n "deep_report|deep_reports|public_version|report_version" src/db/operations.py
```

Keep public function names unchanged and re-export them from `src/db/operations.py`:

```python
from .deep_report_ops import *
```

Use explicit imports instead of `*` if the moved function list is short enough to keep readable.

- [ ] **Step 9: 验证 Deep Reports**

Run:

```bash
uv run pytest tests/test_deep_reports_db.py tests/test_deep_reports_api.py tests/test_deep_reports_pipeline.py tests/test_deep_reports_rebuild.py -q
```

Expected:

```text
所有测试通过。
```

- [ ] **Step 10: 全量非集成验证**

Run:

```bash
uv run pytest -m "not integration and not e2e"
```

Expected:

```text
所有测试通过。
```

---

### Task 4: Analyzer 有限并发

**Files:**
- Modify: `src/graph/analyzers/base.py`
- Modify: `config/agents.yaml`
- Modify: `tests/test_analyzer.py`

**Interfaces:**
- Consumes: `analyze_items(items, agent_name, registry, prompt_template, system_prompt="")`
- Produces: 同一个函数签名，内部按 `params.concurrency` 控制并发，返回顺序与输入顺序一致。

- [ ] **Step 1: 写顺序稳定测试**

Add to `tests/test_analyzer.py`:

```python
@pytest.mark.asyncio
async def test_analyze_items_preserves_input_order_with_concurrency():
    items = [
        RawItem(url="https://example.com/1", title="one", description="d1", source="rss", source_detail="s", raw_metadata={"source_id": "rss"}),
        RawItem(url="https://example.com/2", title="two", description="d2", source="rss", source_detail="s", raw_metadata={"source_id": "rss"}),
    ]
    registry = FakeRegistry([
        '{"title":"one","summary":"摘要一","tags":["AI"],"language":"zh"}',
        '{"title":"two","summary":"摘要二","tags":["AI"],"language":"zh"}',
    ])
    registry.params = {"temperature": 0, "max_tokens": 128, "concurrency": 2}

    analyzed, costs = await analyze_items(items, "rss_analyzer", registry, "标题:{title}\\n描述:{description}\\nURL:{url}\\n元数据:{metadata}\\n{schema}")

    assert [item.ref_url for item in analyzed] == ["https://example.com/1", "https://example.com/2"]
    assert len(costs) == 2
```

If existing test fakes use different class names, adapt only the fake construction and keep the assertion unchanged.

- [ ] **Step 2: 运行测试确认失败或暴露现状**

Run:

```bash
uv run pytest tests/test_analyzer.py::test_analyze_items_preserves_input_order_with_concurrency -q
```

Expected:

```text
FAIL if fake/params support is missing, or PASS if current fake already serializes safely. Continue implementation either way because production code still lacks configured concurrency.
```

- [ ] **Step 3: 实现最小并发**

In `src/graph/analyzers/base.py`, add helpers:

```python
def _positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)
```

Refactor `analyze_items()` so each item is processed by an inner coroutine returning `(index, analyzed_or_none, costs)` and gathered with:

```python
concurrency = _positive_int(params.get("concurrency"), 1)
semaphore = asyncio.Semaphore(concurrency)
task_results = await asyncio.gather(*[
    analyze_one(index, item, semaphore)
    for index, item in enumerate(items)
])
for _, analyzed, item_costs in sorted(task_results, key=lambda item: item[0]):
    costs.extend(item_costs)
    if analyzed is not None:
        results.append(analyzed)
```

Keep current cost status values unchanged:

```python
provider_unavailable
request_failed
parse_failed
success
```

- [ ] **Step 4: 配置默认值**

In `config/agents.yaml`, add conservative analyzer concurrency where analyzer params already exist:

```yaml
params:
  concurrency: 2
```

Do not add new provider, model, or fallback configuration.

- [ ] **Step 5: 验证 Analyzer 和 Pipeline**

Run:

```bash
uv run pytest tests/test_analyzer.py tests/test_pipeline.py -q
```

Expected:

```text
所有测试通过。
```

---

### Task 5: 收紧主链路异常处理

**Files:**
- Modify: `src/graph/analyzers/base.py`
- Modify: `src/graph/reviewer.py`
- Modify if needed: `src/core/source_discovery.py`
- Modify if needed: `src/deep_reports/service.py`
- Existing tests only, unless a bug is found.

**Interfaces:**
- Consumes: 现有错误状态和日志字段。
- Produces: 更明确的异常分类；Deep Reports best-effort 隔离保持不变。

- [ ] **Step 1: 列出宽异常位置**

Run:

```bash
rg -n "except Exception|except:" src/graph src/core src/deep_reports
```

Expected:

```text
输出所有宽异常位置。
```

- [ ] **Step 2: 只收紧 Analyzer 明确边界**

In `src/graph/analyzers/base.py`, keep parse failures as:

```python
except (ValueError, TypeError) as parse_error:
    cost_record.status = "parse_failed"
    cost_record.error = str(parse_error)
```

Keep request failures as broad enough for provider SDK/runtime errors:

```python
except Exception as e:
    status = "request_failed"
```

Do not swallow the error silently; every path must append a `CostRecord`.

- [ ] **Step 3: 只收紧 Reviewer prompt 读取 fallback**

In `src/graph/reviewer.py`, replace broad prompt file fallback exceptions with file/parse related exceptions:

```python
except OSError:
    return GITHUB_REVIEWER_FALLBACK_PROMPT
```

For JSON parsing, keep explicit:

```python
except ValueError:
    raise ValueError("Reviewer output is not valid JSON")
```

- [ ] **Step 4: 保留 Deep Reports 隔离边界**

In `src/deep_reports/service.py`, keep broad `except Exception as exc` only around stage-level isolation where failure must not fail the main pipeline. Ensure each broad catch logs or records a `deep.failed` event.

- [ ] **Step 5: 验证主链路**

Run:

```bash
uv run pytest tests/test_analyzer.py tests/test_reviewer.py tests/test_deep_reports_pipeline.py -q
```

Expected:

```text
所有测试通过。
```

---

### Task 6: 最终验证与文档回写

**Files:**
- Modify if needed: `docs/codemap.md`
- Modify if needed: `docs/structure.md`
- Modify if needed: `docs/bug-progress.md`

**Interfaces:**
- Consumes: Tasks 1-5 的实际改动。
- Produces: 与最终代码一致的文档和验证记录。

- [ ] **Step 1: 更新代码地图**

If Task 2/3 changed module ownership, update `docs/codemap.md` with:

```markdown
- `src/services/pipeline_helpers.py`
  - Pipeline 纯辅助函数：source filter、source summary、retry review merge、成本汇总。

- `src/db/operations.py`
  - 数据库操作兼容入口，re-export articles/pipeline/cost/deep report 子模块函数。
```

- [ ] **Step 2: 更新目录结构**

If `docs/structure.md` lists DB internals, add:

```markdown
src/db/articles.py
src/db/pipeline_ops.py
src/db/costs.py
src/db/deep_report_ops.py
```

- [ ] **Step 3: 全量非集成测试**

Run:

```bash
uv run pytest -m "not integration and not e2e"
```

Expected:

```text
所有测试通过。
```

- [ ] **Step 4: 检查无意改动**

Run:

```bash
git diff --stat
git diff -- README.md docs/codemap.md docs/structure.md src/main.py src/services/pipeline_helpers.py src/db/operations.py src/db/articles.py src/db/pipeline_ops.py src/db/costs.py src/db/deep_report_ops.py src/graph/analyzers/base.py config/agents.yaml tests/test_pipeline_helpers.py tests/test_analyzer.py
```

Expected:

```text
Diff 只包含本计划相关改动，没有格式化无关文件。
```

- [ ] **Step 5: 提交建议**

Use small commits:

```bash
git add README.md docs/codemap.md docs/structure.md
git commit -m "docs: align project architecture notes"

git add src/main.py src/services/pipeline_helpers.py tests/test_pipeline_helpers.py
git commit -m "refactor: extract pipeline helper functions"

git add src/db/operations.py src/db/articles.py src/db/pipeline_ops.py src/db/costs.py src/db/deep_report_ops.py docs/codemap.md docs/structure.md
git commit -m "refactor: split database operations by responsibility"

git add src/graph/analyzers/base.py config/agents.yaml tests/test_analyzer.py
git commit -m "perf: add bounded analyzer concurrency"
```

## Rollback Plan

- 文档任务可直接 revert 对应 docs commit。
- `pipeline_helpers` 任务可将 helper 函数移回 `src/main.py`，删除 `src/services/pipeline_helpers.py`。
- DB 拆分任务可将函数移回 `src/db/operations.py`，删除新增 DB 子模块；外部 import 因保留 re-export 不需要额外回滚。
- Analyzer 并发任务可把 `concurrency` 默认值设回 `1`，或 revert `src/graph/analyzers/base.py` 与 `config/agents.yaml` 对应 commit。

## Explicitly Skipped

- 不引入 Celery/RQ/Arq 等任务队列。
- 不新增语义去重。
- 不做多用户、登录、权限系统。
- 不替换 SQLite。
- 不引入 Alembic/SQLAlchemy 迁移。
- 不重写前端和仪表盘。
- 不调整 Reviewer 分数阈值或 Prompt 策略。
