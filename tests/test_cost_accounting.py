from src.graph.state import CostRecord, RawItem
from src.main import _build_cost_source_map, _summarize_item_costs
from src.core.database import Database
from src.db.operations import save_cost_log

import pytest
from pathlib import Path


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


def test_build_cost_source_map_uses_config_source_id_for_all_sources():
    rss = RawItem(
        url="https://36kr.com/p/1",
        title="rss",
        source="rss",
        source_detail="36氪",
        raw_metadata={"source_id": "rss_36kr"},
    )
    arxiv = RawItem(
        url="https://arxiv.org/abs/2605.1",
        title="paper",
        source="arxiv",
        source_detail="cs.AI",
        raw_metadata={"source_id": "rss_arxiv"},
    )

    mapping = _build_cost_source_map([rss, arxiv])

    assert mapping["https://36kr.com/p/1"] == ("rss", "36氪", "rss_36kr")
    assert mapping["https://arxiv.org/abs/2605.1"] == ("arxiv", "cs.AI", "rss_arxiv")


def test_summarize_item_costs_groups_by_ref_url():
    costs = [
        CostRecord(agent="rss_analyzer", provider="deepseek", model="m", tokens_in=100, tokens_out=20, cost=0.1, ref_url="u1"),
        CostRecord(agent="reviewer", provider="deepseek", model="m", tokens_in=200, tokens_out=30, cost=0.2, ref_url="u1"),
        CostRecord(agent="reviewer", provider="deepseek", model="m", tokens_in=300, tokens_out=40, cost=0.3, ref_url="u2"),
    ]

    summary = _summarize_item_costs(costs)

    assert summary["u1"] == (0.3, 350)
    assert summary["u2"] == (0.3, 340)


@pytest.mark.asyncio
async def test_save_cost_log_persists_audit_fields(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await db.execute(
            "INSERT INTO pipeline_runs (id, started_at, status, trigger) VALUES ('run_1', datetime('now', '+8 hours'), 'completed', 'test')"
        )
        await save_cost_log(
            db,
            "run_1",
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
                status="parse_failed",
                error="invalid json",
                latency_ms=1234,
                attempt_no=2,
                prompt_name="rss_analyzer",
                prompt_version="2026-06-02",
            ),
        )

        row = await db.fetch_one("SELECT * FROM cost_logs WHERE run_id='run_1'")

        assert row["status"] == "parse_failed"
        assert row["error"] == "invalid json"
        assert row["latency_ms"] == 1234
        assert row["attempt_no"] == 2
        assert row["prompt_name"] == "rss_analyzer"
        assert row["prompt_version"] == "2026-06-02"
    finally:
        await db.close()
