from unittest.mock import AsyncMock

import pytest

from src.core.config import SourceConfig


def _source(source_id: str, *, cron: str = "0 8 * * *", enabled: bool = True) -> SourceConfig:
    return SourceConfig(
        id=source_id,
        name=source_id,
        type="rss",
        enabled=enabled,
        priority=1,
        cron=cron,
        max_items=5,
        config={"url": f"https://example.com/{source_id}.xml"},
    )


def test_source_filter_accepts_multiple_ids():
    from src.main import _filter_sources

    sources = [_source("rss_a"), _source("rss_b"), _source("rss_c")]

    assert [s.id for s in _filter_sources(sources, None)] == ["rss_a", "rss_b", "rss_c"]
    assert [s.id for s in _filter_sources(sources, "rss_a")] == ["rss_a"]
    assert [s.id for s in _filter_sources(sources, ["rss_a", "rss_c"])] == ["rss_a", "rss_c"]


def test_group_sources_by_cron_skips_disabled_and_groups_same_cron():
    from src.main import _group_enabled_sources_by_cron

    groups = _group_enabled_sources_by_cron([
        _source("rss_a", cron="0 8 * * *"),
        _source("rss_b", cron="0 8 * * *"),
        _source("rss_c", cron="0 9 * * *"),
        _source("rss_disabled", cron="0 8 * * *", enabled=False),
    ])

    assert groups == {
        "0 8 * * *": ["rss_a", "rss_b"],
        "0 9 * * *": ["rss_c"],
    }


def test_register_source_jobs_registers_one_job_per_cron_group():
    from src.main import _register_source_jobs

    class FakeScheduler:
        def __init__(self):
            self.jobs = []

        def add_job(self, func, trigger, **kwargs):
            self.jobs.append({"func": func, "trigger": trigger, **kwargs})

    scheduler = FakeScheduler()

    _register_source_jobs(
        scheduler,
        [
            _source("rss_a", cron="0 8 * * *"),
            _source("rss_b", cron="0 8 * * *"),
            _source("rss_c", cron="30 9 * * *"),
        ],
        AsyncMock(),
    )

    assert [job["id"] for job in scheduler.jobs] == ["collect-group-1", "collect-group-2"]
    assert [job["minute"] for job in scheduler.jobs] == ["0", "30"]
    assert [job["hour"] for job in scheduler.jobs] == ["8", "9"]
    assert scheduler.jobs[0]["func"].keywords["source_filter"] == ["rss_a", "rss_b"]
    assert scheduler.jobs[1]["func"].keywords["source_filter"] == ["rss_c"]


@pytest.mark.asyncio
async def test_weekly_source_maintenance_initializes_kb_database(monkeypatch):
    from src.scheduler import source_scheduler

    calls = []

    class FakeDatabase:
        def __init__(self, path):
            calls.append(("path", path))

        async def initialize(self):
            calls.append(("initialize", None))

        async def close(self):
            calls.append(("close", None))

    class FakeTracker:
        def __init__(self, db):
            pass

        async def check_and_evict(self, sources):
            return []

    class FakeDiscovery:
        def __init__(self, db):
            pass

        async def discover(self):
            return []

    monkeypatch.setattr(source_scheduler, "Database", FakeDatabase)
    monkeypatch.setattr(source_scheduler, "SourceHealthTracker", FakeTracker)
    monkeypatch.setattr(source_scheduler, "SourceDiscovery", FakeDiscovery)
    monkeypatch.setattr(source_scheduler.SourceManager, "load", lambda: [])

    await source_scheduler.run_weekly_source_maintenance()

    assert calls == [("path", "data/kb.db"), ("initialize", None), ("close", None)]
