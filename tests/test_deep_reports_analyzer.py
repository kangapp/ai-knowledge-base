import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock

from src.deep_reports.models import DeepReportCandidate, DeepReportOutput, RepoFile, SourcePackage

REPO_ROOT = Path(__file__).resolve().parents[1]


def _candidate() -> DeepReportCandidate:
    return DeepReportCandidate(
        repo_url="https://github.com/acme/agent-tool",
        repo_name="acme/agent-tool",
        article_id=42,
        source_id="github_ai_devtools",
        source_detail="github trending",
        title="Agent Tool",
        summary="面向开发者的 AI agent 工具链",
        reviewer_score=88,
        candidate_score=90,
        trigger_reason="high practical value",
        metadata={"stars": 1200},
    )


def _source_package() -> SourcePackage:
    return SourcePackage(
        repo_url="https://github.com/acme/agent-tool",
        repo_name="acme/agent-tool",
        commit_sha="abc123",
        readme_excerpt="AI agent tool for coding workflow",
        tech_stack={"languages": ["Python"], "frameworks": ["FastAPI"]},
        file_tree_summary="src/main.py\nsrc/agents/planner.py",
        entry_files=["src/main.py"],
        key_files=[
            RepoFile(
                path="src/main.py",
                size=100,
                content="from fastapi import FastAPI",
                reason="入口文件",
            )
        ],
        evidence=[
            {"path": "src/main.py", "reason": "入口文件"},
            {"path": "src/agents/planner.py", "reason": "核心 agent 调度"},
        ],
    )


def _valid_output_json() -> str:
    return """
    {
      "title": "acme/agent-tool 源码深度报告",
      "summary": "该项目围绕开发者工作流提供 AI agent 编排能力。",
      "tech_stack": ["Python", "FastAPI"],
      "architecture": {
        "pattern": "分层服务",
        "components": ["API 层", "Agent 编排层"]
      },
      "data_flow": ["请求进入 API", "进入 agent 编排", "返回结果"],
      "use_cases": ["代码助手集成", "工作流自动化"],
      "strengths": ["结构清晰", "入口明确"],
      "limitations": ["缺少更完整部署说明"],
      "actionable_takeaways": ["可先从 src/main.py 阅读入口"],
      "source_evidence": [
        {"path": "src/main.py", "reason": "入口文件"},
        {"path": "src/agents/planner.py", "reason": "核心 agent 调度"}
      ]
    }
    """


def _valid_output_payload() -> dict:
    return json.loads(_valid_output_json())


def _response(content: str, prompt_tokens: int = 1000, completion_tokens: int = 500):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class _FakeBudget:
    def __init__(self):
        self.calls = []

    def add_cost(self, provider: str, cost: float) -> None:
        self.calls.append((provider, cost))


class _FakeHealth:
    def __init__(self):
        self.success_calls = []
        self.failure_calls = []

    def record_success(self, provider: str, latency_ms: int) -> None:
        self.success_calls.append((provider, latency_ms))

    def record_failure(self, provider: str, error: str) -> None:
        self.failure_calls.append((provider, error))


class _FakeRegistry:
    def __init__(self, *, supports_json_mode: bool, responses):
        self._supports_json_mode = supports_json_mode
        self._responses = list(responses)
        self.last_kwargs = None
        self.calls = []
        self.budget = _FakeBudget()
        self.health = _FakeHealth()

    def get_prompt_path(self, agent_name: str) -> str:
        assert agent_name == "deep_report"
        return "prompts/deep_report.md"

    def get_client(self, agent_name: str):
        assert agent_name == "deep_report"
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=AsyncMock(side_effect=self._create))
            )
        )
        return client, "minimax", "MiniMax-M3", {"temperature": 0.2, "max_tokens": 4096}

    async def _create(self, **kwargs):
        self.last_kwargs = kwargs
        self.calls.append(kwargs)
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def supports_json_mode(self, provider_name: str) -> bool:
        assert provider_name == "minimax"
        return self._supports_json_mode

    def calc_cost(self, provider: str, model_id: str, tokens_in: int, tokens_out: int) -> float:
        assert provider == "minimax"
        assert model_id == "MiniMax-M3"
        return (tokens_in + tokens_out) / 1_000_000


