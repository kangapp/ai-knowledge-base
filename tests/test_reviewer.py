# tests/test_reviewer.py
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.graph.state import PipelineState, AnalyzedItem, ReviewedItem
from src.graph.reviewer import reviewer_node, parse_reviewer_output, build_reviewer_user_prompt
from tests.fixtures.llm_responses import REVIEWER_RESPONSE

def test_parse_reviewer_output():
    raw = json.dumps({
        "total_score": 88,
        "dimensions": {
            "ai_relevance": {"score": 24, "reason": "核心 LLM 推理框架"},
            "engineering_relevance": {"score": 28, "reason": "面向开发者和推理基础设施"},
            "content_depth": {"score": 24, "reason": "有技术细节"},
            "info_density": {"score": 12, "reason": "有新信息"},
        },
        "verdict": "approved",
        "retry_feedback": None
    })
    result = parse_reviewer_output(raw)
    assert isinstance(result, ReviewedItem)
    assert result.total_score == 88
    assert result.verdict == "approved"
    assert result.dimensions["ai_relevance"]["score"] == 24
    assert result.dimensions["engineering_relevance"]["score"] == 28
    assert result.retry_feedback is None

def test_parse_reviewer_output_retry():
    raw = json.dumps({
        "total_score": 62,
        "dimensions": {
            "ai_relevance": {"score": 20, "reason": "AI 基础设施"},
            "engineering_relevance": {"score": 19, "reason": "有一定工程线索"},
            "content_depth": {"score": 13, "reason": "有部分细节"},
            "info_density": {"score": 10, "reason": "有一定信息量"},
        },
        "verdict": "retry",
        "retry_feedback": {"suggestions": ["补充 AI 和工程相关度分析", "增加技术深度"]}
    })
    result = parse_reviewer_output(raw)
    assert result.verdict == "retry"
    assert result.retry_feedback["suggestions"] == ["补充 AI 和工程相关度分析", "增加技术深度"]

def test_parse_reviewer_output_markdown_wrapped():
    raw = '```json\n{"total_score": 30, "dimensions": {"ai_relevance": {"score": 5, "reason": "无关"}, "engineering_relevance": {"score": 12, "reason": "弱相关"}, "content_depth": {"score": 8, "reason": "简要"}, "info_density": {"score": 5, "reason": "重复"}}, "verdict": "discarded", "retry_feedback": null}\n```'
    result = parse_reviewer_output(raw)
    assert result.verdict == "discarded"


def test_parse_reviewer_output_extracts_first_json_object_with_trailing_text():
    raw = (
        "<think>需要先评分</think>\n"
        '{"total_score": 85, "dimensions": {"ai_relevance": {"score": 25, "reason": "核心"}, '
        '"engineering_relevance": {"score": 24, "reason": "工程实践"}, '
        '"content_depth": {"score": 24, "reason": "深入"}, '
        '"info_density": {"score": 12, "reason": "密集"}}, '
        '"verdict": "approved", "retry_feedback": null}\n'
        "```"
    )

    result = parse_reviewer_output(raw)

    assert result.total_score == 85
    assert result.verdict == "approved"


