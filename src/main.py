# src/main.py
import os, json, logging, sys, uuid
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .core.config import load_llm_config, load_sources_config, load_agents_config
from .core.database import Database
from .core.llm_client import LLMRegistry
from .graph.pipeline import build_pipeline, record_phase_start, record_phase_end, set_pipeline_db, reset_analyzer_counter
from .graph.state import PipelineState, ReviewedItem
from .graph.collector import collect_all
from .graph.router import router_node  # retry 循环中手动路由 retry items
from .api.routes import router, set_db, set_run_pipeline, set_builder
from .api.config import router as config_router
from .api.stats import router as stats_router
from .db.operations import (
    start_pipeline_run, end_pipeline_run, save_article, save_tags,
    save_cost_log, batch_check_existing_urls, backup_database,
)
from .site.builder import SiteBuilder, DebouncedBuilder

# 结构化日志：stdout JSON lines（每行一条合法 JSON）
class JSONFormatter(logging.Formatter):
    _SKIP_KEYS = {
        "name", "msg", "args", "created", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "pathname",
        "process", "processName", "relativeCreated", "stack_info",
        "exc_info", "exc_text", "thread", "threadName", "message",
    }

    def format(self, record):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        for k, v in record.__dict__.items():
            if k not in self._SKIP_KEYS and not k.startswith("_"):
                entry[k] = v
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger("pipeline")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
DB_PATH = DATA_DIR / "kb.db"
BACKUP_DIR = DATA_DIR / "backup"

# 加载 .env 环境变量
from dotenv import load_dotenv
load_dotenv(BASE_DIR / ".env")

_registry: LLMRegistry | None = None
_db: Database | None = None
_scheduler: AsyncIOScheduler | None = None
_builder: DebouncedBuilder | None = None
_graph = None  # LangGraph 编译图
_running = False


