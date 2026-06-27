from pathlib import Path

import pytest

from src.core.config import SourceConfig
from src.core.database import Database
from src.core.source_registry import (
    list_pipeline_sources,
    list_schedulable_sources,
    sync_sources_config,
    update_source_status,
)


@pytest.mark.asyncio
async def test_sync_sources_config_preserves_manual_disable(tmp_path):
    db = Database(
        tmp_path / "registry.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        source = SourceConfig(
            id="rss_test",
            name="RSS Test",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await sync_sources_config(db, [source])
        assert await update_source_status(
            db,
            "rss_test",
            "disabled",
            "manual disable",
            manual=True,
        )

        await sync_sources_config(db, [source])
        row = await db.fetch_one(
            "SELECT status, enabled, manual_override FROM source_registry WHERE id = ?",
            ("rss_test",),
        )
        assert row["status"] == "disabled"
        assert row["enabled"] == 0
        assert row["manual_override"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_sync_sources_config_preserves_automatic_degraded_status(tmp_path):
    db = Database(
        tmp_path / "registry.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        source = SourceConfig(
            id="rss_test",
            name="RSS Test",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await sync_sources_config(db, [source])
        await update_source_status(db, "rss_test", "degraded", "auto degraded")

        await sync_sources_config(db, [source])
        row = await db.fetch_one(
            "SELECT status, enabled FROM source_registry WHERE id = ?",
            ("rss_test",),
        )
        assert row["status"] == "degraded"
        assert row["enabled"] == 1
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_list_schedulable_sources_returns_active_degraded_and_trial(tmp_path):
    db = Database(
        tmp_path / "registry.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        base = SourceConfig(
            id="rss_active",
            name="RSS Active",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await sync_sources_config(db, [base])
        for source_id, status in [
            ("rss_active", "active"),
            ("rss_trial", "trial"),
            ("rss_degraded", "degraded"),
            ("rss_disabled", "disabled"),
        ]:
            await db.execute(
                """
                INSERT OR REPLACE INTO source_registry
                (id, name, type, status, enabled, priority, cron, max_items, config_json)
                VALUES (?, ?, 'rss', ?, ?, 2, '0 */4 * * *', 10, '{"url":"https://example.com/feed.xml"}')
                """,
                (source_id, source_id, status, 0 if status == "disabled" else 1),
            )
        await db.commit()

        ids = {source.id for source in await list_schedulable_sources(db)}
        assert ids == {"rss_active", "rss_trial", "rss_degraded"}
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_list_pipeline_sources_caps_trial_items_and_applies_filter(tmp_path):
    db = Database(
        tmp_path / "registry.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        for source_id, status in [
            ("rss_active", "active"),
            ("rss_trial", "trial"),
            ("rss_candidate", "candidate"),
        ]:
            await db.execute(
                """
                INSERT INTO source_registry
                (id, name, type, status, enabled, priority, cron, max_items, config_json)
                VALUES (?, ?, 'rss', ?, ?, 2, '0 */4 * * *', 10, '{"url":"https://example.com/feed.xml"}')
                """,
                (source_id, source_id, status, 0 if status == "candidate" else 1),
            )
        await db.commit()

        sources = await list_pipeline_sources(db, ["rss_trial", "rss_candidate"])

        assert [source.id for source in sources] == ["rss_trial"]
        assert sources[0].max_items == 3
    finally:
        await db.close()
