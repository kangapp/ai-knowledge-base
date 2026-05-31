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
        VALUES (?, ?, 'desc', 'summary', ?, 'detail', 80, 'approved', datetime('now'))
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
    assert week["total_collected"] == 18
    assert week["approved_rate"] == 0.667
    assert week["avg_score"] == 85.0


@pytest.mark.asyncio
async def test_dashboard_summary_returns_first_screen_contract(api_client, api_db):
    await _insert_article(api_db, title="A", url="https://example.com/a", source="rss")
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger, summary)
        VALUES ('run_1', datetime('now'), 'completed', 'manual', ?)
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
        VALUES ('run_today', datetime('now'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_yesterday', datetime('now', '-1 day'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES ('run_today', 'reviewer', 'openai', 'gpt-test', 100, 50, 0.25, datetime('now'))
        """
    )
    await api_db.execute(
        """
        INSERT INTO cost_logs
        (run_id, agent, provider, model, tokens_in, tokens_out, cost, created_at)
        VALUES ('run_yesterday', 'reviewer', 'openai', 'gpt-test', 100, 50, 9.0, datetime('now', '-1 day'))
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
        VALUES ('run_today', datetime('now'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO pipeline_runs (id, started_at, status, trigger)
        VALUES ('run_yesterday', datetime('now', '-1 day'), 'completed', 'manual')
        """
    )
    await api_db.execute(
        """
        INSERT INTO circuit_events (provider, event, reason, created_at)
        VALUES ('openai', 'closed', 'ok', datetime('now'))
        """
    )
    await api_db.execute(
        """
        INSERT INTO circuit_events (provider, event, reason, created_at)
        VALUES ('deepseek', 'open', 'old', datetime('now', '-1 day'))
        """
    )
    await api_db.commit()

    body = api_client.get("/api/stats/runtime?days=1").json()

    assert body["code"] == 0
    assert body["data"]["run"]["id"] == "run_today"
    assert [provider["name"] for provider in body["data"]["providers"]] == ["openai"]
