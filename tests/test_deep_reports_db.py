from pathlib import Path
import pytest

from src.core.database import Database
from src.db.operations import (
    get_deep_report,
    get_latest_deep_report,
    list_deep_reports,
    save_deep_report,
)

_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


async def _init_db(tmp_path) -> Database:
    db = Database(str(tmp_path / "kb.db"), migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()
    await db.execute(
        "INSERT INTO articles (id, title, url, source, collected_at) VALUES (?, ?, ?, ?, ?)",
        (12, "Tool", "https://github.com/org/tool", "github", "2026-06-03T10:00:00+08:00"),
    )
    await db.execute(
        "INSERT INTO pipeline_runs (id, started_at, status, trigger) VALUES (?, datetime('now', '+8 hours'), ?, ?)",
        ("run_1", "completed", "test"),
    )
    await db.commit()
    return db


@pytest.mark.asyncio
async def test_save_and_query_deep_report(tmp_path):
    db = await _init_db(tmp_path)
    try:
        report_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/tool",
            repo_name="org/tool",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=88,
            trigger_reason="实用性高，源码结构清晰",
            report_json={"project_overview": "overview"},
            report_markdown="# org/tool",
            evidence_json=[{"path": "src/main.py", "reason": "entry"}],
            tech_stack_json={"languages": ["Python"]},
            file_tree_summary="src/main.py\npyproject.toml",
            analysis_cost=0.012,
            analysis_tokens=2048,
            error="",
        )

        detail = await get_deep_report(db, report_id)
        assert detail["repo_name"] == "org/tool"
        assert detail["report_json"]["project_overview"] == "overview"
        assert detail["evidence_json"][0]["path"] == "src/main.py"

        reports = await list_deep_reports(db, page=1, page_size=10)
        assert reports["total"] == 1
        assert reports["items"][0]["id"] == report_id
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_latest_deep_report_ignores_failed(tmp_path):
    db = await _init_db(tmp_path)
    try:
        completed_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/tool",
            repo_name="org/tool",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=88,
            trigger_reason="实用性高，源码结构清晰",
            report_json={"project_overview": "completed"},
            report_markdown="# completed",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0.012,
            analysis_tokens=2048,
            error="",
        )
        await save_deep_report(
            db,
            repo_url="https://github.com/org/failed-tool",
            repo_name="org/failed-tool",
            article_id=12,
            run_id="run_1",
            commit_sha="def456",
            status="failed",
            candidate_score=91,
            trigger_reason="",
            report_json={"project_overview": "failed"},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0.001,
            analysis_tokens=128,
            error="clone failed",
        )

        latest = await get_latest_deep_report(db)

        assert latest["id"] == completed_id
        assert latest["status"] == "completed"
        assert latest["report_json"]["project_overview"] == "completed"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_save_deep_report_upsert_returns_same_id_and_updates_fields(tmp_path):
    db = await _init_db(tmp_path)
    try:
        first_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/tool",
            repo_name="org/tool",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="failed",
            candidate_score=50,
            trigger_reason="初次分析失败",
            report_json={"project_overview": "old"},
            report_markdown="# old",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="old tree",
            analysis_cost=0.001,
            analysis_tokens=128,
            error="timeout",
        )
        second_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/tool",
            repo_name="org/tool-renamed",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=92,
            trigger_reason="重试成功",
            report_json={"project_overview": "new"},
            report_markdown="# new",
            evidence_json=[{"path": "README.md", "reason": "overview"}],
            tech_stack_json={"languages": ["Python"]},
            file_tree_summary="README.md",
            analysis_cost=0.02,
            analysis_tokens=4096,
            error="",
        )

        detail = await get_deep_report(db, first_id)

        assert second_id == first_id
        assert detail["repo_name"] == "org/tool-renamed"
        assert detail["status"] == "completed"
        assert detail["candidate_score"] == 92
        assert detail["report_json"]["project_overview"] == "new"
        assert detail["evidence_json"][0]["path"] == "README.md"
        assert detail["tech_stack_json"]["languages"] == ["Python"]
        assert detail["error"] == ""
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_save_deep_report_failed_cannot_downgrade_existing_completed(tmp_path):
    db = await _init_db(tmp_path)
    try:
        completed_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/tool",
            repo_name="org/tool",
            article_id=12,
            run_id="run_1",
            commit_sha="abc123",
            status="completed",
            candidate_score=88,
            trigger_reason="首次成功",
            report_json={"project_overview": "completed body"},
            report_markdown="# completed",
            evidence_json=[{"path": "src/main.py", "reason": "entry"}],
            tech_stack_json={"languages": ["Python"]},
            file_tree_summary="src/main.py",
            analysis_cost=0.012,
            analysis_tokens=2048,
            error="",
        )

        returned_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/tool",
            repo_name="org/tool",
            article_id=None,
            run_id="run_1",
            commit_sha="abc123",
            status="failed",
            candidate_score=20,
            trigger_reason="后续失败",
            report_json={},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0.001,
            analysis_tokens=100,
            error="timeout",
        )

        detail = await get_deep_report(db, completed_id)

        assert returned_id == completed_id
        assert detail["status"] == "completed"
        assert detail["article_id"] == 12
        assert detail["run_id"] == "run_1"
        assert detail["report_json"]["project_overview"] == "completed body"
        assert detail["report_markdown"] == "# completed"
        assert detail["evidence_json"] == [{"path": "src/main.py", "reason": "entry"}]
        assert detail["tech_stack_json"] == {"languages": ["Python"]}
        assert detail["analysis_cost"] == 0.012
        assert detail["analysis_tokens"] == 2048
        assert detail["error"] == ""
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_latest_deep_report_uses_updated_at_for_completed_reports(tmp_path):
    db = await _init_db(tmp_path)
    try:
        newer_created_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/newer-created",
            repo_name="org/newer-created",
            article_id=12,
            run_id="run_1",
            commit_sha="newer123",
            status="completed",
            candidate_score=70,
            trigger_reason="先完成",
            report_json={"project_overview": "newer created"},
            report_markdown="# newer created",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0.01,
            analysis_tokens=1000,
            error="",
        )
        older_updated_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/older-updated",
            repo_name="org/older-updated",
            article_id=12,
            run_id="run_1",
            commit_sha="older123",
            status="failed",
            candidate_score=40,
            trigger_reason="初次失败",
            report_json={"project_overview": "failed"},
            report_markdown="",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0.001,
            analysis_tokens=100,
            error="timeout",
        )
        await db.execute(
            "UPDATE deep_reports SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2026-06-03 12:00:00", "2026-06-03 12:00:00", newer_created_id),
        )
        await db.execute(
            "UPDATE deep_reports SET created_at = ?, updated_at = ? WHERE id = ?",
            ("2026-06-03 10:00:00", "2026-06-03 10:00:00", older_updated_id),
        )
        await db.commit()

        updated_id = await save_deep_report(
            db,
            repo_url="https://github.com/org/older-updated",
            repo_name="org/older-updated",
            article_id=12,
            run_id="run_1",
            commit_sha="older123",
            status="completed",
            candidate_score=95,
            trigger_reason="后续完成",
            report_json={"project_overview": "updated completed"},
            report_markdown="# updated completed",
            evidence_json=[],
            tech_stack_json={},
            file_tree_summary="",
            analysis_cost=0.02,
            analysis_tokens=2000,
            error="",
        )
        await db.execute(
            "UPDATE deep_reports SET updated_at = ? WHERE id = ?",
            ("2026-06-03 13:00:00", updated_id),
        )
        await db.commit()

        latest = await get_latest_deep_report(db)

        assert updated_id == older_updated_id
        assert latest["id"] == older_updated_id
        assert latest["report_json"]["project_overview"] == "updated completed"
    finally:
        await db.close()
