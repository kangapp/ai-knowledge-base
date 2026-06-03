# src/main.py
import os, json, logging, sys, uuid
from pathlib import Path
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .core.config import load_llm_config, load_sources_config, load_agents_config
from .core.database import Database
from .core.llm_client import LLMRegistry
from .core.time import now_bj_iso, run_id_bj
from .graph.pipeline import build_pipeline, record_phase_start, record_phase_end, set_pipeline_db, reset_analyzer_counter
from .graph.state import PipelineState, ReviewedItem
from .graph.collector import collect_all
from .graph.reviewer import reviewer_node
from .api.routes import router, set_db, set_run_pipeline, set_builder
from .api.config import router as config_router
from .api.stats import router as stats_router
from .api.sources import router as sources_router
from .api.dashboard import router as dashboard_router
from .api.deep_reports import router as deep_reports_router, set_db as set_deep_reports_db
from .scheduler.source_scheduler import setup_source_scheduler
from .db.operations import (
    start_pipeline_run, end_pipeline_run, save_article, save_tags,
    save_cost_log, batch_check_existing_urls, backup_database,
    batch_save_github_snapshots, get_trending_repo_urls,
    record_collection_item, upsert_pipeline_source_run,
    record_pipeline_event,
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
            "ts": now_bj_iso(),
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
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO), handlers=[handler])
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


def _filter_sources(sources, source_filter: str | list[str] | tuple[str, ...] | set[str] | None):
    if source_filter is None:
        return sources
    if isinstance(source_filter, str):
        source_ids = {source_filter}
    else:
        source_ids = set(source_filter)
    return [source for source in sources if source.id in source_ids]


def _group_enabled_sources_by_cron(sources) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for source in sources:
        if not source.enabled:
            continue
        groups.setdefault(source.cron, []).append(source.id)
    return groups


def _source_filter_label(source_filter) -> str:
    if source_filter is None:
        return "all"
    if isinstance(source_filter, str):
        return source_filter
    return ",".join(source_filter)


def _source_filter_count(source_filter) -> int | None:
    if source_filter is None:
        return None
    if isinstance(source_filter, str):
        return 1
    return len(source_filter)


def _register_source_jobs(scheduler: AsyncIOScheduler, sources, run_pipeline_cb):
    for index, (cron, source_ids) in enumerate(_group_enabled_sources_by_cron(sources).items(), start=1):
        parts = cron.strip().split()
        scheduler.add_job(
            partial(run_pipeline_cb, source_filter=source_ids),
            "cron",
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            id=f"collect-group-{index}",
        )
        logger.info("scheduler.registered", extra={
            "job": f"collect-group-{index}",
            "cron": cron,
            "source_count": len(source_ids),
            "source_filter": ",".join(source_ids),
        })


def _apply_github_velocity_filter(raw_items: list, source, trending_urls: set[str]) -> list:
    return [
        item for item in raw_items
        if item.source != "github"
        or item.raw_metadata.get("source_id") != source.id
        or item.url in trending_urls
    ]


def _build_cost_source_map(items: list) -> dict[str, tuple[str, str, str]]:
    source_map = {}
    for item in items:
        source_id = item.raw_metadata.get("source_id") or item.source_detail or item.source
        source_map[item.url] = (item.source, item.source_detail, source_id)
    return source_map


def _summarize_item_costs(cost_records: list) -> dict[str, tuple[float, int]]:
    summary: dict[str, tuple[float, int]] = {}
    for record in cost_records:
        if not record.ref_url:
            continue
        cost, tokens = summary.get(record.ref_url, (0.0, 0))
        summary[record.ref_url] = (
            round(cost + record.cost, 10),
            tokens + record.tokens_in + record.tokens_out,
        )
    return summary


def _source_identity(item) -> tuple[str, str, str]:
    source_id = item.raw_metadata.get("source_id") or item.source_detail or item.source
    return source_id, item.source, item.source_detail


