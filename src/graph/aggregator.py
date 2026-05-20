# src/graph/aggregator.py
import logging
from .state import PipelineState

logger = logging.getLogger("pipeline")


async def aggregator_node(state: PipelineState) -> dict:
    analyzed = state.analyzed_items
    # 各源数量统计，RSS 细分到子源
    by_source = {}
    rss_detail = {}
    for item in analyzed:
        src = getattr(item, "source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        if src == "rss":
            detail = getattr(item, "source_detail", "unknown")
            rss_detail[detail] = rss_detail.get(detail, 0) + 1

    logger.info("aggregator.done", extra={
        "total_analyzed": len(analyzed),
        "by_source": by_source,
        "rss_detail": rss_detail,
    })
    return {}  # analyzed_items 和 cost_records 由 operator.add reducer 自动累积