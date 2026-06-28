import json
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient

from src.api import routes
from src.api.dashboard import router as dashboard_router
from src.api.routes import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from src.api.sources import router as sources_router
from src.api.stats import router as stats_router
from src.core.config import SourceConfig
from src.core.database import Database


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


@pytest_asyncio.fixture
async def api_db(tmp_path):
    db = Database(tmp_path / "api.db", migrations_dir=_MIGRATIONS_DIR)
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()
        routes.set_db(None)


@pytest.fixture
def api_client(api_db):
    routes.set_db(api_db)
    app = FastAPI()
    app.include_router(routes.router)
    app.include_router(dashboard_router)
    app.include_router(sources_router)
    app.include_router(stats_router)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    return TestClient(app, raise_server_exceptions=False)


async def _insert_article(db: Database, *, title: str, url: str, source: str = "rss"):
    await db.execute(
        """
        INSERT INTO articles
        (title, url, description, summary, source, source_detail, relevance_score,
         status, collected_at)
        VALUES (?, ?, 'desc', 'summary', ?, 'detail', 80, 'approved', datetime('now', '+8 hours'))
        """,
        (title, url, source),
    )


async def _tag_article(db: Database, *, url: str, tag_name: str):
    await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
    tag = await db.fetch_one("SELECT id FROM tags WHERE name = ?", (tag_name,))
    article = await db.fetch_one("SELECT id FROM articles WHERE url = ?", (url,))
    await db.execute(
        "INSERT INTO article_tags (article_id, tag_id) VALUES (?, ?)",
        (article["id"], tag["id"]),
    )


@pytest.mark.asyncio
async def test_articles_returns_real_total_and_tags(api_client, api_db):
    await _insert_article(api_db, title="A", url="https://example.com/a")
    await _insert_article(api_db, title="B", url="https://example.com/b")
    await _tag_article(api_db, url="https://example.com/a", tag_name="AI")
    await api_db.commit()

    response = api_client.get("/api/articles?page=1&page_size=1")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 2
    assert len(body["data"]["items"]) == 1
    assert body["data"]["items"][0]["tags"] == ["AI"]


