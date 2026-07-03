import pytest

from src.core.source_discovery import SourceDiscovery, _stable_rss_id


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
async def test_discover_github_search_extracts_rss_candidate(monkeypatch):
    written = []
    search_url = "https://api.github.com/search/repositories"
    repo_url = "https://api.github.com/repos/owner/radar"
    feed_url = "https://example.com/feed"
    responses = {
        search_url: FakeResponse({
            "items": [
                {"full_name": "owner/radar", "url": repo_url, "html_url": "https://github.com/owner/radar"}
            ]
        }),
        repo_url: FakeResponse({"homepage": "https://example.com", "owner": {"login": "owner"}}),
        f"{repo_url}/readme": FakeResponse({"download_url": "https://raw.example/readme.md"}),
        "https://raw.example/readme.md": FakeResponse(text=f"Follow {feed_url}"),
    }

    import src.core.source_discovery as module

    monkeypatch.setattr(module, "GITHUB_SEARCH_QUERIES", ["ai radar"])
    monkeypatch.setattr(module.httpx, "AsyncClient", lambda **kwargs: FakeClient(responses))

    discovery = SourceDiscovery(db=None)

    async def fake_write(source):
        written.append(source)

    discovery._write_discovered_source = fake_write

    sources = await discovery.discover_github_search(limit_per_query=1)

    assert sources
    assert written == sources
    rss_source = next(source for source in sources if source.type == "rss")
    assert rss_source.id == _stable_rss_id(feed_url)
    assert rss_source.config["url"] == feed_url
    assert rss_source.config["discovered_by"] == "github_search"
    assert rss_source.config["discovery_repo"] == "owner/radar"
    assert rss_source.config["discovery_query"] == "ai radar"


@pytest.mark.asyncio
async def test_discover_github_search_dedupes_same_feed(monkeypatch):
    written = []
    search_url = "https://api.github.com/search/repositories"
    feed_url = "https://example.com/feed"
    responses = {
        search_url: FakeResponse({
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

    async def fake_write(source):
        written.append(source)

    discovery._write_discovered_source = fake_write

    sources = await discovery.discover_github_search(limit_per_query=2)

    rss_sources = [source for source in sources if source.type == "rss"]
    assert len(rss_sources) == 1
    assert len([source for source in written if source.type == "rss"]) == 1
