# Source Governance Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automatic source governance loop from discovery to trial, activation, degradation, quarantine, and disablement.

**Architecture:** Add a database-backed source registry and governance event log while keeping `config/sources.yaml` as bootstrap input. Scheduling and source stats move to the registry; collectors keep their current source interface. Governance decisions are derived from existing pipeline facts plus a new daily health rollup.

**Tech Stack:** Python 3.12, FastAPI, aiosqlite, APScheduler, Pydantic v2, pytest, vanilla JavaScript.

## Global Constraints

- 回复语言：始终使用中文。
- Do not automatically delete sources; automatic actions may disable or change governance status only.
- Budget hard limit events must not reduce source quality scores.
- Feishu must never be auto-discovered or auto-enabled.
- Hotlist sources are manual-only and must not be auto-expanded.
- Keep changes scoped; do not introduce new dependencies.
- API responses must keep the existing `envelope()` response shape.

---

## File Structure

- `src/db/migrations/012_source_governance.sql`: creates registry, daily health, and event tables.
- `src/core/source_registry.py`: converts between `SourceConfig` and DB rows, syncs bootstrap config, lists schedulable sources.
- `src/core/source_governance.py`: scoring and status transition rules.
- `src/core/source_discovery.py`: discovery writes candidates only.
- `src/scheduler/source_scheduler.py`: weekly maintenance runs discovery and governance.
- `src/main.py`: startup sync and source job registration from registry.
- `src/api/sources.py`: stats and actions include governance state.
- `src/site/static/js/dashboard/renderers.js`: shows governance state and budget-blocked status.
- Tests stay in existing files where possible: `tests/test_database.py`, `tests/test_api_contracts.py`, `tests/test_pipeline_observability.py`, `tests/test_dashboard_frontend_contract.py`, plus new `tests/core/test_source_registry.py` and `tests/core/test_source_governance.py`.

---

### Task 1: Add Governance Tables

**Files:**
- Create: `src/db/migrations/012_source_governance.sql`
- Modify: `docs/data-model.md`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces tables: `source_registry`, `source_health_daily`, `source_governance_events`.
- Later tasks rely on `source_registry.status`, `source_registry.manual_override`, and `source_governance_events.reason`.

- [ ] **Step 1: Write failing migration test**

Add to `tests/test_database.py`:

```python
async def test_source_governance_tables_exist(tmp_path):
    migrations_dir = Path(__file__).parent.parent / "src" / "db" / "migrations"
    db = Database(tmp_path / "governance.db", migrations_dir=migrations_dir)
    await db.initialize()
    try:
        tables = {
            row["name"]
            for row in await db.fetch_all(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "source_registry" in tables
        assert "source_health_daily" in tables
        assert "source_governance_events" in tables

        registry_cols = {
            row["name"]
            for row in await db.fetch_all("PRAGMA table_info(source_registry)")
        }
        assert {
            "id",
            "name",
            "type",
            "status",
            "enabled",
            "priority",
            "cron",
            "max_items",
            "config_json",
            "manual_override",
        } <= registry_cols
    finally:
        await db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_database.py::test_source_governance_tables_exist -q`

Expected: FAIL because `source_registry` does not exist.

- [ ] **Step 3: Add migration**

Create `src/db/migrations/012_source_governance.sql`:

