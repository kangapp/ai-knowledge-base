import logging
from .state import PipelineState

logger = logging.getLogger("pipeline")
ROUTE_MAP = {
    "github": "routed_github",
    "rss": "routed_rss",
    "hotlist": "routed_rss",
    "hn": "routed_rss",
    "feishu": "routed_feishu",
    "arxiv": "routed_arxiv",
}


async def router_node(state: PipelineState) -> dict:
    result = {"routed_github": [], "routed_rss": [], "routed_feishu": [], "routed_arxiv": []}
    # RSS 子源统计
    rss_by_source = {}
    for item in state.raw_items:
        key = ROUTE_MAP.get(item.source)
        if key:
            result[key].append(item)
            if item.source in {"rss", "hotlist", "hn"} and item.source_detail:
                rss_by_source[item.source_detail] = rss_by_source.get(item.source_detail, 0) + 1
        else:
            result["routed_rss"].append(item)  # 兜底

    logger.info("router.done", extra={
        "total": len(state.raw_items),
        "github": len(result["routed_github"]),
        "rss": len(result["routed_rss"]),
        "feishu": len(result["routed_feishu"]),
        "arxiv": len(result["routed_arxiv"]),
        "rss_by_source": rss_by_source,
    })
    return result
