from .state import PipelineState

ROUTE_MAP = {"github": "routed_github", "rss": "routed_rss", "feishu": "routed_feishu", "arxiv": "routed_arxiv"}


async def router_node(state: PipelineState) -> dict:
    result = {"routed_github": [], "routed_rss": [], "routed_feishu": [], "routed_arxiv": []}
    for item in state.raw_items:
        key = ROUTE_MAP.get(item.source)
        if key:
            result[key].append(item)
        else:
            result["routed_rss"].append(item)  # 兜底
    return result