async def run_pipeline(trigger: str = "cron", source_filter: str | None = None):
    """source_filter 为 None 时采集所有源，否则只采集指定 source.id"""
    global _registry, _db, _builder, _running, _graph

    if _running:
        logger.warning("pipeline.skip", extra={"reason": "previous run still in progress"})
        return
    _running = True

    try:
        if _registry is None or _db is None or _graph is None:
            logger.error("pipeline.not_initialized")
            return

        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        await start_pipeline_run(_db, run_id, trigger)
        await record_phase_start(_db, run_id, "collect")

        sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
        active_sources = [s for s in sources_cfg.sources if s.enabled]
        if source_filter:
            active_sources = [s for s in active_sources if s.id == source_filter]

        # ====== 图外：Collector + DB 查重（需要 DB 连接） ======
        raw_items, error_log = await collect_all(active_sources)
        await record_phase_end(_db, run_id, "collect", "done", f"collected {len(raw_items)} items")
        logger.info("collector.done", extra={"total": len(raw_items), "errors": len(error_log)})

        if not raw_items and error_log:
            summary = json.dumps({"collected": 0, "errors": error_log})
            await end_pipeline_run(_db, run_id, "failed", summary)
            return

        all_urls = [item.url for item in raw_items]
        existing = await batch_check_existing_urls(_db, all_urls)
        new_items = [item for item in raw_items if item.url not in existing]
        logger.info("collector.dedup", extra={"total": len(raw_items), "new": len(new_items), "skipped": len(raw_items) - len(new_items)})

        if not new_items:
            summary = json.dumps({"collected": {"total": len(raw_items), "new": 0}, "message": "all items already exist"})
            await end_pipeline_run(_db, run_id, "completed", summary)
            return

        # ====== 图内：Router → Fan-out(4×Analyzer) → Aggregator → Reviewer ======
        # 各节点内部记录 phase（route/analyze/aggregate/review）
        reset_analyzer_counter()
        state = PipelineState(raw_items=new_items, run_id=run_id, trigger=trigger, error_log=error_log)
        final_state = await _graph.ainvoke(state)

        # ====== Retry 循环（图外，最多 2 轮） ======
        all_reviewed = list(final_state["reviewed_items"])
        all_costs = list(final_state["cost_records"])
        all_analyzed = list(final_state["analyzed_items"])

        for retry_round in range(1, 3):  # 第 1、2 轮 retry
            retry_reviewed = [r for r in all_reviewed if r.verdict == "retry"]
            if not retry_reviewed:
                break

            # 找到对应的 analyzed items + raw items，递增 retry_count
            retry_raw_items = []
            retry_analyzed_items = []
            for rr in retry_reviewed:
                matched = next((a for a in all_analyzed if a.ref_url == rr.ref_url), None)
                raw = next((r for r in new_items if r.url == rr.ref_url), None)
                if matched and raw and matched.retry_count < 2:
                    matched.retry_count += 1
                    retry_raw_items.append(raw)
                    retry_analyzed_items.append(matched)

            if not retry_raw_items:
                break

            logger.info("pipeline.retry", extra={"round": retry_round, "items": len(retry_raw_items)})

            # 构建 retry state：直接跳过 Router，手动设置 routed_* 再跑图
            retry_state = PipelineState(raw_items=retry_raw_items, run_id=run_id, trigger=trigger)
            retry_state = retry_state.model_copy(update=await router_node(retry_state))
            reset_analyzer_counter()
            retry_result = await _graph.ainvoke(retry_state)

            # 合并结果（同一 ref_url 的 reviewed_item 用最新一轮的覆盖）
            existing_urls = {r.ref_url for r in all_reviewed}
            for r in retry_result["reviewed_items"]:
                if r.ref_url in existing_urls:
                    # 替换旧结果
                    all_reviewed = [x for x in all_reviewed if x.ref_url != r.ref_url]
                all_reviewed.append(r)
                existing_urls.add(r.ref_url)

            all_costs.extend(retry_result["cost_records"])
            all_analyzed.extend(retry_result["analyzed_items"])

        logger.info("pipeline.graph_done", extra={
            "analyzed": len(all_analyzed),
            "reviewed": len(all_reviewed),
            "llm_calls": len(all_costs),
        })

        # ====== 图外：入库（需要 DB 连接） ======
        passed_count = 0
        retry_count = 0
        discarded_count = 0

        for reviewed in all_reviewed:
            raw = next((r for r in new_items if r.url == reviewed.ref_url), None)
            analyzed = next((a for a in all_analyzed if a.ref_url == reviewed.ref_url), None)
            if raw is None or analyzed is None:
                continue

            if reviewed.verdict == "approved":
                article_id = await save_article(_db, raw, analyzed, reviewed, 0, 0)
                if article_id:
                    await save_tags(_db, article_id, analyzed.tags)
                passed_count += 1
            elif reviewed.verdict == "retry":
                if analyzed.retry_count >= 2:
                    discarded_count += 1
                else:
                    await save_article(_db, raw, analyzed, reviewed, 0, 0)
                    retry_count += 1
            else:  # discarded
                discarded_count += 1

        for record in all_costs:
            await save_cost_log(_db, run_id, record)

        summary = json.dumps({
            "collected": {"total": len(raw_items), "new": len(new_items)},
            "analyzed": len(all_analyzed),
            "approved": passed_count,
            "retry": retry_count,
            "discarded": discarded_count,
            "errors": error_log,
        })
        await end_pipeline_run(_db, run_id, "completed", summary)
        logger.info("pipeline.done", extra={
            "run_id": run_id,
            "passed": passed_count,
            "retry": retry_count,
            "discarded": discarded_count,
            "cost": sum(c.cost for c in all_costs),
        })

        # ====== 图外：备份 + 站点构建 ======
        await backup_database(_db, str(BACKUP_DIR))
        if _builder:
            await _builder.schedule()

    except Exception as e:
        logger.error("pipeline.failed", extra={"error": str(e)})
        await end_pipeline_run(_db, run_id, "failed", str(e)) if _db else None
    finally:
        _running = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _registry, _db, _scheduler, _builder, _graph

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    migrations_dir = BASE_DIR / "src" / "db" / "migrations"
    _db = Database(DB_PATH, migrations_dir)
    await _db.initialize()

    llm_cfg = load_llm_config(CONFIG_DIR / "llm.yaml")
    agents_cfg = load_agents_config(CONFIG_DIR / "agents.yaml")
    _registry = LLMRegistry(llm_cfg, agents_cfg)
    _graph = build_pipeline(_registry)

    set_db(_db)
    set_pipeline_db(_db)
    set_run_pipeline(run_pipeline)
    template_dir = BASE_DIR / "src" / "site" / "templates"
    site_builder = SiteBuilder(_db, OUTPUT_DIR, template_dir)
    _builder = DebouncedBuilder(site_builder, debounce_seconds=300)
    set_builder(_builder)

    # APScheduler
    sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
    _scheduler = AsyncIOScheduler()
    for source in sources_cfg.sources:
        if not source.enabled:
            continue
        parts = source.cron.strip().split()
        # 用 functools.partial 绑定 source_filter，每个 cron job 只采集自己的源
        from functools import partial
        _scheduler.add_job(
            partial(run_pipeline, source_filter=source.id),
            "cron",
            minute=parts[0], hour=parts[1], day=parts[2], month=parts[3], day_of_week=parts[4],
            id=f"collect-{source.id}",
        )
    _scheduler.start()

    yield

    if _scheduler:
        _scheduler.shutdown()
    if _db:
        await _db.close()


def create_app() -> FastAPI:
    from .api.routes import http_exception_handler, general_exception_handler

    app = FastAPI(lifespan=lifespan, title="AI Knowledge Base")
    app.include_router(router)
    app.include_router(config_router)
    app.include_router(stats_router)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)