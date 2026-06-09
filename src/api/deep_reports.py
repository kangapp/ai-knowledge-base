from fastapi import APIRouter, HTTPException, Query

from ..api.responses import envelope
from ..core.database import Database
from ..db.operations import (
    get_completed_deep_report,
    get_latest_deep_report,
    list_completed_deep_reports,
)


router = APIRouter()
_db: Database | None = None


def set_db(db: Database):
    global _db
    _db = db


def _require_db() -> Database:
    if _db is None:
        raise HTTPException(status_code=500, detail="DB not initialized")
    return _db


@router.get("/deep-reports")
async def list_reports(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    return envelope(await list_completed_deep_reports(_require_db(), page=page, page_size=page_size))


@router.get("/deep-reports/latest")
async def latest_report():
    report = await get_latest_deep_report(_require_db())
    return envelope(report or {})


@router.get("/deep-reports/{report_id}")
async def report_detail(report_id: int):
    report = await get_completed_deep_report(_require_db(), report_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"深度报告 {report_id} 不存在")
    return envelope(report)
