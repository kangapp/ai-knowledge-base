# src/graph/aggregator.py
import logging
from .state import PipelineState

logger = logging.getLogger("pipeline")


async def aggregator_node(state: PipelineState) -> dict:
    analyzed = state.analyzed_items
    # 各源数量统计
    by_source = {}
    for item in analyzed:
        src = getattr(item, "source", "unknown")
        by_source[src] = by_source.get(src, 0) + 1

    logger.info("aggregator.done", extra={
        "total_analyzed": len(analyzed),
        "by_source": by_source,
    })
    return {}  # analyzed_items 和 cost_records 由 operator.add reducer 自动累积