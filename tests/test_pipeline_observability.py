import pytest
from pathlib import Path

from src.core.budget import BudgetTracker
from src.core.config import BudgetConfig, SourceConfig
from src.core.database import Database
from src.graph.state import CostRecord, RawItem, ReviewedItem, AnalyzedItem
from src.graph.pipeline import record_phase_end, record_phase_start
from src import main
from src.services.pipeline_helpers import (
    build_pipeline_source_summaries,
    merge_retry_review_result,
    prepare_retry_review_items,
)


def test_build_pipeline_source_summaries_groups_funnel_by_source_id():
    raw_items = [
        RawItem(
            url="https://example.com/a",
            title="A",
            source="rss",
            source_detail="RSS Test",
            raw_metadata={"source_id": "rss_test"},
        ),
        RawItem(
            url="https://example.com/b",
            title="B",
            source="rss",
            source_detail="RSS Test",
            raw_metadata={"source_id": "rss_test"},
        ),
        RawItem(
            url="https://github.com/org/repo",
            title="repo",
            source="github",
            source_detail="org/repo",
            raw_metadata={"source_id": "github_ai"},
        ),
    ]
    new_items = [raw_items[0], raw_items[2]]
    analyzed = [
        AnalyzedItem(ref_url="https://example.com/a", title="A", summary="s", tags=["AI"]),
        AnalyzedItem(ref_url="https://github.com/org/repo", title="repo", summary="s", tags=["AI"]),
    ]
    reviewed = [
        ReviewedItem(ref_url="https://example.com/a", total_score=85, dimensions={}, verdict="approved"),
        ReviewedItem(ref_url="https://github.com/org/repo", total_score=30, dimensions={}, verdict="discarded"),
    ]
    costs = [
        CostRecord(
            agent="rss_analyzer",
            provider="minimax",
            model="MiniMax-M3",
            tokens_in=100,
            tokens_out=50,
            cost=0.01,
            ref_url="https://example.com/a",
            source="rss",
            source_detail="RSS Test",
            source_id="rss_test",
        ),
        CostRecord(
            agent="github_analyzer",
            provider="minimax",
            model="MiniMax-M3",
            tokens_in=200,
            tokens_out=80,
            cost=0.02,
            ref_url="https://github.com/org/repo",
            source="github",
            source_detail="org/repo",
            source_id="github_ai",
        ),
    ]

    summaries = build_pipeline_source_summaries(
        run_id="run_1",
        raw_items=raw_items,
        new_items=new_items,
        analyzed_items=analyzed,
        reviewed_items=reviewed,
        cost_records=costs,
        inserted_urls={"https://example.com/a"},
        failed_counts={"rss_test": 1},
    )

    by_source = {row["source_id"]: row for row in summaries}
    assert by_source["rss_test"] == {
        "run_id": "run_1",
        "source_id": "rss_test",
        "source": "rss",
        "source_detail": "RSS Test",
        "collected": 2,
        "new_items": 1,
        "dedup_skipped": 1,
        "analyzed": 1,
        "analysis_failed": 0,
        "approved": 1,
        "retry": 0,
        "discarded": 0,
        "inserted": 1,
        "failed": 1,
        "cost": 0.01,
        "tokens": 150,
        "filtered_items": 0,
        "request_success_rate": 0.667,
        "insert_rate": 1.0,
    }
    assert by_source["github_ai"]["collected"] == 1
    assert by_source["github_ai"]["discarded"] == 1
    assert by_source["github_ai"]["inserted"] == 0
    assert by_source["github_ai"]["tokens"] == 280


