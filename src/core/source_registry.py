import json

from .config import SourceConfig
from .database import Database

SCHEDULABLE_STATUSES = {"active", "degraded", "trial"}


def _status_for_source(source: SourceConfig) -> str:
    return "active" if source.enabled else "disabled"


def _enabled_for_status(status: str) -> int:
    return 1 if status in SCHEDULABLE_STATUSES else 0


def _row_to_source(row) -> SourceConfig:
    return SourceConfig(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        enabled=bool(row["enabled"]),
        priority=row["priority"],
        cron=row["cron"],
        max_items=row["max_items"],
        config=json.loads(row["config_json"] or "{}"),
    )


async def sync_sources_config(db: Database, sources: list[SourceConfig]) -> None:
    for source in sources:
        existing = await db.fetch_one(
            "SELECT manual_override FROM source_registry WHERE id = ?",
            (source.id,),
        )
        if existing and existing["manual_override"]:
            continue
        status = _status_for_source(source)
        await db.execute(
            """
            INSERT INTO source_registry
            (id, name, type, status, enabled, priority, cron, max_items, config_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                type=excluded.type,
                status=excluded.status,
                enabled=excluded.enabled,
                priority=excluded.priority,
                cron=excluded.cron,
                max_items=excluded.max_items,
                config_json=excluded.config_json,
                updated_at=datetime('now', '+8 hours')
            """,
            (
                source.id,
                source.name,
                source.type,
                status,
                _enabled_for_status(status),
                source.priority,
                source.cron,
                source.max_items,
                json.dumps(source.config, ensure_ascii=False),
            ),
        )
    await db.commit()


async def list_schedulable_sources(db: Database) -> list[SourceConfig]:
    rows = await db.fetch_all(
        """
        SELECT *
        FROM source_registry
        WHERE enabled = 1 AND status IN ('active', 'degraded', 'trial')
        ORDER BY priority ASC, id ASC
        """
    )
    return [_row_to_source(row) for row in rows]


async def update_source_status(
    db: Database,
    source_id: str,
    status: str,
    reason: str,
    manual: bool = False,
) -> bool:
    current = await db.fetch_one(
        "SELECT status FROM source_registry WHERE id = ?",
        (source_id,),
    )
    if current is None:
        return False
    await db.execute(
        """
        UPDATE source_registry
        SET status = ?, enabled = ?, manual_override = ?, updated_at = datetime('now', '+8 hours')
        WHERE id = ?
        """,
        (status, _enabled_for_status(status), 1 if manual else 0, source_id),
    )
    await db.execute(
        """
        INSERT INTO source_governance_events
        (source_id, event, from_status, to_status, reason)
        VALUES (?, 'status_changed', ?, ?, ?)
        """,
        (source_id, current["status"], status, reason),
    )
    await db.commit()
    return True