```sql
CREATE TABLE IF NOT EXISTS source_registry (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    enabled         INTEGER NOT NULL DEFAULT 1,
    priority        INTEGER NOT NULL DEFAULT 3,
    cron            TEXT NOT NULL,
    max_items       INTEGER NOT NULL DEFAULT 10,
    config_json     TEXT NOT NULL DEFAULT '{}',
    manual_override INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now', '+8 hours')),
    updated_at      TEXT DEFAULT (datetime('now', '+8 hours'))
);

CREATE TABLE IF NOT EXISTS source_health_daily (
    source_id             TEXT NOT NULL,
    date                  TEXT NOT NULL,
    request_success_rate  REAL NOT NULL DEFAULT 0,
    collected             INTEGER NOT NULL DEFAULT 0,
    new_items             INTEGER NOT NULL DEFAULT 0,
    analyzed              INTEGER NOT NULL DEFAULT 0,
    analysis_failed       INTEGER NOT NULL DEFAULT 0,
    approved              INTEGER NOT NULL DEFAULT 0,
    discarded             INTEGER NOT NULL DEFAULT 0,
    avg_score             REAL,
    cost                  REAL NOT NULL DEFAULT 0,
    tokens                INTEGER NOT NULL DEFAULT 0,
    health_score          REAL,
    budget_blocked        INTEGER NOT NULL DEFAULT 0,
    updated_at            TEXT DEFAULT (datetime('now', '+8 hours')),
    PRIMARY KEY (source_id, date)
);

CREATE TABLE IF NOT EXISTS source_governance_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL,
    event        TEXT NOT NULL,
    from_status  TEXT NOT NULL DEFAULT '',
    to_status    TEXT NOT NULL DEFAULT '',
    reason       TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT DEFAULT (datetime('now', '+8 hours'))
);

CREATE INDEX IF NOT EXISTS idx_source_registry_status
ON source_registry(status, enabled);

CREATE INDEX IF NOT EXISTS idx_source_health_daily_source_date
ON source_health_daily(source_id, date);

CREATE INDEX IF NOT EXISTS idx_source_governance_events_source_time
ON source_governance_events(source_id, created_at);
```

- [ ] **Step 4: Run migration test**

Run: `.venv/bin/python -m pytest tests/test_database.py::test_source_governance_tables_exist -q`

Expected: PASS.

- [ ] **Step 5: Document tables**

Add concise sections to `docs/data-model.md` after `discovered_sources` describing the three new tables and the no-auto-delete rule.

- [ ] **Step 6: Run checks and commit**

Run:

```bash
.venv/bin/python -m pytest tests/test_database.py::test_source_governance_tables_exist -q
git diff --check
git add src/db/migrations/012_source_governance.sql tests/test_database.py docs/data-model.md
git commit -m "feat: add source governance tables"
```

---

### Task 2: Add Source Registry Bootstrap

**Files:**
- Create: `src/core/source_registry.py`
- Modify: `src/main.py`
- Test: `tests/core/test_source_registry.py`

**Interfaces:**
- Produces `async def sync_sources_config(db: Database, sources: list[SourceConfig]) -> None`.
- Produces `async def list_schedulable_sources(db: Database) -> list[SourceConfig]`.
- Produces `async def update_source_status(db: Database, source_id: str, status: str, reason: str, manual: bool = False) -> bool`.

- [ ] **Step 1: Write failing registry tests**

Create `tests/core/test_source_registry.py`:

```python
from pathlib import Path

import pytest

from src.core.config import SourceConfig
from src.core.database import Database
from src.core.source_registry import (
    list_schedulable_sources,
    sync_sources_config,
    update_source_status,
)


@pytest.mark.asyncio
async def test_sync_sources_config_preserves_manual_disable(tmp_path):
    db = Database(
        tmp_path / "registry.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        source = SourceConfig(
            id="rss_test",
            name="RSS Test",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await sync_sources_config(db, [source])
        assert await update_source_status(
            db,
            "rss_test",
            "disabled",
            "manual disable",
            manual=True,
        )

        await sync_sources_config(db, [source])
        row = await db.fetch_one(
            "SELECT status, enabled, manual_override FROM source_registry WHERE id = ?",
            ("rss_test",),
        )
        assert row["status"] == "disabled"
        assert row["enabled"] == 0
        assert row["manual_override"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_list_schedulable_sources_returns_active_degraded_and_trial(tmp_path):
    db = Database(
        tmp_path / "registry.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        base = SourceConfig(
            id="rss_active",
            name="RSS Active",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await sync_sources_config(db, [base])
        for source_id, status in [
            ("rss_active", "active"),
            ("rss_trial", "trial"),
            ("rss_degraded", "degraded"),
            ("rss_disabled", "disabled"),
        ]:
            await db.execute(
                """
                INSERT OR REPLACE INTO source_registry
                (id, name, type, status, enabled, priority, cron, max_items, config_json)
                VALUES (?, ?, 'rss', ?, ?, 2, '0 */4 * * *', 10, '{"url":"https://example.com/feed.xml"}')
                """,
                (source_id, source_id, status, 0 if status == "disabled" else 1),
            )
        await db.commit()

        ids = {source.id for source in await list_schedulable_sources(db)}
        assert ids == {"rss_active", "rss_trial", "rss_degraded"}
    finally:
        await db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/core/test_source_registry.py -q`

