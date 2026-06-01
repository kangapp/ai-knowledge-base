# tests/test_collector.py
import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from src.graph.collector import _build_github_queries, _matches_rss_keywords, collect_github, collect_rss, collect_all
from src.graph.state import RawItem
from src.core.config import SourceConfig


def make_source(**kw):
    defaults = {"id": "test", "name": "Test", "type": "github", "enabled": True, "priority": 1, "cron": "0 9 * * *", "max_items": 10, "config": {}}
    defaults.update(kw)
    return SourceConfig(**defaults)


def test_build_github_queries_do_not_or_topic_qualifiers():
    queries = _build_github_queries(
        {
            "topics": ["llm", "machine-learning", "rag"],
            "keywords": ["AI agent", "RAG", "MCP"],
            "exclude_terms": ["wallpaper", "account"],
            "lookback_type": "created",
            "lookback_days": 7,
        },
        now=datetime(2026, 6, 1, tzinfo=timezone.utc),
    )

    assert queries == [
        "topic:llm created:>2026-05-25",
        "topic:machine-learning created:>2026-05-25",
        "topic:rag created:>2026-05-25",
        '"AI agent" created:>2026-05-25',
        "RAG created:>2026-05-25",
    ]
    assert all(" OR " not in query for query in queries)
    assert all(" NOT " not in query for query in queries)


def test_matches_rss_keywords_does_not_match_ai_inside_words():
    assert not _matches_rss_keywords("Rocket startup raises $24M", ["AI"])
    assert _matches_rss_keywords("AI startup raises $24M", ["AI"])
    assert _matches_rss_keywords("OpenAI releases a new model", ["OpenAI"])
    assert _matches_rss_keywords("天津人工智能传感器产业园开园", ["人工智能"])


@pytest.mark.asyncio
async def test_collect_github_mock():
    source = make_source(type="github", config={"topics": ["ai"], "min_stars": 1, "lookback_days": 7})
    mock_resp = AsyncMock(status_code=200, json=lambda: {"items": [{"full_name": "test/x", "name": "x", "html_url": "https://github.com/test/x", "description": "desc", "stargazers_count": 100, "forks_count": 50, "watchers_count": 30, "language": "Python", "topics": ["ai"], "pushed_at": "2026-05-15T10:00:00Z"}]})
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        items = await collect_github(source)

    assert len(items) == 1
    assert items[0].source == "github"
    assert items[0].url == "https://github.com/test/x"


@pytest.mark.asyncio
async def test_collect_github_filters_excluded_terms_after_search():
    source = make_source(
        type="github",
        config={
            "topics": ["ai"],
            "exclude_terms": ["wallpaper", "account"],
            "min_stars": 1,
            "lookback_days": 7,
        },
    )
    repos = [
        {"full_name": "a/wallpaper-ai", "name": "wallpaper-ai", "html_url": "https://github.com/a/wallpaper-ai", "description": "AI wallpaper", "stargazers_count": 100, "forks_count": 50, "watchers_count": 30, "language": "Python", "topics": ["ai"], "pushed_at": "2026-05-15T10:00:00Z"},
        {"full_name": "b/useful-ai", "name": "useful-ai", "html_url": "https://github.com/b/useful-ai", "description": "Useful AI agent", "stargazers_count": 100, "forks_count": 50, "watchers_count": 30, "language": "Python", "topics": ["ai"], "pushed_at": "2026-05-15T10:00:00Z"},
    ]
    mock_resp = AsyncMock(status_code=200, json=lambda: {"items": repos})
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        items = await collect_github(source)

    assert [item.url for item in items] == ["https://github.com/b/useful-ai"]


@pytest.mark.asyncio
async def test_collect_github_merges_multiple_queries_and_deduplicates():
    source = make_source(
        type="github",
        max_items=2,
        config={
            "topics": ["llm", "rag"],
            "min_stars": 1,
            "lookback_days": 7,
        },
    )
    repo_a = {"full_name": "a/llm", "name": "llm", "html_url": "https://github.com/a/llm", "description": "LLM", "stargazers_count": 100, "forks_count": 50, "watchers_count": 30, "language": "Python", "topics": ["llm"], "pushed_at": "2026-05-15T10:00:00Z"}
    repo_b = {"full_name": "b/rag", "name": "rag", "html_url": "https://github.com/b/rag", "description": "RAG", "stargazers_count": 200, "forks_count": 50, "watchers_count": 30, "language": "Python", "topics": ["rag"], "pushed_at": "2026-05-15T10:00:00Z"}

    responses = [
        AsyncMock(status_code=200, json=lambda: {"items": [repo_a]}),
        AsyncMock(status_code=200, json=lambda: {"items": [repo_a, repo_b]}),
    ]
    for response in responses:
        response.raise_for_status = lambda: None

    fixed_now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    with patch("src.graph.collector.now_bj", return_value=fixed_now), \
            patch("httpx.AsyncClient.get", side_effect=responses) as mock_get:
        items = await collect_github(source)

    queries = [call.kwargs["params"]["q"] for call in mock_get.call_args_list]
    assert queries == [
        "topic:llm created:>2026-05-25",
        "topic:rag created:>2026-05-25",
    ]
    assert [item.url for item in items] == [
        "https://github.com/b/rag",
        "https://github.com/a/llm",
    ]


