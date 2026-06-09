# Deep Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automatic, condition-triggered, source-code-level GitHub deep analysis module that creates evidence-backed repo reports without blocking the main pipeline.

**Architecture:** Add an independent `deep_reports` module after the existing Reviewer/persist flow. The module selects at most one high-value GitHub repo, clones it into a temporary directory, scans source structure deterministically, sends a compact evidence package to an LLM, persists the report, exposes it through API endpoints, and renders static pages.

**Tech Stack:** Python 3.12+, SQLite/aiosqlite, FastAPI, Pydantic v2, existing `LLMRegistry`, Jinja2 static site builder, pytest.

---

## File Structure

Create:

- `src/db/migrations/010_deep_reports.sql`
  Adds `deep_reports` table and bumps `schema_version` to 10.

- `src/deep_reports/__init__.py`
  Package marker.

- `src/deep_reports/models.py`
  Pydantic models and dataclasses for candidate selection, repo inspection, source package, and report output.

- `src/deep_reports/selector.py`
  Selects at most one GitHub repo candidate from current pipeline state.

- `src/deep_reports/inspector.py`
  Clones repo, filters files, extracts README/manifest/tree/key files, never executes repo code.

- `src/deep_reports/summarizer.py`
  Converts raw repo scan into a compact LLM input package.

- `src/deep_reports/analyzer.py`
  Calls LLM through existing registry and parses deep report JSON.

- `src/deep_reports/service.py`
  Orchestrates selector → inspector → summarizer → analyzer → persistence and emits DAG events.

- `src/api/deep_reports.py`
  FastAPI endpoints for report list/latest/detail.

- `src/site/templates/deep.html`
  Static list page shell.

- `src/site/templates/deep-report.html`
  Static detail page shell.

- `src/site/static/js/deep-reports.js`
  Browser-side fetch and rendering for deep reports.

- `prompts/deep_report.md`
  Prompt for source-code-level repo analysis.

- `tests/test_deep_reports_db.py`
  Migration and DB operations tests.

- `tests/test_deep_reports_selector.py`
  Candidate scoring and dedupe tests.

- `tests/test_repo_inspector.py`
  File filtering, manifest parsing, and key file extraction tests.

- `tests/test_deep_reports_analyzer.py`
  JSON parsing and prompt contract tests.

- `tests/test_deep_reports_api.py`
  API contract tests.

- `tests/test_deep_reports_pipeline.py`
  Pipeline orchestration tests proving deep failures do not fail main pipeline.

Modify:

- `src/db/operations.py`
  Add insert/query helpers for `deep_reports`.

- `src/main.py`
  Register deep report API router and call deep report service after source-run summaries.

- `src/site/builder.py`
  Render new static pages.

- `src/site/templates/base.html`
  Add navigation link for deep reports.

- `src/site/static/css/style.css`
  Add restrained styles for deep report list/detail.

- `config/agents.yaml`
  Add `deep_report` agent configuration.

- `docs/api.md`
  Document new API endpoints.

- `docs/data-model.md`
  Document `deep_reports` table.

- `docs/architecture.md`
  Add deep report post-pipeline stage.

- `docs/codemap.md`
  Add module entry points.

- `docs/task.md`
  Add task breakdown/status.

---

### Task 1: Add `deep_reports` Data Model

**Files:**
- Create: `src/db/migrations/010_deep_reports.sql`
- Modify: `src/db/operations.py`
- Test: `tests/test_deep_reports_db.py`, `tests/test_database.py`

- [ ] **Step 1: Write failing migration test**

Add to `tests/test_deep_reports_db.py`:

```python
import json

import pytest

from src.core.database import Database
from src.db.operations import get_deep_report, list_deep_reports, save_deep_report


@pytest.mark.asyncio
async def test_save_and_query_deep_report(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    await db.initialize()
    await db.migrate()

    report_id = await save_deep_report(
        db,
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
        article_id=12,
        run_id="run_1",
        commit_sha="abc123",
        status="completed",
        candidate_score=88,
        trigger_reason="实用性高，源码结构清晰",
        report_json={"project_overview": "overview"},
        report_markdown="# org/tool",
        evidence_json=[{"path": "src/main.py", "reason": "entry"}],
        tech_stack_json={"languages": ["Python"]},
        file_tree_summary="src/main.py\npyproject.toml",
        analysis_cost=0.012,
        analysis_tokens=2048,
        error="",
    )

    detail = await get_deep_report(db, report_id)
    assert detail["repo_name"] == "org/tool"
    assert detail["report_json"]["project_overview"] == "overview"
    assert detail["evidence_json"][0]["path"] == "src/main.py"

    reports = await list_deep_reports(db, page=1, page_size=10)
    assert reports["total"] == 1
    assert reports["items"][0]["id"] == report_id
```

Modify `tests/test_database.py` expected schema version from 9 to 10 and assert `deep_reports` exists:

```python
assert version["version"] == 10
assert "deep_reports" in tables
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_deep_reports_db.py tests/test_database.py::test_initialize_and_migrate -q
```

Expected: FAIL because migration and operations do not exist.

- [ ] **Step 3: Add migration**

Create `src/db/migrations/010_deep_reports.sql`:

```sql
-- src/db/migrations/010_deep_reports.sql

CREATE TABLE IF NOT EXISTS deep_reports (
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
    UNIQUE(repo_url, commit_sha)
);

CREATE INDEX IF NOT EXISTS idx_deep_reports_status_created
    ON deep_reports(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deep_reports_repo_url
    ON deep_reports(repo_url);
CREATE INDEX IF NOT EXISTS idx_deep_reports_run_id
    ON deep_reports(run_id);

INSERT OR REPLACE INTO schema_version (version) VALUES (10);
```

- [ ] **Step 4: Add DB operations**

Append to `src/db/operations.py`:

