# GitHub Search Source Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub-search-based source discoverer that finds candidate RSS/GitHub sources without adding search results to the article feed.

**Architecture:** Extend the existing `SourceDiscovery` flow instead of adding a new subsystem. GitHub search produces `SourceConfig` candidates with discovery metadata, then writes them through the existing `discovered_sources` and `source_registry(candidate)` path.

**Tech Stack:** Python 3.12+, `httpx`, existing `SourceConfig`, SQLite-backed `source_registry`, existing dashboard API/JS.

## Global Constraints

- Search results must not be inserted into `articles`, homepage output, or `data.json`.
- Candidates must enter `source_registry` with `status='candidate'` and `enabled=0`.
- No new dependency.
- First version uses fixed query list and per-query result limit.
- Discovery cadence is twice per week.
- Discovery failures log warning and do not fail the pipeline.

---

## File Structure

- Modify `src/core/source_discovery.py`: add GitHub search discovery helpers and include them in `discover()`.
- Modify `src/scheduler/source_scheduler.py`: set discovery cron to twice weekly if the existing schedule is weekly.
- Modify `src/api/sources.py`: expose discovery metadata already stored in `source_registry.config_json`.
- Modify `src/site/static/js/dashboard/renderers.js`: show discovery source for candidate/trial rows.
- Test `tests/test_source_discovery.py`: unit tests for GitHub search candidates, dedupe, and metadata.
- Test `tests/test_dashboard_frontend_contract.py` or API contract tests: verify discovery metadata is present/displayed.

---

### Task 1: Add GitHub Search Candidate Extraction

**Files:**
- Modify: `src/core/source_discovery.py`
- Test: `tests/test_source_discovery.py`

**Interfaces:**
- Consumes: `SourceDiscovery._write_discovered_source(source: SourceConfig)`
- Produces: `SourceDiscovery.discover_github_search(limit_per_query: int = 10) -> list[SourceConfig]`

- [ ] **Step 1: Write failing tests**

Create or extend `tests/test_source_discovery.py`:

```python
import pytest

from src.core.source_discovery import SourceDiscovery


class FakeResponse:
    def __init__(self, data=None, text="", status_code=200):
        self._data = data or {}
        self.text = text
        self.status_code = status_code

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("bad status")


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses[url]


@pytest.mark.asyncio
async def test_discover_github_search_extracts_rss_candidate(monkeypatch, tmp_path):
    written = []
    search_url = "https://api.github.com/search/repositories"
    repo_url = "https://api.github.com/repos/owner/radar"
    readme_url = "https://api.github.com/repos/owner/radar/readme"
    feed_url = "https://example.com/feed"

    responses = {
        search_url: FakeResponse({"items": [{"full_name": "owner/radar", "url": repo_url, "html_url": "https://github.com/owner/radar"}]}),
        repo_url: FakeResponse({"homepage": "https://example.com", "owner": {"login": "owner"}}),
        readme_url: FakeResponse({"download_url": "https://raw.example/readme.md"}),
        "https://raw.example/readme.md": FakeResponse(text=f"Follow {feed_url}"),
        feed_url: FakeResponse(text="<rss><channel><title>AI Radar</title></channel></rss>"),
    }

    import src.core.source_discovery as module
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: FakeClient(responses))

    discovery = SourceDiscovery(db=None)

    async def fake_write(source):
        written.append(source)

    discovery._write_discovered_source = fake_write

    sources = await discovery.discover_github_search(limit_per_query=1)

    assert sources
    assert written == sources
    assert sources[0].type == "rss"
    assert sources[0].config["url"] == feed_url
    assert sources[0].config["discovered_by"] == "github_search"
    assert sources[0].config["discovery_repo"] == "owner/radar"
    assert sources[0].config["discovery_query"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/test_source_discovery.py::test_discover_github_search_extracts_rss_candidate -q
```

Expected: fails because `discover_github_search` does not exist.

- [ ] **Step 3: Implement minimal discovery code**

