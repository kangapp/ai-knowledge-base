import asyncio
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
    from src.services.pipeline_helpers import filter_sources

    sources = [_source("rss_a"), _source("rss_b"), _source("rss_c")]

    assert [s.id for s in filter_sources(sources, None)] == ["rss_a", "rss_b", "rss_c"]
    assert [s.id for s in filter_sources(sources, "rss_a")] == ["rss_a"]
    assert [s.id for s in filter_sources(sources, ["rss_a", "rss_c"])] == ["rss_a", "rss_c"]


def test_group_sources_by_cron_skips_disabled_and_groups_same_cron():
    from src.services.pipeline_helpers import group_enabled_sources_by_cron

    groups = group_enabled_sources_by_cron([
        _source("rss_a", cron="0 8 * * *"),
        _source("rss_b", cron="0 8 * * *"),
        _source("rss_c", cron="0 9 * * *"),
        _source("rss_disabled", cron="0 8 * * *", enabled=False),
    ])

    assert groups == {
        "0 8 * * *": ["rss_a", "rss_b"],
        "0 9 * * *": ["rss_c"],
    }


def test_group_enabled_sources_keeps_only_schedulable_registry_statuses():
    from src.services.pipeline_helpers import group_enabled_sources_by_cron

    sources = [
        SourceConfig(id="active", name="Active", type="rss", enabled=True, priority=1, cron="0 1 * * *", max_items=10, config={}),
        SourceConfig(id="trial", name="Trial", type="rss", enabled=True, priority=1, cron="0 1 * * *", max_items=10, config={}),
    ]

    grouped = group_enabled_sources_by_cron(sources)
    assert grouped == {"0 1 * * *": ["active", "trial"]}


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
    assert all(str(job["timezone"]) == "Asia/Shanghai" for job in scheduler.jobs)
    assert scheduler.jobs[0]["func"].keywords["source_filter"] == ["rss_a", "rss_b"]
    assert scheduler.jobs[1]["func"].keywords["source_filter"] == ["rss_c"]


@pytest.mark.asyncio
async def test_pipeline_slot_waits_for_previous_run_instead_of_skipping(monkeypatch):
    from src import main

    monkeypatch.setattr(main, "_pipeline_lock", asyncio.Lock())
    order = []

    async def worker(name: str, delay: float):
        lock = await main._wait_for_pipeline_slot(name)
        try:
            order.append(f"{name}:start")
            await asyncio.sleep(delay)
            order.append(f"{name}:done")
        finally:
            lock.release()

    first = asyncio.create_task(worker("rss_a", 0.02))
    await asyncio.sleep(0)
    second = asyncio.create_task(worker("rss_b", 0))
    await asyncio.gather(first, second)

    assert order == ["rss_a:start", "rss_a:done", "rss_b:start", "rss_b:done"]


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

    class FakeDiscovery:
        def __init__(self, db):
            pass

        async def discover(self):
            calls.append(("discover", None))
            return []

    async def fake_promote(db):
        calls.append(("promote", None))
        return []

    async def fake_evaluate(db):
        calls.append(("evaluate", None))
        return {}

    monkeypatch.setattr(source_scheduler, "Database", FakeDatabase)
    monkeypatch.setattr(source_scheduler, "SourceDiscovery", FakeDiscovery)
    monkeypatch.setattr(source_scheduler, "promote_candidates_to_trial", fake_promote)
    monkeypatch.setattr(source_scheduler, "evaluate_trial_sources", fake_evaluate)

    await source_scheduler.run_weekly_source_maintenance()

    assert calls == [
        ("path", "data/kb.db"),
        ("initialize", None),
        ("discover", None),
        ("promote", None),
        ("evaluate", None),
        ("close", None),
    ]


def test_weekly_source_maintenance_uses_beijing_timezone():
    from src.scheduler import source_scheduler

    class FakeScheduler:
        def __init__(self):
            self.job = None

        def add_job(self, func, trigger, **kwargs):
            self.job = {"func": func, "trigger": trigger, **kwargs}

    scheduler = FakeScheduler()
    source_scheduler.setup_source_scheduler(scheduler)

    assert str(scheduler.job["trigger"].timezone) == "Asia/Shanghai"


def test_source_maintenance_runs_twice_weekly():
    from src.scheduler.source_scheduler import SOURCE_DISCOVERY_CRON

    assert SOURCE_DISCOVERY_CRON == {"day_of_week": "mon,thu", "hour": 9, "minute": 0}
