from .database import Database
from .time import today_bj


def calculate_health_score(metrics: dict) -> float | None:
    if metrics.get("budget_blocked"):
        return None

    collected = metrics.get("collected", 0) or 0
    new_items = metrics.get("new_items", 0) or 0
    approved = metrics.get("approved", 0) or 0
    cost = metrics.get("cost", 0.0) or 0.0

    request_success = float(metrics.get("request_success_rate", 0) or 0)
    fresh_rate = new_items / collected if collected else 0
    approved_rate = approved / new_items if new_items else 0
    avg_score_norm = float(metrics.get("avg_score") or 0) / 100
    cost_efficiency = min((approved / cost) / 200, 1.0) if cost else 0

    score = (
        request_success * 25
        + fresh_rate * 20
        + approved_rate * 25
        + avg_score_norm * 20
        + cost_efficiency * 10
    )
    return round(score, 1)


async def _change_status(db: Database, source_id: str, status: str, reason: str) -> str:
    row = await db.fetch_one(
        "SELECT status, manual_override FROM source_registry WHERE id = ?",
        (source_id,),
    )
    if row is None or row["manual_override"]:
        return row["status"] if row else ""
    if row["status"] == status:
        return status
    enabled = 1 if status in {"active", "degraded", "trial"} else 0
    await db.execute(
        """
        UPDATE source_registry
        SET status = ?, enabled = ?, updated_at = datetime('now', '+8 hours')
        WHERE id = ?
        """,
        (status, enabled, source_id),
    )
    await db.execute(
        """
        INSERT INTO source_governance_events
        (source_id, event, from_status, to_status, reason)
        VALUES (?, 'auto_transition', ?, ?, ?)
        """,
        (source_id, row["status"], status, reason),
    )
    await db.commit()
    return status


async def apply_governance(db: Database, source_id: str) -> str | None:
    rows = await db.fetch_all(
        """
        SELECT health_score
        FROM source_health_daily
        WHERE source_id = ? AND health_score IS NOT NULL
        ORDER BY date DESC
        LIMIT 3
        """,
        (source_id,),
    )
    if not rows:
        return None

    scores = [row["health_score"] for row in rows]
    current = await db.fetch_one(
        "SELECT status FROM source_registry WHERE id = ?",
        (source_id,),
    )
    if current is None:
        return None

    latest = scores[0]
    if len(scores) == 3 and all(score < 30 for score in scores):
        if current["status"] == "quarantined":
            return await _change_status(db, source_id, "disabled", "连续低分隔离后仍不达标")
        return await _change_status(db, source_id, "quarantined", "连续3次健康分低于30")
    if latest < 50 and current["status"] == "active":
        return await _change_status(db, source_id, "degraded", "健康分低于50")
    return current["status"]


async def rollup_source_health_daily(db: Database, run_id: str) -> None:
    rows = await db.fetch_all(
        """
        SELECT *
        FROM pipeline_source_runs
        WHERE run_id = ?
        """,
        (run_id,),
    )
    date = today_bj()
    for row in rows:
        attempts = row["collected"] + row["failed"]
        request_success_rate = row["collected"] / attempts if attempts else 0
        budget_blocked = 1 if row["analysis_failed"] and row["cost"] == 0 else 0
        metrics = {
            "request_success_rate": request_success_rate,
            "collected": row["collected"],
            "new_items": row["new_items"],
            "approved": row["approved"],
            "avg_score": None,
            "cost": row["cost"],
            "budget_blocked": budget_blocked,
        }
        score = calculate_health_score(metrics)
        await db.execute(
            """
            INSERT INTO source_health_daily
            (source_id, date, request_success_rate, collected, new_items, analyzed,
             analysis_failed, approved, discarded, cost, tokens, health_score, budget_blocked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, date) DO UPDATE SET
                request_success_rate=excluded.request_success_rate,
                collected=source_health_daily.collected + excluded.collected,
                new_items=source_health_daily.new_items + excluded.new_items,
                analyzed=source_health_daily.analyzed + excluded.analyzed,
                analysis_failed=source_health_daily.analysis_failed + excluded.analysis_failed,
                approved=source_health_daily.approved + excluded.approved,
                discarded=source_health_daily.discarded + excluded.discarded,
                cost=source_health_daily.cost + excluded.cost,
                tokens=source_health_daily.tokens + excluded.tokens,
                health_score=excluded.health_score,
                budget_blocked=MAX(source_health_daily.budget_blocked, excluded.budget_blocked),
                updated_at=datetime('now', '+8 hours')
            """,
            (
                row["source_id"],
                date,
                request_success_rate,
                row["collected"],
                row["new_items"],
                row["analyzed"],
                row["analysis_failed"],
                row["approved"],
                row["discarded"],
                row["cost"],
                row["tokens"],
                score,
                budget_blocked,
            ),
        )
        await apply_governance(db, row["source_id"])
    await db.commit()
