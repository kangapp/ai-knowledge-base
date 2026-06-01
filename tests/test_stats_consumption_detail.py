from pathlib import Path

import pytest

from src.core.database import Database
from src.db.operations import get_consumption_detail_stats, save_cost_log
from src.graph.state import CostRecord


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def _insert_cost(
    db: Database,
    *,
    run_id: str,
    agent: str,
    provider: str,
    cost: float,
    days_ago: int,
    ref_url: str | None = None,
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
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at, ref_url)
        VALUES (?, ?, ?, 'test-model', 100, 100, ?, datetime('now', ?), ?)
        """,
        (run_id, agent, provider, cost, f"-{days_ago} days", ref_url),
    )


async def _insert_article(
    db: Database,
    *,
    title: str,
    url: str,
    source: str,
    source_detail: str | None = None,
):
    await db.execute(
        """
        INSERT INTO articles (title, url, description, source, source_detail, status, collected_at)
        VALUES (?, ?, 'test article', ?, ?, 'approved', datetime('now'))
        """,
        (title, url, source, source_detail),
    )


@pytest.mark.asyncio
async def test_consumption_detail_day_uses_today_window(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await _insert_cost(db, run_id="r1", agent="rss_analyzer", provider="deepseek", cost=0.2, days_ago=0)
        await _insert_cost(db, run_id="r2", agent="reviewer", provider="deepseek", cost=0.3, days_ago=1)
        await _insert_cost(db, run_id="r3", agent="github_analyzer", provider="minimax", cost=9.0, days_ago=8)
        await db.commit()

        data = await get_consumption_detail_stats(db, "day")

        assert data["period_cost"] == 0.2
        assert data["period_tokens"] == 200
        assert data["period_days"] == 1
        assert data["trend"][0]["llm_calls"] == data["trend"][0]["articles"]
        assert len(data["trend"]) == 3
        assert sum(row["cost"] for row in data["trend"]) == 9.5
        assert {row["provider"] for row in data["provider_trend"]} == {"deepseek", "minimax"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_consumption_detail_accepts_monthly_budget(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await _insert_cost(db, run_id="r1", agent="rss_analyzer", provider="deepseek", cost=0.2, days_ago=0)
        await db.commit()

        data = await get_consumption_detail_stats(db, "day", monthly_budget=1.0)

        assert data["budget_progress"] == 0.2
        assert data["budget_remaining"] == 0.8
        assert data["monthly_budget"] == 1.0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_consumption_detail_week_uses_recent_7_day_window(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await _insert_cost(db, run_id="r1", agent="rss_analyzer", provider="deepseek", cost=0.2, days_ago=0)
        await _insert_cost(db, run_id="r2", agent="reviewer", provider="deepseek", cost=0.3, days_ago=6)
        await _insert_cost(db, run_id="r3", agent="github_analyzer", provider="minimax", cost=9.0, days_ago=7)
        await db.commit()

        data = await get_consumption_detail_stats(db, "week", trend_window="7d")

        assert data["period_cost"] == 0.5
        assert data["period_tokens"] == 400
        assert data["period_days"] == 2
        assert all("W" in row["label"] for row in data["trend"])
        assert sum(row["cost"] for row in data["trend"]) == 0.5
        assert {row["provider"] for row in data["provider_trend"]} == {"deepseek"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_consumption_detail_day_accepts_custom_trend_window(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await _insert_cost(db, run_id="r1", agent="rss_analyzer", provider="deepseek", cost=0.2, days_ago=0)
        await _insert_cost(db, run_id="r2", agent="reviewer", provider="deepseek", cost=0.3, days_ago=1)
        await _insert_cost(db, run_id="r3", agent="github_analyzer", provider="minimax", cost=9.0, days_ago=8)
        await db.commit()

        data = await get_consumption_detail_stats(db, "day", trend_window="2d")

        assert data["period_cost"] == 0.2
        assert len(data["trend"]) == 2
        assert sum(row["cost"] for row in data["trend"]) == 0.5
        assert data["trend_window"] == "2d"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_consumption_detail_source_trend_uses_article_source_detail(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        rss_url = "https://36kr.com/p/123"
        arxiv_url = "https://arxiv.org/abs/2605.00001"
        await _insert_article(db, title="36kr item", url=rss_url, source="rss", source_detail="36氪")
        await _insert_article(db, title="arxiv item", url=arxiv_url, source="arxiv", source_detail="cs.AI")
        await _insert_cost(db, run_id="r1", agent="rss_analyzer", provider="deepseek", cost=0.2, days_ago=0, ref_url=rss_url)
        await _insert_cost(db, run_id="r1", agent="reviewer", provider="deepseek", cost=0.3, days_ago=0, ref_url=rss_url)
        await _insert_cost(db, run_id="r2", agent="arxiv_analyzer", provider="minimax", cost=0.4, days_ago=0, ref_url=arxiv_url)
        await _insert_cost(db, run_id="r2", agent="reviewer", provider="minimax", cost=0.5, days_ago=0, ref_url=arxiv_url)
        await db.commit()

        data = await get_consumption_detail_stats(db, "day")

        source_costs = {
            (row["source"], row["type"]): row["cost"]
            for row in data["source_trend"]
        }
        assert source_costs[("36氪", "analyze")] == 0.2
        assert source_costs[("36氪", "review")] == 0.3
        assert source_costs[("arxiv", "analyze")] == 0.4
        assert source_costs[("arxiv", "review")] == 0.5
        assert "review" not in {row["source"] for row in data["source_trend"]}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_consumption_detail_source_trend_falls_back_to_ref_url_origin(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await _insert_cost(
            db,
            run_id="r1",
            agent="reviewer",
            provider="deepseek",
            cost=0.2,
            days_ago=0,
            ref_url="https://36kr.com/p/3831073348855433?f=rss",
        )
        await _insert_cost(
            db,
            run_id="r2",
            agent="reviewer",
            provider="deepseek",
            cost=0.3,
            days_ago=0,
            ref_url="https://github.com/baoweise-bot/aimili-vpngate",
        )
        await _insert_cost(
            db,
            run_id="r3",
            agent="reviewer",
            provider="deepseek",
            cost=0.4,
            days_ago=0,
            ref_url="https://arxiv.org/abs/2605.00001",
        )
        await db.commit()

        data = await get_consumption_detail_stats(db, "day")

        source_costs = {
            (row["source"], row["type"]): row["cost"]
            for row in data["source_trend"]
        }
        assert source_costs[("36氪", "review")] == 0.2
        assert source_costs[("github", "review")] == 0.3
        assert source_costs[("arxiv", "review")] == 0.4
        assert "review" not in {row["source"] for row in data["source_trend"]}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_consumption_detail_source_trend_prefers_cost_log_source_fields(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await db.execute(
            """
            INSERT OR IGNORE INTO pipeline_runs (id, started_at, status, trigger, summary)
            VALUES ('r1', datetime('now'), 'completed', 'test', '{}')
            """
        )
        await save_cost_log(
            db,
            "r1",
            CostRecord(
                agent="reviewer",
                provider="deepseek",
                model="test-model",
                tokens_in=100,
                tokens_out=100,
                cost=0.2,
                ref_url="https://unknown.example/item",
                source="rss",
                source_detail="36氪",
                source_id="https://36kr.com/feed",
            ),
        )

        data = await get_consumption_detail_stats(db, "day")

        assert {
            (row["source"], row["type"]): row["cost"]
            for row in data["source_trend"]
        } == {("36氪", "review"): 0.2}
    finally:
        await db.close()