Expected: FAIL because `src.core.source_registry` does not exist.

- [ ] **Step 3: Implement registry module**

Create `src/core/source_registry.py`:

```python
import json

from .config import SourceConfig
from .database import Database

SCHEDULABLE_STATUSES = {"active", "degraded", "trial"}


def _status_for_source(source: SourceConfig) -> str:
    return "active" if source.enabled else "disabled"


def _enabled_for_status(status: str) -> int:
    return 1 if status in SCHEDULABLE_STATUSES else 0


def _row_to_source(row) -> SourceConfig:
    return SourceConfig(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        enabled=bool(row["enabled"]),
        priority=row["priority"],
        cron=row["cron"],
        max_items=row["max_items"],
        config=json.loads(row["config_json"] or "{}"),
    )


async def sync_sources_config(db: Database, sources: list[SourceConfig]) -> None:
    for source in sources:
        existing = await db.fetch_one(
            "SELECT manual_override FROM source_registry WHERE id = ?",
            (source.id,),
        )
        if existing and existing["manual_override"]:
            continue
        status = _status_for_source(source)
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                status=excluded.status,
                enabled=excluded.enabled,
                priority=excluded.priority,
                cron=excluded.cron,
                max_items=excluded.max_items,
                config_json=excluded.config_json,
                updated_at=datetime('now', '+8 hours')
            """,
            (
                source.id,
                source.name,
                source.type,
                status,
                _enabled_for_status(status),
                source.priority,
                source.cron,
                source.max_items,
                json.dumps(source.config, ensure_ascii=False),
            ),
        )
    await db.commit()


async def list_schedulable_sources(db: Database) -> list[SourceConfig]:
    rows = await db.fetch_all(
        """
        SELECT *
        FROM source_registry
        WHERE enabled = 1 AND status IN ('active', 'degraded', 'trial')
        ORDER BY priority ASC, id ASC
        """
    )
    return [_row_to_source(row) for row in rows]


async def update_source_status(
    db: Database,
    source_id: str,
    status: str,
    reason: str,
    manual: bool = False,
) -> bool:
    current = await db.fetch_one(
        "SELECT status FROM source_registry WHERE id = ?",
        (source_id,),
    )
    if current is None:
        return False
    await db.execute(
        """
        UPDATE source_registry
        SET status = ?, enabled = ?, manual_override = ?, updated_at = datetime('now', '+8 hours')
        WHERE id = ?
        """,
        (status, _enabled_for_status(status), 1 if manual else 0, source_id),
    )
    await db.execute(
        """
        INSERT INTO source_governance_events
        (source_id, event, from_status, to_status, reason)
        VALUES (?, 'status_changed', ?, ?, ?)
        """,
        (source_id, current["status"], status, reason),
    )
    await db.commit()
    return True
```

- [ ] **Step 4: Wire startup sync**

In `src/main.py`, import:

```python
from .core.source_registry import sync_sources_config
```

In `lifespan()`, after `sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")`, add:

```python
    await sync_sources_config(_db, sources_cfg.sources)
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/python -m pytest tests/core/test_source_registry.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git diff --check
git add src/core/source_registry.py src/main.py tests/core/test_source_registry.py
git commit -m "feat: add source registry bootstrap"
```

---

### Task 3: Schedule Sources From Registry

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes `list_schedulable_sources(db) -> list[SourceConfig]`.
- Produces scheduler registration that uses registry statuses instead of raw `sources.yaml` enabled flags.

- [ ] **Step 1: Write failing scheduler test**

Add to `tests/test_scheduler.py`:

```python
def test_group_enabled_sources_keeps_only_schedulable_registry_statuses():
    from src.main import _group_enabled_sources_by_cron
    from src.core.config import SourceConfig

    sources = [
        SourceConfig(id="active", name="Active", type="rss", enabled=True, priority=1, cron="0 1 * * *", max_items=10, config={}),
        SourceConfig(id="trial", name="Trial", type="rss", enabled=True, priority=1, cron="0 1 * * *", max_items=10, config={}),
    ]

    grouped = _group_enabled_sources_by_cron(sources)
    assert grouped == {"0 1 * * *": ["active", "trial"]}
```