In `src/core/source_discovery.py`, add constants and helpers near the existing discovery constants:

```python
GITHUB_SEARCH_API_URL = "https://api.github.com/search/repositories"
GITHUB_SEARCH_QUERIES = [
    "ai knowledge base",
    "ai radar",
    "llm radar",
    "agent radar",
    "awesome ai tools",
    "ai newsletter",
    "llm news",
]
FEED_PATHS = ("/feed", "/rss.xml", "/atom.xml")
```

Add small helpers:

```python
def _source_with_discovery_metadata(source: SourceConfig, query: str, repo: str) -> SourceConfig:
    source.config["discovered_by"] = "github_search"
    source.config["discovery_query"] = query
    source.config["discovery_repo"] = repo
    return source


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s)>'\"]+", text or "")


def _looks_like_feed_url(url: str) -> bool:
    lowered = url.lower()
    return any(part in lowered for part in ("/feed", "rss", "atom"))
```

Add `SourceDiscovery.discover_github_search()`:

```python
    async def discover_github_search(self, limit_per_query: int = 10) -> list[SourceConfig]:
        discovered: list[SourceConfig] = []
        seen_ids: set[str] = set()

        try:
            async with httpx.AsyncClient(timeout=20, headers=RSS_NEIGHBOR_HEADERS) as client:
                for query in GITHUB_SEARCH_QUERIES:
                    search_resp = await client.get(
                        GITHUB_SEARCH_API_URL,
                        params={"q": query, "sort": "stars", "order": "desc", "per_page": limit_per_query},
                    )
                    search_resp.raise_for_status()
                    for repo in search_resp.json().get("items", []):
                        full_name = repo.get("full_name") or ""
                        repo_api_url = repo.get("url") or ""
                        if not full_name or not repo_api_url:
                            continue

                        repo_resp = await client.get(repo_api_url)
                        repo_resp.raise_for_status()
                        repo_data = repo_resp.json()
                        urls = _extract_urls(repo_data.get("homepage") or "")

                        readme_resp = await client.get(f"{repo_api_url}/readme")
                        if readme_resp.status_code < 400:
                            readme_url = readme_resp.json().get("download_url")
                            if readme_url:
                                raw = await client.get(readme_url)
                                urls.extend(_extract_urls(raw.text))

                        for url in urls:
                            candidate = None
                            if _looks_like_feed_url(url):
                                candidate = SourceConfig(
                                    id=_stable_rss_id(url),
                                    name=urlparse(url).netloc[:50],
                                    type="rss",
                                    enabled=True,
                                    priority=2,
                                    cron="0 */4 * * *",
                                    max_items=10,
                                    config={"url": url, "filter_keywords": ["AI", "LLM", "agent", "RAG"]},
                                )
                            if candidate is None or candidate.id in seen_ids:
                                continue
                            candidate = _source_with_discovery_metadata(candidate, query, full_name)
                            await self._write_discovered_source(candidate)
                            discovered.append(candidate)
                            seen_ids.add(candidate.id)

        except Exception as e:
            logger.warning("discovery.github_search.error", extra={"error": str(e)})

        logger.info("discovery.github_search", extra={"found": len(discovered)})
        return discovered
```

- [ ] **Step 4: Include in full discovery flow**

Update `SourceDiscovery.discover()`:

```python
    async def discover(self) -> list[SourceConfig]:
        approved_sources = await self.discover_from_approved_articles()
        github_sources = await self.discover_github_topics()
        github_search_sources = await self.discover_github_search()
        rss_sources = await self.scan_rss_neighbors()
        return approved_sources + github_sources + github_search_sources + rss_sources
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest tests/test_source_discovery.py -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/source_discovery.py tests/test_source_discovery.py
git commit -m "feat: discover sources from github search"
```

---

### Task 2: Keep Candidates Deduped and Non-Article

**Files:**
- Modify: `src/core/source_discovery.py`
- Test: `tests/test_source_discovery.py`

