import json
import re

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
    phase_list = [dict(p) for p in phases]
    recent_rows = await _db.fetch_all(
        """
        SELECT id, status, trigger, started_at, ended_at
        FROM pipeline_runs ORDER BY started_at DESC LIMIT 12
        """
    )
    recent_runs = [dict(row) for row in recent_rows]
    postprocess = _build_postprocess(last_run["status"], phase_list, events_list)
    summary = _build_dag_summary(last_run, source_funnels, postprocess)
    processing_stages = _build_processing_stages(
        last_run["status"],
        phase_list,
        source_funnels,
        events_list,
        summary,
    )
    review_rounds = _build_review_rounds(phase_list)

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
        "phases": phase_list,
        "progress": progress,
        "summary": summary,
        "processing_stages": processing_stages,
        "review_rounds": review_rounds,
        "postprocess": postprocess,
        "recent_runs": recent_runs,
        "events": events_list,
        "source_funnels": source_funnels,
        "active_items": active_items,
        "logs": logs,
    })


def _normalize_phase_status(status: str) -> str:
    return {
        "done": "completed",
        "completed": "completed",
        "running": "running",
        "queued": "queued",
        "failed": "failed",
        "skipped": "skipped",
        "superseded": "superseded",
    }.get(status or "", status or "waiting")


def _stage_from_phases(
    stage_id: str,
    label: str,
    phase_names: set[str],
    run_status: str,
    phases: list[dict],
) -> dict:
    rows = [phase for phase in phases if phase["phase"] in phase_names]
    if not rows:
        status = "waiting" if run_status == "running" else "skipped"
        return {
            "id": stage_id,
            "label": label,
            "status": status,
            "duration_ms": None,
            "details": "",
        }

    statuses = {_normalize_phase_status(row["status"]) for row in rows}
    if "failed" in statuses:
        status = "failed"
    elif "running" in statuses:
        status = "running"
    elif statuses <= {"completed", "skipped", "superseded"}:
        status = "completed" if "completed" in statuses else rows[-1]["status"]
        status = _normalize_phase_status(status)
    else:
        status = _normalize_phase_status(rows[-1]["status"])
    return {
        "id": stage_id,
        "label": label,
        "status": status,
        "duration_ms": sum(row["duration_ms"] or 0 for row in rows) or None,
        "details": rows[-1].get("details") or "",
    }


def _build_processing_stages(
    run_status: str,
    phases: list[dict],
    source_funnels: list[dict],
    events: list[dict],
    summary: dict,
) -> list[dict]:
    definitions = [
        ("collect", "采集与去重", {"collect"}),
        ("route", "来源路由", {"route"}),
        ("analyze", "并行分析", {"analyze", "aggregate"}),
        ("review", "审核与重审", {"review"}),
        ("persist", "结果落库", {"persist"}),
    ]
    stages = [
        _stage_from_phases(stage_id, label, names, run_status, phases)
        for stage_id, label, names in definitions
    ]
    persist_events = [event for event in events if event.get("phase") == "persist"]
    persist_stage = stages[-1]
    if persist_stage["status"] == "skipped" and persist_events:
        persist_stage["status"] = "completed"
        persist_stage["details"] = f"处理 {len(persist_events)} 条结果"
    elif persist_stage["status"] in {"skipped", "untracked"} and (
        summary["new_items"] or summary["inserted"] or summary["discarded"]
    ):
        persist_stage["status"] = "completed"
        persist_stage["details"] = (
            f"入库 {summary['inserted']}，丢弃 {summary['discarded']}"
        )

    analyze_stage = stages[2]
    analyze_stage["sources"] = [
        {
            "source_id": row.get("source_id", ""),
            "label": row.get("source_detail") or row.get("source_id", ""),
            "analyzed": row.get("analyzed", 0) or 0,
            "failed": row.get("analysis_failed", 0) or 0,
        }
        for row in source_funnels
        if (row.get("new_items", 0) or 0) > 0
    ]
    return stages


def _detail_metric(details: str, name: str) -> int:
    match = re.search(rf"(?:^|,\s*){re.escape(name)}:(\d+)", details or "")
    return int(match.group(1)) if match else 0


def _build_review_rounds(phases: list[dict]) -> list[dict]:
    rounds = []
    for index, phase in enumerate(row for row in phases if row["phase"] == "review"):
        details = phase.get("details") or ""
        rounds.append({
            "index": index,
            "label": "初审" if index == 0 else f"重审 {index}",
            "status": _normalize_phase_status(phase.get("status", "")),
            "duration_ms": phase.get("duration_ms"),
            "approved": _detail_metric(details, "approved"),
            "retry": _detail_metric(details, "retry"),
            "discarded": _detail_metric(details, "discarded"),
        })
    return rounds


def _postprocess_item(
    phase_name: str,
    label: str,
    run_status: str,
    phases: list[dict],
    events: list[dict],
) -> dict:
    rows = [phase for phase in phases if phase["phase"] == phase_name]
    related_events = [event for event in events if event.get("phase") == phase_name]
    if rows:
        row = rows[-1]
        status = _normalize_phase_status(row.get("status", ""))
        details = row.get("details") or ""
        duration_ms = row.get("duration_ms")
    elif related_events:
        event = related_events[-1]
        status = _normalize_phase_status(event.get("status", ""))
        details = event.get("message") or ""
        duration_ms = event.get("latency_ms")
    else:
        status = "waiting" if run_status == "running" else "untracked"
        details = ""
        duration_ms = None
    return {
        "id": phase_name,
        "label": label,
        "status": status,
        "duration_ms": duration_ms,
        "details": details,
    }


def _build_postprocess(run_status: str, phases: list[dict], events: list[dict]) -> dict:
    return {
        "deep_report": _postprocess_item(
            "deep_report", "深度报告", run_status, phases, events
        ),
        "backup": _postprocess_item(
            "backup", "数据库备份", run_status, phases, events
        ),
        "build": _postprocess_item(
            "build", "静态站构建", run_status, phases, events
        ),
    }


def _build_dag_summary(last_run, source_funnels: list[dict], postprocess: dict) -> dict:
    try:
        stored_summary = json.loads(last_run["summary"] or "{}")
    except json.JSONDecodeError:
        stored_summary = {}
    collected_summary = stored_summary.get("collected", {})
    if isinstance(collected_summary, int):
        collected_summary = {"total": collected_summary, "new": 0}

    def metric(name: str, fallback: int = 0) -> int:
        value = sum(row.get(name, 0) or 0 for row in source_funnels)
        return value if value else fallback

    return {
        "pipeline_status": last_run["status"],
        "publication_status": postprocess["build"]["status"],
        "trigger": last_run["trigger"] or "",
        "started_at": last_run["started_at"],
        "ended_at": last_run["ended_at"],
        "collected": metric("collected", collected_summary.get("total", 0) or 0),
        "new_items": metric("new_items", collected_summary.get("new", 0) or 0),
        "analyzed": metric("analyzed", stored_summary.get("analyzed", 0) or 0),
        "inserted": metric("inserted", stored_summary.get("approved", 0) or 0),
        "discarded": metric("discarded", stored_summary.get("discarded", 0) or 0),
        "failed": sum(
            (row.get("failed", 0) or 0) + (row.get("analysis_failed", 0) or 0)
            for row in source_funnels
        ),
        "cost": round(sum(row.get("cost", 0) or 0 for row in source_funnels), 10),
        "tokens": sum(row.get("tokens", 0) or 0 for row in source_funnels),
    }


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
