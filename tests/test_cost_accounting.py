from src.graph.state import CostRecord, RawItem
from src.main import _build_cost_source_map, _summarize_item_costs


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