**Interfaces:**
- Consumes: `discover_github_search(limit_per_query: int = 10)`
- Produces: no duplicate candidates for repeated URLs; no writes outside `_write_discovered_source`.

- [ ] **Step 1: Add dedupe test**

Add:

```python
@pytest.mark.asyncio
async def test_discover_github_search_dedupes_same_feed(monkeypatch):
    written = []
    feed_url = "https://example.com/feed"
    responses = {
        "https://api.github.com/search/repositories": FakeResponse({
            "items": [
                {"full_name": "a/one", "url": "https://api.github.com/repos/a/one"},
                {"full_name": "b/two", "url": "https://api.github.com/repos/b/two"},
            ]
        }),
        "https://api.github.com/repos/a/one": FakeResponse({"homepage": feed_url}),
        "https://api.github.com/repos/a/one/readme": FakeResponse(status_code=404),
        "https://api.github.com/repos/b/two": FakeResponse({"homepage": feed_url}),
        "https://api.github.com/repos/b/two/readme": FakeResponse(status_code=404),
    }

    import src.core.source_discovery as module
    monkeypatch.setattr(module, "GITHUB_SEARCH_QUERIES", ["ai radar"])
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: FakeClient(responses))

    discovery = SourceDiscovery(db=None)
    discovery._write_discovered_source = lambda source: written.append(source)

    sources = await discovery.discover_github_search(limit_per_query=2)

    assert len(sources) == 1
    assert len(written) == 1
```

- [ ] **Step 2: Make `_write_discovered_source` awaitable in test**

Use this helper if needed:

```python
async def fake_write(source):
    written.append(source)
```

- [ ] **Step 3: Run test**

```bash
uv run pytest tests/test_source_discovery.py::test_discover_github_search_dedupes_same_feed -q
```

Expected: pass.

- [ ] **Step 4: Run article non-regression tests**

```bash
uv run pytest tests/test_site_builder.py tests/test_pipeline.py -q
```

Expected: pass. This verifies the discoverer did not enter article rendering or normal pipeline article writes.

- [ ] **Step 5: Commit**

```bash
git add src/core/source_discovery.py tests/test_source_discovery.py
git commit -m "test: cover github discovery dedupe"
```

---

### Task 3: Show Discovery Metadata in Source Health

**Files:**
- Modify: `src/api/sources.py`
- Modify: `src/site/static/js/dashboard/renderers.js`
- Test: `tests/test_api_contracts.py`
- Test: `tests/test_dashboard_frontend_contract.py`

**Interfaces:**
- Consumes: `source_registry.config_json.discovered_by`, `discovery_query`, `discovery_repo`
- Produces: API fields `discovered_by`, `discovery_query`, `discovery_repo` for source rows.

- [ ] **Step 1: Inspect current source stats row shape**

Run:

```bash
sed -n '1,260p' src/api/sources.py
```

Confirm where rows from `source_registry.config_json` are parsed.

- [ ] **Step 2: Add API contract test**

In `tests/test_api_contracts.py`, add a small test near existing `/api/sources/stats` tests:

```python
async def test_sources_stats_exposes_discovery_metadata(api_client, api_db):
    await api_db.execute(
        """
        INSERT INTO source_registry
        (id, name, type, status, enabled, priority, cron, max_items, config_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "rss_discovered",
            "Discovered RSS",
            "rss",
            "candidate",
            0,
            2,
            "0 */4 * * *",
            10,
            '{"url":"https://example.com/feed","discovered_by":"github_search","discovery_query":"ai radar","discovery_repo":"owner/radar"}',
        ),
    )
    await api_db.commit()

    response = api_client.get("/api/sources/stats?period=7")
    assert response.status_code == 200
    row = next(item for item in response.json()["data"]["sources"] if item["source_id"] == "rss_discovered")
    assert row["discovered_by"] == "github_search"
    assert row["discovery_query"] == "ai radar"
    assert row["discovery_repo"] == "owner/radar"
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/test_api_contracts.py::test_sources_stats_exposes_discovery_metadata -q
```

