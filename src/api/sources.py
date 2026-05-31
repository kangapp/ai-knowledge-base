# src/api/sources.py
import logging
from datetime import date, datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException
from ..core.database import Database
from ..core.source_health import SourceHealthTracker
from ..core.source_manager import SourceManager
from ..core.config import SourceConfig
from .responses import envelope

router = APIRouter(prefix="/api/sources", tags=["sources"])
logger = logging.getLogger("api")


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _source_to_dict(source: SourceConfig, health: dict | None = None) -> dict:
    result = {
        "id": source.id,
        "name": source.name,
        "type": source.type,
        "status": "active" if source.enabled else "disabled",
        "priority": source.priority,
        "cron": source.cron,
    }
    if health:
        result["recent_approved_rate"] = health.get("recent_approved_rate", 0)
        result["recent_total"] = health.get("recent_total", 0)
        result["avg_score"] = health.get("avg_score")
    return result


async def _get_request_db() -> tuple[Database, bool]:
    from . import routes

    db = getattr(routes, "_db", None)
    if db is not None:
        return db, False

    fallback_db = Database("data/kb.db")
    await fallback_db.initialize()
    return fallback_db, True


@router.get("/")
async def list_sources():
    """数据源列表（含状态）"""
    db, should_close = await _get_request_db()
    try:
        sources = SourceManager.load()
        tracker = SourceHealthTracker(db)
        health_data = await tracker.get_all_sources_health()
        health_map = {h["source_id"]: h for h in health_data}

        items = [_source_to_dict(s, health_map.get(s.id)) for s in sources]
        return envelope({"items": items, "total": len(items)})
    finally:
        if should_close:
            await db.close()


@router.get("/stats")
async def get_source_stats(period: str = "week"):
    """数据源健康统计（聚合数据）"""
    valid_periods = {"day": 1, "week": 7, "month": 30}
    days = valid_periods.get(period, 7)
    end_date = date.fromisoformat(_today())
    start_date = (end_date - timedelta(days=days - 1)).isoformat()

    db, should_close = await _get_request_db()
    try:
        tracker = SourceHealthTracker(db)
        health_data = await tracker.get_all_sources_health(start_date=start_date)

        sources = SourceManager.load()
        source_map = {s.id: s for s in sources}

        stats = []
        for h in health_data:
            source = source_map.get(h["source_id"])
            if not source:
                continue
            total = h["recent_total"]
            approved = sum(r["approved"] for r in h["records"]) if h["records"] else 0
            approved_rate = approved / total if total > 0 else 0

            # 计算趋势
            if len(h["records"]) >= 2:
                first_half_total = sum(r["total_collected"] for r in h["records"][len(h["records"])//2:])
                second_half_total = sum(r["total_collected"] for r in h["records"][:len(h["records"])//2:])

                if first_half_total == 0 or second_half_total == 0:
                    trend = "stable"
                else:
                    first_half = sum(r["approved"] for r in h["records"][len(h["records"])//2:]) / first_half_total
                    second_half = sum(r["approved"] for r in h["records"][:len(h["records"])//2:]) / second_half_total
                    if approved_rate > first_half * 1.1:
                        trend = "rising"
                    elif approved_rate < first_half * 0.9:
                        trend = "falling"
                    else:
                        trend = "stable"
            else:
                trend = "stable"

            stats.append({
                "id": h["source_id"],
                "name": source.name,
                "type": source.type,
                "approved_rate": round(approved_rate, 3),
                "total_collected": total,
                "avg_score": h["avg_score"],
                "trend": trend,
            })

        return envelope({"period": period, "sources": stats})
    finally:
        if should_close:
            await db.close()


@router.post("/{source_id}/action")
async def source_action(source_id: str, action: str):
    """手动操作数据源（enable/disable/remove）"""
    if action not in {"enable", "disable", "remove"}:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    source = SourceManager.get(source_id)
    if not source:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")

    if action == "remove":
        SourceManager.remove(source_id)
        logger.info(f"api.source.remove", extra={"source_id": source_id})
        return envelope({"message": f"Source {source_id} removed"})
    elif action == "disable":
        SourceManager.update(source_id, enabled=False)
        return envelope({"message": f"Source {source_id} disabled"})
    elif action == "enable":
        SourceManager.update(source_id, enabled=True)
        return envelope({"message": f"Source {source_id} enabled"})


@router.post("/maintenance/clear-health")
async def clear_source_health():
    """清除所有 source_health 数据，下次采集自动重建（修正旧格式数据）"""
    db, should_close = await _get_request_db()
    try:
        await db.execute("DELETE FROM source_health")
        await db.commit()
        logger.info("api.source_health.cleared")
        return envelope({"message": "source_health cleared, will rebuild on next pipeline run"})
    finally:
        if should_close:
            await db.close()


@router.get("/discovered")
async def list_discovered():
    """已发现待审核的数据源"""
    db, should_close = await _get_request_db()
    try:
        rows = await db.fetch_all("""
            SELECT * FROM discovered_sources
            WHERE status = 'candidate'
            ORDER BY discovered_at DESC
        """)
        return envelope({"items": [dict(r) for r in rows], "total": len(rows)})
    finally:
        if should_close:
            await db.close()
