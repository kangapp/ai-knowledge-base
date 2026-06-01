# src/scheduler/source_scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ..core.source_manager import SourceManager
from ..core.source_health import SourceHealthTracker
from ..core.source_discovery import SourceDiscovery
from ..core.database import Database

logger = logging.getLogger("pipeline")


async def run_weekly_source_maintenance():
    """
    每周执行的维护任务：
    1. 淘汰低质量数据源
    2. 发现新数据源并添加
    """
    db = Database("data/kb.db")
    try:
        await db.initialize()
        # 1. 健康检查 + 淘汰
        tracker = SourceHealthTracker(db)
        sources = SourceManager.load()
        evicted = await tracker.check_and_evict(sources)
        for e in evicted:
            logger.info("scheduler.evicted", extra={"source_id": e["source_id"], "reason": e["reason"]})

        # 2. 发现新数据源
        discovery = SourceDiscovery(db)
        new_sources = await discovery.discover()
        added_count = 0
        for source in new_sources:
            if SourceManager.add(source):
                added_count += 1

        logger.info("scheduler.complete", extra={
            "evicted": len(evicted),
            "discovered": len(new_sources),
            "added": added_count,
        })
    finally:
        await db.close()


def setup_source_scheduler(scheduler: AsyncIOScheduler):
    """将每周维护任务注册到 scheduler"""
    scheduler.add_job(
        run_weekly_source_maintenance,
        CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="source_weekly_maintenance",
        name="数据源健康维护（发现+淘汰）",
        max_instances=1,
        misfire_grace_time=3600,
    )
    logger.info("scheduler.registered", extra={"job": "source_weekly_maintenance", "trigger": "每周一 09:00"})
