# tests/test_database.py
import json
from pathlib import Path
import aiosqlite
import pytest
from src.core.database import Database
from src.db import operations
from src.db.operations import get_trending_repo_urls

# 相对测试文件定位到项目根目录下的实际 migrations 目录
_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


@pytest.mark.asyncio
async def test_initialize_and_migrate(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path, migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()

        tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        names = {t["name"] for t in tables}
        assert "articles" in names
        assert "tags" in names
        assert "article_tags" in names
        assert "pipeline_runs" in names
        assert "cost_logs" in names
        assert "provider_health" in names
        assert "circuit_events" in names
        assert "schema_version" in names

        # 验证迁移版本
        v = await db.fetch_one("SELECT version FROM schema_version")
        assert v["version"] == 9

        cost_log_columns = await db.fetch_all("PRAGMA table_info(cost_logs)")
        column_names = {row["name"] for row in cost_log_columns}
        assert {
            "source",
            "source_detail",
            "source_id",
            "status",
            "error",
            "latency_ms",
            "attempt_no",
            "prompt_name",
            "prompt_version",
        }.issubset(column_names)
        assert "collection_items" in names
        assert "pipeline_source_runs" in names
        assert "pipeline_events" in names
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_record_pipeline_event_persists_structured_payload(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await db.execute(
            "INSERT INTO pipeline_runs (id, started_at, status, trigger) VALUES ('run_1', datetime('now', '+8 hours'), 'running', 'test')"
        )

        event_id = await operations.record_pipeline_event(
            db,
            run_id="run_1",
            phase="analyze",
            event="analyzer.item_done",
            level="info",
            status="done",
            source_id="github_ai_devtools",
            source="github",
            source_detail="org/repo",
            ref_url="https://github.com/org/repo",
            title="repo",
            agent="github_analyzer",
            provider="minimax",
            model="MiniMax-M3",
            attempt_no=1,
            latency_ms=1200,
            cost=0.001,
            tokens=300,
            message="分析完成",
            payload={"score": 88},
        )

        row = await db.fetch_one("SELECT * FROM pipeline_events WHERE id = ?", (event_id,))

        assert row["run_id"] == "run_1"
        assert row["phase"] == "analyze"
        assert row["event"] == "analyzer.item_done"
        assert row["source_id"] == "github_ai_devtools"
        assert row["ref_url"] == "https://github.com/org/repo"
        assert json.loads(row["payload"]) == {"score": 88}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_url_unique_constraint(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path, migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()

        await db.execute(
            "INSERT INTO articles (title, url, source, collected_at) VALUES (?, ?, ?, ?)",
            ("Test", "https://example.com/1", "github", "2026-05-16T10:00:00Z")
        )
        with pytest.raises(aiosqlite.IntegrityError):
            await db.execute(
                "INSERT INTO articles (title, url, source, collected_at) VALUES (?, ?, ?, ?)",
                ("Test2", "https://example.com/1", "rss", "2026-05-16T11:00:00Z")
            )
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_fts5_sync(tmp_path):
    """验证 FTS5 外部内容表与 articles 表自动同步"""
    db_path = tmp_path / "test.db"
    db = Database(db_path, migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()

        # INSERT → FTS5 自动索引
        await db.execute(
            "INSERT INTO articles (title, url, source, summary, description, collected_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("LLM 框架", "https://example.com/2", "github", "高性能 LLM 推理", "描述文本", "2026-05-16T10:00:00Z")
        )
        await db.commit()

        rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("LLM",))
        assert len(rows) == 1

        # UPDATE → FTS5 同步更新
        row = await db.fetch_one("SELECT id FROM articles WHERE url = ?", ("https://example.com/2",))
        await db.execute(
            "UPDATE articles SET title = ?, summary = ? WHERE id = ?",
            ("Agent 框架", "Agent 相关推理", row["id"])
        )
        await db.commit()

        # 旧内容搜不到
        rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("LLM",))
        assert len(rows) == 0
        # 新内容可搜
        rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("Agent",))
        assert len(rows) == 1

        # DELETE → FTS5 同步删除
        await db.execute("DELETE FROM articles WHERE id = ?", (row["id"],))
        await db.commit()
        rows = await db.fetch_all("SELECT * FROM articles_fts WHERE articles_fts MATCH ?", ("Agent",))
        assert len(rows) == 0
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_get_trending_repo_urls_uses_nearest_baseline_snapshot(tmp_path):
    db_path = tmp_path / "test.db"
    db = Database(db_path, migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await db.execute(
            """
            INSERT INTO github_repo_snapshots
            (repo_url, repo_name, stars, forks, watchers, snapshot_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("https://github.com/org/repo", "org/repo", 90, 10, 90, "2026-05-24"),
        )
        await db.execute(
            """
            INSERT INTO github_repo_snapshots
            (repo_url, repo_name, stars, forks, watchers, snapshot_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("https://github.com/org/repo", "org/repo", 170, 20, 170, "2026-06-01"),
        )
        await db.commit()

        urls = await get_trending_repo_urls(db, min_velocity=10, days=7)

        assert urls == {"https://github.com/org/repo"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_record_collection_item_upserts_status_by_run_and_url(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()
        await db.execute(
            "INSERT INTO pipeline_runs (id, started_at, status, trigger) VALUES ('run_1', datetime('now', '+8 hours'), 'completed', 'test')"
        )

        await operations.record_collection_item(
            db,
            run_id="run_1",
            url="https://example.com/a",
            title="A",
            source="rss",
            source_id="rss_test",
            source_detail="RSS Test",
            status="collected",
            reason="collector",
            raw_metadata={"source_id": "rss_test"},
        )
        await operations.record_collection_item(
            db,
            run_id="run_1",
            url="https://example.com/a",
            title="A",
            source="rss",
            source_id="rss_test",
            source_detail="RSS Test",
            status="inserted",
            reason="approved",
            raw_metadata={"source_id": "rss_test"},
        )

        rows = await db.fetch_all("SELECT * FROM collection_items")

        assert len(rows) == 1
        assert rows[0]["status"] == "inserted"
        assert rows[0]["reason"] == "approved"
        assert rows[0]["source_id"] == "rss_test"
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_upsert_pipeline_source_run_persists_funnel_metrics(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()

        await db.execute(
            "INSERT INTO pipeline_runs (id, started_at, status, trigger) VALUES ('run_1', datetime('now', '+8 hours'), 'completed', 'test')"
        )
        await operations.upsert_pipeline_source_run(
            db,
            {
                "run_id": "run_1",
                "source_id": "rss_test",
                "source": "rss",
                "source_detail": "RSS Test",
                "collected": 5,
                "new_items": 3,
                "dedup_skipped": 2,
                "analyzed": 3,
                "analysis_failed": 0,
                "approved": 2,
                "retry": 0,
                "discarded": 1,
                "inserted": 2,
                "failed": 0,
                "cost": 0.12,
                "tokens": 3200,
            },
        )
        await db.commit()

        row = await db.fetch_one("SELECT * FROM pipeline_source_runs WHERE run_id='run_1' AND source_id='rss_test'")

        assert row["collected"] == 5
        assert row["new_items"] == 3
        assert row["dedup_skipped"] == 2
        assert row["approved"] == 2
        assert row["cost"] == 0.12
        assert row["tokens"] == 3200
    finally:
        await db.close()
