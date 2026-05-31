# tests/test_collector.py
import pytest
from unittest.mock import AsyncMock, patch
from src.graph.collector import collect_github, collect_rss, collect_all
from src.graph.state import RawItem
from src.core.config import SourceConfig


def make_source(**kw):
    defaults = {"id": "test", "name": "Test", "type": "github", "enabled": True, "priority": 1, "cron": "0 9 * * *", "max_items": 10, "config": {}}
    defaults.update(kw)
    return SourceConfig(**defaults)


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

    with patch("feedparser.parse", return_value=type("Feed", (), {"entries": [entry]})()):
        items = await collect_rss(source)

    assert len(items) == 1
    assert items[0].source_detail == "36氪"
    assert items[0].raw_metadata["source_id"] == "rss_36kr"


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
