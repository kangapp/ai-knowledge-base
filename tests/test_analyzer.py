import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.graph.state import RawItem, AnalyzedItem
from tests.fixtures.llm_responses import GITHUB_ANALYZE_RESPONSE

@pytest.mark.asyncio
async def test_parse_and_validate_success():
    from src.graph.analyzers.base import parse_and_validate
    raw = json.dumps({"title": "Test", "summary": "A test", "tags": ["AI"], "language": "zh"})
    result = parse_and_validate(raw, ref_url="https://example.com/test")
    assert result.title == "Test"
    assert result.ref_url == "https://example.com/test"
    assert result.tags == ["AI"]
    assert result.retry_count == 0

def test_parse_markdown_wrapped_json():
    from src.graph.analyzers.base import parse_and_validate
    raw = '```json\n{"title": "T", "summary": "S", "tags": ["X"], "language": "en"}\n```'
    result = parse_and_validate(raw, ref_url="https://example.com/t")
    assert result.title == "T"

def test_invalid_output_raises():
    from src.graph.analyzers.base import parse_and_validate
    with pytest.raises(Exception):
        parse_and_validate('not json at all') 


def test_parse_and_validate_propagates_source_context():
    from src.graph.analyzers.base import parse_and_validate

    raw_item = RawItem(
        url="https://github.com/Lum1104/Understand-Anything",
        title="Understand-Anything",
        source="github",
        source_detail="Lum1104/Understand-Anything",
        raw_metadata={
            "source_id": "github_ai_devtools",
            "stars": 49166,
            "topics": ["knowledge-graph", "codex"],
        },
    )
    raw = json.dumps({"title": "T", "summary": "S", "tags": ["AI"], "language": "zh"})

    result = parse_and_validate(raw, ref_url=raw_item.url, source_item=raw_item)

    assert result.source == "github"
    assert result.source_detail == "Lum1104/Understand-Anything"
    assert result.source_id == "github_ai_devtools"
    assert result.metadata["stars"] == 49166


@pytest.mark.asyncio
async def test_analyze_items_records_cost_when_parse_fails():
    from src.core.config import (
        AgentConfig,
        AgentsConfig,
        BudgetConfig,
        LLMConfig,
        ModelBinding,
        ModelInfo,
        ModelRef,
        ProviderConfig,
    )
    from src.core.llm_client import LLMRegistry
    from src.graph.analyzers.base import analyze_items

    llm_cfg = LLMConfig(providers={
        "minimax": ProviderConfig(
            base_url="https://api.minimax.chat/v1",
            api_key="sk-test",
            models=[ModelInfo(id="MiniMax-M3", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)],
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "github_analyzer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
                params={"temperature": 0.3, "max_tokens": 2048},
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

    items = [
        RawItem(
            url="https://github.com/org/repo",
            title="repo",
            source="github",
            raw_metadata={"source_id": "github_trending"},
        )
    ]
    analyzed, costs = await analyze_items(items, "github_analyzer", registry, "标题: {title}\n{schema}")

    assert analyzed == []
    assert len(costs) == 2
    assert costs[0].ref_url == "https://github.com/org/repo"
    assert costs[0].source_id == "github_trending"
    assert sum(record.cost for record in costs) > 0