def _build_pipeline_source_summaries(
    *,
    run_id: str,
    raw_items: list,
    new_items: list,
    analyzed_items: list,
    reviewed_items: list,
    cost_records: list,
    inserted_urls: set[str],
    failed_counts: dict[str, int] | None = None,
) -> list[dict]:
    summaries: dict[str, dict] = {}

    def ensure(source_id: str, source: str, source_detail: str) -> dict:
        if source_id not in summaries:
            summaries[source_id] = {
                "run_id": run_id,
                "source_id": source_id,
                "source": source,
                "source_detail": source_detail,
                "collected": 0,
                "new_items": 0,
                "dedup_skipped": 0,
                "analyzed": 0,
                "analysis_failed": 0,
                "approved": 0,
                "retry": 0,
                "discarded": 0,
                "inserted": 0,
                "failed": 0,
                "cost": 0.0,
                "tokens": 0,
                "filtered_items": 0,
                "request_success_rate": 0,
                "insert_rate": 0,
            }
        return summaries[source_id]

    url_to_source: dict[str, tuple[str, str, str]] = {}
    for item in raw_items:
        source_id, source, source_detail = _source_identity(item)
        url_to_source[item.url] = (source_id, source, source_detail)
        ensure(source_id, source, source_detail)["collected"] += 1

    new_urls = {item.url for item in new_items}
    for item in new_items:
        source_id, source, source_detail = _source_identity(item)
        ensure(source_id, source, source_detail)["new_items"] += 1

    for item in raw_items:
        if item.url not in new_urls:
            source_id, source, source_detail = _source_identity(item)
            ensure(source_id, source, source_detail)["dedup_skipped"] += 1

    for item in analyzed_items:
        mapping = url_to_source.get(item.ref_url)
        if mapping:
            ensure(*mapping)["analyzed"] += 1

    for item in new_items:
        if item.url not in {analyzed.ref_url for analyzed in analyzed_items}:
            source_id, source, source_detail = _source_identity(item)
            ensure(source_id, source, source_detail)["analysis_failed"] += 1

    for reviewed in reviewed_items:
        mapping = url_to_source.get(reviewed.ref_url)
        if not mapping:
            continue
        summary = ensure(*mapping)
        if reviewed.verdict == "approved":
            summary["approved"] += 1
        elif reviewed.verdict == "retry":
            summary["retry"] += 1
        else:
            summary["discarded"] += 1

    for url in inserted_urls:
        mapping = url_to_source.get(url)
        if mapping:
            ensure(*mapping)["inserted"] += 1

    for record in cost_records:
        source_id = record.source_id
        source = record.source
        source_detail = record.source_detail
        if not source_id and record.ref_url in url_to_source:
            source_id, source, source_detail = url_to_source[record.ref_url]
        if not source_id:
            continue
        summary = ensure(source_id, source or source_id, source_detail or "")
        summary["cost"] = round(summary["cost"] + record.cost, 10)
        summary["tokens"] += record.tokens_in + record.tokens_out

    for source_id, count in (failed_counts or {}).items():
        summary = ensure(source_id, source_id, "")
        summary["failed"] += count

    for summary in summaries.values():
        summary["filtered_items"] = summary["retry"] + summary["discarded"]
        attempts = summary["collected"] + summary["failed"]
        summary["request_success_rate"] = round(summary["collected"] / attempts, 3) if attempts else 0
        summary["insert_rate"] = round(summary["inserted"] / summary["new_items"], 3) if summary["new_items"] else 0

    return list(summaries.values())


def _prepare_retry_review_items(
    retry_reviewed: list[ReviewedItem],
    analyzed_items: list,
    raw_items: list,
) -> list:
    retry_items = []
    raw_urls = {item.url for item in raw_items}
    for reviewed in retry_reviewed:
        if reviewed.ref_url not in raw_urls:
            continue
        matched = next((item for item in analyzed_items if item.ref_url == reviewed.ref_url), None)
        if matched and matched.retry_count < 2:
            matched.retry_count += 1
            retry_items.append(matched)
    return retry_items


def _merge_retry_review_result(
    all_reviewed: list[ReviewedItem],
    all_costs: list,
    retry_result: dict,
) -> list[ReviewedItem]:
    existing_urls = {item.ref_url for item in all_reviewed}
    for item in retry_result.get("reviewed_items", []):
        if item.ref_url in existing_urls:
            all_reviewed = [current for current in all_reviewed if current.ref_url != item.ref_url]
        all_reviewed.append(item)
        existing_urls.add(item.ref_url)
    all_costs.extend(retry_result.get("cost_records", []))
    return all_reviewed


