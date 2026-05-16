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
    mock_resp = AsyncMock(status_code=200, json=lambda: {"items": [{"full_name": "test/x", "name": "x", "html_url": "https://github.com/test/x", "description": "desc", "stargazers_count": 100, "language": "Python", "topics": ["ai"], "pushed_at": "2026-05-15T10:00:00Z"}]})
    mock_resp.raise_for_status = lambda: None

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        items = await collect_github(source)

    assert len(items) == 1
    assert items[0].source == "github"
    assert items[0].url == "https://github.com/test/x"


@pytest.mark.asyncio
async def test_collector_single_source_failure_isolated():
    """一个源挂了，其余正常返回"""
    async def fail(src):
        raise Exception("API down")
    async def ok(src):
        return [RawItem(url="x", title="x", source="rss", collected_at="")]

    results, errors = await collect_all(
        [mock_source("rss"), mock_source("feishu")],
        collectors={"rss": ok, "feishu": fail}
    )
    assert len(results) == 1
    assert len(errors) == 1
    assert errors[0]["source"] == "feishu"


def mock_source(t, src_id=None):
    return make_source(type=t, id=src_id or t)