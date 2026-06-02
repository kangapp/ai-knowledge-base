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
        "minimax": ProviderConfig(
            base_url="https://api.minimax.chat/v1", api_key="sk-test",
            models=[ModelInfo(id="MiniMax-M3", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)]
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "github_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "rss_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "feishu_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
            "arxiv_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 4096}
            ),
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
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


def test_github_review_prompt_uses_source_context_from_analyzed_item():
    from src.graph.reviewer import build_reviewer_user_prompt

    analyzed = AnalyzedItem(
        ref_url="https://github.com/Lum1104/Understand-Anything",
        title="Understand-Anything",
        summary="代码知识图谱工具",
        tags=["AI", "RAG", "Tool"],
        source="github",
        source_detail="Lum1104/Understand-Anything",
        source_id="github_ai_devtools",
        metadata={"stars": 49166, "topics": ["knowledge-graph", "codex"]},
    )

    prompt = build_reviewer_user_prompt(analyzed)

    assert "内容类型: github_repo" in prompt
    assert "source_id: github_ai_devtools" in prompt

@pytest.mark.asyncio
async def test_pipeline_e2e_mocked(registry):
    """全链路 mock 测试：router → fan-out → aggregator → reviewer"""
    from src.graph import pipeline as pl
    from src.graph.router import router_node
    from unittest.mock import patch, AsyncMock, MagicMock

    # Mock DB — phase 记录需要 execute/commit/fetch_one
    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.fetch_one = AsyncMock(return_value=None)
    pl.set_pipeline_db(mock_db)

    # 先定义 mock 函数
    async def mock_analyze_github(items, reg):
        return [AnalyzedItem(ref_url="https://github.com/test/x", title="Test", summary="Mocked", tags=["AI"], language="zh")], [CostRecord(agent="github_analyzer", provider="minimax", model="MiniMax-M3", tokens_in=100, tokens_out=50, cost=0.001)]

    async def mock_analyze_rss(items, reg):
        return [], []

    async def mock_reviewer(state, reg):
        return {
            "reviewed_items": [ReviewedItem(ref_url="https://github.com/test/x", total_score=85, dimensions={}, verdict="approved")],
            "cost_records": []
        }

    # Patch 分析函数 + reviewer 内部函数，再 build 图
    with patch.object(pl, "analyze_github", mock_analyze_github), \
         patch.object(pl, "analyze_rss", mock_analyze_rss), \
         patch.object(pl, "_reviewer_fn", mock_reviewer):
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

    pl.reset_analyzer_counter()
    result = await graph.ainvoke(state)

    assert len(result["analyzed_items"]) == 1
    assert result["analyzed_items"][0].ref_url == "https://github.com/test/x"
    assert len(result["reviewed_items"]) == 1
    assert result["reviewed_items"][0].verdict == "approved"


@pytest.mark.asyncio
async def test_reviewer_health_uses_config_source_id(registry):
    """Reviewer 阶段 source_health 主键使用配置 id，而不是展示名或分类名。"""
    from src.graph import pipeline as pl
    from unittest.mock import MagicMock, patch

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.fetch_one = AsyncMock(return_value=None)
    pl.set_pipeline_db(mock_db)

    async def mock_reviewer(state, reg):
        return {
            "reviewed_items": [
                ReviewedItem(ref_url="https://36kr.com/p/1", total_score=80, dimensions={}, verdict="approved"),
                ReviewedItem(ref_url="https://arxiv.org/abs/2605.1", total_score=90, dimensions={}, verdict="approved"),
            ],
            "cost_records": [],
        }

    recorded = []

    async def fake_record_source_health(db, record):
        recorded.append(record)

    node = pl._ReviewerNode(registry)
    node._reviewer = mock_reviewer
    state = PipelineState(
        run_id="test_run",
        routed_rss=[
            RawItem(
                url="https://36kr.com/p/1",
                title="rss",
                source="rss",
                source_detail="36氪",
                raw_metadata={"source_id": "rss_36kr"},
            )
        ],
        routed_arxiv=[
            RawItem(
                url="https://arxiv.org/abs/2605.1",
                title="arxiv",
                source="arxiv",
                source_detail="cs.AI",
                raw_metadata={"source_id": "rss_arxiv"},
            )
        ],
    )

    with patch("src.db.operations.record_source_health", fake_record_source_health):
        await node(state)

    assert {record.source_id for record in recorded} == {"rss_36kr", "rss_arxiv"}
