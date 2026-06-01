# tests/test_reviewer.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.graph.state import PipelineState, AnalyzedItem, ReviewedItem
from src.graph.reviewer import reviewer_node, parse_reviewer_output
from tests.fixtures.llm_responses import REVIEWER_RESPONSE

def test_parse_reviewer_output():
    raw = json.dumps({
        "total_score": 85,
        "dimensions": {
            "ai_relevance": {"score": 35, "reason": "核心 LLM 推理框架"},
            "content_depth": {"score": 25, "reason": "有技术细节"},
            "info_density": {"score": 12, "reason": "有新信息"},
            "timeliness": {"score": 13, "reason": "本周发布"}
        },
        "verdict": "approved",
        "retry_feedback": None
    })
    result = parse_reviewer_output(raw)
    assert isinstance(result, ReviewedItem)
    assert result.total_score == 85
    assert result.verdict == "approved"
    assert result.dimensions["ai_relevance"]["score"] == 35
    assert result.retry_feedback is None

def test_parse_reviewer_output_retry():
    raw = json.dumps({
        "total_score": 65,
        "dimensions": {
            "ai_relevance": {"score": 25, "reason": "AI 基础设施"},
            "content_depth": {"score": 18, "reason": "有部分细节"},
            "info_density": {"score": 10, "reason": "有一定信息量"},
            "timeliness": {"score": 12, "reason": "本周"}
        },
        "verdict": "retry",
        "retry_feedback": {"suggestions": ["补充 AI 相关度分析", "增加技术深度"]}
    })
    result = parse_reviewer_output(raw)
    assert result.verdict == "retry"
    assert result.retry_feedback["suggestions"] == ["补充 AI 相关度分析", "增加技术深度"]

def test_parse_reviewer_output_markdown_wrapped():
    raw = '```json\n{"total_score": 30, "dimensions": {"ai_relevance": {"score": 5, "reason": "无关"}, "content_depth": {"score": 8, "reason": "简要"}, "info_density": {"score": 5, "reason": "重复"}, "timeliness": {"score": 12, "reason": "本周"}}, "verdict": "discarded", "retry_feedback": null}\n```'
    result = parse_reviewer_output(raw)
    assert result.verdict == "discarded"


def test_parse_reviewer_output_normalizes_dimension_alias_and_score():
    raw = json.dumps({
        "total_score": 99,
        "dimensions": {
            "ai_relevance": {"score": 34, "reason": "AI 基础设施"},
            "content_depth": {"score": 20, "reason": "有细节"},
            "information_density": {"score": 10, "reason": "有信息量"},
            "timeliness": {"score": 9, "reason": "本月"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw)

    assert result.total_score == 73
    assert set(result.dimensions) == {"ai_relevance", "content_depth", "info_density", "timeliness"}
    assert result.dimensions["info_density"]["score"] == 10
    assert result.verdict == "retry"
    assert result.retry_feedback is not None


def test_parse_reviewer_output_discards_low_ai_relevance_even_when_model_approves():
    raw = json.dumps({
        "total_score": 85,
        "dimensions": {
            "ai_relevance": {"score": 15, "reason": "只泛泛提到 AI"},
            "content_depth": {"score": 25, "reason": "有行业细节"},
            "info_density": {"score": 14, "reason": "信息密集"},
            "timeliness": {"score": 15, "reason": "本周"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw)

    assert result.total_score == 69
    assert result.verdict == "discarded"
    assert result.retry_feedback is None


@pytest.mark.asyncio
async def test_reviewer_node_mocked():
    """Mock LLM 调用，验证 Reviewer 节点正确分类"""
    from src.core.llm_client import LLMRegistry
    from src.core.config import (
        LLMConfig, AgentsConfig, ProviderConfig, ModelInfo,
        AgentConfig, ModelBinding, ModelRef, BudgetConfig
    )

    llm_cfg = LLMConfig(providers={
        "minimax": ProviderConfig(
            base_url="https://api.minimax.chat/v1", api_key="sk-test",
            models=[ModelInfo(id="MiniMax-M2.7", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)]
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M2.7"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 1024}
            ),
        },
        budget=BudgetConfig(monthly=10.0)
    )
    registry = LLMRegistry(llm_cfg, agents_cfg)

    # Mock AsyncOpenAI client
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "total_score": 88, "dimensions": {
                "ai_relevance": {"score": 38, "reason": "核心 Agent 框架"},
                "content_depth": {"score": 25, "reason": "深度原创"},
                "info_density": {"score": 13, "reason": "新颖"},
                "timeliness": {"score": 12, "reason": "本周"}
            }, "verdict": "approved", "retry_feedback": None
        })))
    ]
    mock_response.usage = MagicMock(prompt_tokens=300, completion_tokens=120)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    registry._clients["minimax"] = mock_client

    state = PipelineState(analyzed_items=[
        AnalyzedItem(ref_url="https://example.com/1", title="Test Agent", summary="A new agent framework", tags=["Agent", "Framework"], language="zh", retry_count=0)
    ])
    result = await reviewer_node(state, registry)

    assert len(result["reviewed_items"]) == 1
    reviewed = result["reviewed_items"][0]
    assert reviewed.verdict == "approved"
    assert reviewed.total_score == 88
    assert len(result["cost_records"]) == 1


@pytest.mark.asyncio
async def test_reviewer_node_records_cost_when_parse_fails():
    from src.core.config import (
        AgentConfig, AgentsConfig, ProviderConfig, ModelInfo,
        ModelBinding, ModelRef, BudgetConfig, LLMConfig,
    )
    from src.core.llm_client import LLMRegistry

    llm_cfg = LLMConfig(providers={
        "minimax": ProviderConfig(
            base_url="https://api.minimax.chat/v1",
            api_key="sk-test",
            models=[ModelInfo(id="MiniMax-M2.7", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)],
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M2.7"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 1024},
            )
        },
        budget=BudgetConfig(monthly=10.0),
    )
    registry = LLMRegistry(llm_cfg, agents_cfg)

    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="not json"))]
    mock_response.usage = MagicMock(prompt_tokens=1000, completion_tokens=500)
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    registry._clients["minimax"] = mock_client

    state = PipelineState(analyzed_items=[
        AnalyzedItem(ref_url="https://example.com/1", title="bad", summary="bad", tags=["AI"], language="zh")
    ])
    result = await reviewer_node(state, registry)

    assert result["reviewed_items"][0].verdict == "discarded"
    assert len(result["cost_records"]) == 2
    assert result["cost_records"][0].ref_url == "https://example.com/1"
    assert sum(record.cost for record in result["cost_records"]) > 0
