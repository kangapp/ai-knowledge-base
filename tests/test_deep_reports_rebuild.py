from pathlib import Path

import pytest

from src.core.database import Database
from src.db.operations import (
    get_public_deep_report_version,
    save_deep_report,
)
from src.deep_reports.models import DeepReportOutput, RepoFile, RepoInspection
from src.deep_reports.rebuild import rebuild_deep_reports
from src.graph.state import CostRecord


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def _init_db(tmp_path) -> Database:
    db = Database(tmp_path / "deep_reports_rebuild.db", migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()
    await db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES (?, datetime('now', '+8 hours'), ?, ?)
        """,
        ("legacy_run", "completed", "test"),
    )
    await db.commit()
    return db


async def _save_v1(db: Database, repo_name: str, commit_sha: str) -> int:
    return await save_deep_report(
        db,
        repo_url=f"https://github.com/{repo_name}",
        repo_name=repo_name,
        article_id=None,
        run_id="legacy_run",
        commit_sha=commit_sha,
        status="completed",
        candidate_score=90,
        trigger_reason="legacy report",
        report_json={"summary": f"legacy {repo_name}"},
        report_markdown="# legacy",
        evidence_json=[],
        tech_stack_json={},
        file_tree_summary="README.md",
        analysis_cost=0.01,
        analysis_tokens=1000,
        error="",
        report_version=1,
    )


def _inspection(repo_url: str, repo_name: str) -> RepoInspection:
    return RepoInspection(
        repo_url=repo_url,
        repo_name=repo_name,
        commit_sha=f"{repo_name.split('/')[-1]}-sha",
        readme="Coding agent tool with install and CLI instructions",
        manifests={"pyproject.toml": "[project]"},
        file_tree=["README.md", "src/main.py"],
        entry_files=["src/main.py"],
        key_files=[
            RepoFile(
                path="src/main.py",
                size=100,
                content="print('tool')",
                reason="应用入口",
            )
        ],
    )


def _report(repo_name: str) -> DeepReportOutput:
    return DeepReportOutput.model_validate({
        "title": f"{repo_name} 深度报告",
        "summary": "面向开发者的 Coding 工具。",
        "tech_stack": ["Python"],
        "use_cases": ["代码理解"],
        "decision": {
            "recommendation": "适合开发者试用。",
            "reasons": ["入口清晰"],
            "best_for": ["开发者"],
            "not_for": ["完全离线团队"],
        },
        "architecture": {
            "pattern": "pipeline",
            "summary": "请求经过 Agent 和工具后输出结果。",
            "nodes": [
                {"id": "input", "label": "Input", "role": "输入", "group": "interface"},
                {"id": "agent", "label": "Agent", "role": "编排", "group": "core"},
                {"id": "tools", "label": "Tools", "role": "执行", "group": "core"},
                {"id": "output", "label": "Output", "role": "输出", "group": "interface"},
            ],
            "edges": [
                {"source": "input", "target": "agent", "label": "任务"},
                {"source": "agent", "target": "tools", "label": "调用"},
                {"source": "tools", "target": "output", "label": "结果"},
            ],
        },
        "quick_start": {
            "prerequisites": ["Python"],
            "steps": [
                {"id": "install", "title": "安装", "description": "安装依赖"},
                {"id": "config", "title": "配置", "description": "设置配置"},
                {"id": "run", "title": "运行", "description": "启动 CLI"},
            ],
            "expected_result": "返回代码分析结果。",
        },
        "deployment": {
            "prerequisites": ["Linux 主机"],
            "steps": [
                {"id": "prepare", "title": "准备", "description": "准备环境"},
                {"id": "deploy", "title": "部署", "description": "安装服务"},
                {"id": "health", "title": "检查", "description": "检查健康"},
            ],
            "operations": ["监控模型调用"],
        },
        "core_modules": [
            {"name": "Agent", "responsibility": "编排工具", "depends_on": ["Tools"]},
        ],
        "runtime_data_flow": [
            {"id": "request", "title": "请求", "description": "提交任务"},
            {"id": "execute", "title": "执行", "description": "调用工具"},
            {"id": "result", "title": "结果", "description": "返回结果"},
        ],
        "strengths": ["结构清晰"],
        "limitations": ["依赖外部模型"],
        "actionable_takeaways": ["先验证 CLI"],
        "source_evidence": [{"path": "src/main.py", "reason": "应用入口"}],
    })


async def _analyze(candidate, _source_package, _registry):
    return _report(candidate.repo_name), []


def _cost_record(repo_url: str, cost: float) -> CostRecord:
    return CostRecord(
        agent="deep_report",
        provider="minimax",
        model="MiniMax-M3",
        tokens_in=100,
        tokens_out=50,
        cost=cost,
        ref_url=repo_url,
        source="github",
        status="success",
        attempt_no=1,
        prompt_name="deep_report",
        prompt_version="current",
    )


async def _count_version(db: Database, version: int) -> int:
    row = await db.fetch_one(
        "SELECT COUNT(*) AS c FROM deep_reports WHERE report_version = ?",
        (version,),
    )
    return row["c"]


@pytest.mark.asyncio
async def test_rebuild_dry_run_does_not_modify_database(tmp_path):
    db = await _init_db(tmp_path)
    try:
        await _save_v1(db, "org/one", "one-old")
        await _save_v1(db, "org/two", "two-old")

        result = await rebuild_deep_reports(
            db,
            registry=None,
            dry_run=True,
            max_reports=None,
            repo_url=None,
        )

        assert result.planned == 2
        assert result.completed == 0
        assert result.failed == []
        assert result.switched is False
        assert await get_public_deep_report_version(db) == 1
        assert await _count_version(db, 1) == 2
        assert await _count_version(db, 2) == 0
        run = await db.fetch_one(
            "SELECT id FROM pipeline_runs WHERE trigger = 'deep_report_rebuild'"
        )
        assert run is None
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_full_rebuild_switches_to_v2_and_deletes_v1(tmp_path):
    db = await _init_db(tmp_path)
    try:
        await _save_v1(db, "org/one", "one-old")
        await _save_v1(db, "org/two", "two-old")

        result = await rebuild_deep_reports(
            db,
            registry=object(),
            dry_run=False,
            max_reports=None,
            repo_url=None,
            clone_and_inspect_fn=_inspection,
            analyze_fn=_analyze,
        )

        assert result.planned == 2
        assert result.completed == 2
        assert result.failed == []
        assert result.switched is True
        assert await get_public_deep_report_version(db) == 2
        assert await _count_version(db, 1) == 0
        assert await _count_version(db, 2) == 2
        statuses = await db.fetch_all(
            "SELECT status FROM deep_reports WHERE report_version = 2 ORDER BY repo_url"
        )
        assert [row["status"] for row in statuses] == ["completed", "completed"]
        run = await db.fetch_one(
            """
            SELECT status, summary
            FROM pipeline_runs
            WHERE trigger = 'deep_report_rebuild'
            """
        )
        assert run["status"] == "completed"
        assert '"switched":true' in run["summary"]
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_partial_failure_switches_and_keeps_v2_failed_for_retry(tmp_path):
    db = await _init_db(tmp_path)
    try:
        await _save_v1(db, "org/one", "one-old")
        await _save_v1(db, "org/two", "two-old")

        def flaky_inspection(repo_url: str, repo_name: str):
            if repo_name == "org/two":
                raise RuntimeError("clone failed")
            return _inspection(repo_url, repo_name)

        result = await rebuild_deep_reports(
            db,
            registry=object(),
            dry_run=False,
            max_reports=None,
            repo_url=None,
            clone_and_inspect_fn=flaky_inspection,
            analyze_fn=_analyze,
        )

        assert result.completed == 1
        assert result.failed == ["https://github.com/org/two"]
        assert result.switched is True
        assert await get_public_deep_report_version(db) == 2
        assert await _count_version(db, 1) == 0
        failed = await db.fetch_one(
            """
            SELECT status, error, commit_sha
            FROM deep_reports
            WHERE repo_url = ? AND report_version = 2
            """,
            ("https://github.com/org/two",),
        )
        assert failed["status"] == "failed"
        assert failed["error"] == "clone failed"
        assert failed["commit_sha"] == "two-old"

        retry = await rebuild_deep_reports(
            db,
            registry=object(),
            dry_run=False,
            max_reports=None,
            repo_url="https://github.com/org/two",
            clone_and_inspect_fn=lambda repo_url, repo_name: _inspection(
                repo_url,
                repo_name,
            ).model_copy(update={"commit_sha": "two-old"}),
            analyze_fn=_analyze,
        )

        assert retry.planned == 1
        assert retry.completed == 1
        assert retry.failed == []
        assert retry.switched is False
        completed = await db.fetch_one(
            """
            SELECT status, error
            FROM deep_reports
            WHERE repo_url = ? AND report_version = 2
            """,
            ("https://github.com/org/two",),
        )
        assert completed["status"] == "completed"
        assert completed["error"] == ""
        rows = await db.fetch_one(
            """
            SELECT COUNT(*) AS c
            FROM deep_reports
            WHERE repo_url = ? AND report_version = 2
            """,
            ("https://github.com/org/two",),
        )
        assert rows["c"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_limited_rebuild_does_not_switch_public_version(tmp_path):
    db = await _init_db(tmp_path)
    try:
        await _save_v1(db, "org/one", "one-old")
        await _save_v1(db, "org/two", "two-old")

        result = await rebuild_deep_reports(
            db,
            registry=object(),
            dry_run=False,
            max_reports=1,
            repo_url=None,
            clone_and_inspect_fn=_inspection,
            analyze_fn=_analyze,
        )

        assert result.planned == 1
        assert result.completed == 1
        assert result.switched is False
        assert await get_public_deep_report_version(db) == 1
        assert await _count_version(db, 1) == 2
        assert await _count_version(db, 2) == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_cost_limit_stops_batch_without_switching(tmp_path):
    db = await _init_db(tmp_path)
    try:
        await _save_v1(db, "org/one", "one-old")
        await _save_v1(db, "org/two", "two-old")

        async def costly_analyze(candidate, _source_package, _registry):
            return _report(candidate.repo_name), [
                _cost_record(candidate.repo_url, 0.6)
            ]

        result = await rebuild_deep_reports(
            db,
            registry=object(),
            dry_run=False,
            max_reports=None,
            repo_url=None,
            max_cost=0.5,
            clone_and_inspect_fn=_inspection,
            analyze_fn=costly_analyze,
        )

        assert result.planned == 2
        assert result.completed == 1
        assert result.switched is False
        assert await get_public_deep_report_version(db) == 1
        assert await _count_version(db, 1) == 2
        costs = await db.fetch_one(
            """
            SELECT COUNT(*) AS c, SUM(cost) AS total
            FROM cost_logs
            WHERE agent = 'deep_report'
            """
        )
        assert costs["c"] == 1
        assert costs["total"] == pytest.approx(0.6)
    finally:
        await db.close()
