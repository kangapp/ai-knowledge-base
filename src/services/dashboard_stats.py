import json

from ..core.database import Database


def _date_window_modifier(days: int) -> str:
    return f"-{max(days - 1, 0)} days"


async def get_dashboard_summary(db: Database, days: int = 30) -> dict:
    cutoff = _date_window_modifier(days)
    pipeline_rows = await db.fetch_all(
        "SELECT summary FROM pipeline_runs WHERE started_at >= date('now', '+8 hours', ?) AND status='completed'",
        (cutoff,),
    )
    pipeline_approved = 0
    pipeline_discarded = 0
    pipeline_retry = 0
    for row in pipeline_rows:
        try:
            summary = json.loads(row["summary"] or "{}")
        except json.JSONDecodeError:
            continue
        pipeline_approved += summary.get("approved", 0)
        pipeline_discarded += summary.get("discarded", 0)
        pipeline_retry += summary.get("retry", 0)

    period_total_collected = pipeline_approved + pipeline_discarded + pipeline_retry
    pass_rate = pipeline_approved / period_total_collected if period_total_collected > 0 else 0

    total = await db.fetch_one("SELECT COUNT(*) as c FROM articles WHERE status='approved'")
    period_cost = await db.fetch_one(
        "SELECT COALESCE(SUM(cost),0) as t FROM cost_logs WHERE created_at >= date('now', '+8 hours', ?)",
        (cutoff,),
    )
    cost_total = await db.fetch_one("SELECT COALESCE(SUM(cost),0) as t FROM cost_logs")
    active_sources = await db.fetch_one(
        "SELECT COUNT(DISTINCT source) as c FROM articles WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)",
        (cutoff,),
    )
    avg_score = await db.fetch_one("SELECT AVG(relevance_score) as avg FROM articles WHERE status='approved'")

    return {
        "total_articles": total["c"] if total else 0,
        "period_articles": pipeline_approved,
        "period_cost": round(period_cost["t"] if period_cost else 0, 4),
        "total_cost": round(cost_total["t"] if cost_total else 0, 4),
        "active_sources": active_sources["c"] if active_sources else 0,
        "avg_score": round(avg_score["avg"], 1) if avg_score and avg_score["avg"] else 0,
        "pass_rate": round(pass_rate, 3),
        "period_total_collected": period_total_collected,
    }


async def get_enhanced_stats(db: Database, days: int = 30) -> dict:
    summary = await get_dashboard_summary(db, days)
    cutoff = _date_window_modifier(days)

    hourly = await db.fetch_all("""
        SELECT strftime('%Y-%m-%dT%H:00', created_at) as hour,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '+8 hours', '-2 days')
        GROUP BY hour ORDER BY hour
    """)
    daily = await db.fetch_all("""
        SELECT date(created_at) as date, SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= date('now', '+8 hours', ?)
        GROUP BY date(created_at) ORDER BY date
    """, (cutoff,))
    weekly = await db.fetch_all("""
        SELECT strftime('%Y-W%W', created_at) as week,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '+8 hours', '-12 weeks')
        GROUP BY week ORDER BY week
    """)
    monthly = await db.fetch_all("""
        SELECT strftime('%Y-%m', created_at) as month,
               SUM(cost) as cost, COUNT(*) as articles
        FROM cost_logs
        WHERE created_at >= datetime('now', '+8 hours', '-12 months')
        GROUP BY month ORDER BY month
    """)
    source_dist = await db.fetch_all("""
        SELECT source, COUNT(*) as count
        FROM articles WHERE status='approved'
        GROUP BY source ORDER BY count DESC
    """)
    active_detail = await db.fetch_all("""
        SELECT source, source_detail, COUNT(*) as count
        FROM articles
        WHERE status='approved' AND collected_at >= date('now', '+8 hours', ?)
        GROUP BY source, source_detail
        ORDER BY count DESC
    """, (cutoff,))

    return {
        "summary": summary,
        "hourly_cost": [dict(r) for r in hourly],
        "daily_cost": [dict(r) for r in daily],
        "weekly_cost": [dict(r) for r in weekly],
        "monthly_cost": [dict(r) for r in monthly],
        "source_distribution": [dict(r) for r in source_dist],
        "active_source_details": [dict(r) for r in active_detail],
    }
