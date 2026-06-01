# src/api/stats.py
import sys
from fastapi import APIRouter, Query

from ..db import operations
from ..services.dashboard_stats import get_enhanced_stats

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
    return envelope(await get_enhanced_stats(db, days))

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

@router.get("/quality-detail")
async def get_stats_quality_detail(period: str = Query(default="week", pattern="^(day|week|month)$")):
    db = get_db()
    return envelope(await operations.get_quality_detail_stats(db, period))

@router.get("/consumption-detail")
async def get_stats_consumption_detail(
    period: str = Query(default="week", pattern="^(day|week|month)$"),
    trend_window: str | None = Query(default=None, pattern=r"^\d+[dwm]$"),
):
    db = get_db()
    return envelope(await operations.get_consumption_detail_stats(db, period, trend_window))