@pytest.mark.asyncio
async def test_article_detail_includes_tags(api_client, api_db):
    await _insert_article(api_db, title="A", url="https://example.com/a")
    await _tag_article(api_db, url="https://example.com/a", tag_name="Agent")
    await api_db.commit()
    article = await api_db.fetch_one("SELECT id FROM articles WHERE url = ?", ("https://example.com/a",))

    response = api_client.get(f"/api/articles/{article['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["title"] == "A"
    assert body["data"]["tags"] == ["Agent"]
    assert body["data"]["dimensions"] == {}
    assert body["data"]["deep_report"] is None


@pytest.mark.asyncio
async def test_article_detail_includes_dimensions_and_public_deep_report(api_client, api_db):
    extra_data = json.dumps(
        {
            "dimensions": {
                "ai_relevance": {"score": 35, "reason": "与 Agent 开发直接相关"},
                "content_depth": {"score": 24, "reason": "包含实现细节"},
                "information_density": {"score": 12, "reason": "信息密度高"},
                "timeliness": {"score": 14, "reason": "近期发布"},
            }
        },
        ensure_ascii=False,
    )
    await api_db.execute(
        """
        INSERT INTO articles
        (title, url, description, summary, source, source_detail, relevance_score,
         status, collected_at, published_at, extra_data)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'approved', ?, ?, ?)
        """,
        (
            "Agent Tool",
            "https://github.com/example/agent-tool",
            "Original project description",
            "中文分析摘要",
            "github",
            "example/agent-tool",
            85,
            "2026-06-20T10:00:00+08:00",
            "2026-06-19T08:00:00+08:00",
            extra_data,
        ),
    )
    article = await api_db.fetch_one(
        "SELECT id FROM articles WHERE url = ?",
        ("https://github.com/example/agent-tool",),
    )
    await api_db.execute(
        """
        INSERT INTO deep_reports
        (repo_url, repo_name, article_id, run_id, commit_sha, status,
         candidate_score, trigger_reason, report_version)
        VALUES (?, ?, ?, NULL, ?, 'completed', ?, ?, 1)
        """,
        (
            "https://github.com/example/agent-tool",
            "example/agent-tool",
            article["id"],
            "abc123",
            92,
            "值得深入评估",
        ),
    )
    await api_db.commit()

    response = api_client.get(f"/api/articles/{article['id']}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["dimensions"]["ai_relevance"] == {
        "score": 35,
        "max_score": 40,
        "reason": "与 Agent 开发直接相关",
    }
    assert data["dimensions"]["info_density"]["score"] == 12
    assert data["deep_report"]["repo_name"] == "example/agent-tool"
    assert data["deep_report"]["candidate_score"] == 92
    assert data["deep_report"]["url"].startswith("/deep-report.html?id=")
    assert "extra_data" not in data


@pytest.mark.asyncio
async def test_article_detail_includes_github_review_dimensions(api_client, api_db):
    extra_data = json.dumps(
        {
            "dimensions": {
                "ai_relevance": {"score": 32, "reason": "AI 开发工具"},
                "developer_utility": {"score": 23, "reason": "能直接改善开发流程"},
                "project_signal": {"score": 15, "reason": "社区信号强"},
                "content_clarity": {"score": 8, "reason": "说明清楚"},
            }
        },
        ensure_ascii=False,
    )
    await api_db.execute(
        """
        INSERT INTO articles
        (title, url, description, summary, source, source_detail, relevance_score,
         status, collected_at, extra_data)
        VALUES (?, ?, 'desc', 'summary', 'github', 'example/repo', 78, 'approved', datetime('now', '+8 hours'), ?)
        """,
        (
            "Repo",
            "https://github.com/example/repo",
            extra_data,
        ),
    )
    article = await api_db.fetch_one(
        "SELECT id FROM articles WHERE url = ?",
        ("https://github.com/example/repo",),
    )
    await api_db.commit()

    response = api_client.get(f"/api/articles/{article['id']}")

    assert response.status_code == 200
    dimensions = response.json()["data"]["dimensions"]
    assert dimensions["ai_relevance"]["max_score"] == 35
    assert dimensions["developer_utility"] == {
        "score": 23,
        "max_score": 30,
        "reason": "能直接改善开发流程",
    }
    assert dimensions["project_signal"]["max_score"] == 20
    assert dimensions["content_clarity"]["max_score"] == 15


def test_http_errors_use_project_error_codes(api_client):
    response = api_client.get("/api/articles/99999")

    assert response.status_code == 404
    assert response.json() == {
        "code": 40401,
        "data": None,
        "message": "文章 99999 不存在",
    }


def test_validation_errors_use_project_error_code(api_client):
    response = api_client.get("/api/articles?page=0")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 40001
    assert body["data"] is None
    assert "参数校验失败" in body["message"]


@pytest.mark.asyncio
async def test_sources_use_injected_database(api_client, api_db, monkeypatch):
    await api_db.execute(
        """
        INSERT INTO source_health
        (source_id, date, total_collected, approved, avg_score)
        VALUES ('rss_test', '2026-05-31', 10, 4, 82.5)
        """
    )
    await api_db.commit()
    monkeypatch.setattr(
        "src.api.sources.SourceManager.load",
        lambda: [
            SourceConfig(
                id="rss_test",
                name="RSS Test",
                type="rss",
                enabled=True,
                priority=2,
                cron="0 9 * * *",
                max_items=5,
                config={"url": "https://example.com/feed.xml"},
            )
        ],
    )

    response = api_client.get("/api/sources/")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["id"] == "rss_test"
    assert body["data"]["items"][0]["recent_total"] == 10


@pytest.mark.asyncio
async def test_source_stats_period_uses_calendar_window(api_client, api_db, monkeypatch):
    rows = [
        ("rss_test", "2026-05-31", 10, 4, 1, 0, 80.0),
        ("rss_test", "2026-05-30", 8, 8, 0, 0, 90.0),
        ("rss_test", "2026-05-20", 100, 100, 0, 0, 100.0),
    ]
    for row in rows:
        await api_db.execute(
            """
            INSERT INTO source_health
            (source_id, date, total_collected, approved, rejected, failed, avg_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_source_1', '2026-05-31T09:00:00', 'completed', 'test')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_source_runs
        (run_id, source_id, source, source_detail, collected, new_items, dedup_skipped,
         analyzed, analysis_failed, approved, retry, discarded, inserted, failed, cost, tokens)
        VALUES ('run_source_1', 'rss_test', 'rss', 'RSS Test', 10, 6, 4, 5, 1, 4, 0, 1, 4, 0, 0.12, 3200)
        """
    )
    await api_db.commit()
    monkeypatch.setattr(
        "src.api.sources.SourceManager.load",
        lambda: [
            SourceConfig(
                id="rss_test",
                name="RSS Test",
                type="rss",
                enabled=True,
                priority=2,
                cron="0 9 * * *",
                max_items=5,
                config={"url": "https://example.com/feed.xml"},
            )
        ],
    )
    monkeypatch.setattr("src.api.sources._today", lambda: "2026-05-31")

    day = api_client.get("/api/sources/stats?period=day").json()["data"]["sources"][0]
    week = api_client.get("/api/sources/stats?period=week").json()["data"]["sources"][0]

    assert day["id"] == "rss_test"
    assert day["name"] == "RSS Test"
    assert day["total_collected"] == 10
    assert day["approved_rate"] == 0.4
    assert day["avg_score"] == 80.0
    assert day["new_items"] == 6
    assert day["dedup_skipped"] == 4
    assert day["analyzed"] == 5
    assert day["analysis_failed"] == 1
    assert day["discarded"] == 1
    assert day["inserted"] == 4
    assert day["filtered_items"] == 1
    assert day["request_success_rate"] == 1
    assert day["insert_rate"] == pytest.approx(0.667, abs=0.001)
    assert day["cost"] == 0.12
    assert day["tokens"] == 3200
    assert week["total_collected"] == 18
    assert week["approved_rate"] == 0.667
    assert week["avg_score"] == 85.0


@pytest.mark.asyncio
async def test_source_stats_include_governance_fields(api_client, api_db, monkeypatch):
    await api_db.execute(
        """
        INSERT INTO source_registry
        (id, name, type, status, enabled, priority, cron, max_items, config_json)
        VALUES ('rss_test', 'RSS Test', 'rss', 'degraded', 1, 2, '0 1 * * *', 5, '{}')
        """
    )
    await api_db.execute(
        """
        INSERT INTO source_health_daily
        (source_id, date, health_score, budget_blocked)
        VALUES ('rss_test', '2026-06-27', 42, 1)
        """
    )
    await api_db.execute(
        """
        INSERT INTO source_governance_events
        (source_id, event, from_status, to_status, reason)
        VALUES ('rss_test', 'auto_transition', 'active', 'degraded', '健康分低于50')
        """
    )
    await api_db.commit()
    monkeypatch.setattr(
        "src.api.sources.SourceManager.load",
        lambda: [
            SourceConfig(
                id="rss_test",
                name="RSS Test",
                type="rss",
                enabled=True,
                priority=2,
                cron="0 1 * * *",
                max_items=5,
                config={},
            )
        ],
    )
    monkeypatch.setattr("src.api.sources._today", lambda: "2026-06-27")

    source = api_client.get("/api/sources/stats?period=day").json()["data"]["sources"][0]

    assert source["governance_status"] == "degraded"
    assert source["health_score"] == 42
    assert source["budget_blocked"] is True
    assert source["last_governance_reason"] == "健康分低于50"


@pytest.mark.parametrize(
    ("enabled", "latest", "expected"),
    [
        (False, None, "disabled"),
        (True, None, "not_scheduled"),
        (True, {"collected": 0, "new_items": 0, "failed": 1}, "failed"),
        (True, {"collected": 0, "new_items": 0, "failed": 0}, "success_zero"),
        (True, {"collected": 10, "new_items": 0, "failed": 0}, "dedup_only"),
        (
            True,
            {"collected": 3, "new_items": 3, "analyzed": 0, "analysis_failed": 3, "failed": 0},
            "analysis_failed",
        ),
        (
            True,
            {"collected": 3, "new_items": 2, "analyzed": 2, "analysis_failed": 0, "failed": 0},
            "healthy",
        ),
    ],
)
def test_source_health_status_distinguishes_pipeline_stages(enabled, latest, expected):
    from src.api.sources import _derive_health_status

    source = SourceConfig(
        id="rss_test",
        name="RSS Test",
        type="rss",
        enabled=enabled,
        priority=2,
        cron="0 9 * * *",
        max_items=5,
        config={"url": "https://example.com/feed.xml"},
    )

    assert _derive_health_status(source, latest) == expected


@pytest.mark.asyncio
async def test_source_stats_returns_configured_sources_without_health_history(
    api_client,
    api_db,
    monkeypatch,
):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_failed_source', '2026-05-31T09:00:00', 'completed', 'test')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_source_runs
        (run_id, source_id, source, source_detail, collected, new_items, dedup_skipped,
         analyzed, analysis_failed, approved, retry, discarded, inserted, failed, cost, tokens)
        VALUES ('run_failed_source', 'rss_failed', 'rss', 'Failed RSS', 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0)
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_events
        (run_id, ts, phase, event, level, status, source_id, message)
        VALUES
        ('run_failed_source', '2026-05-31T09:00:01', 'collect', 'collector.source_error',
         'error', 'failed', 'rss_failed', '404 Not Found')
        """
    )
    await api_db.commit()
    monkeypatch.setattr(
        "src.api.sources.SourceManager.load",
        lambda: [
            SourceConfig(
                id="rss_failed",
                name="Failed RSS",
                type="rss",
                enabled=True,
                priority=2,
                cron="0 9 * * *",
                max_items=5,
                config={"url": "https://example.com/failed.xml"},
            ),
            SourceConfig(
                id="rss_pending",
                name="Pending RSS",
                type="rss",
                enabled=True,
                priority=2,
                cron="0 10 * * *",
                max_items=5,
                config={"url": "https://example.com/pending.xml"},
            ),
            SourceConfig(
                id="rss_disabled",
                name="Disabled RSS",
                type="rss",
                enabled=False,
                priority=2,
                cron="0 11 * * *",
                max_items=5,
                config={"url": "https://example.com/disabled.xml"},
            ),
        ],
    )
    monkeypatch.setattr("src.api.sources._today", lambda: "2026-05-31")

    body = api_client.get("/api/sources/stats?period=day").json()["data"]
    sources = {source["id"]: source for source in body["sources"]}

    assert set(sources) == {"rss_failed", "rss_pending", "rss_disabled"}
    assert sources["rss_failed"]["health_status"] == "failed"
    assert sources["rss_failed"]["last_error"] == "404 Not Found"
    assert sources["rss_failed"]["last_run_at"] is not None
    assert sources["rss_pending"]["health_status"] == "not_scheduled"
    assert sources["rss_disabled"]["health_status"] == "disabled"


@pytest.mark.asyncio
async def test_source_stats_exposes_latest_analyzer_failure_reason(
    api_client,
    api_db,
    monkeypatch,
):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_analysis_failed', '2026-05-31T09:00:00', 'failed', 'cron')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_source_runs
        (run_id, source_id, source, source_detail, collected, new_items, dedup_skipped,
         analyzed, analysis_failed, approved, retry, discarded, inserted, failed, cost, tokens)
        VALUES ('run_analysis_failed', 'rss_test', 'rss', 'RSS Test', 3, 3, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0)
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_events
        (run_id, ts, phase, event, level, status, source_id, message)
        VALUES
        ('run_analysis_failed', '2026-05-31T09:00:01', 'analyze',
         'analyzer.provider_unavailable', 'error', 'failed', 'rss_test',
         'No available provider for rss_analyzer')
        """
    )
    await api_db.commit()
    monkeypatch.setattr(
        "src.api.sources.SourceManager.load",
        lambda: [
            SourceConfig(
                id="rss_test",
                name="RSS Test",
                type="rss",
                enabled=True,
                priority=2,
                cron="0 9 * * *",
                max_items=5,
                config={"url": "https://example.com/feed.xml"},
            )
        ],
    )
    monkeypatch.setattr("src.api.sources._today", lambda: "2026-05-31")

    source = api_client.get("/api/sources/stats?period=day").json()["data"]["sources"][0]

    assert source["health_status"] == "analysis_failed"
    assert source["last_error"] == "No available provider for rss_analyzer"


