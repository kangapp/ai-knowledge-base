from .database import Database
from .time import today_bj

TRIAL_RUNS_REQUIRED = 3
TRIAL_MIN_SUCCESS_RATE = 0.8
TRIAL_MIN_HEALTH_SCORE = 50
RECOVERY_MIN_AVG_SCORE = 60


def calculate_health_score(metrics: dict) -> float | None:
    if metrics.get("budget_blocked"):
        return None

    collected = metrics.get("collected", 0) or 0
    new_items = metrics.get("new_items", 0) or 0
    approved = metrics.get("approved", 0) or 0
    cost = metrics.get("cost", 0.0) or 0.0
    request_failed = bool(metrics.get("request_failed"))

    if not request_failed and new_items == 0:
        return None

    request_success = float(metrics.get("request_success_rate", 0) or 0)
    fresh_rate = new_items / collected if collected else 0
    approved_rate = approved / new_items if new_items else 0
    avg_score = metrics.get("avg_score")
    avg_score_norm = (float(avg_score) / 100) if avg_score is not None else approved_rate
    cost_efficiency = min((approved / cost) / 200, 1.0) if cost else 0

    score = (
        request_success * 25
        + fresh_rate * 20
        + approved_rate * 25
        + avg_score_norm * 20
        + cost_efficiency * 10
    )
    return round(score, 1)


def _metrics_from_daily_row(row, request_failed: bool = False) -> dict:
    return {
        "request_success_rate": row["request_success_rate"],
        "request_failed": request_failed,
        "collected": row["collected"],
        "new_items": row["new_items"],
        "approved": row["approved"],
        "avg_score": row["avg_score"],
        "cost": row["cost"],
        "budget_blocked": row["budget_blocked"],
    }


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
    if len(scores) == 3 and sum(scores) / len(scores) < 50 and current["status"] == "active":
        return await _change_status(db, source_id, "degraded", "最近3次平均健康分低于50")
    if len(scores) == 3 and sum(scores) / len(scores) >= RECOVERY_MIN_AVG_SCORE and current["status"] == "degraded":
        return await _change_status(db, source_id, "active", "最近3次平均健康分恢复到60以上")
    return current["status"]


async def promote_candidates_to_trial(db: Database, limit: int = 5) -> list[str]:
    rows = await db.fetch_all(
        """
        SELECT id, status
        FROM source_registry
        WHERE status = 'candidate' AND manual_override = 0
        ORDER BY created_at ASC, id ASC
        LIMIT ?
        """,
        (limit,),
    )
    promoted: list[str] = []
    for row in rows:
        await _change_status(db, row["id"], "trial", "候选源进入小流量试跑")
        promoted.append(row["id"])
    return promoted


def _trial_passes(rows) -> bool:
    if any(row["budget_blocked"] for row in rows):
        return False
    return all(
        row["request_success_rate"] >= TRIAL_MIN_SUCCESS_RATE
        and row["new_items"] > 0
        and row["health_score"] is not None
        and row["health_score"] >= TRIAL_MIN_HEALTH_SCORE
        for row in rows
    )


async def evaluate_trial_sources(db: Database) -> dict[str, str]:
    trials = await db.fetch_all(
        """
        SELECT id
        FROM source_registry
        WHERE status = 'trial' AND manual_override = 0
        ORDER BY id ASC
        """
    )
    changed: dict[str, str] = {}
    for trial in trials:
        rows = await db.fetch_all(
            """
            SELECT request_success_rate, new_items, health_score, budget_blocked
            FROM source_health_daily
            WHERE source_id = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (trial["id"], TRIAL_RUNS_REQUIRED),
        )
        if len(rows) < TRIAL_RUNS_REQUIRED:
            continue
        if _trial_passes(rows):
            changed[trial["id"]] = await _change_status(db, trial["id"], "active", "试跑3次达标，自动上线")
        else:
            changed[trial["id"]] = await _change_status(db, trial["id"], "rejected", "试跑3次未达标，自动拒绝")
    return changed


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
            "request_failed": attempts > 0 and row["collected"] == 0,
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
             analysis_failed, approved, discarded, failed, cost, tokens, health_score, budget_blocked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id, date) DO UPDATE SET
                collected=source_health_daily.collected + excluded.collected,
                new_items=source_health_daily.new_items + excluded.new_items,
                analyzed=source_health_daily.analyzed + excluded.analyzed,
                analysis_failed=source_health_daily.analysis_failed + excluded.analysis_failed,
                approved=source_health_daily.approved + excluded.approved,
                discarded=source_health_daily.discarded + excluded.discarded,
                failed=source_health_daily.failed + excluded.failed,
                cost=source_health_daily.cost + excluded.cost,
                tokens=source_health_daily.tokens + excluded.tokens,
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
                row["failed"],
                row["cost"],
                row["tokens"],
                score,
                budget_blocked,
            ),
        )
        daily = await db.fetch_one(
            """
            SELECT *
            FROM source_health_daily
            WHERE source_id = ? AND date = ?
            """,
            (row["source_id"], date),
        )
        if daily:
            daily_attempts = daily["collected"] + daily["failed"]
            daily_success_rate = daily["collected"] / daily_attempts if daily_attempts else 0
            await db.execute(
                """
                UPDATE source_health_daily
                SET request_success_rate = ?, health_score = ?, updated_at = datetime('now', '+8 hours')
                WHERE source_id = ? AND date = ?
                """,
                (
                    daily_success_rate,
                    calculate_health_score(
                        _metrics_from_daily_row(
                            daily,
                            request_failed=daily_attempts > 0 and daily["collected"] == 0,
                        )
                        | {"request_success_rate": daily_success_rate}
                    ),
                    row["source_id"],
                    date,
                ),
            )
        await apply_governance(db, row["source_id"])
    await db.commit()
