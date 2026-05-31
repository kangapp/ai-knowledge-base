# tests/test_database.py
from pathlib import Path
import aiosqlite
import pytest
from src.core.database import Database

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
        assert v["version"] == 6

        cost_log_columns = await db.fetch_all("PRAGMA table_info(cost_logs)")
        column_names = {row["name"] for row in cost_log_columns}
        assert {"source", "source_detail", "source_id"}.issubset(column_names)
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