```python
def _decode_json_field(value: str, fallback):
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _deep_report_row(row) -> dict:
    item = dict(row)
    item["report_json"] = _decode_json_field(item.get("report_json", ""), {})
    item["evidence_json"] = _decode_json_field(item.get("evidence_json", ""), [])
    item["tech_stack_json"] = _decode_json_field(item.get("tech_stack_json", ""), {})
    return item


async def save_deep_report(
    db: Database,
    *,
    repo_url: str,
    repo_name: str,
    article_id: int | None,
    run_id: str,
    commit_sha: str,
    status: str,
    candidate_score: int,
    trigger_reason: str,
    report_json: dict,
    report_markdown: str,
    evidence_json: list,
    tech_stack_json: dict,
    file_tree_summary: str,
    analysis_cost: float,
    analysis_tokens: int,
    error: str,
) -> int:
    await db.execute(
        """
        INSERT INTO deep_reports
        (repo_url, repo_name, article_id, run_id, commit_sha, status, candidate_score,
         trigger_reason, report_json, report_markdown, evidence_json, tech_stack_json,
         file_tree_summary, analysis_cost, analysis_tokens, error, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(repo_url, commit_sha) DO UPDATE SET
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
        RETURNING id
        """,
        (
            repo_url,
            repo_name,
            article_id,
            run_id,
            commit_sha,
            status,
            candidate_score,
            trigger_reason,
            json.dumps(report_json, ensure_ascii=False, separators=(",", ":")),
            report_markdown,
            json.dumps(evidence_json, ensure_ascii=False, separators=(",", ":")),
            json.dumps(tech_stack_json, ensure_ascii=False, separators=(",", ":")),
            file_tree_summary,
            analysis_cost,
            analysis_tokens,
            error,
            now_bj_iso(),
        ),
    )
    row = await db.fetch_one("SELECT last_insert_rowid() AS id")
    await db.commit()
    return row["id"] if row else 0


async def get_deep_report(db: Database, report_id: int) -> dict | None:
    row = await db.fetch_one("SELECT * FROM deep_reports WHERE id=?", (report_id,))
    return _deep_report_row(row) if row else None


async def get_latest_deep_report(db: Database) -> dict | None:
    row = await db.fetch_one(
        "SELECT * FROM deep_reports WHERE status='completed' ORDER BY created_at DESC LIMIT 1"
    )
    return _deep_report_row(row) if row else None


async def list_deep_reports(db: Database, page: int = 1, page_size: int = 20) -> dict:
    offset = (page - 1) * page_size
    rows = await db.fetch_all(
        "SELECT * FROM deep_reports ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (page_size, offset),
    )
    total = await db.fetch_one("SELECT COUNT(*) AS count FROM deep_reports")
    return {
        "items": [_deep_report_row(row) for row in rows],
        "total": total["count"] if total else 0,
        "page": page,
        "page_size": page_size,
    }
```

Ensure `src/db/operations.py` already imports `json`, `Database`, and `now_bj_iso`; add missing imports only if absent.

- [ ] **Step 5: Run tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_deep_reports_db.py tests/test_database.py::test_initialize_and_migrate -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/db/migrations/010_deep_reports.sql src/db/operations.py tests/test_deep_reports_db.py tests/test_database.py
git commit -m "Add deep reports persistence"
```

---

### Task 2: Add Deep Report API

**Files:**
- Create: `src/api/deep_reports.py`
- Modify: `src/main.py`
- Test: `tests/test_deep_reports_api.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_deep_reports_api.py`:

```python
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.deep_reports import router, set_db
from src.core.database import Database
from src.db.operations import save_deep_report


@pytest.mark.asyncio
async def test_deep_reports_list_latest_and_detail(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    await db.initialize()
    await db.migrate()
    report_id = await save_deep_report(
        db,
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
        article_id=None,
        run_id="run_1",
        commit_sha="abc123",
        status="completed",
        candidate_score=88,
        trigger_reason="实用性高",
        report_json={"project_overview": "overview"},
        report_markdown="# Report",
        evidence_json=[],
        tech_stack_json={"languages": ["Python"]},
        file_tree_summary="src/main.py",
        analysis_cost=0.01,
        analysis_tokens=100,
        error="",
    )

    app = FastAPI()
    set_db(db)
    app.include_router(router, prefix="/api")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listing = await client.get("/api/deep-reports")
        latest = await client.get("/api/deep-reports/latest")
        detail = await client.get(f"/api/deep-reports/{report_id}")
        missing = await client.get("/api/deep-reports/999")

    assert listing.status_code == 200
    assert listing.json()["data"]["total"] == 1
    assert latest.json()["data"]["repo_name"] == "org/tool"
    assert detail.json()["data"]["id"] == report_id
    assert missing.status_code == 404
    assert missing.json()["code"] == 40401
```

- [ ] **Step 2: Run test to verify failure**

```bash
.venv/bin/python -m pytest tests/test_deep_reports_api.py -q
```

Expected: FAIL because `src.api.deep_reports` does not exist.

- [ ] **Step 3: Implement API router**

Create `src/api/deep_reports.py`:

```python
from fastapi import APIRouter, HTTPException, Query

from ..api.responses import envelope
from ..core.database import Database
from ..db.operations import get_deep_report, get_latest_deep_report, list_deep_reports

router = APIRouter()
_db: Database | None = None


def set_db(db: Database):
    global _db
    _db = db


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")
    return _db


@router.get("/deep-reports")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return envelope(await list_deep_reports(_require_db(), page=page, page_size=page_size))


@router.get("/deep-reports/latest")
async def latest_report():
    report = await get_latest_deep_report(_require_db())
    return envelope(report or {})


@router.get("/deep-reports/{report_id}")
async def report_detail(report_id: int):
    report = await get_deep_report(_require_db(), report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"深度报告 {report_id} 不存在")
    return envelope(report)
```

Modify `src/main.py`:

```python
from .api.deep_reports import router as deep_reports_router, set_db as set_deep_reports_db
```

Inside `create_app()` or lifespan setup, mirror existing DB injection:

```python
set_deep_reports_db(_db)
app.include_router(deep_reports_router, prefix="/api")
```

Use the exact location where other routers are registered.

- [ ] **Step 4: Run tests**

```bash
.venv/bin/python -m pytest tests/test_deep_reports_api.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/deep_reports.py src/main.py tests/test_deep_reports_api.py
git commit -m "Add deep report API"
```

---

### Task 3: Implement Repo Inspector

**Files:**
- Create: `src/deep_reports/__init__.py`
- Create: `src/deep_reports/models.py`
- Create: `src/deep_reports/inspector.py`
- Test: `tests/test_repo_inspector.py`

- [ ] **Step 1: Write failing inspector tests**

Create `tests/test_repo_inspector.py`:

```python
from pathlib import Path

from src.deep_reports.inspector import inspect_local_repo


def test_inspect_local_repo_filters_generated_files_and_finds_key_files(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Tool\nUseful AI repo", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname='tool'\ndependencies=['fastapi']\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    (repo / "src" / "models.py").write_text("class Document: pass\n", encoding="utf-8")
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "ignored.js").write_text("ignored", encoding="utf-8")
    (repo / "dist").mkdir()
    (repo / "dist" / "bundle.js").write_text("ignored", encoding="utf-8")

    result = inspect_local_repo(repo, repo_url="https://github.com/org/tool", repo_name="org/tool")

    assert result.readme.startswith("# Tool")
    assert "pyproject.toml" in result.manifests
    assert "src/main.py" in result.entry_files
    assert "src/models.py" in [item.path for item in result.key_files]
    assert all("node_modules" not in item.path for item in result.key_files)
    assert all("dist" not in path for path in result.file_tree)
```

- [ ] **Step 2: Run test to verify failure**

```bash
.venv/bin/python -m pytest tests/test_repo_inspector.py -q
```

Expected: FAIL because package does not exist.

- [ ] **Step 3: Add models**

Create `src/deep_reports/__init__.py` as an empty file.

Create `src/deep_reports/models.py`:

```python
from pydantic import BaseModel, Field


class RepoFile(BaseModel):
    path: str
    size: int
    content: str = ""
    reason: str = ""


class RepoInspection(BaseModel):
    repo_url: str
    repo_name: str
    commit_sha: str = ""
    readme: str = ""
    manifests: dict[str, str] = Field(default_factory=dict)
    file_tree: list[str] = Field(default_factory=list)
    entry_files: list[str] = Field(default_factory=list)
    key_files: list[RepoFile] = Field(default_factory=list)
    skipped_reason: str = ""
```

- [ ] **Step 4: Add inspector implementation**

Create `src/deep_reports/inspector.py`:

```python
import subprocess
import tempfile
from pathlib import Path

from .models import RepoFile, RepoInspection

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "vendor", ".venv",
    "coverage", "__pycache__", ".next", ".cache",
}
MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "go.mod",
    "Cargo.toml", "Dockerfile", "docker-compose.yml",
}
ENTRY_NAMES = {
    "main.py", "app.py", "server.py", "cli.py", "index.ts", "index.js",
    "main.ts", "main.js", "server.ts", "server.js",
}
KEY_PATH_PARTS = {
    "src", "app", "packages", "models", "schema", "db", "store",
    "graph", "agent", "index", "api", "server", "cli",
}


