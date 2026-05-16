# tests/test_pipeline.py
import pytest
from unittest.mock import AsyncMock
from src.graph.pipeline import build_pipeline
from src.graph.state import PipelineState, RawItem, AnalyzedItem, CostRecord, ReviewedItem
from src.core.llm_client import LLMRegistry
from src.core.config import (
    LLMConfig, AgentsConfig, ProviderConfig, ModelInfo,
    AgentConfig, ModelBinding, ModelRef, BudgetConfig
)

@pytest.fixture
def registry():
    llm_cfg = LLMConfig(providers={
        "deepseek": ProviderConfig(
            base_url="https://api.deepseek.com/v1", api_key="sk-test",
            models=[ModelInfo(id="deepseek-chat", price_per_1k_in=0.000014, price_per_1k_out=0.000028, max_tokens=8192)]
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "github_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "rss_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "feishu_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "arxiv_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 4096}
            ),
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="deepseek", model="deepseek-chat"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 1024}
            ),
        },
        budget=BudgetConfig(monthly=10.0)
    )
    return LLMRegistry(llm_cfg, agents_cfg)

def test_pipeline_structure(registry):
    graph = build_pipeline(registry)
    nodes = graph.get_graph().nodes
    names = {n for n in nodes}
    assert "router" in names
    assert "github_analyzer" in names
    assert "rss_analyzer" in names
    assert "feishu_analyzer" in names
    assert "arxiv_analyzer" in names
    assert "aggregator" in names
    assert "reviewer" in names

@pytest.mark.asyncio
async def test_pipeline_e2e_mocked(registry):
    """全链路 mock 测试：router → fan-out → aggregator → reviewer"""
    from src.graph import pipeline as pl
    from src.graph.router import router_node
    from unittest.mock import patch

    # 先定义 mock 函数
    async def mock_analyze_github(items, reg):
        return [AnalyzedItem(ref_url="https://github.com/test/x", title="Test", summary="Mocked", tags=["AI"], language="zh")], [CostRecord(agent="github_analyzer", provider="deepseek", model="deepseek-chat", tokens_in=100, tokens_out=50, cost=0.001)]

    async def mock_analyze_rss(items, reg):
        return [], []

    async def mock_reviewer(state, reg):
        return {
            "reviewed_items": [ReviewedItem(ref_url="https://github.com/test/x", total_score=85, dimensions={}, verdict="approved")],
            "cost_records": []
        }

    # Patch 分析函数，再 build 图（_AnalyzerNode 在 build 时捕获）
    with patch.object(pl, "analyze_github", mock_analyze_github), \
         patch.object(pl, "analyze_rss", mock_analyze_rss), \
         patch.object(pl, "reviewer_node", mock_reviewer):
        graph = build_pipeline(registry)

    state = PipelineState(
        raw_items=[
            RawItem(url="https://github.com/test/x", title="x", description="desc", source="github", collected_at="2026-05-16T10:00:00Z"),
            RawItem(url="https://example.com/y", title="y", description="desc", source="rss", collected_at="2026-05-16T10:00:00Z"),
        ],
        run_id="test_run", trigger="manual"
    )

    # Router 先跑一次得到 routed_*
    routed = await router_node(state)
    state = state.model_copy(update=routed)

    result = await graph.ainvoke(state)

    assert len(result["analyzed_items"]) == 1
    assert result["analyzed_items"][0].ref_url == "https://github.com/test/x"
    assert len(result["reviewed_items"]) == 1
    assert result["reviewed_items"][0].verdict == "approved"