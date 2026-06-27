from pathlib import Path

import pytest

from src.core.config import SourceConfig
from src.core.database import Database
from src.core.source_discovery import SourceDiscovery


@pytest.mark.asyncio
async def test_discovered_source_is_candidate_only(tmp_path):
    db = Database(
        tmp_path / "governance.db",
        migrations_dir=Path(__file__).parents[2] / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        discovery = SourceDiscovery(db)
        source = SourceConfig(
            id="rss_candidate",
            name="Candidate RSS",
            type="rss",
            enabled=True,
            priority=2,
            cron="0 */4 * * *",
            max_items=10,
            config={"url": "https://example.com/feed.xml"},
        )
        await discovery._write_discovered_source(source)

        row = await db.fetch_one(
            "SELECT status, enabled FROM source_registry WHERE id = ?",
            ("rss_candidate",),
        )
        assert row["status"] == "candidate"
        assert row["enabled"] == 0
    finally:
        await db.close()
