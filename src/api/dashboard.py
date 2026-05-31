from fastapi import APIRouter, Query

from ..services.dashboard_stats import get_dashboard_summary
from .responses import envelope
from .stats import get_db


router = APIRouter(prefix="/api/dashboard")


@router.get("/summary")
async def dashboard_summary(days: int = Query(default=7, ge=1, le=3650)):
    db = get_db()
    return envelope(await get_dashboard_summary(db, days))