@pytest.mark.asyncio
async def test_dashboard_summary_returns_first_screen_contract(api_client, api_db):
    await _insert_article(api_db, title="A", url="https://example.com/a", source="rss")
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger, summary)
        VALUES ('run_1', datetime('now', '+8 hours'), 'completed', 'manual', ?)
        """,
        ('{"approved": 1, "discarded": 1, "retry": 0}',),
    )
    await api_db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost)
        VALUES ('run_1', 'reviewer', 'openai', 'gpt-test', 100, 50, 0.25)
        """
    )
    await api_db.commit()

    response = api_client.get("/api/dashboard/summary?days=7")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"] == {
        "total_articles": 1,
        "period_articles": 1,
        "period_cost": 0.25,
        "total_cost": 0.25,
        "active_sources": 1,
        "avg_score": 80.0,
        "pass_rate": 0.5,
        "period_total_collected": 2,
    }


@pytest.mark.asyncio
async def test_cost_and_stats_days_use_natural_day_window(api_client, api_db):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_today', datetime('now', '+8 hours'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_yesterday', datetime('now', '+8 hours', '-1 day'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES ('run_today', 'reviewer', 'openai', 'gpt-test', 100, 50, 0.25, datetime('now', '+8 hours'))
        """
    )
    await api_db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES ('run_yesterday', 'reviewer', 'openai', 'gpt-test', 100, 50, 9.0, datetime('now', '+8 hours', '-1 day'))
        """
    )
    await api_db.commit()

    stats = api_client.get("/api/stats?days=1").json()["data"]
    cost_summary = api_client.get("/api/cost/summary?days=1").json()["data"]

    assert stats["period_cost"] == 0.25
    assert cost_summary == [
        {
            "provider": "openai",
            "model": "gpt-test",
            "total_cost": 0.25,
            "total_tokens": 150,
        }
    ]


