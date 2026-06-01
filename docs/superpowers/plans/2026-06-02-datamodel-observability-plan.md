# Data Model Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Extend the data model so the dashboard can explain collection funnels, source effectiveness, and LLM cost failures with durable facts.

**Architecture:** Keep `articles` as the approved/retry content result table. Add process-level tables for collection item events and per-run source funnels, then extend `cost_logs` with lightweight audit columns. Existing aggregate tables remain for fast dashboard reads.

**Tech Stack:** Python 3.12+, SQLite migrations, aiosqlite, Pydantic v2, pytest-asyncio.

---

### Task 1: Schema and Database Operations

**Files:**
- Create: `src/db/migrations/008_observability_tables.sql`
- Modify: `src/db/operations.py`
- Test: `tests/test_database.py`

- [x] Write failing tests for new tables and helper functions.
- [x] Run targeted tests and confirm failure because tables/functions are missing.
- [x] Add migration 008 with `collection_items`, `pipeline_source_runs`, and extra `cost_logs` audit columns.
- [x] Add focused operation helpers to upsert collection items and source-run summaries.
- [x] Run targeted tests and confirm pass.

### Task 2: Pipeline Integration

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_pipeline_observability.py`

- [x] Write failing tests for pipeline source funnel calculation from collected/new/reviewed/cost records.
- [x] Run targeted tests and confirm failure because funnel helper is missing.
- [x] Add small pure helpers for source summaries and collection item status transitions.
- [x] Persist collected, dedup-skipped, reviewed, and inserted status records in the pipeline.
- [x] Persist one `pipeline_source_runs` row per run/source.
- [x] Run targeted tests and confirm pass.

### Task 3: Cost Log Audit Fields

**Files:**
- Modify: `src/graph/state.py`
- Modify: `src/graph/analyzers/base.py`
- Modify: `src/graph/reviewer.py`
- Modify: `src/db/operations.py`
- Test: `tests/test_cost_accounting.py`

- [x] Write failing tests for `CostRecord` status, attempt number, prompt name, and parse failure persistence.
- [x] Run targeted tests and confirm failure.
- [x] Extend `CostRecord` and `save_cost_log` with audit columns.
- [x] Set success/parse failure audit data in analyzer and reviewer call paths.
- [x] Run targeted tests and confirm pass.

### Task 4: Documentation and Verification

**Files:**
- Modify: `docs/data-model.md`
- Modify: `docs/api.md`
- Modify: `docs/codemap.md`
- Modify: `docs/task.md`

- [x] Fix current doc/schema mismatches for `pipeline_phase_logs`, `schema_version`, `extra_data`, and DAG sample.
- [x] Document `collection_items`, `pipeline_source_runs`, and `cost_logs` audit columns.
- [x] Run `uv run pytest -m "not integration and not e2e"` or `.venv/bin/python -m pytest -m "not integration and not e2e"`.
- [x] Check `git status --short`.
