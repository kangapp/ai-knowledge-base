# src/scheduler/source_scheduler.py
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ..core.source_discovery import SourceDiscovery
from ..core.source_governance import evaluate_trial_sources, promote_candidates_to_trial
from ..core.database import Database
from ..core.time import BEIJING_TZ

logger = logging.getLogger("pipeline")


async def run_weekly_source_maintenance():
    """
    每周执行的维护任务：
    1. 发现新数据源，写入候选池
    2. 候选源进入小流量试跑
    3. 试跑源按健康数据自动上线或拒绝
    """
    db = Database("data/kb.db")
    try:
        await db.initialize()
        discovery = SourceDiscovery(db)
        new_sources = await discovery.discover()
        promoted = await promote_candidates_to_trial(db)
        trial_changes = await evaluate_trial_sources(db)

        logger.info("scheduler.complete", extra={
            "discovered": len(new_sources),
            "promoted_to_trial": len(promoted),
            "trial_promoted": sum(1 for status in trial_changes.values() if status == "active"),
            "trial_rejected": sum(1 for status in trial_changes.values() if status == "rejected"),
        })
    finally:
        await db.close()


def setup_source_scheduler(scheduler: AsyncIOScheduler):
    """将每周维护任务注册到 scheduler"""
    scheduler.add_job(
        run_weekly_source_maintenance,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=BEIJING_TZ),
        id="source_weekly_maintenance",
        name="数据源健康维护（发现+淘汰）",
        max_instances=1,
        misfire_grace_time=3600,
    )
    logger.info("scheduler.registered", extra={"job": "source_weekly_maintenance", "trigger": "每周一 09:00"})