@pytest.mark.asyncio
async def test_runtime_stats_days_use_natural_day_window(api_client, api_db):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_today', datetime('now', '+8 hours'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_yesterday', datetime('now', '+8 hours', '-1 day'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO circuit_events (provider, event, reason, created_at)
        VALUES ('openai', 'closed', 'ok', datetime('now', '+8 hours'))
        """
    )
    await api_db.execute(
        """
        INSERT INTO circuit_events (provider, event, reason, created_at)
        VALUES ('deepseek', 'open', 'old', datetime('now', '+8 hours', '-1 day'))
        """
    )
    await api_db.commit()

    body = api_client.get("/api/stats/runtime?days=1").json()

    assert body["code"] == 0
    assert body["data"]["run"]["id"] == "run_today"
    assert [provider["name"] for provider in body["data"]["providers"]] == ["openai"]


@pytest.mark.asyncio
async def test_consumption_detail_api_passes_trend_window(api_client, api_db):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_today', datetime('now', '+8 hours'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_old', datetime('now', '+8 hours', '-3 days'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES ('run_today', 'reviewer', 'openai', 'gpt-test', 100, 50, 0.25, datetime('now', '+8 hours'))
        """
    )
    await api_db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES ('run_old', 'reviewer', 'openai', 'gpt-test', 100, 50, 9.0, datetime('now', '+8 hours', '-3 days'))
        """
    )
    await api_db.commit()

    body = api_client.get("/api/stats/consumption-detail?period=day&trend_window=2d").json()

    assert body["code"] == 0
    assert body["data"]["period_cost"] == 0.25
    assert body["data"]["trend_window"] == "2d"
    assert sum(row["cost"] for row in body["data"]["trend"]) == 0.25


@pytest.mark.asyncio
async def test_pipeline_dag_returns_fine_grained_events_and_progress(api_client, api_db):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_dag', '2026-06-02T21:10:00', 'running', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_phase_logs
        (run_id, phase, status, started_at, ended_at, duration_ms, details)
        VALUES
        ('run_dag', 'collect', 'done', '2026-06-02T21:10:00', '2026-06-02T21:10:05', 5000, 'collected 2 items'),
        ('run_dag', 'analyze', 'running', '2026-06-02T21:10:06', NULL, NULL, NULL)
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_source_runs
        (run_id, source_id, source, source_detail, collected, new_items, dedup_skipped,
         analyzed, analysis_failed, approved, retry, discarded, inserted, failed, cost, tokens)
        VALUES ('run_dag', 'github_ai_devtools', 'github', 'AI DevTools', 2, 2, 0, 1, 0, 0, 0, 0, 0, 0, 0.03, 3000)
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_events
        (run_id, ts, phase, event, level, status, source_id, source, source_detail,
         ref_url, title, agent, provider, model, attempt_no, latency_ms, cost, tokens, message, payload)
        VALUES
        ('run_dag', '2026-06-02T21:10:01', 'collect', 'collector.source_done', 'info', 'done',
         'github_ai_devtools', 'github', 'AI DevTools', '', '', '', '', '', NULL, NULL, NULL, NULL, 'GitHub 采集完成', '{"collected":2}'),
        ('run_dag', '2026-06-02T21:10:07', 'analyze', 'analyzer.item_start', 'info', 'running',
         'github_ai_devtools', 'github', 'AI DevTools', 'https://github.com/org/repo', 'repo',
         'github_analyzer', 'minimax', 'MiniMax-M3', 1, NULL, NULL, NULL, '开始分析 repo', '{}')
        """
    )
    await api_db.commit()

    body = api_client.get("/api/pipeline/dag").json()

    assert body["code"] == 0
    data = body["data"]
    assert data["run_id"] == "run_dag"
    assert data["current_phase"] == "analyze"
    assert data["progress"]["total_units"] == 2
    assert data["progress"]["completed_units"] == 1
    assert data["progress"]["percent"] == 50
    assert data["source_funnels"][0]["source_id"] == "github_ai_devtools"
    assert data["source_funnels"][0]["analyzed"] == 1
    assert data["events"][-1]["event"] == "analyzer.item_start"
    assert data["active_items"][0]["ref_url"] == "https://github.com/org/repo"
    assert data["summary"]["pipeline_status"] == "running"
    assert data["processing_stages"][2]["id"] == "analyze"
    assert data["processing_stages"][2]["status"] == "running"
    assert data["postprocess"]["build"]["status"] == "waiting"
    assert data["recent_runs"][0]["id"] == "run_dag"