def test_parse_deep_report_output_accepts_fenced_json():
    from src.deep_reports.analyzer import parse_deep_report_output

    output = parse_deep_report_output(f"```json\n{_valid_output_json()}\n```")

    assert isinstance(output, DeepReportOutput)
    assert output.title == "acme/agent-tool 源码深度报告"
    assert output.source_evidence[0].path == "src/main.py"
    assert output.architecture.pattern == "分层服务"


def test_parse_deep_report_output_accepts_noisy_json():
    from src.deep_reports.analyzer import parse_deep_report_output

    raw = f"<think>先分析</think>\n{_valid_output_json()}\n补充说明不要解析"
    output = parse_deep_report_output(raw)

    assert output.summary.startswith("该项目围绕开发者工作流")


def test_parse_deep_report_output_rejects_missing_required_fields():
    from src.deep_reports.analyzer import parse_deep_report_output

    with pytest.raises(Exception):
        parse_deep_report_output('{"title": "only title"}')


@pytest.mark.parametrize(
    "payload",
    [
        {
            "title": "x",
            "summary": "y",
            "tech_stack": ["Python"],
            "data_flow": ["a"],
            "use_cases": ["b"],
            "strengths": ["c"],
            "limitations": ["d"],
            "actionable_takeaways": ["e"],
            "source_evidence": [{"path": "src/main.py", "reason": "入口"}],
        },
        {
            "title": "x",
            "summary": "y",
            "tech_stack": ["Python"],
            "architecture": {"pattern": "分层", "components": ["API"]},
            "use_cases": ["b"],
            "strengths": ["c"],
            "limitations": ["d"],
            "actionable_takeaways": ["e"],
            "source_evidence": [{"path": "src/main.py", "reason": "入口"}],
        },
        {
            "title": "x",
            "summary": "y",
            "tech_stack": ["Python"],
            "architecture": {"pattern": "分层", "components": ["API"]},
            "data_flow": ["a"],
            "use_cases": ["b"],
            "strengths": ["c"],
            "limitations": ["d"],
            "actionable_takeaways": ["e"],
        },
        {
            "title": "x",
            "summary": "y",
            "tech_stack": ["Python"],
            "architecture": {"pattern": "分层", "components": ["API"]},
            "data_flow": ["a"],
            "use_cases": ["b"],
            "strengths": ["c"],
            "limitations": ["d"],
            "actionable_takeaways": ["e"],
            "source_evidence": [{}],
        },
    ],
)
def test_parse_deep_report_output_rejects_missing_nested_required_fields(payload):
    from src.deep_reports.analyzer import parse_deep_report_output

    with pytest.raises(Exception):
        parse_deep_report_output(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.update({"unexpected": "value"}),
        lambda payload: payload["architecture"].update({"extra": "value"}),
        lambda payload: payload["source_evidence"][0].update({"extra": "value"}),
    ],
)
def test_parse_deep_report_output_rejects_extra_fields(mutator):
    from src.deep_reports.analyzer import parse_deep_report_output

    payload = _valid_output_payload()
    mutator(payload)

    with pytest.raises(Exception):
        parse_deep_report_output(json.dumps(payload, ensure_ascii=False))


def test_prompt_template_contains_required_placeholders():
    prompt_path = REPO_ROOT / "prompts" / "deep_report.md"
    template = prompt_path.read_text(encoding="utf-8")

    rendered = template.format(
        repo_name="acme/agent-tool",
        repo_url="https://github.com/acme/agent-tool",
        candidate_context="候选上下文",
        source_package="源码摘要",
        schema='{"title":"string","architecture":{"pattern":"string","components":["string"]},"source_evidence":[{"path":"string","reason":"string"}]}',
    )

    assert "acme/agent-tool" in rendered
    assert "候选上下文" in rendered
    assert "源码摘要" in rendered
    assert '"components":["string"]' in rendered
    assert '"reason":"string"' in rendered


@pytest.mark.asyncio
async def test_analyze_deep_report_success_uses_json_mode_when_supported():
    from src.deep_reports.analyzer import analyze_deep_report

    registry = _FakeRegistry(
        supports_json_mode=True,
        responses=[_response(_valid_output_json())],
    )

    report, cost_records = await analyze_deep_report(_candidate(), _source_package(), registry)

    assert report is not None
    assert report.title == "acme/agent-tool 源码深度报告"
    assert len(cost_records) == 1
    assert cost_records[0].status == "success"
    assert cost_records[0].ref_url == "https://github.com/acme/agent-tool"
    assert cost_records[0].source == "github"
    assert cost_records[0].source_detail == "github trending"
    assert cost_records[0].source_id == "github_ai_devtools"
    assert cost_records[0].prompt_name == "deep_report"
    assert cost_records[0].agent == "deep_report"
    assert registry.last_kwargs["response_format"] == {"type": "json_object"}
    assert registry.health.success_calls == [("minimax", 0)]
    assert registry.health.failure_calls == []


