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
    row = await _db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if not row:
        raise HTTPException(status_code=404, detail=f"文章 {article_id} 不存在")
    article = dict(row)
    article["tags"] = await operations.get_article_tags(_db, article_id)
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
async def get_pipeline_dag():
    if not _db:
        raise HTTPException(500, "DB not initialized")

    # Get latest run
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

    return envelope({
        "run_id": run_id,
        "run_id_bj": run_id,
        "status": last_run["status"],
        "current_phase": phases[-1]["phase"] if phases and phases[-1]["status"] == "running" else None,
        "phases": [dict(p) for p in phases],
        "logs": logs,
    })