def test_build_pipeline_source_summaries_exposes_filtered_items():
    raw_items = [
        RawItem(
            url="https://example.com/a",
            title="A",
            source="rss",
            source_detail="RSS Test",
            raw_metadata={"source_id": "rss_test"},
        ),
        RawItem(
            url="https://example.com/b",
            title="B",
            source="rss",
            source_detail="RSS Test",
            raw_metadata={"source_id": "rss_test"},
        ),
    ]
    reviewed = [
        ReviewedItem(ref_url="https://example.com/a", total_score=10, dimensions={}, verdict="discarded"),
        ReviewedItem(ref_url="https://example.com/b", total_score=70, dimensions={}, verdict="retry"),
    ]

    summaries = build_pipeline_source_summaries(
        run_id="run_1",
        raw_items=raw_items,
        new_items=raw_items,
        analyzed_items=[
            AnalyzedItem(ref_url=item.url, title=item.title, summary="s", tags=["AI"])
            for item in raw_items
        ],
        reviewed_items=reviewed,
        cost_records=[],
        inserted_urls=set(),
    )

    summary = summaries[0]
    assert summary["filtered_items"] == 2
    assert summary["request_success_rate"] == 1
    assert summary["insert_rate"] == 0


def test_build_pipeline_source_summaries_records_successful_zero_source():
    source = SourceConfig(
        id="rss_verge",
        name="The Verge",
        type="rss",
        enabled=True,
        priority=1,
        cron="0 * * * *",
        max_items=10,
    )

    summaries = build_pipeline_source_summaries(
        run_id="run_zero",
        raw_items=[],
        new_items=[],
        analyzed_items=[],
        reviewed_items=[],
        cost_records=[],
        inserted_urls=set(),
        active_sources=[source],
    )

    assert summaries == [
        {
            "run_id": "run_zero",
            "source_id": "rss_verge",
            "source": "rss",
            "source_detail": "The Verge",
            "collected": 0,
            "new_items": 0,
            "dedup_skipped": 0,
            "analyzed": 0,
            "analysis_failed": 0,
            "approved": 0,
            "retry": 0,
            "discarded": 0,
            "inserted": 0,
            "failed": 0,
            "cost": 0.0,
            "tokens": 0,
            "filtered_items": 0,
            "request_success_rate": 0,
            "insert_rate": 0,
        }
    ]


def test_prepare_retry_review_items_reuses_existing_analysis():
    raw = RawItem(
        url="https://github.com/org/repo",
        title="repo",
        source="github",
        source_detail="org/repo",
        raw_metadata={"source_id": "github_ai_devtools"},
    )
    analyzed = AnalyzedItem(
        ref_url=raw.url,
        title="repo analyzed",
        summary="s",
        tags=["AI"],
        retry_count=0,
        source="github",
        source_detail="org/repo",
        source_id="github_ai_devtools",
    )
    reviewed = ReviewedItem(ref_url=raw.url, total_score=60, dimensions={}, verdict="retry")

    retry_items = prepare_retry_review_items([reviewed], [analyzed], [raw])

    assert retry_items == [analyzed]
    assert retry_items[0].retry_count == 1
    assert retry_items[0].title == "repo analyzed"


def test_merge_retry_review_result_accepts_review_only_result():
    original = ReviewedItem(
        ref_url="https://example.com/a",
        total_score=60,
        dimensions={},
        verdict="retry",
    )
    updated = ReviewedItem(
        ref_url="https://example.com/a",
        total_score=72,
        dimensions={},
        verdict="approved",
    )
    cost = CostRecord(
        agent="reviewer",
        provider="minimax",
        model="MiniMax-M3",
        tokens_in=10,
        tokens_out=5,
        cost=0.001,
        status="success",
        ref_url=updated.ref_url,
    )

    reviewed = merge_retry_review_result(
        all_reviewed=[original],
        all_costs=[],
        retry_result={"reviewed_items": [updated], "cost_records": [cost]},
    )

    assert reviewed == [updated]