Expected: fails because fields are absent.

- [ ] **Step 4: Add minimal API fields**

In `src/api/sources.py`, when building each source row:

```python
config = json.loads(row["config_json"] or "{}")
result["discovered_by"] = config.get("discovered_by")
result["discovery_query"] = config.get("discovery_query")
result["discovery_repo"] = config.get("discovery_repo")
```

Use the existing row variable names in the file.

- [ ] **Step 5: Add frontend contract test**

In `tests/test_dashboard_frontend_contract.py`, assert the renderer references `discovery_query`:

```python
def test_dashboard_sources_render_discovery_metadata():
    js = Path("src/site/static/js/dashboard/renderers.js").read_text()
    assert "discovery_query" in js
    assert "discovery_repo" in js
```

- [ ] **Step 6: Render metadata only when present**

In `src/site/static/js/dashboard/renderers.js`, inside the source table row template, add a compact line for candidate/trial rows:

```javascript
const discoveryText = s.discovery_query
    ? `GitHub Search: ${escapeHtml(s.discovery_query)}${s.discovery_repo ? ` / ${escapeHtml(s.discovery_repo)}` : ''}`
    : '';
```

Show it in the data-source cell under the display name:

```javascript
${discoveryText ? `<div class="source-discovery-meta">${discoveryText}</div>` : ''}
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/test_api_contracts.py::test_sources_stats_exposes_discovery_metadata tests/test_dashboard_frontend_contract.py -q
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add src/api/sources.py src/site/static/js/dashboard/renderers.js tests/test_api_contracts.py tests/test_dashboard_frontend_contract.py
git commit -m "feat: show source discovery metadata"
```

---

### Task 4: Set Discovery Cadence to Twice Weekly

**Files:**
- Modify: `src/scheduler/source_scheduler.py` or `src/main.py`, whichever owns the discovery cron.
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: existing source discovery scheduler.
- Produces: discovery job runs twice weekly.

- [ ] **Step 1: Locate current discovery schedule**

Run:

```bash
rg -n "discover|source_discovery|promote_candidates" src/main.py src/scheduler tests/test_scheduler.py
```

- [ ] **Step 2: Add schedule test**

In `tests/test_scheduler.py`, add or update the existing discovery scheduler test to expect two weekday triggers. If cron is expressed directly, assert the day-of-week field:

```python
def test_source_discovery_runs_twice_weekly():
    from src.scheduler.source_scheduler import SOURCE_DISCOVERY_CRON

    assert SOURCE_DISCOVERY_CRON["day_of_week"] in {"mon,thu", "1,4"}
```

- [ ] **Step 3: Implement minimal constant**

If there is no constant, add one in the scheduler module:

```python
SOURCE_DISCOVERY_CRON = {"day_of_week": "mon,thu", "hour": 9, "minute": 0}
```

Use it where the scheduler registers the discovery job.

- [ ] **Step 4: Run scheduler tests**

```bash
uv run pytest tests/test_scheduler.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/scheduler/source_scheduler.py src/main.py tests/test_scheduler.py
git commit -m "feat: run source discovery twice weekly"
```

---

### Task 5: Final Verification

**Files:**
- No new files expected.

**Interfaces:**
- Consumes all previous tasks.
- Produces verified branch ready to push.

- [ ] **Step 1: Run focused suite**

```bash
uv run pytest tests/test_source_discovery.py tests/test_scheduler.py tests/test_api_contracts.py tests/test_dashboard_frontend_contract.py -q
```

Expected: pass.

- [ ] **Step 2: Run standard non-integration suite**

```bash
uv run pytest -m "not integration and not e2e"
```

Expected: pass.

- [ ] **Step 3: Check git status**

```bash
git status --short --branch
```

Expected: clean except intended commits.

- [ ] **Step 4: Push**

```bash
git push origin master
```

Expected: push succeeds.