This locks the helper behavior used after registry filtering.

- [ ] **Step 2: Run test**

Run: `.venv/bin/python -m pytest tests/test_scheduler.py::test_group_enabled_sources_keeps_only_schedulable_registry_statuses -q`

Expected: PASS. This test locks the grouping helper while the next step changes where the source list comes from.

- [ ] **Step 3: Register jobs from registry**

In `src/main.py`, import:

```python
from .core.source_registry import list_schedulable_sources, sync_sources_config
```

Replace startup scheduler source loading with:

```python
    sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
    await sync_sources_config(_db, sources_cfg.sources)
    schedulable_sources = await list_schedulable_sources(_db)
    _scheduler = AsyncIOScheduler(timezone=BEIJING_TZ)
    _register_source_jobs(_scheduler, schedulable_sources, run_pipeline)
```

- [ ] **Step 4: Keep run_pipeline registry-compatible**

Inside `run_pipeline()`, keep existing `sources_cfg` loading for now:

```python
        sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
        active_sources = [s for s in sources_cfg.sources if s.enabled]
        active_sources = _filter_sources(active_sources, source_filter)
```

This remains valid because scheduled jobs pass explicit `source_filter` ids. Task 6 will move run-time source lookup fully to registry.

- [ ] **Step 5: Run scheduler tests**

Run: `.venv/bin/python -m pytest tests/test_scheduler.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git diff --check
git add src/main.py tests/test_scheduler.py
git commit -m "feat: schedule sources from registry"
```

---

### Task 4: Make Discovery Candidate-Only

**Files:**
- Modify: `src/core/source_discovery.py`
- Modify: `src/scheduler/source_scheduler.py`
- Test: `tests/core/test_source_governance.py`

**Interfaces:**
- Produces `SourceDiscovery.discover()` that writes candidates but does not cause `SourceManager.add()`.
- Consumes `source_registry.status = 'candidate'`.

- [ ] **Step 1: Write failing discovery test**

Create `tests/core/test_source_governance.py`:

```python
from pathlib import Path

import pytest

from src.core.config import SourceConfig
from src.core.database import Database
from src.core.source_discovery import SourceDiscovery


@pytest.mark.asyncio
async def test_discovered_source_is_candidate_only(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        discovery = SourceDiscovery(db)
        source = SourceConfig(
            id="rss_candidate",
            name="Candidate RSS",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await discovery._write_discovered_source(source)

        row = await db.fetch_one(
            "SELECT status, enabled FROM source_registry WHERE id = ?",
            ("rss_candidate",),
        )
        assert row["status"] == "candidate"
        assert row["enabled"] == 0
    finally:
        await db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/core/test_source_governance.py::test_discovered_source_is_candidate_only -q`

Expected: FAIL because `_write_discovered_source()` does not write `source_registry`.

- [ ] **Step 3: Update discovery writer**

In `src/core/source_discovery.py`, add `json` import and extend `_write_discovered_source()` after the existing `discovered_sources` insert:

```python
            await self._db.execute(
                """
                INSERT INTO source_registry
                (id, name, type, status, enabled, priority, cron, max_items, config_json)
                VALUES (?, ?, ?, 'candidate', 0, ?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (
                    source.id,
                    source.name,
                    source.type,
                    source.priority,
                    source.cron,
                    source.max_items,
                    json.dumps(source.config, ensure_ascii=False),
                ),
            )
```

- [ ] **Step 4: Stop auto-adding discovered sources**

In `src/scheduler/source_scheduler.py`, replace:

```python
        added_count = 0
        for source in new_sources:
            if SourceManager.add(source):
                added_count += 1
```

with:

```python
        added_count = 0
```

Keep the log field for compatibility; it should remain zero.

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/core/test_source_governance.py::test_discovered_source_is_candidate_only -q
.venv/bin/python -m pytest tests/core/test_source_registry.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git diff --check
git add src/core/source_discovery.py src/scheduler/source_scheduler.py tests/core/test_source_governance.py
git commit -m "feat: keep discovered sources as candidates"
```

---

### Task 5: Add Scoring And Status Transitions

**Files:**
- Create: `src/core/source_governance.py`
- Modify: `src/main.py`
- Test: `tests/core/test_source_governance.py`

**Interfaces:**
- Produces `def calculate_health_score(metrics: dict) -> float | None`.
- Produces `async def apply_governance(db: Database, source_id: str) -> str | None`.
- Produces `async def rollup_source_health_daily(db: Database, run_id: str) -> None`.

- [ ] **Step 1: Add failing scoring tests**

Append to `tests/core/test_source_governance.py`:

```python
from src.core.source_governance import calculate_health_score