def _is_text_file(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\0" not in chunk


def _should_skip(path: Path, root: Path) -> bool:
    rel_parts = path.relative_to(root).parts
    return any(part in SKIP_DIRS for part in rel_parts)


def _read_limited(path: Path, limit: int = 80_000) -> str:
    data = path.read_bytes()[:limit]
    return data.decode("utf-8", errors="replace")


def inspect_local_repo(root: Path, *, repo_url: str, repo_name: str) -> RepoInspection:
    file_tree: list[str] = []
    manifests: dict[str, str] = {}
    entry_files: list[str] = []
    key_files: list[RepoFile] = []
    readme = ""

    for path in sorted(root.rglob("*")):
        if not path.is_file() or _should_skip(path, root):
            continue
        rel = path.relative_to(root).as_posix()
        if path.stat().st_size > 80_000 or not _is_text_file(path):
            continue

        file_tree.append(rel)
        if path.name.lower().startswith("readme") and not readme:
            readme = _read_limited(path)
        if path.name in MANIFEST_NAMES:
            manifests[rel] = _read_limited(path)
        if path.name in ENTRY_NAMES:
            entry_files.append(rel)

        parts = set(Path(rel).parts)
        if len(key_files) < 15 and (parts & KEY_PATH_PARTS or path.name in ENTRY_NAMES):
            key_files.append(RepoFile(
                path=rel,
                size=path.stat().st_size,
                content=_read_limited(path),
                reason="入口文件" if path.name in ENTRY_NAMES else "核心目录源码",
            ))

    return RepoInspection(
        repo_url=repo_url,
        repo_name=repo_name,
        readme=readme,
        manifests=manifests,
        file_tree=file_tree[:300],
        entry_files=entry_files[:20],
        key_files=key_files,
    )


def clone_and_inspect(repo_url: str, repo_name: str, timeout_seconds: int = 60) -> RepoInspection:
    with tempfile.TemporaryDirectory(prefix="deep-report-") as tmp:
        root = Path(tmp) / "repo"
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(root)],
            check=True,
            timeout=timeout_seconds,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            timeout=10,
        ).strip()
        result = inspect_local_repo(root, repo_url=repo_url, repo_name=repo_name)
        return result.model_copy(update={"commit_sha": commit})
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/test_repo_inspector.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/deep_reports/__init__.py src/deep_reports/models.py src/deep_reports/inspector.py tests/test_repo_inspector.py
git commit -m "Add repo inspector for deep reports"
```

---

### Task 4: Implement Source Summarizer

**Files:**
- Create: `src/deep_reports/summarizer.py`
- Modify: `src/deep_reports/models.py`
- Test: `tests/test_repo_inspector.py`

- [ ] **Step 1: Write failing summarizer test**

Append to `tests/test_repo_inspector.py`:

```python
from src.deep_reports.models import RepoFile, RepoInspection
from src.deep_reports.summarizer import build_source_package


def test_build_source_package_extracts_stack_and_evidence():
    inspection = RepoInspection(
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
        readme="# Tool\nAI repo analyzer",
        manifests={"pyproject.toml": "[project]\ndependencies=['fastapi','openai']"},
        file_tree=["pyproject.toml", "src/main.py", "src/models.py"],
        entry_files=["src/main.py"],
        key_files=[
            RepoFile(path="src/main.py", size=20, content="from fastapi import FastAPI", reason="入口文件"),
            RepoFile(path="src/models.py", size=20, content="class Document: pass", reason="核心目录源码"),
        ],
    )

    package = build_source_package(inspection)

    assert package.repo_name == "org/tool"
    assert "Python" in package.tech_stack["languages"]
    assert "FastAPI" in package.tech_stack["frameworks"]
    assert package.entry_files == ["src/main.py"]
    assert package.evidence[0]["path"] == "pyproject.toml"
