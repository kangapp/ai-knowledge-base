from pathlib import Path
import shutil

import pytest

from src.core.database import Database
from src.db.operations import record_source_health
from src.graph.state import CollectResult


_MIGRATIONS_DIR = Path(__file__).parent.parent / "src" / "db" / "migrations"


@pytest.mark.asyncio
async def test_record_source_health_merges_collection_and_review_stats(tmp_path):
    db = Database(tmp_path / "test.db", migrations_dir=_MIGRATIONS_DIR)
    try:
        await db.initialize()

        await record_source_health(db, CollectResult(source_id="rss_36kr", total=8))
        await record_source_health(db, CollectResult(source_id="rss_36kr", total=2))
        await record_source_health(
            db,
            CollectResult(source_id="rss_36kr", total=3, approved=2, rejected=1, avg_score=80),
        )
        await record_source_health(
            db,
            CollectResult(source_id="rss_36kr", total=2, approved=1, rejected=1, avg_score=50),
        )

        row = await db.fetch_one(
            "SELECT total_collected, approved, rejected, failed, avg_score FROM source_health WHERE source_id = ?",
            ("rss_36kr",),
        )

        assert row["total_collected"] == 10
        assert row["approved"] == 3
        assert row["rejected"] == 2
        assert row["failed"] == 0
        assert row["avg_score"] == pytest.approx(70.0)
    finally:
        await db.close()


@pytest.mark.asyncio
async def test_source_health_migration_merges_legacy_display_source_ids(tmp_path):
    db_path = tmp_path / "legacy.db"
    legacy_migrations = tmp_path / "migrations_v6"
    legacy_migrations.mkdir()
    for migration in sorted(_MIGRATIONS_DIR.glob("*.sql")):
        if int(migration.name.split("_")[0]) <= 6:
            shutil.copy2(migration, legacy_migrations / migration.name)

    db = Database(db_path, migrations_dir=legacy_migrations)
    try:
        await db.initialize()
        await db.execute("DELETE FROM source_health")
        await db.execute(
            """
            INSERT INTO source_health
            (source_id, date, total_collected, approved, rejected, failed, avg_score)
            VALUES ('rss_36kr', '2026-05-31', 8, 0, 0, 0, NULL)
            """
        )
        await db.execute(
            """
            INSERT INTO source_health
            (source_id, date, total_collected, approved, rejected, failed, avg_score)
            VALUES ('36氪', '2026-05-31', 1, 1, 0, 0, 80)
            """
        )
        await db.execute(
            """
            INSERT INTO source_health
            (source_id, date, total_collected, approved, rejected, failed, avg_score)
            VALUES ('cs.AI', '2026-05-31', 3, 2, 1, 0, 75)
            """
        )
        await db.commit()
    finally:
        await db.close()

    migrated = Database(db_path, migrations_dir=_MIGRATIONS_DIR)
    try:
        await migrated.initialize()
        rss = await migrated.fetch_one(
            "SELECT total_collected, approved, rejected, avg_score FROM source_health WHERE source_id = 'rss_36kr'"
        )
        arxiv = await migrated.fetch_one(
            "SELECT total_collected, approved, rejected, avg_score FROM source_health WHERE source_id = 'rss_arxiv'"
        )
        legacy = await migrated.fetch_all(
            "SELECT source_id FROM source_health WHERE source_id IN ('36氪', 'cs.AI', 'cs.CL', 'cs.LG')"
        )

        assert rss["total_collected"] == 8
        assert rss["approved"] == 1
        assert rss["rejected"] == 0
        assert rss["avg_score"] == 80
        assert arxiv["total_collected"] == 0
        assert arxiv["approved"] == 2
        assert arxiv["rejected"] == 1
        assert arxiv["avg_score"] == 75
        assert legacy == []
    finally:
        await migrated.close()
