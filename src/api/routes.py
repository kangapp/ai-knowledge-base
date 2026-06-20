import json

from fastapi import APIRouter, Query, HTTPException
from ..core.database import Database
from ..core.time import parse_bj_datetime
from ..db import operations
from .responses import (
    envelope,
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)

router = APIRouter(prefix="/api")
_db: Database | None = None

def set_db(db: Database | None):
    global _db; _db = db

# ===== 端点 =====

@router.get("/articles")
async def list_articles(
    query: str = Query(default=""),
    source: str = Query(default=""),
    days: int = Query(default=30, ge=1, le=3650),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    offset = (page - 1) * page_size
    rows = await operations.search_articles(_db, query, source, days, page_size, offset)
    total = await operations.count_articles(_db, query, source, days)
    return envelope({
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


@router.get("/articles/{article_id}")
async def get_article(article_id: int):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    article = await operations.get_article_detail(_db, article_id)
    if not article:
        raise HTTPException(status_code=404, detail=f"文章 {article_id} 不存在")
    return envelope(article)


@router.get("/search")
async def search(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    rows = await operations.search_articles(_db, q, days=3650, limit=limit)
    return envelope({"items": rows, "total": len(rows)})


@router.get("/stats")
async def get_stats(days: int = Query(default=30, ge=1, le=3650)):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    return envelope(await operations.get_stats(_db, days))


@router.get("/health")
async def health():
    return {"status": "ok"}  # 不包信封，Caddy/Compose healthcheck 直接读


@router.get("/cost/summary")
async def cost_summary(days: int = Query(default=30, ge=1, le=3650)):
    if not _db:
        raise HTTPException(500, "DB not initialized")
    rows = await _db.fetch_all(
        "SELECT provider, model, SUM(cost) as total_cost, SUM(tokens_in+tokens_out) as total_tokens "
        "FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?) GROUP BY provider, model",
        (operations.date_window_modifier(days),),
    )
    return envelope([dict(r) for r in rows])


_run_pipeline_cb = None
_builder = None

def set_run_pipeline(cb):
    global _run_pipeline_cb; _run_pipeline_cb = cb

def set_builder(builder):
    global _builder; _builder = builder

@router.post("/pipeline/run")
async def trigger_pipeline(source: str = Query(default="")):
    if not _run_pipeline_cb:
        raise HTTPException(500, "Pipeline not initialized")
    import asyncio
    asyncio.create_task(_run_pipeline_cb(
        trigger="manual",
        source_filter=source or None,  # 空字符串 = 全量
    ))
    return envelope({"status": "queued"}, "Pipeline triggered")


@router.post("/pipeline/build")
async def trigger_build():
    if not _builder:
        raise HTTPException(500, "Builder not initialized")
    await _builder.build_now()
    return envelope({"status": "done"}, "Build triggered")


@router.get("/pipeline/dag")
async def get_pipeline_dag(run_id: str = Query(default=""), detail: str = Query(default="summary")):
    if not _db:
        raise HTTPException(500, "DB not initialized")

    # Get latest run
    if run_id:
        last_run = await _db.fetch_one("SELECT * FROM pipeline_runs WHERE id=?", (run_id,))
    else:
        last_run = await _db.fetch_one(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
        )
    if not last_run:
        return envelope({"status": "idle", "phases": [], "logs": []})

    run_id = last_run["id"]
    phases = await _db.fetch_all(
        """SELECT phase, status, started_at, ended_at, duration_ms, details
           FROM pipeline_phase_logs WHERE run_id=? ORDER BY id""",
        (run_id,),
    )
    events = await _db.fetch_all(
        """SELECT id, ts, phase, event, level, status, source_id, source, source_detail,
                  ref_url, title, agent, provider, model, attempt_no, latency_ms,
                  cost, tokens, message, payload
           FROM pipeline_events WHERE run_id=? ORDER BY id DESC LIMIT ?""",
        (run_id, 500 if detail == "full" else 100),
    )
    events_list = [_event_to_dict(row) for row in reversed(events)]
    source_rows = await _db.fetch_all(
        """SELECT source_id, source, source_detail, collected, new_items, dedup_skipped,
                  analyzed, analysis_failed, approved, retry, discarded, inserted,
                  failed, cost, tokens
           FROM pipeline_source_runs WHERE run_id=? ORDER BY source_id""",
        (run_id,),
    )
    source_funnels = [dict(row) for row in source_rows]
    active_items = _active_items_from_events(events_list)
    progress = _build_dag_progress(last_run["status"], phases, source_funnels, events_list)

    # Generate logs from phase transitions
    logs = []
    for p in phases:
        started_at = p["started_at"]
        if started_at:
            dt = parse_bj_datetime(started_at)
            time_str = dt.strftime("%H:%M:%S")
        else:
            time_str = ""
        if p["status"] == "done":
            msg = f"{p['phase']} 完成"
            if p["details"]:
                msg += f" ({p['details']})"
            logs.append({"time": time_str, "message": msg, "level": "success"})
        elif p["status"] == "running":
            msg = f"{p['phase']} 进行中"
            if p["details"]:
                msg += f" ({p['details']})"
            logs.append({"time": time_str, "message": msg, "level": "info"})
    for event in events_list[-50:]:
        logs.append({
            "time": _event_time(event),
            "message": event["message"] or event["event"],
            "level": _log_level(event["level"]),
            "event": event["event"],
            "phase": event["phase"],
            "ref_url": event.get("ref_url") or "",
            "source_id": event.get("source_id") or "",
        })

    return envelope({
        "run_id": run_id,
        "run_id_bj": run_id,
        "status": last_run["status"],
        "current_phase": phases[-1]["phase"] if phases and phases[-1]["status"] == "running" else None,
        "phases": [dict(p) for p in phases],
        "progress": progress,
        "events": events_list,
        "source_funnels": source_funnels,
        "active_items": active_items,
        "logs": logs,
    })


def _event_to_dict(row) -> dict:
    item = dict(row)
    raw_payload = item.get("payload") or "{}"
    try:
        item["payload"] = json.loads(raw_payload)
    except json.JSONDecodeError:
        item["payload"] = {}
    return item


def _event_time(event: dict) -> str:
    ts = event.get("ts")
    if not ts:
        return ""
    return parse_bj_datetime(ts).strftime("%H:%M:%S")


def _log_level(level: str) -> str:
    if level in {"error", "warning"}:
        return level
    if level == "success":
        return "success"
    return "info"


def _active_items_from_events(events: list[dict]) -> list[dict]:
    active: dict[str, dict] = {}
    for event in events:
        ref_url = event.get("ref_url")
        if not ref_url:
            continue
        event_name = event.get("event") or ""
        if event_name.endswith("_start") or event.get("status") == "running":
            active[ref_url] = {
                "ref_url": ref_url,
                "title": event.get("title") or "",
                "phase": event.get("phase") or "",
                "event": event_name,
                "agent": event.get("agent") or "",
                "source_id": event.get("source_id") or "",
                "started_at": event.get("ts") or "",
            }
        elif event_name.endswith("_done") or event_name.endswith("_failed") or event.get("status") in {"done", "failed"}:
            active.pop(ref_url, None)
    return list(active.values())[-20:]


def _build_dag_progress(status: str, phases, source_funnels: list[dict], events: list[dict]) -> dict:
    total_units = sum(row.get("new_items", 0) or 0 for row in source_funnels)
    completed_units = sum(row.get("inserted", 0) or 0 for row in source_funnels)
    completed_units += sum(row.get("discarded", 0) or 0 for row in source_funnels)
    completed_units += sum(row.get("analysis_failed", 0) or 0 for row in source_funnels)

    if total_units == 0:
        started = sum(1 for phase in phases if phase["status"] in {"running", "done"})
        total_units = max(len(phases), 1)
        completed_units = sum(1 for phase in phases if phase["status"] == "done")
        if status == "running" and started:
            completed_units = max(completed_units, started - 1)

    if events:
        event_completed = sum(
            1
            for event in events
            if event.get("event", "").endswith("_done") or event.get("status") == "done"
        )
        event_started = sum(
            1
            for event in events
            if event.get("event", "").endswith("_start") or event.get("status") == "running"
        )
        total_units = max(total_units, event_started, event_completed)
        completed_units = max(completed_units, event_completed)

    if status == "completed":
        completed_units = max(completed_units, total_units)
    percent = round(completed_units / total_units * 100) if total_units else 0
    return {
        "total_units": total_units,
        "completed_units": min(completed_units, total_units),
        "percent": min(percent, 100),
    }