def test_budget_blocked_does_not_score_source():
    assert calculate_health_score({"budget_blocked": 1}) is None


def test_health_score_uses_quality_freshness_and_cost():
    score = calculate_health_score({
        "request_success_rate": 1.0,
        "collected": 10,
        "new_items": 5,
        "approved": 2,
        "avg_score": 80,
        "cost": 0.02,
    })
    assert score == 66.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/core/test_source_governance.py::test_budget_blocked_does_not_score_source tests/core/test_source_governance.py::test_health_score_uses_quality_freshness_and_cost -q`

Expected: FAIL because `src.core.source_governance` does not exist.

- [ ] **Step 3: Implement scoring**

Create `src/core/source_governance.py`:

```python
from .database import Database
from .time import today_bj


def calculate_health_score(metrics: dict) -> float | None:
    if metrics.get("budget_blocked"):
        return None

    collected = metrics.get("collected", 0) or 0
    new_items = metrics.get("new_items", 0) or 0
    approved = metrics.get("approved", 0) or 0
    cost = metrics.get("cost", 0.0) or 0.0

    request_success = float(metrics.get("request_success_rate", 0) or 0)
    fresh_rate = new_items / collected if collected else 0
    approved_rate = approved / new_items if new_items else 0
    avg_score_norm = float(metrics.get("avg_score") or 0) / 100
    cost_efficiency = min((approved / cost) / 100, 1.0) if cost else 0

    score = (
        request_success * 25
        + fresh_rate * 20
        + approved_rate * 25
        + avg_score_norm * 20
        + cost_efficiency * 10
    )
    return round(score, 1)
```

- [ ] **Step 4: Add transition tests**

Append to `tests/core/test_source_governance.py`:

```python
from src.core.source_governance import apply_governance


