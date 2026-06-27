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
