import json
import pytest
from pathlib import Path
from src.graph.analyzers.base import parse_and_validate
from src.graph.state import AnalyzedItem

PROMPT_FILES = ["github_analyzer.md", "rss_analyzer.md", "feishu_analyzer.md", "arxiv_analyzer.md"]


@pytest.mark.parametrize("prompt_file", PROMPT_FILES)
def test_prompt_has_schema_instruction(prompt_file):
    content = (Path(__file__).parent.parent / "prompts" / prompt_file).read_text()
    assert "json" in content.lower()
    assert "schema" in content.lower()  # 检查 schema 占位符存在


@pytest.mark.parametrize("seed", json.loads((Path(__file__).parent / "fixtures" / "seed_articles.json").read_text()))
def test_seed_article_valid_structure(seed):
    assert "url" in seed
    assert "title" in seed
    assert "source" in seed


def test_parse_and_validate_all_seeds():
    """验证 parse_and_validate 函数对各种 LLM 输出格式的容错能力"""
    # 正常 JSON
    result = parse_and_validate('{"title": "T", "summary": "S", "tags": ["AI"], "language": "zh"}')
    assert isinstance(result, AnalyzedItem)
    # markdown 包裹
    result2 = parse_and_validate('```json\n{"title": "T2", "summary": "S2", "tags": ["LLM"], "language": "en"}\n```')
    assert isinstance(result2, AnalyzedItem)
    # 缺少字段抛异常
    with pytest.raises(Exception):
        parse_and_validate('{"title": "T"}')  # 缺少 summary