@pytest.mark.asyncio
async def test_collect_rss_records_config_source_id():
    source = make_source(
        id="rss_36kr",
        name="36氪",
        type="rss",
        config={"url": "https://36kr.com/feed", "filter_keywords": []},
    )
    entry = {
        "title": "AI news",
        "summary": "LLM update",
        "link": "https://36kr.com/p/1",
        "published": "2026-05-31T10:00:00Z",
    }

    mock_resp = AsyncMock()
    mock_resp.text = "<rss></rss>"
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp), \
         patch("feedparser.parse", return_value=type("Feed", (), {"entries": [entry]})()):
        items = await collect_rss(source)

    assert len(items) == 1
    assert items[0].source_detail == "36氪"
    assert items[0].raw_metadata["source_id"] == "rss_36kr"


@pytest.mark.asyncio
async def test_collect_rss_filters_ascii_acronym_by_word_boundary():
    source = make_source(
        id="rss_techcrunch",
        name="TechCrunch",
        type="rss",
        config={"url": "https://techcrunch.com/feed", "filter_keywords": ["AI"]},
    )
    entries = [
        {"title": "Rocket startup raises $24M", "summary": "", "link": "https://example.com/1"},
        {"title": "AI startup raises $24M", "summary": "", "link": "https://example.com/2"},
    ]

    mock_resp = AsyncMock()
    mock_resp.text = "<rss></rss>"
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp), \
         patch("feedparser.parse", return_value=type("Feed", (), {"entries": entries})()):
        items = await collect_rss(source)

    assert [item.url for item in items] == ["https://example.com/2"]


@pytest.mark.asyncio
async def test_collect_rss_title_scope_ignores_summary_noise():
    source = make_source(
        id="rss_36kr",
        name="36氪",
        type="rss",
        config={
            "url": "https://36kr.com/feed",
            "filter_keywords": ["AI", "豆包"],
            "filter_scope": "title",
        },
    )
    entries = [
        {
            "title": "今年盛夏，WAVES之夜会浪的一群年轻人",
            "summary": "市集里也有 AI 硬件、咖啡和独立杂志。",
            "link": "https://example.com/1",
        },
        {
            "title": "豆包6月下旬正式付费",
            "summary": "产品商业化更新。",
            "link": "https://example.com/2",
        },
    ]

    mock_resp = AsyncMock()
    mock_resp.text = "<rss></rss>"
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp), \
         patch("feedparser.parse", return_value=type("Feed", (), {"entries": entries})()):
        items = await collect_rss(source)

    assert [item.url for item in items] == ["https://example.com/2"]


@pytest.mark.asyncio
async def test_collect_rss_fetches_feed_with_http_client_before_parsing():
    source = make_source(
        id="rss_test",
        name="RSS Test",
        type="rss",
        config={"url": "https://example.com/feed", "filter_keywords": []},
    )
    mock_resp = AsyncMock()
    mock_resp.text = "<rss><channel /></rss>"
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp) as mock_get, \
         patch("feedparser.parse", return_value=type("Feed", (), {"entries": []})()) as mock_parse:
        await collect_rss(source)

    mock_get.assert_called_once_with("https://example.com/feed")
    mock_parse.assert_called_once_with("<rss><channel /></rss>")


@pytest.mark.asyncio
async def test_collect_github_multi_threshold_filter():
    """多维阈值过滤：stars/forks/watchers 全部达标才通过"""
    source = make_source(type="github", config={
        "topics": ["ai"],
        "min_stars": 50,
        "min_forks": 20,
        "min_watchers": 10,
        "lookback_days": 7,
    })

    repos = [
        {"full_name": "a/x", "name": "x", "html_url": "https://github.com/a/x", "description": "ok", "stargazers_count": 100, "forks_count": 50, "watchers_count": 30, "language": "Python", "topics": [], "pushed_at": "2026-05-15T10:00:00Z"},
        {"full_name": "b/y", "name": "y", "html_url": "https://github.com/b/y", "description": "low forks", "stargazers_count": 100, "forks_count": 5, "watchers_count": 30, "language": "Python", "topics": [], "pushed_at": "2026-05-15T10:00:00Z"},
        {"full_name": "c/z", "name": "z", "html_url": "https://github.com/c/z", "description": "low watchers", "stargazers_count": 100, "forks_count": 50, "watchers_count": 3, "language": "Python", "topics": [], "pushed_at": "2026-05-15T10:00:00Z"},
        {"full_name": "d/w", "name": "w", "html_url": "https://github.com/d/w", "description": "low stars", "stargazers_count": 10, "forks_count": 50, "watchers_count": 30, "language": "Python", "topics": [], "pushed_at": "2026-05-15T10:00:00Z"},
        {"full_name": "e/v", "name": "v", "html_url": "https://github.com/e/v", "description": "all ok", "stargazers_count": 80, "forks_count": 25, "watchers_count": 15, "language": "Python", "topics": [], "pushed_at": "2026-05-15T10:00:00Z"},
    ]
    mock_resp = AsyncMock(status_code=200, json=lambda: {"items": repos})
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        items = await collect_github(source)

    assert len(items) == 2
    assert items[0].raw_metadata["forks"] == 50
    assert items[0].raw_metadata["watchers"] == 30
    assert items[1].raw_metadata["forks"] == 25
    assert items[1].raw_metadata["watchers"] == 15


@pytest.mark.asyncio
async def test_collector_single_source_failure_isolated():
    """一个源挂了，其余正常返回"""
    async def fail(src):
        raise Exception("API down")
    async def ok(src):
        return [RawItem(url="x", title="x", source="rss", collected_at="")]

    mock_db = AsyncMock()
    results, errors = await collect_all(
        mock_db,
        [mock_source("rss"), mock_source("feishu")],
        collectors={"rss": ok, "feishu": fail}
    )
    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0]["source"] == "feishu"


def mock_source(t, src_id=None):
    return make_source(type=t, id=src_id or t)