async def _record_collected_items(db, run_id: str, items: list, status: str, reason: str):
    for item in items:
        source_id, source, source_detail = _source_identity(item)
        await record_collection_item(
            db,
            run_id=run_id,
            url=item.url,
            title=item.title,
            source=source,
            source_id=source_id,
            source_detail=source_detail,
            status=status,
            reason=reason,
            raw_metadata=item.raw_metadata,
        )


async def _record_source_summaries(
    db,
    *,
    run_id: str,
    raw_items: list,
    new_items: list,
    analyzed_items: list,
    reviewed_items: list,
    cost_records: list,
    inserted_urls: set[str],
    error_log: list[dict],
):
    failed_counts: dict[str, int] = {}
    for error in error_log:
        source_id = error.get("source")
        if source_id:
            failed_counts[source_id] = failed_counts.get(source_id, 0) + 1
    summaries = _build_pipeline_source_summaries(
        run_id=run_id,
        raw_items=raw_items,
        new_items=new_items,
        analyzed_items=analyzed_items,
        reviewed_items=reviewed_items,
        cost_records=cost_records,
        inserted_urls=inserted_urls,
        failed_counts=failed_counts,
    )
    for summary in summaries:
        await upsert_pipeline_source_run(db, summary)
    await db.commit()


async def run_pipeline(trigger: str = "cron", source_filter: str | list[str] | tuple[str, ...] | set[str] | None = None):
    """source_filter 为 None 时采集所有源；否则采集指定 source.id 或一组 source.id。"""
    global _registry, _db, _builder, _running, _graph

    if _running:
        logger.warning("pipeline.skip", extra={
            "reason": "previous run still in progress",
            "source_filter": _source_filter_label(source_filter),
            "source_count": _source_filter_count(source_filter),
        })
        return
    _running = True

    run_id: str | None = None

    try:
        if _registry is None or _db is None or _graph is None:
            logger.error("pipeline.not_initialized")
            return

        run_id = run_id_bj()
        await start_pipeline_run(_db, run_id, trigger)
        await record_phase_start(_db, run_id, "collect")

        sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
        active_sources = [s for s in sources_cfg.sources if s.enabled]
        active_sources = _filter_sources(active_sources, source_filter)
        logger.info("pipeline.start", extra={
            "run_id": run_id,
            "trigger": trigger,
            "source_filter": _source_filter_label(source_filter),
            "source_count": len(active_sources),
            "sources": [source.id for source in active_sources],
        })

        # ====== 图外：Collector + DB 查重（需要 DB 连接） ======
        raw_items, error_log = await collect_all(_db, active_sources)
        await _record_collected_items(_db, run_id, raw_items, "collected", "collector")
        for error in error_log:
            await record_pipeline_event(
                _db,
                run_id=run_id,
                phase="collect",
                event="collector.source_error",
                level="error",
                status="failed",
                source_id=error.get("source", ""),
                message=error.get("error", "source collect failed"),
                payload=error,
            )
        await record_phase_end(_db, run_id, "collect", "done", f"collected {len(raw_items)} items")
        await record_pipeline_event(
            _db,
            run_id=run_id,
            phase="collect",
            event="collector.done",
            level="success",
            status="done",
            message=f"采集完成：{len(raw_items)} 条",
            payload={"total": len(raw_items), "errors": len(error_log)},
        )
        logger.info("collector.done", extra={"total": len(raw_items), "errors": len(error_log)})

        # 记录 GitHub repo 快照
        github_items = [i for i in raw_items if i.source == "github"]
        if github_items:
            await batch_save_github_snapshots(_db, github_items)

        # 趋势筛选（对 trend_mode=true 的源）
        for src in active_sources:
            if src.type == "github" and src.config.get("trend_mode"):
                min_vel = src.config.get("trend_velocity_threshold", 5)
                trending = await get_trending_repo_urls(_db, min_vel, days=7)
                raw_items = _apply_github_velocity_filter(raw_items, src, trending)

        if not raw_items and error_log:
            await _record_source_summaries(
                _db,
                run_id=run_id,
                raw_items=[],
                new_items=[],
                analyzed_items=[],
                reviewed_items=[],
                cost_records=[],
                inserted_urls=set(),
                error_log=error_log,
            )
            summary = json.dumps({"collected": 0, "errors": error_log})
            await end_pipeline_run(_db, run_id, "failed", summary)
            return

        all_urls = [item.url for item in raw_items]
        existing = await batch_check_existing_urls(_db, all_urls)
        new_items = [item for item in raw_items if item.url not in existing]
        skipped_items = [item for item in raw_items if item.url in existing]
        await _record_collected_items(_db, run_id, skipped_items, "dedup_skipped", "url_exists")
        for item in skipped_items:
            source_id, source, source_detail = _source_identity(item)
            await record_pipeline_event(
                _db,
                run_id=run_id,
                phase="collect",
                event="collector.item_dedup_skipped",
                level="info",
                status="skipped",
                source_id=source_id,
                source=source,
                source_detail=source_detail,
                ref_url=item.url,
                title=item.title,
                message="URL 已存在，跳过 LLM",
            )
        logger.info("collector.dedup", extra={"total": len(raw_items), "new": len(new_items), "skipped": len(raw_items) - len(new_items)})
        await record_pipeline_event(
            _db,
            run_id=run_id,
            phase="collect",
            event="collector.dedup_done",
            level="success",
            status="done",
            message=f"去重完成：新 {len(new_items)}，跳过 {len(skipped_items)}",
            payload={"new": len(new_items), "skipped": len(skipped_items)},
        )

        if not new_items:
            await _record_source_summaries(
                _db,
                run_id=run_id,
                raw_items=raw_items,
                new_items=[],
                analyzed_items=[],
                reviewed_items=[],
                cost_records=[],
                inserted_urls=set(),
                error_log=error_log,
            )
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

            retry_analyzed_items = _prepare_retry_review_items(retry_reviewed, all_analyzed, new_items)
            if not retry_analyzed_items:
                break

            logger.info("pipeline.retry", extra={
                "round": retry_round,
                "items": len(retry_analyzed_items),
                "mode": "review_only",
            })
            await record_pipeline_event(
                _db,
                run_id=run_id,
                phase="review",
                event="reviewer.round_start",
                status="running",
                message=f"开始第 {retry_round} 轮重审：{len(retry_analyzed_items)} 条",
                payload={"round": retry_round, "items": len(retry_analyzed_items), "mode": "review_only"},
            )

            retry_state = PipelineState(
                raw_items=[],
                analyzed_items=retry_analyzed_items,
                run_id=run_id,
                trigger=trigger,
            )
            await record_phase_start(_db, run_id, "review")
            retry_result = await reviewer_node(retry_state, _registry)
            reviewed = retry_result.get("reviewed_items", [])
            total_cost = sum(c.cost for c in retry_result.get("cost_records", []))
            await record_phase_end(
                _db,
                run_id,
                "review",
                "done",
                (
                    f"approved:{sum(1 for r in reviewed if r.verdict == 'approved')}, "
                    f"retry:{sum(1 for r in reviewed if r.verdict == 'retry')}, "
                    f"discarded:{sum(1 for r in reviewed if r.verdict == 'discarded')}, "
                    f"cost:${total_cost:.6f}, mode:review_only"
                ),
            )
            await record_pipeline_event(
                _db,
                run_id=run_id,
                phase="review",
                event="reviewer.round_done",
                level="success",
                status="done",
                cost=total_cost,
                message=f"第 {retry_round} 轮重审完成",
                payload={
                    "round": retry_round,
                    "approved": sum(1 for r in reviewed if r.verdict == "approved"),
                    "retry": sum(1 for r in reviewed if r.verdict == "retry"),
                    "discarded": sum(1 for r in reviewed if r.verdict == "discarded"),
                    "mode": "review_only",
                },
            )

            # 合并结果（同一 ref_url 的 reviewed_item 用最新一轮的覆盖）
            all_reviewed = _merge_retry_review_result(all_reviewed, all_costs, retry_result)

        logger.info("pipeline.graph_done", extra={
            "analyzed": len(all_analyzed),
            "reviewed": len(all_reviewed),
            "llm_calls": len(all_costs),
        })

        # ====== 图外：入库（需要 DB 连接） ======
        passed_count = 0
        retry_count = 0
        discarded_count = 0
        inserted_urls: set[str] = set()
        cost_source_map = _build_cost_source_map(new_items)
        item_costs = _summarize_item_costs(all_costs)

        for reviewed in all_reviewed:
            raw = next((r for r in new_items if r.url == reviewed.ref_url), None)
            analyzed = next((a for a in all_analyzed if a.ref_url == reviewed.ref_url), None)
            if raw is None or analyzed is None:
                continue

            if reviewed.verdict == "approved":
                analysis_cost, analysis_tokens = item_costs.get(reviewed.ref_url, (0.0, 0))
                article_id = await save_article(_db, raw, analyzed, reviewed, analysis_cost, analysis_tokens)
                if article_id:
                    inserted_urls.add(reviewed.ref_url)
                    source_id, source, source_detail = _source_identity(raw)
                    await record_collection_item(
                        _db,
                        run_id=run_id,
                        url=raw.url,
                        title=raw.title,
                        source=source,
                        source_id=source_id,
                        source_detail=source_detail,
                        status="inserted",
                        reason="approved",
                        raw_metadata=raw.raw_metadata,
                        article_id=article_id,
                    )
                    tags = list(analyzed.tags)
                    if raw.source == "github" and raw.raw_metadata.get("source_id"):
                        src_id = raw.raw_metadata["source_id"]
                        if "hot" in src_id or "trending_hot" in src_id:
                            tags.append("热门")
                        elif "velocity" in src_id or "trending_velocity" in src_id:
                            tags.append("趋势")
                    await save_tags(_db, article_id, tags)
                    await record_pipeline_event(
                        _db,
                        run_id=run_id,
                        phase="persist",
                        event="pipeline.persist_inserted",
                        level="success",
                        status="inserted",
                        source_id=source_id,
                        source=source,
                        source_detail=source_detail,
                        ref_url=raw.url,
                        title=analyzed.title,
                        cost=analysis_cost,
                        tokens=analysis_tokens,
                        message="文章已入库",
                        payload={"article_id": article_id, "score": reviewed.total_score},
                    )
                passed_count += 1
            elif reviewed.verdict == "retry":
                if analyzed.retry_count >= 2:
                    source_id, source, source_detail = _source_identity(raw)
                    await record_pipeline_event(
                        _db,
                        run_id=run_id,
                        phase="persist",
                        event="pipeline.persist_discarded",
                        level="warning",
                        status="discarded",
                        source_id=source_id,
                        source=source,
                        source_detail=source_detail,
                        ref_url=raw.url,
                        title=analyzed.title,
                        message="达到最大重试次数后丢弃",
                        payload={"score": reviewed.total_score, "retry_count": analyzed.retry_count},
                    )
                    discarded_count += 1
                else:
                    analysis_cost, analysis_tokens = item_costs.get(reviewed.ref_url, (0.0, 0))
                    await save_article(_db, raw, analyzed, reviewed, analysis_cost, analysis_tokens)
                    source_id, source, source_detail = _source_identity(raw)
                    await record_collection_item(
                        _db,
                        run_id=run_id,
                        url=raw.url,
                        title=raw.title,
                        source=source,
                        source_id=source_id,
                        source_detail=source_detail,
                        status="reviewed_retry",
                        reason="retry",
                        raw_metadata=raw.raw_metadata,
                    )
                    await record_pipeline_event(
                        _db,
                        run_id=run_id,
                        phase="persist",
                        event="pipeline.persist_retry",
                        level="warning",
                        status="retry",
                        source_id=source_id,
                        source=source,
                        source_detail=source_detail,
                        ref_url=raw.url,
                        title=analyzed.title,
                        cost=analysis_cost,
                        tokens=analysis_tokens,
                        message="文章保留为 retry",
                        payload={"score": reviewed.total_score, "retry_count": analyzed.retry_count},
                    )
                    retry_count += 1
            else:  # discarded
                source_id, source, source_detail = _source_identity(raw)
                await record_collection_item(
                    _db,
                    run_id=run_id,
                    url=raw.url,
                    title=raw.title,
                    source=source,
                    source_id=source_id,
                    source_detail=source_detail,
                    status="reviewed_discarded",
                    reason="discarded",
                    raw_metadata=raw.raw_metadata,
                )
                await record_pipeline_event(
                    _db,
                    run_id=run_id,
                    phase="persist",
                    event="pipeline.persist_discarded",
                    level="warning",
                    status="discarded",
                    source_id=source_id,
                    source=source,
                    source_detail=source_detail,
                    ref_url=raw.url,
                    title=analyzed.title,
                    message="审核未通过，丢弃",
                    payload={"score": reviewed.total_score},
                )
                discarded_count += 1

        for record in all_costs:
            if not record.source and record.ref_url in cost_source_map:
                record.source, record.source_detail, record.source_id = cost_source_map[record.ref_url]
            await save_cost_log(_db, run_id, record)

        await _record_source_summaries(
            _db,
            run_id=run_id,
            raw_items=raw_items,
            new_items=new_items,
            analyzed_items=all_analyzed,
            reviewed_items=all_reviewed,
            cost_records=all_costs,
            inserted_urls=inserted_urls,
            error_log=error_log,
        )

        summary = json.dumps({
            "collected": {"total": len(raw_items), "new": len(new_items)},
            "analyzed": len(all_analyzed),
            "approved": passed_count,
            "retry": retry_count,
            "discarded": discarded_count,
            "errors": error_log,
        })
        await end_pipeline_run(_db, run_id, "completed", summary)
        await record_pipeline_event(
            _db,
            run_id=run_id,
            phase="pipeline",
            event="pipeline.done",
            level="success",
            status="completed",
            cost=sum(c.cost for c in all_costs),
            message="流水线完成",
            payload={
                "approved": passed_count,
                "retry": retry_count,
                "discarded": discarded_count,
                "analyzed": len(all_analyzed),
            },
        )
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
            await record_pipeline_event(
                _db,
                run_id=run_id,
                phase="build",
                event="site.build_queued",
                status="queued",
                message="静态站构建已排队",
            )
            await _builder.schedule()

    except Exception as e:
        logger.error("pipeline.failed", extra={"error": str(e)})
        if _db and run_id:
            await record_pipeline_event(
                _db,
                run_id=run_id,
                phase="pipeline",
                event="pipeline.failed",
                level="error",
                status="failed",
                message=str(e),
            )
            await end_pipeline_run(_db, run_id, "failed", str(e))
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
    _registry.health._db = _db
    _graph = build_pipeline(_registry)

    set_db(_db)
    set_deep_reports_db(_db)
    set_pipeline_db(_db)
    set_run_pipeline(run_pipeline)
    template_dir = BASE_DIR / "src" / "site" / "templates"
    site_builder = SiteBuilder(_db, OUTPUT_DIR, template_dir)
    _builder = DebouncedBuilder(site_builder, debounce_seconds=300)
    set_builder(_builder)

    # APScheduler
    sources_cfg = load_sources_config(CONFIG_DIR / "sources.yaml")
    _scheduler = AsyncIOScheduler()
    _register_source_jobs(_scheduler, sources_cfg.sources, run_pipeline)
    _scheduler.start()
    setup_source_scheduler(_scheduler)

    yield

    if _scheduler:
        _scheduler.shutdown()
    if _db:
        await _db.close()


def create_app() -> FastAPI:
    from .api.routes import (
        general_exception_handler,
        http_exception_handler,
        validation_exception_handler,
    )

    app = FastAPI(lifespan=lifespan, title="AI Knowledge Base")
    app.include_router(router)
    app.include_router(config_router)
    app.include_router(stats_router)
    app.include_router(sources_router)
    app.include_router(dashboard_router)
    app.include_router(deep_reports_router, prefix="/api")
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