def test_parse_reviewer_output_normalizes_dimension_alias_and_score():
    raw = json.dumps({
        "total_score": 99,
        "dimensions": {
            "ai_relevance": {"score": 34, "reason": "AI 基础设施"},
            "engineering_relevance": {"score": 35, "reason": "工程实践"},
            "content_depth": {"score": 20, "reason": "有细节"},
            "information_density": {"score": 10, "reason": "有信息量"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw)

    assert result.total_score == 90
    assert set(result.dimensions) == {"ai_relevance", "engineering_relevance", "content_depth", "info_density"}
    assert result.dimensions["ai_relevance"]["score"] == 30
    assert result.dimensions["engineering_relevance"]["score"] == 30
    assert result.dimensions["info_density"]["score"] == 10
    assert result.verdict == "approved"
    assert result.retry_feedback is None


def test_parse_reviewer_output_discards_low_ai_relevance_even_when_model_approves():
    raw = json.dumps({
        "total_score": 85,
        "dimensions": {
            "ai_relevance": {"score": 15, "reason": "只泛泛提到 AI"},
            "engineering_relevance": {"score": 28, "reason": "工程相关"},
            "content_depth": {"score": 25, "reason": "有行业细节"},
            "info_density": {"score": 14, "reason": "信息密集"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw)

    assert result.total_score == 82
    assert result.verdict == "discarded"
    assert result.retry_feedback is None


def test_parse_reviewer_output_discards_ai_news_without_engineering_value():
    raw = json.dumps({
        "total_score": 72,
        "dimensions": {
            "ai_relevance": {"score": 26, "reason": "自主机器人应用新闻"},
            "engineering_relevance": {"score": 8, "reason": "没有编码、工程或基础设施细节"},
            "content_depth": {"score": 25, "reason": "有现场信息"},
            "info_density": {"score": 13, "reason": "信息密集"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw)

    assert result.verdict == "discarded"
    assert result.retry_feedback is None


def test_analyzed_item_accepts_review_context():
    item = AnalyzedItem(
        ref_url="https://github.com/Lum1104/Understand-Anything",
        title="Understand-Anything",
        summary="代码知识图谱工具",
        tags=["AI", "RAG", "Tool"],
        source="github",
        source_detail="Lum1104/Understand-Anything",
        source_id="github_ai_devtools",
        metadata={"stars": 49166, "forks": 4003, "language": "TypeScript"},
    )

    assert item.source == "github"
    assert item.source_id == "github_ai_devtools"
    assert item.metadata["stars"] == 49166


def test_github_reviewer_prompt_includes_repo_signals():
    item = AnalyzedItem(
        ref_url="https://github.com/Lum1104/Understand-Anything",
        title="Understand-Anything - 代码交互式知识图谱工具",
        summary="将任意代码库转化为可探索、可搜索、可提问的交互式知识图谱。",
        tags=["AI", "Agent", "RAG"],
        source="github",
        source_detail="Lum1104/Understand-Anything",
        source_id="github_ai_devtools",
        metadata={
            "stars": 49166,
            "forks": 4003,
            "language": "TypeScript",
            "topics": ["codebase-analysis", "knowledge-graph", "codex", "claude-code"],
        },
    )

    prompt = build_reviewer_user_prompt(item)

    assert "内容类型: github_repo" in prompt
    assert "source_id: github_ai_devtools" in prompt
    assert "stars: 49166" in prompt
    assert "topics: codebase-analysis, knowledge-graph, codex, claude-code" in prompt


def test_parse_github_review_approves_under_repo_policy():
    raw = json.dumps({
        "total_score": 70,
        "dimensions": {
            "ai_relevance": {"score": 30, "reason": "AI code knowledge graph tool"},
            "developer_utility": {"score": 18, "reason": "solves codebase understanding"},
            "project_signal": {"score": 14, "reason": "strong stars and topics"},
            "content_clarity": {"score": 8, "reason": "clear summary"},
        },
        "verdict": "discarded",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw, review_kind="github_repo")

    assert result.total_score == 70
    assert result.verdict == "approved"


def test_parse_data_infra_github_review_uses_data_infra_relevance():
    raw = json.dumps({
        "total_score": 77,
        "dimensions": {
            "data_infra_relevance": {"score": 27, "reason": "核心 analytics engineering 基础设施"},
            "developer_utility": {"score": 24, "reason": "核心 analytics engineering 工作流"},
            "project_signal": {"score": 18, "reason": "强社区信号"},
            "content_clarity": {"score": 8, "reason": "用途清楚"},
        },
        "verdict": "discarded",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(
        raw,
        review_kind="github_repo",
        source_id="github_data_infra",
    )

    assert result.total_score == 77
    assert "data_infra_relevance" in result.dimensions
    assert "ai_relevance" not in result.dimensions
    assert result.verdict == "approved"


def test_parse_data_infra_github_review_discards_low_infra_relevance():
    raw = json.dumps({
        "total_score": 73,
        "dimensions": {
            "data_infra_relevance": {"score": 21, "reason": "只是普通 SQL demo"},
            "developer_utility": {"score": 24, "reason": "有一定实用性"},
            "project_signal": {"score": 18, "reason": "强社区信号"},
            "content_clarity": {"score": 10, "reason": "用途清楚"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(
        raw,
        review_kind="github_repo",
        source_id="github_data_infra",
    )

    assert result.verdict == "discarded"


def test_parse_data_ai_github_review_still_requires_ai_relevance():
    raw = json.dumps({
        "total_score": 70,
        "dimensions": {
            "ai_relevance": {"score": 8, "reason": "纯数据工程基础设施"},
            "developer_utility": {"score": 28, "reason": "实用"},
            "project_signal": {"score": 20, "reason": "强社区信号"},
            "content_clarity": {"score": 14, "reason": "清楚"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(
        raw,
        review_kind="github_repo",
        source_id="github_data_ai",
    )

    assert result.verdict == "discarded"


def test_parse_github_review_retries_when_useful_but_thin():
    raw = json.dumps({
        "total_score": 58,
        "dimensions": {
            "ai_relevance": {"score": 28, "reason": "AI devtool"},
            "developer_utility": {"score": 14, "reason": "useful but thin"},
            "project_signal": {"score": 10, "reason": "some stars"},
            "content_clarity": {"score": 6, "reason": "basic summary"},
        },
        "verdict": "discarded",
        "retry_feedback": {"suggestions": ["补充技术细节"]},
    })

    result = parse_reviewer_output(raw, review_kind="github_repo")

    assert result.total_score == 58
    assert result.verdict == "retry"


def test_understand_anything_like_repo_is_approved_with_repo_policy():
    raw = json.dumps({
        "total_score": 72,
        "dimensions": {
            "ai_relevance": {
                "score": 31,
                "reason": "围绕代码知识图谱、AI 编程助手和 RAG 式问答，属于 AI 开发者工具",
            },
            "developer_utility": {
                "score": 20,
                "reason": "帮助开发者理解大型代码库结构、依赖和上下文",
            },
            "project_signal": {
                "score": 14,
                "reason": "高 star，topics 命中 codebase-analysis、knowledge-graph、codex、claude-code",
            },
            "content_clarity": {
                "score": 7,
                "reason": "摘要清楚说明功能，但技术实现细节有限",
            },
        },
        "verdict": "discarded",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw, review_kind="github_repo")

    assert result.verdict == "approved"
    assert result.total_score == 72


def test_article_policy_still_discards_shallow_article():
    raw = json.dumps({
        "total_score": 59,
        "dimensions": {
            "ai_relevance": {"score": 24, "reason": "AI related"},
            "engineering_relevance": {"score": 24, "reason": "engineering related"},
            "content_depth": {"score": 11, "reason": "thin"},
            "info_density": {"score": 7, "reason": "normal"},
        },
        "verdict": "approved",
        "retry_feedback": None,
    })

    result = parse_reviewer_output(raw)

    assert result.verdict == "discarded"


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
            models=[ModelInfo(id="MiniMax-M3", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)]
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
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
                "ai_relevance": {"score": 27, "reason": "核心 Agent 框架"},
                "engineering_relevance": {"score": 27, "reason": "面向开发者工程实践"},
                "content_depth": {"score": 22, "reason": "深度原创"},
                "info_density": {"score": 12, "reason": "新颖"},
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
    assert mock_client.chat.completions.create.call_args.kwargs["extra_body"] == {
        "thinking": {"type": "disabled"}
    }


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
            models=[ModelInfo(id="MiniMax-M3", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)],
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
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
    registry.health.record_failure = MagicMock()

    state = PipelineState(analyzed_items=[
        AnalyzedItem(ref_url="https://example.com/1", title="bad", summary="bad", tags=["AI"], language="zh")
    ])
    result = await reviewer_node(state, registry)

    assert result["reviewed_items"][0].verdict == "discarded"
    assert len(result["cost_records"]) == 2
    assert result["cost_records"][0].ref_url == "https://example.com/1"
    assert sum(record.cost for record in result["cost_records"]) > 0
    registry.health.record_failure.assert_not_called()


@pytest.mark.asyncio
async def test_reviewer_node_runs_with_limited_concurrency_and_keeps_order():
    from src.core.config import (
        AgentConfig, AgentsConfig, ProviderConfig, ModelInfo,
        ModelBinding, ModelRef, BudgetConfig, LLMConfig,
    )
    from src.core.llm_client import LLMRegistry

    llm_cfg = LLMConfig(providers={
        "minimax": ProviderConfig(
            base_url="https://api.minimax.chat/v1",
            api_key="sk-test",
            models=[ModelInfo(id="MiniMax-M3", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)],
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 1024, "concurrency": 2, "timeout_seconds": 1},
            )
        },
        budget=BudgetConfig(monthly=10.0),
    )
    registry = LLMRegistry(llm_cfg, agents_cfg)

    active = 0
    max_active = 0

    async def create_response(**kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        response = AsyncMock()
        response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "total_score": 88,
            "dimensions": {
                "ai_relevance": {"score": 27, "reason": "核心 Agent 框架"},
                "engineering_relevance": {"score": 27, "reason": "面向开发者工程实践"},
                "content_depth": {"score": 22, "reason": "深度原创"},
                "info_density": {"score": 12, "reason": "新颖"},
            },
            "verdict": "approved",
            "retry_feedback": None,
        })))]
        response.usage = MagicMock(prompt_tokens=300, completion_tokens=120)
        return response

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=create_response)
    registry._clients["minimax"] = mock_client

    state = PipelineState(analyzed_items=[
        AnalyzedItem(ref_url=f"https://example.com/{i}", title=f"item {i}", summary="s", tags=["AI"])
        for i in range(4)
    ])

    result = await reviewer_node(state, registry)

    assert [item.ref_url for item in result["reviewed_items"]] == [f"https://example.com/{i}" for i in range(4)]
    assert max_active == 2
    assert len(result["cost_records"]) == 4


@pytest.mark.asyncio
async def test_reviewer_node_times_out_slow_request_and_discards_item():
    from src.core.config import (
        AgentConfig, AgentsConfig, ProviderConfig, ModelInfo,
        ModelBinding, ModelRef, BudgetConfig, LLMConfig,
    )
    from src.core.llm_client import LLMRegistry

    llm_cfg = LLMConfig(providers={
        "minimax": ProviderConfig(
            base_url="https://api.minimax.chat/v1",
            api_key="sk-test",
            models=[ModelInfo(id="MiniMax-M3", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)],
        )
    })
    agents_cfg = AgentsConfig(
        agents={
            "reviewer": AgentConfig(
                model=ModelBinding(primary=ModelRef(provider="minimax", model="MiniMax-M3"), fallback=[]),
                params={"temperature": 0.0, "max_tokens": 1024, "concurrency": 1, "timeout_seconds": 0.01},
            )
        },
        budget=BudgetConfig(monthly=10.0),
    )
    registry = LLMRegistry(llm_cfg, agents_cfg)

    async def slow_response(**kwargs):
        await asyncio.sleep(0.05)
        response = AsyncMock()
        response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "total_score": 88,
            "dimensions": {
                "ai_relevance": {"score": 27, "reason": "核心 Agent 框架"},
                "engineering_relevance": {"score": 27, "reason": "面向开发者工程实践"},
                "content_depth": {"score": 22, "reason": "深度原创"},
                "info_density": {"score": 12, "reason": "新颖"},
            },
            "verdict": "approved",
            "retry_feedback": None,
        })))]
        response.usage = MagicMock(prompt_tokens=300, completion_tokens=120)
        return response

    mock_client = AsyncMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=slow_response)
    registry._clients["minimax"] = mock_client

    state = PipelineState(analyzed_items=[
        AnalyzedItem(ref_url="https://example.com/slow", title="slow", summary="s", tags=["AI"])
    ])

    result = await reviewer_node(state, registry)

    assert result["reviewed_items"][0].verdict == "discarded"
    assert len(result["cost_records"]) == 2
    assert {record.status for record in result["cost_records"]} == {"request_failed"}
    assert "TimeoutError" in result["cost_records"][0].error