@pytest.mark.asyncio
async def test_low_scores_progress_to_quarantine(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_low', 'Low', 'rss', 'active', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for day in ["2026-06-25", "2026-06-26", "2026-06-27"]:
            await db.execute(
                """
                INSERT INTO source_health_daily
                (source_id, date, health_score)
                VALUES ('rss_low', ?, 20)
                """,
                (day,),
            )
        await db.commit()

        status = await apply_governance(db, "rss_low")
        assert status == "quarantined"
    finally:
        await db.close()
```

- [ ] **Step 5: Implement transitions**

Append to `src/core/source_governance.py`:

```python
async def _change_status(db: Database, source_id: str, status: str, reason: str) -> str:
    row = await db.fetch_one(
        "SELECT status, manual_override FROM source_registry WHERE id = ?",
        (source_id,),
    )
    if row is None or row["manual_override"]:
        return row["status"] if row else ""
    if row["status"] == status:
        return status
    enabled = 1 if status in {"active", "degraded", "trial"} else 0
    await db.execute(
        """
        UPDATE source_registry
        SET status = ?, enabled = ?, updated_at = datetime('now', '+8 hours')
        WHERE id = ?
        """,
        (status, enabled, source_id),
    )
    await db.execute(
        """
        INSERT INTO source_governance_events
        (source_id, event, from_status, to_status, reason)
        VALUES (?, 'auto_transition', ?, ?, ?)
        """,
        (source_id, row["status"], status, reason),
    )
    await db.commit()
    return status


async def apply_governance(db: Database, source_id: str) -> str | None:
    rows = await db.fetch_all(
        """
        SELECT health_score
        FROM source_health_daily
        WHERE source_id = ? AND health_score IS NOT NULL
        ORDER BY date DESC
        LIMIT 3
        """,
        (source_id,),
    )
    if not rows:
        return None
    scores = [row["health_score"] for row in rows]
    latest = scores[0]
    current = await db.fetch_one(
        "SELECT status FROM source_registry WHERE id = ?",
        (source_id,),
    )
    if current is None:
        return None
    if len(scores) == 3 and all(score < 30 for score in scores):
        if current["status"] == "quarantined":
            return await _change_status(db, source_id, "disabled", "连续低分隔离后仍不达标")
        return await _change_status(db, source_id, "quarantined", "连续3次健康分低于30")
    if latest < 50 and current["status"] == "active":
        return await _change_status(db, source_id, "degraded", "健康分低于50")
    return current["status"]
```

- [ ] **Step 6: Implement daily rollup**

Append to `src/core/source_governance.py`:

```python
async def rollup_source_health_daily(db: Database, run_id: str) -> None:
    rows = await db.fetch_all(
        """
        SELECT *
        FROM pipeline_source_runs
        WHERE run_id = ?
        """,
        (run_id,),
    )
    date = today_bj()
    for row in rows:
        budget_blocked = 1 if row["analysis_failed"] and row["cost"] == 0 else 0
        metrics = {
            "request_success_rate": row["request_success_rate"],
            "collected": row["collected"],
            "new_items": row["new_items"],
            "approved": row["approved"],
            "avg_score": None,
            "cost": row["cost"],
            "budget_blocked": budget_blocked,
        }
        score = calculate_health_score(metrics)
        await db.execute(
            """
            INSERT INTO source_health_daily
            (source_id, date, request_success_rate, collected, new_items, analyzed,
             analysis_failed, approved, discarded, cost, tokens, health_score, budget_blocked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, date) DO UPDATE SET
                request_success_rate=excluded.request_success_rate,
                collected=source_health_daily.collected + excluded.collected,
                new_items=source_health_daily.new_items + excluded.new_items,
                analyzed=source_health_daily.analyzed + excluded.analyzed,
                analysis_failed=source_health_daily.analysis_failed + excluded.analysis_failed,
                approved=source_health_daily.approved + excluded.approved,
                discarded=source_health_daily.discarded + excluded.discarded,
                cost=source_health_daily.cost + excluded.cost,
                tokens=source_health_daily.tokens + excluded.tokens,
                health_score=excluded.health_score,
                budget_blocked=MAX(source_health_daily.budget_blocked, excluded.budget_blocked),
                updated_at=datetime('now', '+8 hours')
            """,
            (
                row["source_id"],
                date,
                row["request_success_rate"],
                row["collected"],
                row["new_items"],
                row["analyzed"],
                row["analysis_failed"],
                row["approved"],
                row["discarded"],
                row["cost"],
                row["tokens"],
                score,
                budget_blocked,
            ),
        )
        await apply_governance(db, row["source_id"])
    await db.commit()
```

- [ ] **Step 7: Call rollup after source summaries**

In `src/main.py`, import:

```python
from .core.source_governance import rollup_source_health_daily
```

After `_record_source_summaries(...)`, add:

```python
        await rollup_source_health_daily(_db, run_id)
```

- [ ] **Step 8: Run tests and commit**

Run:

```bash
.venv/bin/python -m pytest tests/core/test_source_governance.py -q
.venv/bin/python -m pytest tests/test_pipeline_observability.py -q
git diff --check
git add src/core/source_governance.py src/main.py tests/core/test_source_governance.py
git commit -m "feat: score and transition source governance"
```

---

### Task 6: Expose Governance In Source API

**Files:**
- Modify: `src/api/sources.py`
- Test: `tests/test_api_contracts.py`

**Interfaces:**
- Consumes `source_registry`, `source_health_daily`, and `source_governance_events`.
- Produces `governance_status`, `health_score`, `budget_blocked`, and `last_governance_reason` in `/api/sources/stats`.

- [ ] **Step 1: Write failing API contract test**

Add to `tests/test_api_contracts.py`:

```python
@pytest.mark.asyncio
async def test_source_stats_include_governance_fields(tmp_path, monkeypatch):
    db = Database(
        tmp_path / "api.db",
        migrations_dir=Path(__file__).parent.parent / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_test', 'RSS Test', 'rss', 'degraded', 1, 2, '0 1 * * *', 5, '{}')
            """
        )
        await db.execute(
            """
            INSERT INTO source_health_daily
            (source_id, date, health_score, budget_blocked)
            VALUES ('rss_test', '2026-06-27', 42, 1)
            """
        )
        await db.execute(
            """
            INSERT INTO source_governance_events
            (source_id, event, from_status, to_status, reason)
            VALUES ('rss_test', 'auto_transition', 'active', 'degraded', '健康分低于50')
            """
        )
        await db.commit()

        from src.api import sources as sources_api
        monkeypatch.setattr(sources_api, "_get_request_db", lambda: _async_db(db))
        monkeypatch.setattr(
            sources_api.SourceManager,
            "load",
            lambda: [
                SourceConfig(
                    id="rss_test",
                    name="RSS Test",
                    type="rss",
                    enabled=True,
                    priority=2,
                    cron="0 1 * * *",
                    max_items=5,
                    config={},
                )
            ],
        )

        payload = await sources_api.get_source_stats("week")
        source = payload["data"]["sources"][0]
        assert source["governance_status"] == "degraded"
        assert source["health_score"] == 42
        assert source["budget_blocked"] is True
        assert source["last_governance_reason"] == "健康分低于50"
    finally:
        await db.close()
```

If `_async_db` does not exist in this test file, add:

```python
async def _async_db(db):
    return db, False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_api_contracts.py::test_source_stats_include_governance_fields -q`

Expected: FAIL because fields are missing.

- [ ] **Step 3: Add API helper queries**

In `src/api/sources.py`, add:

```python
async def _get_governance_map(db: Database) -> dict[str, dict]:
    rows = await db.fetch_all("""
        SELECT sr.id, sr.status, shd.health_score, shd.budget_blocked
        FROM source_registry sr
        LEFT JOIN (
            SELECT source_id, health_score, budget_blocked
            FROM source_health_daily
            WHERE (source_id, date) IN (
                SELECT source_id, MAX(date)
                FROM source_health_daily
                GROUP BY source_id
            )
        ) shd ON shd.source_id = sr.id
    """)
    return {
        row["id"]: {
            "governance_status": row["status"],
            "health_score": row["health_score"],
            "budget_blocked": bool(row["budget_blocked"] or 0),
        }
        for row in rows
    }


async def _get_latest_governance_reasons(db: Database) -> dict[str, str]:
    rows = await db.fetch_all("""
        WITH ranked AS (
            SELECT source_id, reason,
                   ROW_NUMBER() OVER (
                       PARTITION BY source_id
                       ORDER BY created_at DESC, id DESC
                   ) AS row_number
            FROM source_governance_events
        )
        SELECT source_id, reason
        FROM ranked
        WHERE row_number = 1
    """)
    return {row["source_id"]: row["reason"] for row in rows}
```

- [ ] **Step 4: Include fields in stats**

Inside `get_source_stats()`, load:

```python
        governance_map = await _get_governance_map(db)
        governance_reasons = await _get_latest_governance_reasons(db)
```

In each source dict add:

```python
                "governance_status": governance_map.get(source.id, {}).get("governance_status"),
                "health_score": governance_map.get(source.id, {}).get("health_score"),
                "budget_blocked": governance_map.get(source.id, {}).get("budget_blocked", False),
                "last_governance_reason": governance_reasons.get(source.id),
```

- [ ] **Step 5: Run API tests**

Run: `.venv/bin/python -m pytest tests/test_api_contracts.py::test_source_stats_include_governance_fields -q`

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git diff --check
git add src/api/sources.py tests/test_api_contracts.py
git commit -m "feat: expose source governance status"
```

---

### Task 7: Update Dashboard Contract

**Files:**
- Modify: `src/site/static/js/dashboard/renderers.js`
- Modify: `src/site/static/css/style.css`
- Test: `tests/test_dashboard_frontend_contract.py`

**Interfaces:**
- Consumes source stats fields: `governance_status`, `health_score`, `budget_blocked`, `last_governance_reason`.
- Produces visible table columns for governance status and score.

- [ ] **Step 1: Write failing frontend contract test**

Add to `tests/test_dashboard_frontend_contract.py`:

```python
def test_dashboard_renders_source_governance_fields():
    renderers = Path("src/site/static/js/dashboard/renderers.js").read_text()
    assert "governance_status" in renderers
    assert "health_score" in renderers
    assert "budget_blocked" in renderers
    assert "last_governance_reason" in renderers
    assert "治理状态" in renderers
    assert "健康分" in renderers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dashboard_frontend_contract.py::test_dashboard_renders_source_governance_fields -q`

Expected: FAIL because renderer does not include these fields.

- [ ] **Step 3: Add renderer labels**

In `src/site/static/js/dashboard/renderers.js`, add:

```javascript
    function governanceLabel(status) {
        return {
            candidate: '候选',
            trial: '试运行',
            active: '运行中',
            degraded: '降权',
            quarantined: '隔离',
            disabled: '已禁用',
            rejected: '已拒绝',
        }[status] || '-';
    }
```

- [ ] **Step 4: Add table columns**

In the source table header, change:

```javascript
<th>数据源</th><th>状态</th><th>窗口采集</th><th>本轮新增</th>
```

to:

```javascript
<th>数据源</th><th>状态</th><th>治理状态</th><th>健康分</th><th>窗口采集</th><th>本轮新增</th>
```

In each row after the health status cell, add:

```javascript
<td><span class="source-governance-status ${escapeHtml(s.governance_status || '')}">${governanceLabel(s.governance_status)}</span></td>
<td>${s.health_score == null ? '-' : Number(s.health_score).toFixed(1)}</td>
```

Change the error cell content to prefer budget/governance context:

```javascript
const errorText = s.budget_blocked ? '预算阻断' : (s.last_error || s.last_governance_reason || '-');
```

Use `errorText` in the title and text.

- [ ] **Step 5: Add CSS**

In `src/site/static/css/style.css`, add:

```css
.source-governance-status {
  display: inline-block;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  background: #eef2ff;
  color: #3730a3;
  white-space: nowrap;
  font-size: 0.75rem;
}
.source-governance-status.degraded { background: #fef3c7; color: #92400e; }
.source-governance-status.quarantined,
.source-governance-status.disabled,
.source-governance-status.rejected { background: #fee2e2; color: #991b1b; }
.source-governance-status.active,
.source-governance-status.trial { background: #dcfce7; color: #166534; }
```

- [ ] **Step 6: Run frontend test**

Run: `.venv/bin/python -m pytest tests/test_dashboard_frontend_contract.py::test_dashboard_renders_source_governance_fields -q`

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git diff --check
git add src/site/static/js/dashboard/renderers.js src/site/static/css/style.css tests/test_dashboard_frontend_contract.py
git commit -m "feat: show source governance in dashboard"
```

---

### Task 8: Final Documentation And Verification

**Files:**
- Modify: `docs/api.md`
- Modify: `docs/codemap.md`
- Modify: `docs/operations.md`
- Modify: `docs/task.md`

**Interfaces:**
- Documents API fields, source governance entry points, and operational rules.

- [ ] **Step 1: Update API docs**

In `docs/api.md`, update `/api/sources/stats` response fields with:

```markdown
- `governance_status`: candidate/trial/active/degraded/quarantined/disabled/rejected
- `health_score`: 自动治理健康分，预算阻断轮次不更新
- `budget_blocked`: 最近健康汇总是否被预算阻断
- `last_governance_reason`: 最近自动治理动作原因
```

- [ ] **Step 2: Update codemap**

In `docs/codemap.md`, add:

```markdown
- `src/core/source_registry.py`
  - DB-backed source registry; syncs `sources.yaml` bootstrap data and returns schedulable sources.
- `src/core/source_governance.py`
  - Computes daily source health scores and applies automatic status transitions.
```

- [ ] **Step 3: Update operations**

In `docs/operations.md`, add:

```markdown
- **数据源自动治理**：预算阻断不计入源质量；自动动作只会降权、隔离或禁用，不会删除。人工禁用不会被自动恢复。
```

- [ ] **Step 4: Update task ledger**

In `docs/task.md`, add a completed section summarizing source governance automation.

- [ ] **Step 5: Run full affected tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_database.py \
  tests/core/test_source_registry.py \
  tests/core/test_source_governance.py \
  tests/test_api_contracts.py \
  tests/test_dashboard_frontend_contract.py \
  tests/test_pipeline_observability.py \
  tests/test_scheduler.py -q
```

Expected: PASS.

- [ ] **Step 6: Run final checks and commit**

Run:

```bash
git diff --check
git status --short
git add docs/api.md docs/codemap.md docs/operations.md docs/task.md
git commit -m "docs: document source governance automation"
```
