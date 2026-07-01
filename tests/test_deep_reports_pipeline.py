import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src import main
from src.core.config import SourceConfig, SourcesConfig
from src.core.database import Database
from src.db.operations import save_deep_report
from src.deep_reports.models import (
    DeepReportCandidate,
    DeepReportOutput,
    DeepReportSelection,
    DeepReportStageResult,
    RepoFile,
    RepoInspection,
)
from src.graph.state import AnalyzedItem, CostRecord, RawItem, ReviewedItem

_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def _init_db(tmp_path) -> Database:
    db = Database(tmp_path / "deep_reports_pipeline.db", migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()
    await db.execute(
        "INSERT INTO pipeline_runs (id, started_at, status, trigger) VALUES (?, datetime('now', '+8 hours'), ?, ?)",
        ("run_1", "running", "test"),
    )
    await db.execute(
        "INSERT INTO articles (id, title, url, source, collected_at) VALUES (?, ?, ?, ?, ?)",
        (42, "Dev Agent", "https://github.com/acme/dev-agent", "github", "2026-06-09T10:00:00+08:00"),
    )
    await db.commit()
    return db


def _raw(
    url: str,
    *,
    source: str = "github",
    source_id: str = "github_ai_devtools",
    source_detail: str = "github trending",
    title: str = "Dev Agent",
    description: str = "AI coding agent CLI for developer workflow automation",
) -> RawItem:
    return RawItem(
        url=url,
        title=title,
        description=description,
        source=source,
        source_detail=source_detail,
        collected_at="2026-06-09T10:00:00+08:00",
        raw_metadata={
            "source_id": source_id,
            "stars": 2400,
            "topics": ["agent", "developer-tools"],
        },
    )


def _analyzed(url: str, *, source: str = "github", source_id: str = "github_ai_devtools") -> AnalyzedItem:
    return AnalyzedItem(
        ref_url=url,
        title="Dev Agent",
        summary="实用的 AI developer tool，支持 CLI workflow automation",
        tags=["AI", "Agent", "CLI"],
        source=source,
        source_detail="github trending",
        source_id=source_id,
        project_type="coding_tool",
    )


def _reviewed(url: str, *, verdict: str = "approved", score: int = 88) -> ReviewedItem:
    return ReviewedItem(
        ref_url=url,
        total_score=score,
        dimensions={
            "ai_relevance": {"score": 32},
            "developer_utility": {"score": 26},
        },
        verdict=verdict,
    )


def _inspection(repo_url: str = "https://github.com/acme/dev-agent", repo_name: str = "acme/dev-agent") -> RepoInspection:
    return RepoInspection(
        repo_url=repo_url,
        repo_name=repo_name,
        commit_sha="abc123",
        readme="README overview",
        manifests={"pyproject.toml": "[project]\ndependencies = ['fastapi', 'openai']"},
        file_tree=["README.md", "pyproject.toml", "src/main.py"],
        entry_files=["src/main.py"],
        key_files=[RepoFile(path="src/main.py", size=120, content="print('x')", reason="应用入口")],
    )


def _report() -> DeepReportOutput:
    return DeepReportOutput.model_validate({
        "title": "Dev Agent Deep Report",
        "summary": "一个聚焦开发者工作流的 AI Agent 工具。",
        "tech_stack": ["Python", "FastAPI", "OpenAI"],
        "use_cases": ["代码理解", "工作流自动化"],
        "decision": {
            "recommendation": "适合需要开发工作流自动化的团队。",
            "reasons": ["入口清晰", "模块边界明确"],
            "best_for": ["需要仓库级上下文的开发者"],
            "not_for": ["要求完全离线运行的团队"],
        },
        "architecture": {
            "pattern": "pipeline",
            "summary": "入口接收任务，Agent 编排工具并输出结果。",
            "nodes": [
                {"id": "input", "label": "Input", "role": "接收任务", "group": "interface"},
                {"id": "agent", "label": "Agent", "role": "编排任务", "group": "core"},
                {"id": "tools", "label": "Tools", "role": "执行工具", "group": "core"},
                {"id": "output", "label": "Output", "role": "返回结果", "group": "interface"},
            ],
            "edges": [
                {"source": "input", "target": "agent", "label": "任务"},
                {"source": "agent", "target": "tools", "label": "调用"},
                {"source": "tools", "target": "output", "label": "结果"},
            ],
        },
        "quick_start": {
            "prerequisites": ["Python 3.12", "模型 API Key"],
            "steps": [
                {"id": "install", "title": "安装", "description": "安装依赖"},
                {"id": "config", "title": "配置", "description": "设置模型密钥"},
                {"id": "run", "title": "启动", "description": "运行 CLI"},
            ],
            "expected_result": "CLI 返回代码分析结果。",
        },
        "deployment": {
            "prerequisites": ["可运行 Python 的主机"],
            "steps": [
                {"id": "prepare", "title": "准备环境", "description": "安装运行时"},
                {"id": "deploy", "title": "部署", "description": "配置服务"},
                {"id": "health", "title": "检查", "description": "验证服务可用"},
            ],
            "operations": ["监控模型调用失败"],
        },
        "core_modules": [
            {"name": "Agent", "responsibility": "编排工具", "depends_on": ["Tools"]},
        ],
        "runtime_data_flow": [
            {"id": "request", "title": "请求", "description": "用户提交任务"},
            {"id": "plan", "title": "规划", "description": "Agent 拆分任务"},
            {"id": "result", "title": "结果", "description": "返回执行结果"},
        ],
        "strengths": ["结构清晰", "实用性强"],
        "limitations": ["依赖外部模型"],
        "actionable_takeaways": ["先用 CLI 验证核心工作流"],
        "source_evidence": [
            {"path": "src/main.py", "reason": "应用入口"},
            {"path": "pyproject.toml", "reason": "声明主要依赖"},
        ],
    })


def _cost(
    *,
    status: str,
    cost: float,
    tokens_in: int,
    tokens_out: int,
    attempt_no: int,
    error: str = "",
    ref_url: str = "https://github.com/acme/dev-agent",
) -> CostRecord:
    return CostRecord(
        agent="deep_report",
        provider="minimax",
        model="MiniMax-M3",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        ref_url=ref_url,
        source="github",
        source_detail="github trending",
        source_id="github_ai_devtools",
        status=status,
        error=error,
        latency_ms=1000 + attempt_no,
        attempt_no=attempt_no,
        prompt_name="deep_report",
        prompt_version="current",
    )


@pytest.mark.asyncio
async def test_deep_report_stage_skips_when_no_candidate(tmp_path):
    db = await _init_db(tmp_path)
    try:
        raw = _raw("https://example.com/post", source="rss", source_id="rss_36kr")
        analyzed = _analyzed(raw.url, source="rss", source_id="rss_36kr")
        reviewed = _reviewed(raw.url)

        from src.deep_reports.service import run_deep_report_stage

        result = await run_deep_report_stage(
            db=db,
            registry=None,
            run_id="run_1",
            raw_items=[raw],
            analyzed_items=[analyzed],
            reviewed_items=[reviewed],
            clone_and_inspect_fn=lambda *_args, **_kwargs: pytest.fail("should not clone"),
            analyze_fn=None,
        )

        assert result == DeepReportStageResult(status="skipped", message="no candidate")
        rows = await db.fetch_all("SELECT * FROM deep_reports")
        assert rows == []
        events = await db.fetch_all(
            "SELECT event, status, payload FROM pipeline_events ORDER BY id"
        )
        assert [(row["event"], row["status"]) for row in events] == [
            ("deep.selector_start", "running"),
            ("deep.selector_skipped", "skipped"),
        ]
        payload = json.loads(events[-1]["payload"])
        assert payload["reviewed_total"] == 1
        assert payload["eligible"] == 0
        assert payload["rejected"]["not_github"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_deep_report_stage_selector_error_returns_failed_without_raise(tmp_path, monkeypatch):
    db = await _init_db(tmp_path)
    try:
        raw = _raw("https://github.com/acme/dev-agent")
        analyzed = _analyzed(raw.url)
        reviewed = _reviewed(raw.url)

        async def failing_selector(*_args, **_kwargs):
            raise RuntimeError("selector exploded")

        monkeypatch.setattr("src.deep_reports.service.select_deep_report_candidate", failing_selector)

        from src.deep_reports.service import run_deep_report_stage

        result = await run_deep_report_stage(
            db=db,
            registry="registry",
            run_id="run_1",
            raw_items=[raw],
            analyzed_items=[analyzed],
            reviewed_items=[reviewed],
        )

        assert result.status == "failed"
        assert result.message == "selector exploded"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_deep_report_stage_clone_failure_persists_failed_row_and_event(tmp_path):
    db = await _init_db(tmp_path)
    try:
        raw = _raw("https://github.com/acme/dev-agent")
        analyzed = _analyzed(raw.url)
        reviewed = _reviewed(raw.url)

        def failing_clone(_repo_url: str, _repo_name: str):
            raise RuntimeError("clone exploded")

        from src.deep_reports.service import run_deep_report_stage

        result = await run_deep_report_stage(
            db=db,
            registry=object(),
            run_id="run_1",
            raw_items=[raw],
            analyzed_items=[analyzed],
            reviewed_items=[reviewed],
            article_ids={raw.url: 42},
            clone_and_inspect_fn=failing_clone,
        )

        assert result.status == "failed"
        assert result.repo_url == "https://github.com/acme/dev-agent"
        row = await db.fetch_one("SELECT * FROM deep_reports WHERE repo_url = ?", (result.repo_url,))
        assert row["status"] == "failed"
        assert row["article_id"] == 42
        assert row["error"] == "clone exploded"
        events = await db.fetch_all(
            "SELECT event, status, message, payload FROM pipeline_events ORDER BY id"
        )
        assert [(item["event"], item["status"]) for item in events] == [
            ("deep.selector_start", "running"),
            ("deep.selector_done", "done"),
            ("deep.clone_start", "running"),
            ("deep.failed", "failed"),
        ]
        selector_payload = json.loads(events[1]["payload"])
        assert selector_payload["candidate_score"] == 90
        assert selector_payload["project_type"] == "coding_tool"
        assert selector_payload["diagnostics"]["eligible"] == 1
        assert events[-1]["message"] == "clone exploded"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_deep_report_stage_success_saves_costs_report_and_uses_to_thread(tmp_path, monkeypatch):
    db = await _init_db(tmp_path)
    try:
        raw = _raw("https://github.com/acme/dev-agent/")
        analyzed = _analyzed(raw.url)
        reviewed = _reviewed(raw.url)
        to_thread_calls = []

        async def fake_to_thread(func, *args, **kwargs):
            to_thread_calls.append((func, args, kwargs))
            return func(*args, **kwargs)

        async def fake_analyze(candidate, source_package, registry):
            assert registry == "registry"
            assert candidate.article_id == 42
            assert source_package.tech_stack["languages"] == ["Python"]
            return _report(), [
                _cost(status="parse_failed", cost=0.002, tokens_in=100, tokens_out=30, attempt_no=1, error="bad json"),
                _cost(status="success", cost=0.003, tokens_in=120, tokens_out=40, attempt_no=2),
            ]

        monkeypatch.setattr("src.deep_reports.service.asyncio.to_thread", fake_to_thread)

        from src.deep_reports.service import run_deep_report_stage

        result = await run_deep_report_stage(
            db=db,
            registry="registry",
            run_id="run_1",
            raw_items=[raw],
            analyzed_items=[analyzed],
            reviewed_items=[reviewed],
            article_ids={"https://github.com/acme/dev-agent": 42},
            clone_and_inspect_fn=_inspection,
            analyze_fn=fake_analyze,
        )

        assert result.status == "completed"
        assert result.report_id is not None
        assert result.repo_url == "https://github.com/acme/dev-agent"
        assert len(to_thread_calls) == 1
        assert to_thread_calls[0][1] == ("https://github.com/acme/dev-agent", "acme/dev-agent")

        report_row = await db.fetch_one("SELECT * FROM deep_reports WHERE id = ?", (result.report_id,))
        assert report_row["status"] == "completed"
        assert report_row["report_version"] == 2
        assert report_row["article_id"] == 42
        assert report_row["commit_sha"] == "abc123"
        report_json = json.loads(report_row["report_json"])
        assert report_json["title"] == "Dev Agent Deep Report"
        assert report_json["decision"]["recommendation"]
        assert json.loads(report_row["evidence_json"]) == [
            {"path": "src/main.py", "reason": "应用入口"},
            {"path": "pyproject.toml", "reason": "声明主要依赖"},
        ]
        assert json.loads(report_row["tech_stack_json"]) == {
            "languages": ["Python"],
            "frameworks": ["FastAPI"],
            "dependencies": ["OpenAI"],
        }
        assert report_row["analysis_cost"] == pytest.approx(0.005)
        assert report_row["analysis_tokens"] == 290
        assert "## 概述" in report_row["report_markdown"]
        assert "## 采用结论" in report_row["report_markdown"]
        assert "## 技术栈" in report_row["report_markdown"]
        assert "## 架构" in report_row["report_markdown"]
        assert "## 快速上手" in report_row["report_markdown"]
        assert "## 部署运行" in report_row["report_markdown"]
        assert "## 运行时数据流" in report_row["report_markdown"]
        assert "## 场景" in report_row["report_markdown"]
        assert "## 优势" in report_row["report_markdown"]
        assert "## 局限" in report_row["report_markdown"]
        assert "## 建议" in report_row["report_markdown"]
        assert "## 证据" in report_row["report_markdown"]

        cost_rows = await db.fetch_all(
            "SELECT status, error, cost, tokens_in, tokens_out, attempt_no FROM cost_logs ORDER BY id"
        )
        assert [dict(row) for row in cost_rows] == [
            {
                "status": "parse_failed",
                "error": "bad json",
                "cost": 0.002,
                "tokens_in": 100,
                "tokens_out": 30,
                "attempt_no": 1,
            },
            {
                "status": "success",
                "error": "",
                "cost": 0.003,
                "tokens_in": 120,
                "tokens_out": 40,
                "attempt_no": 2,
            },
        ]

        events = await db.fetch_all("SELECT event, status, cost, tokens, payload FROM pipeline_events ORDER BY id")
        assert [(row["event"], row["status"]) for row in events] == [
            ("deep.selector_start", "running"),
            ("deep.selector_done", "done"),
            ("deep.clone_start", "running"),
            ("deep.scan_done", "done"),
            ("deep.analyze_start", "running"),
            ("deep.persist_done", "completed"),
        ]
        persist_event = dict(events[-1])
        assert persist_event["cost"] == pytest.approx(0.005)
        assert persist_event["tokens"] == 290
        assert json.loads(persist_event["payload"]) == {
            "report_id": result.report_id,
            "candidate_score": report_row["candidate_score"],
            "report_version": 2,
        }
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_deep_report_stage_persist_done_event_failure_keeps_completed_report(tmp_path, monkeypatch):
    db = await _init_db(tmp_path)
    try:
        raw = _raw("https://github.com/acme/dev-agent")
        analyzed = _analyzed(raw.url)
        reviewed = _reviewed(raw.url)
        original_record_event = main.record_pipeline_event

        async def flaky_record_event(*args, **kwargs):
            if kwargs.get("event") == "deep.persist_done":
                raise RuntimeError("persist_done event exploded")
            return await original_record_event(*args, **kwargs)

        monkeypatch.setattr("src.deep_reports.service.record_pipeline_event", flaky_record_event)

        async def fake_analyze(_candidate, _source_package, _registry):
            return _report(), [_cost(status="success", cost=0.003, tokens_in=120, tokens_out=40, attempt_no=1)]

        from src.deep_reports.service import run_deep_report_stage

        result = await run_deep_report_stage(
            db=db,
            registry="registry",
            run_id="run_1",
            raw_items=[raw],
            analyzed_items=[analyzed],
            reviewed_items=[reviewed],
            article_ids={raw.url: 42},
            clone_and_inspect_fn=_inspection,
            analyze_fn=fake_analyze,
        )

        row = await db.fetch_one("SELECT status, error, report_json, report_markdown FROM deep_reports WHERE repo_url = ?", (raw.url,))
        assert result.status == "completed"
        assert row["status"] == "completed"
        assert row["error"] == ""
        assert json.loads(row["report_json"])["title"] == "Dev Agent Deep Report"
        assert "## 采用结论" in row["report_markdown"]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_deep_report_stage_analyze_none_still_saves_costs_and_failed_report(tmp_path):
    db = await _init_db(tmp_path)
    try:
        raw = _raw("https://github.com/acme/dev-agent")
        analyzed = _analyzed(raw.url)
        reviewed = _reviewed(raw.url)

        async def fake_analyze(_candidate, _source_package, _registry):
            return None, [
                _cost(status="request_failed", cost=0.001, tokens_in=90, tokens_out=0, attempt_no=1, error="timeout"),
                _cost(status="parse_failed", cost=0.002, tokens_in=110, tokens_out=20, attempt_no=2),
            ]

        from src.deep_reports.service import run_deep_report_stage

        result = await run_deep_report_stage(
            db=db,
            registry="registry",
            run_id="run_1",
            raw_items=[raw],
            analyzed_items=[analyzed],
            reviewed_items=[reviewed],
            article_ids={raw.url: 42},
            clone_and_inspect_fn=_inspection,
            analyze_fn=fake_analyze,
        )

        assert result.status == "failed"
        row = await db.fetch_one("SELECT * FROM deep_reports WHERE repo_url = ?", (result.repo_url,))
        assert row["status"] == "failed"
        assert row["report_version"] == 2
        assert row["error"] == "parse_failed"
        assert row["analysis_cost"] == pytest.approx(0.003)
        assert row["analysis_tokens"] == 220
        assert row["commit_sha"] == "abc123"
        assert json.loads(row["tech_stack_json"])["languages"] == ["Python"]
        assert row["file_tree_summary"] == "README.md\npyproject.toml\nsrc/main.py"
        cost_rows = await db.fetch_all("SELECT status, error FROM cost_logs ORDER BY id")
        assert [(item["status"], item["error"]) for item in cost_rows] == [
            ("request_failed", "timeout"),
            ("parse_failed", ""),
        ]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_deep_report_stage_same_commit_failure_does_not_downgrade_completed_report(tmp_path):
    db = await _init_db(tmp_path)
    try:
        existing_id = await save_deep_report(
            db,
            repo_url="https://github.com/acme/dev-agent",
            repo_name="acme/dev-agent",
            article_id=42,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=90,
            trigger_reason="首次成功",
            report_json={"title": "Historical Deep Report", "summary": "old"},
            report_markdown="# historical",
            evidence_json=[{"path": "README.md", "reason": "overview"}],
            tech_stack_json={"languages": ["Python"]},
            file_tree_summary="README.md",
            analysis_cost=0.02,
            analysis_tokens=1000,
            error="",
        )

        raw = _raw("https://github.com/acme/dev-agent")
        analyzed = _analyzed(raw.url)
        reviewed = _reviewed(raw.url)

        async def fake_analyze(_candidate, _source_package, _registry):
            return None, [_cost(status="request_failed", cost=0.001, tokens_in=90, tokens_out=0, attempt_no=1, error="timeout")]

        from src.deep_reports.service import run_deep_report_stage
        async def fake_selector(*_args, **_kwargs):
            return DeepReportSelection(
                candidate=DeepReportCandidate(
                    repo_url=raw.url,
                    repo_name="acme/dev-agent",
                    article_id=42,
                    source_id="github_ai_devtools",
                    source_detail="github trending",
                    title="Dev Agent",
                    summary="summary",
                    reviewer_score=88,
                    candidate_score=90,
                    trigger_reason="forced",
                    metadata={"project_type": "coding_tool"},
                ),
                diagnostics={"eligible": 1, "rejected": {}},
            )

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr("src.deep_reports.service.select_deep_report_candidate", fake_selector)
            result = await run_deep_report_stage(
                db=db,
                registry="registry",
                run_id="run_1",
                raw_items=[raw],
                analyzed_items=[analyzed],
                reviewed_items=[reviewed],
                article_ids={raw.url: 42},
                clone_and_inspect_fn=_inspection,
                analyze_fn=fake_analyze,
            )

        row = await db.fetch_one("SELECT * FROM deep_reports WHERE id = ?", (existing_id,))
        event = await db.fetch_one(
            "SELECT event, status, message, payload FROM pipeline_events WHERE event = 'deep.failed' ORDER BY id DESC LIMIT 1"
        )
        cost_row = await db.fetch_one(
            "SELECT status, error, cost FROM cost_logs WHERE ref_url = ? ORDER BY id DESC LIMIT 1",
            (raw.url,),
        )

        assert result.status == "failed"
        assert result.report_id == existing_id
        assert row["status"] == "completed"
        assert row["article_id"] == 42
        assert json.loads(row["report_json"])["title"] == "Historical Deep Report"
        assert row["report_markdown"] == "# historical"
        assert json.loads(row["evidence_json"]) == [{"path": "README.md", "reason": "overview"}]
        assert event["status"] == "failed"
        assert event["message"] == "timeout"
        assert json.loads(event["payload"])["report_id"] == existing_id
        assert cost_row["status"] == "request_failed"
        assert cost_row["error"] == "timeout"
        assert cost_row["cost"] == pytest.approx(0.001)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_deep_report_stage_returns_failed_when_failed_report_and_failed_event_both_fail(tmp_path, monkeypatch):
    db = await _init_db(tmp_path)
    try:
        raw = _raw("https://github.com/acme/dev-agent")
        analyzed = _analyzed(raw.url)
        reviewed = _reviewed(raw.url)

        async def fake_analyze(_candidate, _source_package, _registry):
            return None, [_cost(status="request_failed", cost=0.001, tokens_in=50, tokens_out=0, attempt_no=1, error="boom")]

        async def failing_save_failed_report(*_args, **_kwargs):
            raise RuntimeError("save failed report exploded")

        original_record_event = main.record_pipeline_event

        async def flaky_record_event(*args, **kwargs):
            if kwargs.get("event") == "deep.failed":
                raise RuntimeError("failed event exploded")
            return await original_record_event(*args, **kwargs)

        monkeypatch.setattr("src.deep_reports.service._save_failed_report", failing_save_failed_report)
        monkeypatch.setattr("src.deep_reports.service.record_pipeline_event", flaky_record_event)

        from src.deep_reports.service import run_deep_report_stage

        result = await run_deep_report_stage(
            db=db,
            registry="registry",
            run_id="run_1",
            raw_items=[raw],
            analyzed_items=[analyzed],
            reviewed_items=[reviewed],
            clone_and_inspect_fn=_inspection,
            analyze_fn=fake_analyze,
        )

        assert result.status == "failed"
        assert result.message == "boom"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_main_pipeline_calls_deep_report_stage_and_failed_stage_keeps_completed(tmp_path, monkeypatch):
    db = Database(tmp_path / "pipeline_main.db", migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()

    raw = _raw("https://github.com/acme/dev-agent")
    analyzed = _analyzed(raw.url)
    reviewed = _reviewed(raw.url, score=91)
    pipeline_cost = CostRecord(
        agent="github_analyzer",
        provider="minimax",
        model="MiniMax-M3",
        tokens_in=100,
        tokens_out=50,
        cost=0.01,
        ref_url=raw.url,
        source="github",
        source_detail="github trending",
        source_id="github_ai_devtools",
    )

    class StubGraph:
        async def ainvoke(self, _state):
            return {
                "analyzed_items": [analyzed],
                "reviewed_items": [reviewed],
                "cost_records": [pipeline_cost],
            }

    source_cfg = SourceConfig(
        id="github_ai_devtools",
        name="GitHub AI Devtools",
        type="github",
        enabled=True,
        priority=1,
        cron="0 9 * * *",
        max_items=10,
        config={},
    )

    captured = {}

    async def fake_stage(**kwargs):
        captured["article_ids"] = dict(kwargs["article_ids"] or {})
        return DeepReportStageResult(
            status="failed",
            report_id=77,
            repo_url="https://github.com/acme/dev-agent",
            message="deep stage failed",
        )

    async def fake_collect_all(_db, _sources):
        return [raw], []

    async def fake_backup_database(_db, _path):
        return None

    monkeypatch.setattr(main, "_db", db)
    monkeypatch.setattr(main, "_registry", object())
    monkeypatch.setattr(main, "_graph", StubGraph())
    monkeypatch.setattr(main, "_builder", None)
    monkeypatch.setattr(main, "_pipeline_lock", None)
    monkeypatch.setattr(main, "load_sources_config", lambda _path: SourcesConfig(sources=[source_cfg]))
    monkeypatch.setattr(main, "collect_all", fake_collect_all)
    monkeypatch.setattr(main, "batch_check_existing_urls", AsyncMock(return_value=set()))
    monkeypatch.setattr(main, "batch_save_github_snapshots", AsyncMock())
    monkeypatch.setattr(main, "backup_database", fake_backup_database)
    monkeypatch.setattr(main, "run_deep_report_stage", fake_stage)

    try:
        await main.run_pipeline(trigger="manual")

        article = await db.fetch_one("SELECT id, url FROM articles WHERE url = ?", (raw.url,))
        run_row = await db.fetch_one("SELECT status, summary FROM pipeline_runs ORDER BY rowid DESC LIMIT 1")
        summary = json.loads(run_row["summary"])

        assert captured["article_ids"] == {raw.url: article["id"]}
        assert run_row["status"] == "completed"
        assert summary["approved"] == 1
        assert summary["deep_report"] == {
            "status": "failed",
            "report_id": 77,
            "repo_url": "https://github.com/acme/dev-agent",
        }
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_main_pipeline_keeps_completed_when_deep_report_stage_raises(tmp_path, monkeypatch):
    db = Database(tmp_path / "pipeline_main_raise.db", migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()

    raw = _raw("https://github.com/acme/dev-agent")
    analyzed = _analyzed(raw.url)
    reviewed = _reviewed(raw.url, score=91)
    pipeline_cost = CostRecord(
        agent="github_analyzer",
        provider="minimax",
        model="MiniMax-M3",
        tokens_in=100,
        tokens_out=50,
        cost=0.01,
        ref_url=raw.url,
        source="github",
        source_detail="github trending",
        source_id="github_ai_devtools",
    )

    class StubGraph:
        async def ainvoke(self, _state):
            return {
                "analyzed_items": [analyzed],
                "reviewed_items": [reviewed],
                "cost_records": [pipeline_cost],
            }

    source_cfg = SourceConfig(
        id="github_ai_devtools",
        name="GitHub AI Devtools",
        type="github",
        enabled=True,
        priority=1,
        cron="0 9 * * *",
        max_items=10,
        config={},
    )

    async def fake_collect_all(_db, _sources):
        return [raw], []

    async def fake_backup_database(_db, _path):
        return None

    async def raising_stage(**_kwargs):
        raise RuntimeError("deep stage escaped")

    monkeypatch.setattr(main, "_db", db)
    monkeypatch.setattr(main, "_registry", object())
    monkeypatch.setattr(main, "_graph", StubGraph())
    monkeypatch.setattr(main, "_builder", None)
    monkeypatch.setattr(main, "_pipeline_lock", None)
    monkeypatch.setattr(main, "load_sources_config", lambda _path: SourcesConfig(sources=[source_cfg]))
    monkeypatch.setattr(main, "collect_all", fake_collect_all)
    monkeypatch.setattr(main, "batch_check_existing_urls", AsyncMock(return_value=set()))
    monkeypatch.setattr(main, "batch_save_github_snapshots", AsyncMock())
    monkeypatch.setattr(main, "backup_database", fake_backup_database)
    monkeypatch.setattr(main, "run_deep_report_stage", raising_stage)

    try:
        await main.run_pipeline(trigger="manual")

        run_row = await db.fetch_one("SELECT status, summary FROM pipeline_runs ORDER BY rowid DESC LIMIT 1")
        summary = json.loads(run_row["summary"])

        assert run_row["status"] == "completed"
        assert summary["deep_report"]["status"] == "failed"
        assert summary["deep_report"]["report_id"] is None
        assert summary["deep_report"]["repo_url"] == ""
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_main_pipeline_passes_retry_article_id_to_deep_report_stage(tmp_path, monkeypatch):
    db = Database(tmp_path / "pipeline_main_retry.db", migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()

    raw = _raw("https://github.com/acme/retry-agent")
    analyzed = _analyzed(raw.url)
    reviewed = _reviewed(raw.url, verdict="retry", score=75)
    pipeline_cost = CostRecord(
        agent="github_analyzer",
        provider="minimax",
        model="MiniMax-M3",
        tokens_in=100,
        tokens_out=50,
        cost=0.01,
        ref_url=raw.url,
        source="github",
        source_detail="github trending",
        source_id="github_ai_devtools",
    )

    class StubGraph:
        async def ainvoke(self, _state):
            return {
                "analyzed_items": [analyzed],
                "reviewed_items": [reviewed],
                "cost_records": [pipeline_cost],
            }

    source_cfg = SourceConfig(
        id="github_ai_devtools",
        name="GitHub AI Devtools",
        type="github",
        enabled=True,
        priority=1,
        cron="0 9 * * *",
        max_items=10,
        config={},
    )

    captured = {}

    async def fake_collect_all(_db, _sources):
        return [raw], []

    async def fake_backup_database(_db, _path):
        return None

    async def fake_stage(**kwargs):
        captured["article_ids"] = dict(kwargs["article_ids"] or {})
        return DeepReportStageResult(status="skipped", message="no candidate")

    monkeypatch.setattr(main, "_db", db)
    monkeypatch.setattr(main, "_registry", object())
    monkeypatch.setattr(main, "_graph", StubGraph())
    monkeypatch.setattr(main, "_builder", None)
    monkeypatch.setattr(main, "_pipeline_lock", None)
    monkeypatch.setattr(main, "load_sources_config", lambda _path: SourcesConfig(sources=[source_cfg]))
    monkeypatch.setattr(main, "collect_all", fake_collect_all)
    monkeypatch.setattr(main, "batch_check_existing_urls", AsyncMock(return_value=set()))
    monkeypatch.setattr(main, "batch_save_github_snapshots", AsyncMock())
    monkeypatch.setattr(main, "backup_database", fake_backup_database)
    monkeypatch.setattr(main, "run_deep_report_stage", fake_stage)
    monkeypatch.setattr(main, "_prepare_retry_review_items", lambda *_args, **_kwargs: [])

    try:
        await main.run_pipeline(trigger="manual")

        article = await db.fetch_one("SELECT id, status, url FROM articles WHERE url = ?", (raw.url,))
        run_row = await db.fetch_one("SELECT status FROM pipeline_runs ORDER BY rowid DESC LIMIT 1")

        assert article["status"] == "retry"
        assert captured["article_ids"] == {raw.url: article["id"]}
        assert run_row["status"] == "completed"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_main_pipeline_marks_run_failed_when_all_analysis_fails(
    tmp_path,
    monkeypatch,
):
    db = Database(
        tmp_path / "pipeline_all_analysis_failed.db",
        migrations_dir=_MIGRATIONS_DIR,
    )
    await db.initialize()
    raw = _raw("https://github.com/acme/unavailable-agent")
    failure = CostRecord(
        agent="github_analyzer",
        provider="",
        model="",
        tokens_in=0,
        tokens_out=0,
        cost=0,
        ref_url=raw.url,
        source="github",
        source_detail=raw.source_detail,
        source_id="github_ai_devtools",
        status="provider_unavailable",
        error="Budget hard limit reached",
    )

    class StubGraph:
        async def ainvoke(self, _state):
            return {
                "analyzed_items": [],
                "reviewed_items": [],
                "cost_records": [failure],
            }

    source_cfg = SourceConfig(
        id="github_ai_devtools",
        name="GitHub AI Devtools",
        type="github",
        enabled=True,
        priority=1,
        cron="0 9 * * *",
        max_items=10,
        config={},
    )

    async def fake_collect_all(_db, _sources):
        return [raw], []

    deep_stage = AsyncMock()
    monkeypatch.setattr(main, "_db", db)
    monkeypatch.setattr(main, "_registry", object())
    monkeypatch.setattr(main, "_graph", StubGraph())
    monkeypatch.setattr(main, "_builder", None)
    monkeypatch.setattr(main, "_pipeline_lock", None)
    monkeypatch.setattr(
        main,
        "load_sources_config",
        lambda _path: SourcesConfig(sources=[source_cfg]),
    )
    monkeypatch.setattr(main, "collect_all", fake_collect_all)
    monkeypatch.setattr(
        main,
        "batch_check_existing_urls",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(main, "batch_save_github_snapshots", AsyncMock())
    monkeypatch.setattr(main, "run_deep_report_stage", deep_stage)

    try:
        await main.run_pipeline(trigger="manual")

        run = await db.fetch_one(
            "SELECT status, summary FROM pipeline_runs ORDER BY rowid DESC LIMIT 1"
        )
        item = await db.fetch_one(
            "SELECT status, reason FROM collection_items WHERE url = ?",
            (raw.url,),
        )
        cost = await db.fetch_one(
            "SELECT status, error FROM cost_logs WHERE ref_url = ?",
            (raw.url,),
        )

        assert run["status"] == "failed"
        assert "Budget hard limit reached" in run["summary"]
        assert item["status"] == "analysis_failed"
        assert item["reason"] == "Budget hard limit reached"
        assert cost["status"] == "provider_unavailable"
        assert cost["error"] == "Budget hard limit reached"
        deep_stage.assert_not_awaited()
    finally:
        await db.close()
