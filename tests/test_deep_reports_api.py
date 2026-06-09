import json
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.api.deep_reports import router as deep_reports_router
from src.api.deep_reports import set_db as set_deep_reports_db
from src.api.routes import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from src.core.database import Database
from src.db.operations import save_deep_report


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


@pytest_asyncio.fixture
async def api_db(tmp_path):
    db = Database(tmp_path / "deep_reports_api.db", migrations_dir=_MIGRATIONS_DIR)
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
    try:
        yield db
    finally:
        await db.close()
        set_deep_reports_db(None)


@pytest.fixture
def api_client(api_db):
    set_deep_reports_db(api_db)
    app = FastAPI()
    app.include_router(deep_reports_router, prefix="/api")
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    return TestClient(app, raise_server_exceptions=False)


async def _save_report(
    db: Database,
    *,
    repo_url: str,
    repo_name: str,
    status: str = "completed",
    candidate_score: int = 88,
    overview: str = "overview",
) -> int:
    return await save_deep_report(
        db,
        repo_url=repo_url,
        repo_name=repo_name,
        article_id=12,
        run_id="run_1",
        commit_sha="abc123",
        status=status,
        candidate_score=candidate_score,
        trigger_reason="实用性高，源码结构清晰",
        report_json={"project_overview": overview, "summary": overview},
        report_markdown=f"# {repo_name}",
        evidence_json=[{"path": "README.md", "reason": "overview"}],
        tech_stack_json={"languages": ["Python"]},
        file_tree_summary="README.md",
        analysis_cost=0.012,
        analysis_tokens=2048,
        error="" if status == "completed" else "clone failed",
    )


@pytest.mark.asyncio
async def test_list_latest_and_detail_return_deep_reports(api_client, api_db):
    report_id = await _save_report(
        api_db,
        repo_url="https://github.com/org/tool",
        repo_name="org/tool",
    )

    list_response = api_client.get("/api/deep-reports")
    latest_response = api_client.get("/api/deep-reports/latest")
    detail_response = api_client.get(f"/api/deep-reports/{report_id}")

    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["code"] == 0
    assert list_body["data"]["total"] == 1
    assert list_body["data"]["items"][0]["id"] == report_id
    assert "report_json" not in list_body["data"]["items"][0]
    assert "report_markdown" not in list_body["data"]["items"][0]
    assert "evidence_json" not in list_body["data"]["items"][0]
    assert "file_tree_summary" not in list_body["data"]["items"][0]
    assert list_body["data"]["items"][0]["report_summary"] == "overview"
    assert list_body["data"]["items"][0]["report_tech_stack"] == []

    assert latest_response.status_code == 200
    latest_body = latest_response.json()
    assert latest_body["code"] == 0
    assert latest_body["data"]["id"] == report_id
    assert latest_body["data"]["status"] == "completed"

    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["code"] == 0
    assert detail_body["data"]["repo_name"] == "org/tool"
    assert detail_body["data"]["report_json"]["project_overview"] == "overview"


def test_missing_detail_returns_404_envelope(api_client):
    response = api_client.get("/api/deep-reports/99999")

    assert response.status_code == 404
    assert response.json() == {
        "code": 40401,
        "data": None,
        "message": "深度报告 99999 不存在",
    }


@pytest.mark.asyncio
async def test_failed_detail_returns_404_envelope(api_client, api_db):
    report_id = await _save_report(
        api_db,
        repo_url="https://github.com/org/failed-tool",
        repo_name="org/failed-tool",
        status="failed",
    )

    response = api_client.get(f"/api/deep-reports/{report_id}")

    assert response.status_code == 404
    assert response.json() == {
        "code": 40401,
        "data": None,
        "message": f"深度报告 {report_id} 不存在",
    }


@pytest.mark.asyncio
async def test_latest_returns_empty_object_without_completed_report(api_client, api_db):
    await _save_report(
        api_db,
        repo_url="https://github.com/org/failed-tool",
        repo_name="org/failed-tool",
        status="failed",
    )

    response = api_client.get("/api/deep-reports/latest")

    assert response.status_code == 200
    assert response.json() == {"code": 0, "data": {}, "message": "ok"}


@pytest.mark.asyncio
async def test_list_reports_uses_page_and_page_size(api_client, api_db):
    first_id = await _save_report(
        api_db,
        repo_url="https://github.com/org/first",
        repo_name="org/first",
        candidate_score=80,
    )
    second_id = await _save_report(
        api_db,
        repo_url="https://github.com/org/second",
        repo_name="org/second",
        candidate_score=90,
    )
    await _save_report(
        api_db,
        repo_url="https://github.com/org/failed-third",
        repo_name="org/failed-third",
        status="failed",
        candidate_score=99,
    )

    response = api_client.get("/api/deep-reports?page=2&page_size=1")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 2
    assert body["data"]["page"] == 2
    assert body["data"]["page_size"] == 1
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["id"] in {first_id, second_id}
    assert body["data"]["items"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_public_list_ignores_failed_reports_before_pagination(api_client, api_db):
    completed_id = await _save_report(
        api_db,
        repo_url="https://github.com/org/completed-only",
        repo_name="org/completed-only",
        status="completed",
        candidate_score=88,
    )
    await api_db.execute(
        "UPDATE deep_reports SET updated_at = ?, created_at = ? WHERE id = ?",
        ("2026-06-01T09:00:00+08:00", "2026-06-01T09:00:00+08:00", completed_id),
    )

    failed_rows = []
    for index in range(101):
        failed_rows.append((
            f"https://github.com/org/failed-{index}",
            f"org/failed-{index}",
            12,
            "run_1",
            f"failedsha{index}",
            "failed",
            100 - (index % 10),
            "should stay internal",
            json.dumps({"summary": f"failed-{index}"}, ensure_ascii=False),
            "",
            "[]",
            "{}",
            "",
            0.001,
            128,
            "clone failed",
            f"2026-06-09T10:{index % 60:02d}:00+08:00",
            f"2026-06-09T10:{index % 60:02d}:00+08:00",
        ))

    await api_db.execute_many(
        """
        INSERT INTO deep_reports
        (repo_url, repo_name, article_id, run_id, commit_sha, status, candidate_score,
         trigger_reason, report_json, report_markdown, evidence_json, tech_stack_json,
         file_tree_summary, analysis_cost, analysis_tokens, error, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        failed_rows,
    )
    await api_db.commit()

    response = api_client.get("/api/deep-reports?page=1&page_size=100")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    assert [item["id"] for item in body["data"]["items"]] == [completed_id]
    assert all(item["status"] == "completed" for item in body["data"]["items"])