```

- [ ] **Step 2: Run test to verify failure**

```bash
.venv/bin/python -m pytest tests/test_repo_inspector.py::test_build_source_package_extracts_stack_and_evidence -q
```

Expected: FAIL because summarizer does not exist.

- [ ] **Step 3: Add model**

Add to `src/deep_reports/models.py`:

```python
class SourcePackage(BaseModel):
    repo_url: str
    repo_name: str
    commit_sha: str = ""
    readme_excerpt: str = ""
    tech_stack: dict = Field(default_factory=dict)
    file_tree_summary: str = ""
    entry_files: list[str] = Field(default_factory=list)
    key_files: list[RepoFile] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
```

- [ ] **Step 4: Implement summarizer**

Create `src/deep_reports/summarizer.py`:

```python
from .models import RepoInspection, SourcePackage


def _detect_tech_stack(manifests: dict[str, str], file_tree: list[str]) -> dict:
    languages = set()
    frameworks = set()
    dependencies = set()
    joined = "\n".join(manifests.values()).lower()

    if any(path.endswith(".py") for path in file_tree) or "pyproject.toml" in manifests:
        languages.add("Python")
    if any(path.endswith((".ts", ".tsx", ".js", ".jsx")) for path in file_tree) or "package.json" in manifests:
        languages.add("JavaScript/TypeScript")
    if "go.mod" in manifests:
        languages.add("Go")
    if "cargo.toml" in {path.lower() for path in manifests}:
        languages.add("Rust")

    if "fastapi" in joined:
        frameworks.add("FastAPI")
    if "next" in joined:
        frameworks.add("Next.js")
    if "react" in joined:
        frameworks.add("React")
    if "openai" in joined:
        dependencies.add("OpenAI")
    if "langchain" in joined:
        dependencies.add("LangChain")

    return {
        "languages": sorted(languages),
        "frameworks": sorted(frameworks),
        "dependencies": sorted(dependencies),
    }


def build_source_package(inspection: RepoInspection) -> SourcePackage:
    evidence = []
    for path in inspection.manifests:
        evidence.append({"path": path, "reason": "manifest 显示技术栈和依赖"})
    for path in inspection.entry_files:
        evidence.append({"path": path, "reason": "入口文件"})
    for item in inspection.key_files[:10]:
        evidence.append({"path": item.path, "reason": item.reason})

    return SourcePackage(
        repo_url=inspection.repo_url,
        repo_name=inspection.repo_name,
        commit_sha=inspection.commit_sha,
        readme_excerpt=inspection.readme[:4000],
        tech_stack=_detect_tech_stack(inspection.manifests, inspection.file_tree),
        file_tree_summary="\n".join(inspection.file_tree[:300]),
        entry_files=inspection.entry_files,
        key_files=inspection.key_files[:15],
        evidence=evidence[:30],
    )
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/test_repo_inspector.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/deep_reports/models.py src/deep_reports/summarizer.py tests/test_repo_inspector.py
git commit -m "Add source package summarizer"
```

---

### Task 5: Implement Candidate Selector

**Files:**
- Create: `src/deep_reports/selector.py`
- Modify: `src/deep_reports/models.py`
- Test: `tests/test_deep_reports_selector.py`

**Final selector rules:**
- Only GitHub repository root URLs are eligible: `https://github.com/{owner}/{repo}` with optional trailing `/` and optional repo suffix `.git`; reject issue/tree/pull/query/fragment URLs.
- Normalize every accepted candidate to `repo_url="https://github.com/{owner}/{repo}"` and `repo_name="{owner}/{repo}"`; use this normalized `repo_url` for candidate output and recent-report lookup.
- Skip only recent `status='completed'` reports in the last 7 Beijing-time days: `datetime(updated_at) >= datetime('now', '+8 hours', '-7 days')`.
- Recent `pending`, `report`, and `failed` rows do not suppress retry.
- Build the candidate first, then apply `candidate_score >= 70`; do not pre-filter by reviewer `total_score`.
- Source priority uses both `source_id` and `source_detail`: `github_ai_devtools > github_trending_velocity > github_trending_hot > github_trending > others`. `source_detail` terms such as `ai`, `devtools`, `agent`, `rag`, and `code` should be treated as GitHub AI-tool source signals when `source_id` is absent.
- Effective `source_detail` is `analyzed.source_detail` first, then `raw.source_detail`; use the same effective value for source priority, source-detail score bonus, and `DeepReportCandidate.source_detail`.
- `raw.raw_metadata["topics"]` and `AnalyzedItem.tags` may be absent or malformed; only list/tuple/set values contribute to practical hits. Integers and strings are treated as empty collections.

- [ ] **Step 1: Write failing selector tests**

Create `tests/test_deep_reports_selector.py`:

```python
import pytest

from src.core.database import Database
from src.db.operations import save_deep_report
from src.deep_reports.selector import select_deep_report_candidate
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem


@pytest.mark.asyncio
async def test_selector_prefers_practical_github_ai_tool(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    await db.initialize()
    await db.migrate()
    raw_items = [
        RawItem(
            url="https://github.com/org/tool",
            title="AI Code Tool",
            source="github",
            source_detail="org/tool",
            raw_metadata={"source_id": "github_ai_devtools", "stars": 1200, "forks": 80, "topics": ["agent", "code"]},
        ),
        RawItem(
            url="https://example.com/news",
            title="AI News",
            source="rss",
            source_detail="36氪",
            raw_metadata={"source_id": "rss_36kr"},
        ),
    ]
    analyzed = [
        AnalyzedItem(ref_url=raw_items[0].url, title="AI Code Tool", summary="agent code tool", tags=["Agent", "开发工具"]),
        AnalyzedItem(ref_url=raw_items[1].url, title="AI News", summary="news", tags=["AI"]),
    ]
    reviewed = [
        ReviewedItem(ref_url=raw_items[0].url, total_score=82, dimensions={}, verdict="approved"),
        ReviewedItem(ref_url=raw_items[1].url, total_score=90, dimensions={}, verdict="approved"),
    ]

    candidate = await select_deep_report_candidate(db, raw_items, analyzed, reviewed)

    assert candidate is not None
    assert candidate.repo_url == "https://github.com/org/tool"
    assert candidate.repo_name == "org/tool"
    assert candidate.candidate_score >= 70


@pytest.mark.asyncio
async def test_selector_skips_recently_reported_repo(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    await db.initialize()
    await db.migrate()
    await save_deep_report(
        db,
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
        article_id=None,
        run_id="run_old",
        commit_sha="abc",
        status="completed",
        candidate_score=88,
        trigger_reason="recent",
        report_json={},
        report_markdown="",
        evidence_json=[],
        tech_stack_json={},
        file_tree_summary="",
        analysis_cost=0,
        analysis_tokens=0,
        error="",
    )
    raw = RawItem(
        url="https://github.com/org/tool",
        title="AI Code Tool",
        source="github",
        source_detail="org/tool",
        raw_metadata={"source_id": "github_ai_devtools", "stars": 1200},
    )
    analyzed = [AnalyzedItem(ref_url=raw.url, title=raw.title, summary="agent code tool", tags=["Agent"])]
    reviewed = [ReviewedItem(ref_url=raw.url, total_score=85, dimensions={}, verdict="approved")]

    candidate = await select_deep_report_candidate(db, [raw], analyzed, reviewed)

    assert candidate is None
```