@pytest.mark.asyncio
async def test_pipeline_dag_aggregates_processing_review_and_postprocess(api_client, api_db):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, ended_at, status, trigger, summary)
        VALUES (
            'run_complete', '2026-06-20T18:00:00', '2026-06-20T18:05:30',
            'completed', 'cron',
            '{"collected":{"total":26,"new":16},"analyzed":16,"approved":5,"retry":0,"discarded":11,"errors":[],"deep_report":{"status":"skipped"}}'
        )
        """
    )
    phases = [
        ("collect", "done", "2026-06-20T18:00:00", "2026-06-20T18:00:08", 8000, "collected 26 items"),
        ("route", "done", "2026-06-20T18:00:08", "2026-06-20T18:00:09", 1000, "total:16"),
        ("analyze", "done", "2026-06-20T18:00:09", "2026-06-20T18:01:53", 104000, "succeeded:16"),
        ("aggregate", "done", "2026-06-20T18:01:53", "2026-06-20T18:01:53", 200, "total:16"),
        ("review", "done", "2026-06-20T18:01:53", "2026-06-20T18:04:08", 135000, "approved:5, retry:5, discarded:6"),
        ("review", "done", "2026-06-20T18:04:08", "2026-06-20T18:05:29", 81000, "approved:0, retry:3, discarded:2, mode:review_only"),
        ("review", "done", "2026-06-20T18:05:29", "2026-06-20T18:05:30", 1000, "approved:0, retry:0, discarded:3, mode:review_only"),
        ("persist", "done", "2026-06-20T18:05:30", "2026-06-20T18:05:30", 300, "inserted:5, discarded:11"),
        ("deep_report", "skipped", "2026-06-20T18:05:30", "2026-06-20T18:05:30", 100, "无符合候选"),
        ("backup", "done", "2026-06-20T18:05:30", "2026-06-20T18:05:31", 800, "数据库备份完成"),
        ("build", "superseded", None, "2026-06-20T18:06:00", None, "被后续流水线合并"),
    ]
    for phase in phases:
        await api_db.execute(
            """
            INSERT INTO pipeline_phase_logs
            (run_id, phase, status, started_at, ended_at, duration_ms, details)
            VALUES ('run_complete', ?, ?, ?, ?, ?, ?)
            """,
            phase,
        )
    await api_db.execute(
        """
        INSERT INTO pipeline_source_runs
        (run_id, source_id, source, source_detail, collected, new_items, dedup_skipped,
         analyzed, analysis_failed, approved, retry, discarded, inserted, failed, cost, tokens)
        VALUES ('run_complete', 'github_hot', 'github', 'GitHub Hot',
                26, 16, 10, 16, 0, 5, 0, 11, 5, 0, 0.041, 12000)
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_events
        (run_id, ts, phase, event, level, status, message)
        VALUES
        ('run_complete', '2026-06-20T18:05:30', 'build', 'site.build_queued', 'info', 'queued', '等待构建'),
        ('run_complete', '2026-06-20T18:06:00', 'build', 'site.build_superseded', 'info', 'superseded', '被后续流水线合并')
        """
    )
    await api_db.commit()

    data = api_client.get("/api/pipeline/dag?run_id=run_complete&detail=full").json()["data"]

    assert data["summary"] == {
        "pipeline_status": "completed",
        "publication_status": "superseded",
        "trigger": "cron",
        "started_at": "2026-06-20T18:00:00",
        "ended_at": "2026-06-20T18:05:30",
        "collected": 26,
        "new_items": 16,
        "analyzed": 16,
        "inserted": 5,
        "discarded": 11,
        "failed": 0,
        "cost": 0.041,
        "tokens": 12000,
    }
    assert [stage["id"] for stage in data["processing_stages"]] == [
        "collect",
        "route",
        "analyze",
        "review",
        "persist",
    ]
    assert all(stage["status"] == "completed" for stage in data["processing_stages"])
    assert [round_["label"] for round_ in data["review_rounds"]] == ["初审", "重审 1", "重审 2"]
    assert data["review_rounds"][1]["retry"] == 3
    assert data["postprocess"]["deep_report"]["status"] == "skipped"
    assert data["postprocess"]["backup"]["status"] == "completed"
    assert data["postprocess"]["build"]["status"] == "superseded"


@pytest.mark.asyncio
async def test_pipeline_dag_uses_run_summary_and_marks_legacy_gaps_untracked(api_client, api_db):
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, ended_at, status, trigger, summary)
        VALUES (
            'run_legacy', '2026-05-30T10:00:00', '2026-05-30T10:18:29',
            'completed', 'cron',
            '{"collected":{"total":8,"new":8},"analyzed":8,"approved":5,"retry":0,"discarded":3,"errors":[]}'
        )
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_phase_logs
        (run_id, phase, status, started_at, ended_at, duration_ms, details)
        VALUES
        ('run_legacy', 'collect', 'done', '2026-05-30T10:00:00', '2026-05-30T10:00:08', 8000, 'collected 8 items'),
        ('run_legacy', 'review', 'done', '2026-05-30T10:10:00', '2026-05-30T10:18:00', 480000, 'approved:5, retry:0, discarded:3')
        """
    )
    await api_db.commit()

    data = api_client.get("/api/pipeline/dag?run_id=run_legacy").json()["data"]

    assert data["summary"]["collected"] == 8
    assert data["summary"]["new_items"] == 8
    assert data["summary"]["analyzed"] == 8
    assert data["summary"]["inserted"] == 5
    assert data["summary"]["discarded"] == 3
    assert data["processing_stages"][-1]["status"] == "completed"
    assert data["postprocess"]["build"]["status"] == "untracked"
