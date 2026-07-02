from pathlib import Path

import pytest

from src.core.config import SourceConfig
from src.core.database import Database
from src.core.source_discovery import SourceDiscovery
from src.core.source_governance import (
    apply_governance,
    calculate_health_score,
    evaluate_trial_sources,
    promote_candidates_to_trial,
    rollup_source_health_daily,
)


@pytest.mark.asyncio
async def test_discovered_source_is_candidate_only(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        discovery = SourceDiscovery(db)
        source = SourceConfig(
            id="rss_candidate",
            name="Candidate RSS",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await discovery._write_discovered_source(source)

        row = await db.fetch_one(
            "SELECT status, enabled FROM source_registry WHERE id = ?",
            ("rss_candidate",),
        )
        assert row["status"] == "candidate"
        assert row["enabled"] == 0
    finally:
        await db.close()


def test_budget_blocked_does_not_score_source():
    assert calculate_health_score({"budget_blocked": 1}) is None


def test_health_score_uses_quality_freshness_and_cost():
    score = calculate_health_score({
        "request_success_rate": 1.0,
        "collected": 10,
        "new_items": 5,
        "approved": 2,
        "avg_score": 80,
        "cost": 0.02,
    })
    assert score == 66.0


def test_dedup_only_run_does_not_score_source():
    assert calculate_health_score({
        "request_success_rate": 1.0,
        "collected": 10,
        "new_items": 0,
        "approved": 0,
        "cost": 0,
    }) is None


@pytest.mark.asyncio
async def test_low_scores_progress_to_quarantine(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_low', 'Low', 'rss', 'active', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for day in ["2026-06-25", "2026-06-26", "2026-06-27"]:
            await db.execute(
                """
                INSERT INTO source_health_daily
                (source_id, date, health_score)
                VALUES ('rss_low', ?, 20)
                """,
                (day,),
            )
        await db.commit()

        status = await apply_governance(db, "rss_low")
        assert status == "quarantined"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_single_low_score_does_not_degrade_active_source(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_low_once', 'Low Once', 'rss', 'active', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for day, score in [
            ("2026-06-25", 80),
            ("2026-06-26", 80),
            ("2026-06-27", 20),
        ]:
            await db.execute(
                """
                INSERT INTO source_health_daily
                (source_id, date, health_score)
                VALUES ('rss_low_once', ?, ?)
                """,
                (day, score),
            )
        await db.commit()

        status = await apply_governance(db, "rss_low_once")
        assert status == "active"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_three_run_average_degrades_active_source(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_low_average', 'Low Average', 'rss', 'active', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for day, score in [
            ("2026-06-25", 40),
            ("2026-06-26", 45),
            ("2026-06-27", 49),
        ]:
            await db.execute(
                """
                INSERT INTO source_health_daily
                (source_id, date, health_score)
                VALUES ('rss_low_average', ?, ?)
                """,
                (day, score),
            )
        await db.commit()

        status = await apply_governance(db, "rss_low_average")
        assert status == "degraded"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_degraded_source_recovers_after_three_good_scores(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_recovered', 'Recovered', 'rss', 'degraded', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for day, score in [
            ("2026-06-25", 60),
            ("2026-06-26", 65),
            ("2026-06-27", 70),
        ]:
            await db.execute(
                """
                INSERT INTO source_health_daily
                (source_id, date, health_score)
                VALUES ('rss_recovered', ?, ?)
                """,
                (day, score),
            )
        await db.commit()

        status = await apply_governance(db, "rss_recovered")
        row = await db.fetch_one(
            "SELECT status FROM source_registry WHERE id = 'rss_recovered'"
        )
        event = await db.fetch_one(
            """
            SELECT from_status, to_status, reason
            FROM source_governance_events
            WHERE source_id = 'rss_recovered'
            """
        )

        assert status == "active"
        assert row["status"] == "active"
        assert event["from_status"] == "degraded"
        assert event["to_status"] == "active"
        assert event["reason"] == "最近3次平均健康分恢复到60以上"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_daily_rollup_recalculates_score_from_accumulated_metrics(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_mixed', 'Mixed', 'rss', 'active', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for run_id, approved in [("run_low", 0), ("run_high", 10)]:
            await db.execute(
                """
                INSERT INTO pipeline_runs (id, started_at, status, trigger)
                VALUES (?, datetime('now', '+8 hours'), 'completed', 'test')
                """,
                (run_id,),
            )
            await db.execute(
                """
                INSERT INTO pipeline_source_runs
                (run_id, source_id, source, source_detail, collected, new_items,
                 analyzed, approved, discarded, failed, cost, tokens)
                VALUES (?, 'rss_mixed', 'rss', 'Mixed', 10, 10, 10, ?, ?, 0, 0.01, 1000)
                """,
                (run_id, approved, 10 - approved),
            )
            await rollup_source_health_daily(db, run_id)

        row = await db.fetch_one(
            """
            SELECT collected, new_items, approved, discarded, cost, health_score
            FROM source_health_daily
            WHERE source_id = 'rss_mixed'
            """
        )

        assert row["collected"] == 20
        assert row["new_items"] == 20
        assert row["approved"] == 10
        assert row["discarded"] == 10
        assert row["cost"] == 0.02
        assert row["health_score"] == 77.5
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_daily_rollup_recalculates_request_success_from_accumulated_attempts(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_flaky', 'Flaky', 'rss', 'active', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for run_id, collected, failed in [
            ("run_success", 10, 0),
            ("run_failed", 0, 1),
        ]:
            await db.execute(
                """
                INSERT INTO pipeline_runs (id, started_at, status, trigger)
                VALUES (?, datetime('now', '+8 hours'), 'completed', 'test')
                """,
                (run_id,),
            )
            await db.execute(
                """
                INSERT INTO pipeline_source_runs
                (run_id, source_id, source, source_detail, collected, new_items,
                 analyzed, approved, discarded, failed, cost, tokens)
                VALUES (?, 'rss_flaky', 'rss', 'Flaky', ?, ?, ?, ?, 0, ?, 0.01, 1000)
                """,
                (run_id, collected, collected, collected, collected, failed),
            )
            await rollup_source_health_daily(db, run_id)

        row = await db.fetch_one(
            """
            SELECT request_success_rate, collected, failed, new_items, approved, health_score
            FROM source_health_daily
            WHERE source_id = 'rss_flaky'
            """
        )

        assert row["collected"] == 10
        assert row["failed"] == 1
        assert row["request_success_rate"] == pytest.approx(10 / 11)
        assert row["new_items"] == 10
        assert row["approved"] == 10
        assert row["health_score"] == 97.7
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_promote_candidates_to_trial_enables_small_batch(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        for source_id in ["rss_candidate_a", "rss_candidate_b"]:
            await db.execute(
                """
                INSERT INTO source_registry
                (id, name, type, status, enabled, priority, cron, max_items, config_json)
                VALUES (?, ?, 'rss', 'candidate', 0, 2, '0 1 * * *', 10, '{}')
                """,
                (source_id, source_id),
            )
        await db.commit()

        promoted = await promote_candidates_to_trial(db, limit=1)

        assert promoted == ["rss_candidate_a"]
        row = await db.fetch_one(
            "SELECT status, enabled FROM source_registry WHERE id = ?",
            ("rss_candidate_a",),
        )
        assert row["status"] == "trial"
        assert row["enabled"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_evaluate_trial_sources_promotes_after_three_good_runs(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_trial', 'Trial', 'rss', 'trial', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for day in ["2026-06-25", "2026-06-26", "2026-06-27"]:
            await db.execute(
                """
                INSERT INTO source_health_daily
                (source_id, date, request_success_rate, collected, new_items, approved, health_score, budget_blocked)
                VALUES ('rss_trial', ?, 1.0, 3, 2, 1, 70, 0)
                """,
                (day,),
            )
        await db.commit()

        changed = await evaluate_trial_sources(db)

        assert changed == {"rss_trial": "active"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_evaluate_trial_sources_rejects_after_three_bad_runs(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES ('rss_trial', 'Trial', 'rss', 'trial', 1, 2, '0 1 * * *', 10, '{}')
            """
        )
        for day in ["2026-06-25", "2026-06-26", "2026-06-27"]:
            await db.execute(
                """
                INSERT INTO source_health_daily
                (source_id, date, request_success_rate, collected, new_items, approved, health_score, budget_blocked)
                VALUES ('rss_trial', ?, 1.0, 3, 0, 0, 25, 0)
                """,
                (day,),
            )
        await db.commit()

        changed = await evaluate_trial_sources(db)

        assert changed == {"rss_trial": "rejected"}
    finally:
        await db.close()