- [ ] **Step 2: Run test to verify failure**

```bash
.venv/bin/python -m pytest tests/test_deep_reports_selector.py -q
```

Expected: FAIL because selector does not exist.

- [ ] **Step 3: Add candidate model**

Add to `src/deep_reports/models.py`:

```python
class DeepReportCandidate(BaseModel):
    repo_url: str
    repo_name: str
    article_id: int | None = None
    source_id: str = ""
    source_detail: str = ""
    title: str = ""
    summary: str = ""
    reviewer_score: int = 0
    candidate_score: int = 0
    trigger_reason: str = ""
    metadata: dict = Field(default_factory=dict)
```

- [ ] **Step 4: Implement selector**

Create `src/deep_reports/selector.py`:

```python
import re
from urllib.parse import urlparse

from src.core.database import Database
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

from .models import DeepReportCandidate

PREFERRED_SOURCES = {
    "github_ai_devtools": 25,
    "github_trending_velocity": 18,
    "github_trending_hot": 14,
    "github_trending": 8,
}
PRACTICAL_TERMS = {
    "tool", "agent", "code", "developer", "rag", "mcp", "cli",
    "knowledge", "graph", "automation", "workflow", "copilot",
}
AI_DEVTOOLS_SOURCE_TERMS = {"ai", "devtools", "agent", "rag", "code", "mcp", "developer"}


def _source_key(source_id: str, source_detail: str) -> str:
    if source_id in PREFERRED_SOURCES:
        return source_id
    detail_terms = set(re.findall(r"[a-z0-9]+", source_detail.lower()))
    if detail_terms & AI_DEVTOOLS_SOURCE_TERMS:
        return "github_ai_devtools"
    if "trending velocity" in source_detail.lower():
        return "github_trending_velocity"
    if "trending hot" in source_detail.lower():
        return "github_trending_hot"
    if "trending" in source_detail.lower():
        return "github_trending"
    return source_id


def _repo_info(url: str) -> tuple[str, str] | None:
    """Return (repo_name, normalized_repo_url), or None for non-root GitHub URLs."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
        return None
    if parsed.params or parsed.query or parsed.fragment:
        return None
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if len(parts) != 2:
        return None
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return None
    repo_name = f"{owner}/{repo}"
    return repo_name, f"https://github.com/{repo_name}"


async def _has_recent_report(db: Database, repo_url: str) -> bool:
    row = await db.fetch_one(
        """
        SELECT id FROM deep_reports
        WHERE repo_url = ?
          AND status = 'completed'
          AND datetime(updated_at) >= datetime('now', '+8 hours', '-7 days')
        LIMIT 1
        """,
        (repo_url,),
    )
    return row is not None


def _effective_source_detail(raw: RawItem, analyzed: AnalyzedItem) -> str:
    return analyzed.source_detail or raw.source_detail


def _score_candidate(raw: RawItem, analyzed: AnalyzedItem, reviewed: ReviewedItem) -> tuple[int, str]:
    metadata = raw.raw_metadata or {}
    source_id = metadata.get("source_id", "")
    source_detail = _effective_source_detail(raw, analyzed)
    source_key = _source_key(source_id, source_detail)
    topics = metadata.get("topics") if isinstance(metadata.get("topics"), (list, tuple, set)) else []
    tags = analyzed.tags if isinstance(analyzed.tags, (list, tuple, set)) else []
    text = " ".join([
        raw.title or "",
        raw.description or "",
        analyzed.summary or "",
        " ".join(str(tag) for tag in tags),
        " ".join(str(topic) for topic in topics),
    ]).lower()
    practical_hits = sum(1 for term in PRACTICAL_TERMS if term in text)
    practical_score = min(45, practical_hits * 9)
    engineering_score = 20 if source_detail else 10
    reviewer_score = round((reviewed.total_score or 0) * 0.15)
    heat_score = min(10, int((metadata.get("stars") or 0) / 500))
    source_bonus = PREFERRED_SOURCES.get(source_key, 0)
    total = min(100, practical_score + engineering_score + reviewer_score + heat_score + source_bonus)
    reason = f"source={source_id}, practical_hits={practical_hits}, reviewer={reviewed.total_score}"
    return total, reason


async def select_deep_report_candidate(
    db: Database,
    raw_items: list[RawItem],
    analyzed_items: list[AnalyzedItem],
    reviewed_items: list[ReviewedItem],
) -> DeepReportCandidate | None:
    analyzed_by_url = {item.ref_url: item for item in analyzed_items}
    reviewed_by_url = {item.ref_url: item for item in reviewed_items}
    candidates: list[DeepReportCandidate] = []

    for raw in raw_items:
        repo_info = _repo_info(raw.url)
        if raw.source != "github" or not repo_info:
            continue
        repo_name, repo_url = repo_info
        analyzed = analyzed_by_url.get(raw.url)
        reviewed = reviewed_by_url.get(raw.url)
        if analyzed is None or reviewed is None:
            continue
        if reviewed.verdict not in {"approved", "retry"}:
            continue
        if await _has_recent_report(db, repo_url):
            continue

        score, reason = _score_candidate(raw, analyzed, reviewed)
        if score < 70:
            continue
        metadata = raw.raw_metadata or {}
        source_detail = _effective_source_detail(raw, analyzed)
        candidates.append(DeepReportCandidate(
            repo_url=repo_url,
            repo_name=repo_name,
            source_id=metadata.get("source_id", ""),
            source_detail=source_detail,
            title=analyzed.title,
            summary=analyzed.summary,
            reviewer_score=reviewed.total_score,
            candidate_score=score,
            trigger_reason=reason,
            metadata=metadata,
        ))

    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.candidate_score, reverse=True)[0]
```

- [ ] **Step 5: Run tests**

