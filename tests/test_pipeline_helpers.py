from types import SimpleNamespace

from src.graph.state import CostRecord, ReviewedItem
from src.services.pipeline_helpers import (
    build_pipeline_source_summaries,
    merge_retry_review_result,
    source_filter_count,
    source_filter_label,
    summarize_item_costs,
)


def test_source_filter_label_and_count():
    assert source_filter_label(None) == "all"
    assert source_filter_count(None) is None
    assert source_filter_label("rss_36kr") == "rss_36kr"
    assert source_filter_count("rss_36kr") == 1
    assert source_filter_label(["a", "b"]) == "a,b"
    assert source_filter_count(["a", "b"]) == 2


def test_summarize_item_costs_ignores_records_without_ref_url():
    records = [
        CostRecord(
            agent="rss",
            provider="p",
            model="m",
            tokens_in=10,
            tokens_out=5,
            cost=0.01,
            ref_url="u1",
        ),
        CostRecord(
            agent="reviewer",
            provider="p",
            model="m",
            tokens_in=2,
            tokens_out=3,
            cost=0.02,
            ref_url="u1",
        ),
        CostRecord(
            agent="reviewer",
            provider="p",
            model="m",
            tokens_in=2,
            tokens_out=3,
            cost=0.02,
            ref_url="",
        ),
    ]

    assert summarize_item_costs(records) == {"u1": (0.03, 20)}


def test_build_pipeline_source_summaries_counts_funnel():
    raw = SimpleNamespace(
        url="https://example.com/a",
        source="rss",
        source_detail="Example",
        raw_metadata={"source_id": "rss_example"},
    )
    analyzed = SimpleNamespace(ref_url=raw.url)
    reviewed = SimpleNamespace(ref_url=raw.url, verdict="approved")
    cost = CostRecord(
        agent="rss",
        provider="p",
        model="m",
        tokens_in=10,
        tokens_out=5,
        cost=0.01,
        ref_url=raw.url,
        source="rss",
        source_detail="Example",
        source_id="rss_example",
    )

    summaries = build_pipeline_source_summaries(
        run_id="run1",
        raw_items=[raw],
        new_items=[raw],
        analyzed_items=[analyzed],
        reviewed_items=[reviewed],
        cost_records=[cost],
        inserted_urls={raw.url},
        active_sources=[],
    )

    assert summaries == [
        {
            "run_id": "run1",
            "source_id": "rss_example",
            "source": "rss",
            "source_detail": "Example",
            "collected": 1,
            "new_items": 1,
            "dedup_skipped": 0,
            "analyzed": 1,
            "analysis_failed": 0,
            "approved": 1,
            "retry": 0,
            "discarded": 0,
            "inserted": 1,
            "failed": 0,
            "cost": 0.01,
            "tokens": 15,
            "filtered_items": 0,
            "request_success_rate": 1.0,
            "insert_rate": 1.0,
        }
    ]


def test_merge_retry_review_result_replaces_existing_review():
    first = ReviewedItem(ref_url="u1", total_score=60, dimensions={}, verdict="retry")
    replacement = ReviewedItem(
        ref_url="u1",
        total_score=85,
        dimensions={},
        verdict="approved",
    )
    costs = []

    result = merge_retry_review_result(
        [first],
        costs,
        {"reviewed_items": [replacement], "cost_records": ["c1"]},
    )

    assert result == [replacement]
    assert costs == ["c1"]
