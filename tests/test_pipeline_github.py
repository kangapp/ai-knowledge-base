from src.core.config import SourceConfig
from src.graph.state import RawItem
from src.main import _apply_github_velocity_filter


def make_item(url: str, source_id: str) -> RawItem:
    return RawItem(
        url=url,
        title=url.rsplit("/", 1)[-1],
        source="github",
        collected_at="2026-06-01T00:00:00Z",
        raw_metadata={"source_id": source_id},
    )


def make_source(source_id: str) -> SourceConfig:
    return SourceConfig(
        id=source_id,
        name=source_id,
        type="github",
        enabled=True,
        priority=1,
        cron="0 9 * * *",
        max_items=10,
        config={"trend_mode": source_id == "github_trending_velocity"},
    )


def test_velocity_filter_only_filters_matching_source_id():
    regular = make_item("https://github.com/org/regular", "github_trending")
    velocity_keep = make_item("https://github.com/org/fast", "github_trending_velocity")
    velocity_drop = make_item("https://github.com/org/slow", "github_trending_velocity")
    rss = RawItem(url="https://example.com/rss", title="rss", source="rss", collected_at="")

    items = _apply_github_velocity_filter(
        [regular, velocity_keep, velocity_drop, rss],
        make_source("github_trending_velocity"),
        {"https://github.com/org/fast"},
    )

    assert items == [regular, velocity_keep, rss]