@pytest.mark.asyncio
async def test_analyze_deep_report_success_skips_json_mode_when_unsupported():
    from src.deep_reports.analyzer import analyze_deep_report

    registry = _FakeRegistry(
        supports_json_mode=False,
        responses=[_response(_valid_output_json())],
    )

    report, cost_records = await analyze_deep_report(_candidate(), _source_package(), registry)

    assert report is not None
    assert len(cost_records) == 1
    assert "response_format" not in registry.last_kwargs


@pytest.mark.asyncio
async def test_analyze_deep_report_parse_failed_returns_attempt_cost_records():
    from src.deep_reports.analyzer import analyze_deep_report

    registry = _FakeRegistry(
        supports_json_mode=True,
        responses=[_response("not json"), _response("still not json")],
    )

    report, cost_records = await analyze_deep_report(_candidate(), _source_package(), registry)

    assert report is None
    assert len(cost_records) == 2
    assert [item.status for item in cost_records] == ["parse_failed", "parse_failed"]
    assert cost_records[0].attempt_no == 1
    assert cost_records[1].attempt_no == 2
    assert all(item.error for item in cost_records)
    assert len(registry.health.failure_calls) == 2
    assert len(registry.budget.calls) == 2


@pytest.mark.asyncio
async def test_analyze_deep_report_retries_after_parse_failure_and_keeps_both_costs():
    from src.deep_reports.analyzer import analyze_deep_report

    registry = _FakeRegistry(
        supports_json_mode=True,
        responses=[
            _response("not json", prompt_tokens=900, completion_tokens=300),
            _response(_valid_output_json(), prompt_tokens=1200, completion_tokens=600),
        ],
    )

    report, cost_records = await analyze_deep_report(_candidate(), _source_package(), registry)

    assert report is not None
    assert len(cost_records) == 2
    assert [item.status for item in cost_records] == ["parse_failed", "success"]
    assert cost_records[0].tokens_in == 900
    assert cost_records[0].tokens_out == 300
    assert cost_records[0].cost > 0
    assert cost_records[1].tokens_in == 1200
    assert cost_records[1].tokens_out == 600
    assert cost_records[1].cost > 0
    assert len(registry.budget.calls) == 2
    assert registry.health.success_calls == [("minimax", 0), ("minimax", 0)]
    assert len(registry.health.failure_calls) == 1


@pytest.mark.asyncio
async def test_analyze_deep_report_uses_validation_feedback_for_repair_attempt():
    from src.deep_reports.analyzer import analyze_deep_report

    invalid_output = '{"title":"缺少其余必填字段"}'
    registry = _FakeRegistry(
        supports_json_mode=False,
        responses=[
            _response(invalid_output),
            _response(_valid_output_json()),
        ],
    )

    report, cost_records = await analyze_deep_report(_candidate(), _source_package(), registry)

    assert report is not None
    assert len(cost_records) == 2
    repair_messages = registry.calls[1]["messages"]
    assert "修复" in repair_messages[0]["content"]
    assert invalid_output in repair_messages[1]["content"]
    assert "Deep report output does not match schema" in repair_messages[1]["content"]
    assert "源码摘要包" not in repair_messages[1]["content"]


@pytest.mark.asyncio
async def test_analyze_deep_report_request_failed_returns_attempt_cost_records():
    from src.deep_reports.analyzer import analyze_deep_report

    registry = _FakeRegistry(
        supports_json_mode=True,
        responses=[RuntimeError("upstream timeout"), RuntimeError("upstream timeout")],
    )

    report, cost_records = await analyze_deep_report(_candidate(), _source_package(), registry)

    assert report is None
    assert len(cost_records) == 2
    assert [item.status for item in cost_records] == ["request_failed", "request_failed"]
    assert cost_records[0].attempt_no == 1
    assert cost_records[1].attempt_no == 2
    assert all(item.cost == 0.0 for item in cost_records)
    assert len(registry.health.failure_calls) == 2