```bash
.venv/bin/python -m pytest tests/test_deep_reports_selector.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/deep_reports/models.py src/deep_reports/selector.py tests/test_deep_reports_selector.py
git commit -m "Add deep report candidate selector"
```

---

### Task 6: Implement Deep Analyzer

**Files:**
- Create: `prompts/deep_report.md`
- Create: `src/deep_reports/analyzer.py`
- Modify: `src/deep_reports/models.py`
- Modify: `config/agents.yaml`
- Test: `tests/test_deep_reports_analyzer.py`

- 实现说明（最终落地）：
  - 使用 `DeepReportOutput` 作为深度报告结构化输出，字段收敛为 `title`、`summary`、`tech_stack`、`architecture`、`data_flow`、`use_cases`、`strengths`、`limitations`、`actionable_takeaways`、`source_evidence`，避免过度复杂。
  - `src/deep_reports/analyzer.py` 提供：
    - `load_deep_report_prompt(registry)`
    - `parse_deep_report_output(raw)`
    - `analyze_deep_report(candidate, source_package, registry)`
  - `analyze_deep_report()` 复用现有 `LLMRegistry.get_client()` / `supports_json_mode()` / `calc_cost()` 模式，最多尝试 2 次。
  - 成功调用后无论 parse 是否成功都先记录 token 与 cost；返回所有 attempt 的 `CostRecord` 列表，失败时最后一条状态分别为 `parse_failed` / `request_failed`。
  - agent 配置名称统一使用 `deep_report`。
  - prompt 模板占位符使用 `{repo_name}`、`{repo_url}`、`{candidate_context}`、`{source_package}`、`{schema}`，并强约束“只输出 JSON、必须中文、不得编造 evidence 中不存在的文件或能力”。

- 验收要点（更新后）：
  - `tests/test_deep_reports_analyzer.py` 覆盖 fenced/noisy JSON 解析、缺字段失败、prompt 渲染、JSON mode 条件传参、success / parse_failed / request_failed 路径。
  - 验证命令以实际存在的测试文件为准：

```bash
.venv/bin/python -m pytest tests/test_deep_reports_analyzer.py
.venv/bin/python -m pytest tests/test_repo_inspector.py tests/test_deep_reports_selector.py tests/test_deep_reports_analyzer.py
```

---

### Task 7: Implement Deep Report Service and Pipeline Hook

**Files:**
- Create: `src/deep_reports/service.py`
- Modify: `src/main.py`
- Test: `tests/test_deep_reports_pipeline.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_deep_reports_pipeline.py`:

```python
import pytest

from src.core.database import Database
from src.deep_reports.service import run_deep_report_stage
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem


@pytest.mark.asyncio
async def test_deep_report_stage_skips_when_no_candidate(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    await db.initialize()
    await db.migrate()

    result = await run_deep_report_stage(
        db=db,
        registry=None,
        run_id="run_1",
        raw_items=[],
        analyzed_items=[],
        reviewed_items=[],
        article_ids=None,
        clone_and_inspect_fn=None,
        analyze_fn=None,
    )

    assert result.status == "skipped"
    events = await db.fetch_all("SELECT event FROM pipeline_events WHERE run_id=?", ("run_1",))
    assert any(row["event"] == "deep.selector_skipped" for row in events)


@pytest.mark.asyncio
async def test_deep_report_stage_failure_does_not_raise(tmp_path):
    db = Database(str(tmp_path / "kb.db"))
    await db.initialize()
    await db.migrate()
    raw = RawItem(
        url="https://github.com/org/tool",
        title="AI Code Tool",
        source="github",
        source_detail="org/tool",
        raw_metadata={"source_id": "github_ai_devtools", "stars": 1200, "topics": ["agent", "code"]},
    )
    analyzed = AnalyzedItem(ref_url=raw.url, title=raw.title, summary="agent code tool", tags=["Agent"])
    reviewed = ReviewedItem(ref_url=raw.url, total_score=85, dimensions={}, verdict="approved")

    def failing_clone(*args, **kwargs):
        raise RuntimeError("clone failed")

    result = await run_deep_report_stage(
        db=db,
        registry=None,
        run_id="run_1",
        raw_items=[raw],
        analyzed_items=[analyzed],
        reviewed_items=[reviewed],
        article_ids=None,
        clone_and_inspect_fn=failing_clone,
        analyze_fn=None,
    )

    assert result.status == "failed"
    events = await db.fetch_all("SELECT event, message FROM pipeline_events WHERE run_id=?", ("run_1",))
    assert any(row["event"] == "deep.failed" and "clone failed" in row["message"] for row in events)
```

- [ ] **Step 2: Run test to verify failure**

```bash
.venv/bin/python -m pytest tests/test_deep_reports_pipeline.py -q
```

Expected: FAIL because service does not exist.

- [ ] **Step 3: Add service result model**

Add to `src/deep_reports/models.py`:

```python
class DeepReportStageResult(BaseModel):
    status: str
    report_id: int | None = None
    repo_url: str = ""
    message: str = ""
```

- [ ] **Step 4: Implement service**

Create `src/deep_reports/service.py`:

