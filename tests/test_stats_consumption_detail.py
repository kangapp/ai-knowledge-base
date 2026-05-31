from pathlib import Path

import pytest

from src.core.database import Database
from src.db.operations import get_consumption_detail_stats


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def _insert_cost(
    db: Database,
    *,
    run_id: str,
    agent: str,
    provider: str,
    cost: float,
    days_ago: int,
):
    await db.execute(
        """
        INSERT OR IGNORE INTO pipeline_runs (id, started_at, status, trigger, summary)
        VALUES (?, datetime('now', ?), 'completed', 'test', '{}')
        """,
        (run_id, f"-{days_ago} days"),
    )
    await db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES (?, ?, ?, 'test-model', 100, 100, ?, datetime('now', ?))
        """,
        (run_id, agent, provider, cost, f"-{days_ago} days"),
    )


@pytest.mark.asyncio
async def test_consumption_detail_day_uses_recent_7_days_daily_window(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await _insert_cost(db, run_id="r1", agent="rss_analyzer", provider="deepseek", cost=0.2, days_ago=0)
        await _insert_cost(db, run_id="r2", agent="reviewer", provider="deepseek", cost=0.3, days_ago=6)
        await _insert_cost(db, run_id="r3", agent="github_analyzer", provider="minimax", cost=9.0, days_ago=8)
        await db.commit()

        data = await get_consumption_detail_stats(db, "day")

        assert data["period_cost"] == 0.5
        assert data["period_tokens"] == 400
        assert data["period_days"] == 2
        assert len(data["trend"]) == 2
        assert sum(row["cost"] for row in data["trend"]) == 0.5
        assert {row["provider"] for row in data["provider_trend"]} == {"deepseek"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_consumption_detail_week_uses_recent_12_weeks_weekly_window(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await _insert_cost(db, run_id="r1", agent="rss_analyzer", provider="deepseek", cost=0.2, days_ago=0)
        await _insert_cost(db, run_id="r2", agent="reviewer", provider="deepseek", cost=0.3, days_ago=50)
        await _insert_cost(db, run_id="r3", agent="github_analyzer", provider="minimax", cost=9.0, days_ago=90)
        await db.commit()

        data = await get_consumption_detail_stats(db, "week")

        assert data["period_cost"] == 0.5
        assert data["period_tokens"] == 400
        assert data["period_days"] == 2
        assert all("W" in row["label"] for row in data["trend"])
        assert sum(row["cost"] for row in data["trend"]) == 0.5
        assert {row["provider"] for row in data["provider_trend"]} == {"deepseek"}
    finally:
        await db.close()