@pytest.mark.asyncio
async def test_phase_end_treats_skipped_and_superseded_as_non_errors(tmp_path):
    migrations_dir = Path(__file__).parent.parent / "src" / "db" / "migrations"
    db = Database(tmp_path / "phase_status.db", migrations_dir=migrations_dir)
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO pipeline_runs (id, started_at, status, trigger)
            VALUES ('run_phase', datetime('now', '+8 hours'), 'running', 'test')
            """
        )
        for phase, status in (("deep_report", "skipped"), ("build", "superseded")):
            await record_phase_start(db, "run_phase", phase)
            await record_phase_end(db, "run_phase", phase, status, "normal branch")

        events = await db.fetch_all(
            """
            SELECT phase, level, status FROM pipeline_events
            WHERE run_id='run_phase' AND event LIKE '%.end'
            ORDER BY id
            """
        )

        assert [dict(row) for row in events] == [
            {"phase": "deep_report", "level": "info", "status": "skipped"},
            {"phase": "build", "level": "info", "status": "superseded"},
        ]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_build_status_callback_updates_single_phase_lifecycle(tmp_path, monkeypatch):
    migrations_dir = Path(__file__).parent.parent / "src" / "db" / "migrations"
    db = Database(tmp_path / "build_status.db", migrations_dir=migrations_dir)
    await db.initialize()
    monkeypatch.setattr(main, "_db", db)
    try:
        await db.execute(
            """
            INSERT INTO pipeline_runs (id, started_at, status, trigger)
            VALUES ('run_build', datetime('now', '+8 hours'), 'completed', 'test')
            """
        )

        for status in ("queued", "running", "completed"):
            await main._record_build_status("run_build", status, status)

        phase = await db.fetch_one(
            """
            SELECT phase, status, started_at, ended_at, details
            FROM pipeline_phase_logs WHERE run_id='run_build' AND phase='build'
            """
        )
        events = await db.fetch_all(
            """
            SELECT event, status FROM pipeline_events
            WHERE run_id='run_build' AND phase='build' ORDER BY id
            """
        )

        assert dict(phase) == {
            "phase": "build",
            "status": "done",
            "started_at": phase["started_at"],
            "ended_at": phase["ended_at"],
            "details": "completed",
        }
        assert phase["started_at"]
        assert phase["ended_at"]
        assert [dict(row) for row in events] == [
            {"event": "site.build_queued", "status": "queued"},
            {"event": "site.build_running", "status": "running"},
            {"event": "site.build_completed", "status": "completed"},
        ]
    finally:
        monkeypatch.setattr(main, "_db", None)
        await db.close()


@pytest.mark.asyncio
async def test_record_skipped_phases_creates_explicit_terminal_states(tmp_path):
    migrations_dir = Path(__file__).parent.parent / "src" / "db" / "migrations"
    db = Database(tmp_path / "skipped_phases.db", migrations_dir=migrations_dir)
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO pipeline_runs (id, started_at, status, trigger)
            VALUES ('run_skip', datetime('now', '+8 hours'), 'running', 'test')
            """
        )

        await main._record_skipped_phases(
            db,
            "run_skip",
            ("route", "analyze", "review", "persist", "deep_report", "backup", "build"),
            "无新条目",
        )

        rows = await db.fetch_all(
            """
            SELECT phase, status, details FROM pipeline_phase_logs
            WHERE run_id='run_skip' ORDER BY id
            """
        )
        assert [dict(row) for row in rows] == [
            {"phase": phase, "status": "skipped", "details": "无新条目"}
            for phase in ("route", "analyze", "review", "persist", "deep_report", "backup", "build")
        ]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sync_registry_budget_uses_today_database_cost(tmp_path):
    migrations_dir = Path(__file__).parent.parent / "src" / "db" / "migrations"
    db = Database(tmp_path / "budget_sync.db", migrations_dir=migrations_dir)
    await db.initialize()
    await db.execute(
        """
        INSERT INTO cost_logs
        (agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES
        ('rss_analyzer', 'minimax', 'MiniMax-M3', 10, 5, 0.12,
         datetime('now', '+8 hours'))
        """
    )
    await db.commit()

    class Registry:
        budget = BudgetTracker(BudgetConfig(monthly=10.0))

    try:
        await main._sync_registry_budget(db, Registry())

        assert Registry.budget.current_daily() == pytest.approx(0.12)
        assert Registry.budget.provider_daily("minimax") == pytest.approx(0.12)
    finally:
        await db.close()
