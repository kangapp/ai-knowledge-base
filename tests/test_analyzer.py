import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.graph.state import RawItem, AnalyzedItem
from tests.fixtures.llm_responses import GITHUB_ANALYZE_RESPONSE

@pytest.mark.asyncio
async def test_parse_and_validate_success():
    from src.graph.analyzers.base import parse_and_validate
    raw = json.dumps({"title": "Test", "summary": "A test", "tags": ["AI"], "language": "zh", "relevance_score": 75})
    result = parse_and_validate(raw, ref_url="https://example.com/test")
    assert result.title == "Test"
    assert result.ref_url == "https://example.com/test"
    assert result.tags == ["AI"]
    assert result.relevance_score == 75
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