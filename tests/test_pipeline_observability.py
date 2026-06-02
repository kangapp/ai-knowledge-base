from src.graph.state import CostRecord, RawItem, ReviewedItem, AnalyzedItem
from src import main


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

    summaries = main._build_pipeline_source_summaries(
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

    summaries = main._build_pipeline_source_summaries(
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

    retry_items = main._prepare_retry_review_items([reviewed], [analyzed], [raw])

    assert retry_items == [analyzed]
    assert retry_items[0].retry_count == 1
    assert retry_items[0].title == "repo analyzed"