```python
from src.core.database import Database
from src.core.llm_client import LLMRegistry
from src.db.operations import record_pipeline_event, save_cost_log, save_deep_report
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

from .analyzer import analyze_source_package, render_report_markdown
from .inspector import clone_and_inspect
from .models import DeepReportStageResult
from .selector import select_deep_report_candidate
from .summarizer import build_source_package


async def run_deep_report_stage(
    *,
    db: Database,
    registry: LLMRegistry | None,
    run_id: str,
    raw_items: list[RawItem],
    analyzed_items: list[AnalyzedItem],
    reviewed_items: list[ReviewedItem],
    article_ids: dict[str, int] | None = None,
    clone_and_inspect_fn=clone_and_inspect,
    analyze_fn=analyze_deep_report,
) -> DeepReportStageResult:
    # 整个 stage（selector_start/select/select_skipped/clone/analyze/persist/failed）
    # 都在总兜底内，任何异常都返回 failed，不向 main 冒泡。
    await record_pipeline_event(
        db,
        run_id=run_id,
        phase="deep_report",
        event="deep.selector_start",
        status="running",
        message="开始选择深度分析候选",
    )
    candidate = await select_deep_report_candidate(db, raw_items, analyzed_items, reviewed_items)
    if candidate is None:
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.selector_skipped",
            status="skipped",
            message="没有满足条件的深度分析候选",
        )
        return DeepReportStageResult(status="skipped", message="no candidate")

    try:
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.clone_start",
            status="running",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.repo_name,
            ref_url=candidate.repo_url,
            title=candidate.title,
            message="开始 clone repo",
        )
        inspection = await asyncio.to_thread(clone_and_inspect_fn, candidate.repo_url, candidate.repo_name)
        package = build_source_package(inspection)
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.scan_done",
            level="success",
            status="done",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.repo_name,
            ref_url=candidate.repo_url,
            title=candidate.title,
            message=f"源码扫描完成：{len(package.key_files)} 个关键文件",
        )
        if registry is None or analyze_fn is None:
            raise RuntimeError("deep_report is not configured")

        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.analyze_start",
            status="running",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.repo_name,
            ref_url=candidate.repo_url,
            title=candidate.title,
            message="开始源码级深度分析",
        )
        report, cost_records = await analyze_fn(candidate, package, registry)
        for cost_record in cost_records:
            await save_cost_log(db, run_id, cost_record)
        markdown = render_report_markdown(report, package)
        report_id = await save_deep_report(
            db,
            repo_url=candidate.repo_url,
            repo_name=candidate.repo_name,
            article_id=candidate.article_id,
            run_id=run_id,
            commit_sha=package.commit_sha or "",
            status="completed",
            candidate_score=candidate.candidate_score,
            trigger_reason=candidate.trigger_reason,
            report_json=report.model_dump(),
            report_markdown=markdown,
            evidence_json=[item.model_dump(mode="json") for item in report.source_evidence],
            tech_stack_json=package.tech_stack,
            file_tree_summary=package.file_tree_summary,
            analysis_cost=sum(item.cost for item in cost_records),
            analysis_tokens=sum(item.tokens_in + item.tokens_out for item in cost_records),
            error="",
        )
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.persist_done",
            level="success",
            status="completed",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.repo_name,
            ref_url=candidate.repo_url,
            title=candidate.title,
            cost=sum(item.cost for item in cost_records),
            tokens=sum(item.tokens_in + item.tokens_out for item in cost_records),
            message="深度分析报告已保存",
            payload={"report_id": report_id, "candidate_score": candidate.candidate_score},
        )
        return DeepReportStageResult(status="completed", report_id=report_id, repo_url=candidate.repo_url)
    except Exception as exc:
        # failed path 也是 best-effort：保存 failed report 或写 deep.failed event 再失败，
        # 都只 logger.exception，最终仍返回 failed。
        ...
```

- [ ] **Step 5: Run service tests**

```bash
.venv/bin/python -m pytest tests/test_deep_reports_pipeline.py -q
```

Expected: PASS.

- [ ] **Step 6: Wire into main pipeline**

Modify `src/main.py` imports:

```python
from .deep_reports.service import run_deep_report_stage
```

After `_record_source_summaries(...)` and before `end_pipeline_run(...)`, add:

```python
await run_deep_report_stage(
    db=_db,
    registry=_registry,
    run_id=run_id,
    raw_items=new_items,
    analyzed_items=all_analyzed,
    reviewed_items=all_reviewed,
    article_ids=article_ids,
)
```

Main 再保留最后一道小兜底：

```python
try:
    deep_report_result = await run_deep_report_stage(...)
except Exception as exc:
    logger.exception("deep_report.stage_unexpected_failure", extra={"run_id": run_id})
    deep_report_result = DeepReportStageResult(status="failed", message=str(exc))
```

这样即使 future regression 让 service 重新抛错，主 pipeline 仍保持 `completed`。另外，completed 报告先保存，再以 best-effort 写 `deep.persist_done` 事件；事件失败只记日志，不能回退成 failed 覆盖已完成报告。DB upsert 还需要保证同一 `repo_url + commit_sha` 的历史 completed 报告不会被后续 failed 尝试降级。Deep report cost records stay inside the stage and are not merged back into the source funnel `all_costs`。approved/retry 已持久化文章都需要回填到 `article_ids`，供 selector 关联当前 run 文章。

- [ ] **Step 7: Run pipeline tests**

```bash
.venv/bin/python -m pytest tests/test_deep_reports_pipeline.py tests/test_pipeline.py tests/test_pipeline_observability.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/deep_reports/service.py src/deep_reports/models.py src/main.py tests/test_deep_reports_pipeline.py
git commit -m "Integrate deep report pipeline stage"
```

---

### Task 8: Add Static Pages

**Files:**
- Create: `src/site/templates/deep.html`
- Create: `src/site/templates/deep-report.html`
- Create: `src/site/static/js/deep-reports.js`
- Modify: `src/site/builder.py`
- Modify: `src/site/templates/base.html`
- Modify: `src/site/static/css/style.css`
- Test: `tests/test_dashboard_frontend_contract.py`

- [x] **最终方案约束**
  - 列表页独立为 `/deep.html`，详情页独立为 `/deep-report.html?id=...`，都继承 `base.html`，脚本通过 `{% block scripts %}` 以 `defer` 方式加载 `deep-reports.js`。
  - `base.html` 导航新增“深度报告”，位置在“仪表盘”和“DAG”之间；`SiteBuilder` 生成 `deep.html` 和 `deep-report.html` 静态外壳。
  - 列表页固定请求 `/api/deep-reports?page=1&page_size=100`，不做分页交互；公开列表 API 由后端直接返回 `status === 'completed'` 的报告，`total` 也是 completed 总数，排序使用 `updated_at DESC, id DESC`。前端保留 `status === 'completed'` 过滤仅作防御；内部审计继续使用全状态 `list_deep_reports()`。
  - 公开详情请求 `/api/deep-reports/{id}` 时，后端只返回 `status='completed'` 的记录；`failed` 或不存在统一返回 `40401`。无 `id` 或 query 中 `id` 非法时，前端回退 `/api/deep-reports/latest`。
  - 详情优先结构化渲染 `report_json`：`summary`、`tech_stack`、`architecture`、`data_flow`、`use_cases`、`strengths`、`limitations`、`actionable_takeaways`、`source_evidence`。数组为空时不渲染空 section。
  - 兼容旧报告时回退 `report_markdown`，只允许 `escapeHtml(reportMarkdown)` 后放入 `<pre style="white-space: pre-wrap">`；禁止 `innerHTML = report_markdown` 或自制 Markdown parser。
  - 所有外链通过 `safeHttpUrl()` 仅接受 `http/https`，渲染为 `target="_blank" rel="noopener noreferrer"`。
  - 前端增加脏数据归一化 helper：`asObject(value)`、`asStringList(value)`、`normalizeEvidence(value)`、`asPositiveInt(value)`。`report_json` 非 plain object 当 `{}`；数组字段只接受字符串；`architecture` 只接受 object；`normalizeEvidence()` 统一把 `source_evidence` 收敛为至少含 `path`/`reason` 一项的安全对象数组，`[null,1,'x',{}]` 视为空；非法 `id` 不生成详情链接。
  - `asPositiveInt(value)` 必须严格：number 只接受 `Number.isInteger(value) && value > 0`；string 必须 `trim()` 后匹配 `/^[1-9]\d*$/`，再转 `Number(value)` 并通过 `Number.isSafeInteger`。因此拒绝 `12abc`、`1e2`、`12<script>`、`01`。
  - `normalizeEvidence()` 需要同时被 `renderEvidenceItems()` 和 `hasStructuredReport()` 复用，避免脏 evidence 单独触发结构化渲染，错误地阻止 markdown fallback。
  - 列表项展示：`repo_name`、摘要（优先 `report_json.summary`）、候选分、前几项技术栈、更新时间、短 SHA、详情入口。
  - 视觉风格保持现有浅色运维/知识库样式，列表项可用单层卡片，详情使用全宽 section，不做卡片套卡。

