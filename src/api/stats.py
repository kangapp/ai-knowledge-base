# src/api/stats.py
import sys
from fastapi import APIRouter, Query

from ..db import operations

router = APIRouter(prefix="/api/stats")

def get_db():
    # 通过 sys.modules 动态获取 routes 模块，确保获取最新的 _db 引用
    from . import routes
    db = getattr(routes, '_db', None)
    if db is None:
        raise RuntimeError("DB not initialized")
    return db

def envelope(data=None, message="ok", code=0):
    from . import routes
    return routes.envelope(data, message, code)

@router.get("/enhanced")
async def get_stats_enhanced(days: int = Query(default=30, ge=1, le=3650)):
    db = get_db()

    # Basic stats
    total = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE status='approved'")
    period = await db.fetch_one(
        "SELECT COUNT(*) as c FROM articles WHERE status='approved' AND collected_at >= date('now', ?)",
        (f"-{days} days",)
    )
    cost_period = await db.fetch_one(
        "SELECT COALESCE(SUM(cost),0) as t FROM cost_logs WHERE created_at >= date('now', ?)",
        (f"-{days} days",)
    )
    cost_total = await db.fetch_one("SELECT COALESCE(SUM(cost),0) as t FROM cost_logs")
    active_sources = await db.fetch_one(
        "SELECT COUNT(DISTINCT source) as c FROM articles WHERE status='approved' AND collected_at >= date('now', ?)",
        (f"-{days} days",)
    )
    avg_score = await db.fetch_one("SELECT AVG(relevance_score) as avg FROM articles WHERE status='approved'")

    # Hourly (past 48 hours)
    hourly = await db.fetch_all("""
        SELECT strftime('%Y-%m-%dT%H:00', created_at) as hour,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '-2 days')
        GROUP BY hour ORDER BY hour
    """)

    # Daily
    daily = await db.fetch_all("""
        SELECT date(created_at) as date, SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= date('now', ?)
        GROUP BY date(created_at) ORDER BY date
    """, (f"-{days} days",))

    # Weekly (past 12 weeks)
    weekly = await db.fetch_all("""
        SELECT strftime('%Y-W%W', created_at) as week,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '-12 weeks')
        GROUP BY week ORDER BY week
    """)

    # Monthly (past 12 months)
    monthly = await db.fetch_all("""
        SELECT strftime('%Y-%m', created_at) as month,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '-12 months')
        GROUP BY month ORDER BY month
    """)

    # Source distribution (grouped by source)
    source_dist = await db.fetch_all("""
        SELECT source, COUNT(*) as count
        FROM articles WHERE status='approved'
        GROUP BY source ORDER BY count DESC
    """)

    # Active source details (RSS细分 + 其他大类)
    active_detail = await db.fetch_all("""
        SELECT source, source_detail, COUNT(*) as count
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', ?)
        GROUP BY source, source_detail
        ORDER BY count DESC
    """, (f"-{days} days",))

    return {
        "code": 0,
        "data": {
            "summary": {
                "total_articles": total["c"] if total else 0,
                "period_articles": period["c"] if period else 0,
                "period_cost": round(cost_period["t"] if cost_period else 0, 4),
                "total_cost": round(cost_total["t"] if cost_total else 0, 4),
                "active_sources": active_sources["c"] if active_sources else 0,
                "avg_score": round(avg_score["avg"], 1) if avg_score and avg_score["avg"] else 0,
            },
            "hourly_cost": [dict(r) for r in hourly],
            "daily_cost": [dict(r) for r in daily],
            "weekly_cost": [dict(r) for r in weekly],
            "monthly_cost": [dict(r) for r in monthly],
            "source_distribution": [dict(r) for r in source_dist],
            "active_source_details": [dict(r) for r in active_detail],
        },
        "message": "ok"
    }

@router.get("/quality")
async def get_stats_quality(days: int = Query(default=30, ge=1, le=3650)):
    db = get_db()
    return envelope(await operations.get_quality_stats(db, days))

@router.get("/runtime")
async def get_stats_runtime(days: int = Query(default=7, ge=1, le=365)):
    db = get_db()
    return envelope(await operations.get_runtime_stats(db, days))

@router.get("/consumption")
async def get_stats_consumption(days: int = Query(default=30, ge=1, le=3650)):
    db = get_db()
    return envelope(await operations.get_consumption_stats(db, days))