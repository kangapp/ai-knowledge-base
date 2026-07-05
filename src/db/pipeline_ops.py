import json

from ..core.database import Database
from ..core.time import now_bj_iso


async def start_pipeline_run(db: Database, run_id: str, trigger: str):
    now = now_bj_iso()
    await db.execute("INSERT INTO pipeline_runs (id, status, started_at, trigger) VALUES (?, 'running', ?, ?)", (run_id, now, trigger))
    await db.commit()


async def end_pipeline_run(db: Database, run_id: str, status: str, summary: str):
    now = now_bj_iso()
    await db.execute("UPDATE pipeline_runs SET ended_at=?, status=?, summary=? WHERE id=?", (now, status, summary, run_id))
    await db.commit()


async def record_pipeline_event(
    db: Database,
    *,
    run_id: str,
    phase: str,
    event: str,
    level: str = "info",
    status: str = "",
    source_id: str = "",
    source: str = "",
    source_detail: str = "",
    ref_url: str = "",
    title: str = "",
    agent: str = "",
    provider: str = "",
    model: str = "",
    attempt_no: int | None = None,
    latency_ms: int | None = None,
    cost: float | None = None,
    tokens: int | None = None,
    message: str = "",
    payload: dict | None = None,
) -> int:
    payload_json = json.dumps(payload or {}, ensure_ascii=False, separators=(",", ":"))
    await db.execute(
        """
        INSERT INTO pipeline_events
        (run_id, ts, phase, event, level, status, source_id, source, source_detail,
         ref_url, title, agent, provider, model, attempt_no, latency_ms, cost, tokens,
         message, payload)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            now_bj_iso(),
            phase,
            event,
            level,
            status,
            source_id,
            source,
            source_detail,
            ref_url,
            title,
            agent,
            provider,
            model,
            attempt_no,
            latency_ms,
            cost,
            tokens,
            message,
            payload_json,
        ),
    )
    await db.commit()
    row = await db.fetch_one("SELECT last_insert_rowid() as id")
    return row["id"] if row else 0


async def record_collection_item(
    db: Database,
    *,
    run_id: str,
    url: str,
    title: str,
    source: str,
    source_id: str,
    source_detail: str = "",
    status: str,
    reason: str = "",
    raw_metadata: dict | None = None,
    article_id: int | None = None,
):
    metadata_json = json.dumps(raw_metadata or {}, ensure_ascii=False)
    await db.execute("""
        INSERT INTO collection_items
        (run_id, url, title, source, source_id, source_detail, status, reason, raw_metadata, article_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, url) DO UPDATE SET
            title=excluded.title,
            source=excluded.source,
            source_id=excluded.source_id,
            source_detail=excluded.source_detail,
            status=excluded.status,
            reason=excluded.reason,
            raw_metadata=excluded.raw_metadata,
            article_id=COALESCE(excluded.article_id, collection_items.article_id),
            updated_at=datetime('now', '+8 hours')
    """, (
        run_id,
        url,
        title,
        source,
        source_id,
        source_detail,
        status,
        reason,
        metadata_json,
        article_id,
    ))
    await db.commit()


async def upsert_pipeline_source_run(db: Database, stats: dict):
    await db.execute("""
        INSERT INTO pipeline_source_runs
        (run_id, source_id, source, source_detail, collected, new_items, dedup_skipped,
         analyzed, analysis_failed, approved, retry, discarded, inserted, failed, cost, tokens)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, source_id) DO UPDATE SET
            source=excluded.source,
            source_detail=excluded.source_detail,
            collected=excluded.collected,
            new_items=excluded.new_items,
            dedup_skipped=excluded.dedup_skipped,
            analyzed=excluded.analyzed,
            analysis_failed=excluded.analysis_failed,
            approved=excluded.approved,
            retry=excluded.retry,
            discarded=excluded.discarded,
            inserted=excluded.inserted,
            failed=excluded.failed,
            cost=excluded.cost,
            tokens=excluded.tokens,
            updated_at=datetime('now', '+8 hours')
    """, (
        stats["run_id"],
        stats["source_id"],
        stats["source"],
        stats.get("source_detail", ""),
        stats.get("collected", 0),
        stats.get("new_items", 0),
        stats.get("dedup_skipped", 0),
        stats.get("analyzed", 0),
        stats.get("analysis_failed", 0),
        stats.get("approved", 0),
        stats.get("retry", 0),
        stats.get("discarded", 0),
        stats.get("inserted", 0),
        stats.get("failed", 0),
        stats.get("cost", 0.0),
        stats.get("tokens", 0),
    ))
