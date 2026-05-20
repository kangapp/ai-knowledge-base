import logging
from .state import PipelineState

logger = logging.getLogger("pipeline")
ROUTE_MAP = {"github": "routed_github", "rss": "routed_rss", "feishu": "routed_feishu", "arxiv": "routed_arxiv"}


async def router_node(state: PipelineState) -> dict:
    result = {"routed_github": [], "routed_rss": [], "routed_feishu": [], "routed_arxiv": []}
    for item in state.raw_items:
        key = ROUTE_MAP.get(item.source)
        if key:
            result[key].append(item)
        else:
            result["routed_rss"].append(item)  # 兜底

    logger.info("router.done", extra={
        "total": len(state.raw_items),
        "github": len(result["routed_github"]),
        "rss": len(result["routed_rss"]),
        "feishu": len(result["routed_feishu"]),
        "arxiv": len(result["routed_arxiv"]),
    })
    return result