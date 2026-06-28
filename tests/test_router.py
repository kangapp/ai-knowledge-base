import pytest
from src.graph.state import PipelineState, RawItem
from src.graph.router import router_node


@pytest.mark.asyncio
async def test_router_classifies_by_source():
    state = PipelineState(raw_items=[
        RawItem(url="a", title="a", source="github", collected_at=""),
        RawItem(url="b", title="b", source="rss", collected_at=""),
        RawItem(url="c", title="c", source="feishu", collected_at=""),
        RawItem(url="d", title="d", source="arxiv", collected_at=""),
        RawItem(url="e", title="e", source="hotlist", collected_at=""),
        RawItem(url="f", title="f", source="hn", collected_at=""),
    ])
    result = await router_node(state)
    assert len(result["routed_github"]) == 1
    assert len(result["routed_rss"]) == 3
    assert len(result["routed_feishu"]) == 1
    assert len(result["routed_arxiv"]) == 1


@pytest.mark.asyncio
async def test_router_empty():
    state = PipelineState()
    result = await router_node(state)
    assert result["routed_github"] == []