- [x] **Task 8 测试与验证**
  - 先补失败契约测试，再实现：
    - `tests/test_dashboard_frontend_contract.py`
    - `tests/test_deep_reports_api.py`
  - 最低验证命令：

```bash
.venv/bin/python -m pytest tests/test_deep_reports_api.py tests/test_dashboard_frontend_contract.py
.venv/bin/python -m pytest tests/test_dashboard_frontend_contract.py tests/test_deep_reports_api.py tests/test_deep_reports_pipeline.py tests/test_deep_reports_db.py
git diff --check HEAD~1 HEAD
```

- [ ] **浏览器实机验证**
  - 由主流程在页面集成完成后执行，不在本 Task 8 文档中提前标记为已完成。

---

### Task 9: Update Documentation

**Files:**
- Modify: `docs/api.md`
- Modify: `docs/data-model.md`
- Modify: `docs/architecture.md`
- Modify: `docs/codemap.md`
- Modify: `docs/task.md`
- Optional Modify: `AGENTS.md`

- [ ] **Step 1: Update API docs**

Add to `docs/api.md`:

```markdown
### GET /api/deep-reports

深度分析报告列表。

参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页数量，最大 100 |

### GET /api/deep-reports/latest

返回最新 completed 深度报告；没有报告时 `data` 为 `{}`。

### GET /api/deep-reports/{id}

返回单篇深度报告详情；不存在时返回 `40401`。
```

- [ ] **Step 2: Update data model docs**

Add `deep_reports` table section to `docs/data-model.md` using the schema from Task 1.

- [ ] **Step 3: Update architecture docs**

Add one paragraph and flowchart entry to `docs/architecture.md`:

```markdown
Reviewer 后新增 Deep Reports 后置阶段：只从高价值 GitHub repo 中选择最多 1 个候选，临时 clone、源码扫描、关键文件抽取、LLM 深度分析并写入 `deep_reports`。该阶段失败不影响主 pipeline。
```

- [ ] **Step 4: Update codemap**

Add to `docs/codemap.md`:

```markdown
- `src/deep_reports/`
  - 源码级 GitHub 深度分析模块。
  - `selector.py` 负责候选选择；`inspector.py` 负责 clone 和源码扫描；`summarizer.py` 负责压缩源码包；`analyzer.py` 负责 LLM 报告；`service.py` 负责 pipeline 接入。
```

- [ ] **Step 5: Update task tracker**

Add P0/P1 task status entries to `docs/task.md`.

- [ ] **Step 6: Run doc checks**

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add docs/api.md docs/data-model.md docs/architecture.md docs/codemap.md docs/task.md AGENTS.md
git commit -m "Document deep reports module"
```

If `AGENTS.md` was not changed, remove it from the `git add` command.

---

### Task 10: Final Verification

**Files:**
- All files changed by Tasks 1-9.

- [x] **Step 1: Run full non-integration test suite**

```bash
.venv/bin/python -m pytest -m "not integration and not e2e"
```

Expected: all tests pass.

- [x] **Step 2: Run prompt regression tests**

```bash
.venv/bin/python -m pytest tests/test_prompt_regression.py tests/test_deep_reports_analyzer.py -q
```

Expected: all tests pass.

- [x] **Step 3: Build static site locally**

Start app:

```bash
.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
curl -sS -X POST http://127.0.0.1:8000/api/pipeline/build
test -f output/deep.html
test -f output/deep-report.html
```

Expected: build returns `{"code":0,...}` and both files exist.

- [x] **Step 4: Browser check**

Use browser automation to open:

```text
http://127.0.0.1:8000/deep.html
```

If FastAPI does not serve static pages locally, use the existing temporary static+API proxy pattern from prior DAG verification and open:

```text
http://127.0.0.1:8001/deep.html
```

Expected: page renders list shell without console errors except optional favicon 404.

- [x] **Step 5: Verify pipeline skip path**

Run targeted test:

```bash
.venv/bin/python -m pytest tests/test_deep_reports_pipeline.py::test_deep_report_stage_skips_when_no_candidate -q
```

Expected: PASS and no pipeline failure.

- [x] **Step 6: Verify diff cleanliness**

```bash
git diff --check
git status --short
```

Expected: `git diff --check` has no output. `git status --short` only shows intended uncommitted files if final commit is not made yet.

- [ ] **Step 7: Final commit if needed**

If any changes remain:

```bash
git add -A
git commit -m "Complete deep reports module"
```

---

## Self-Review

Spec coverage:

- Automatic conditional trigger: Task 5 and Task 7.
- Temporary clone and source scanning: Task 3.
- Deterministic source summarization and evidence package: Task 4.
- LLM deep report generation: Task 6.
- Persistence: Task 1.
- API: Task 2.
- Static pages: Task 8.
- Pipeline/DAG integration and non-blocking failure: Task 7.
- Docs: Task 9.
- Verification: Task 10.

No placeholders are intentionally left. The plan uses concrete files, commands, expected outcomes, and implementation snippets. Type names are introduced before later tasks use them.
