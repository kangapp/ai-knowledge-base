import asyncio
import logging
from urllib.parse import urlparse

from src.core.database import Database
from src.core.llm_client import LLMRegistry
from src.db.operations import record_pipeline_event, save_cost_log, save_deep_report
from src.graph.state import AnalyzedItem, RawItem, ReviewedItem

from .analyzer import analyze_deep_report
from .inspector import clone_and_inspect
from .models import DeepReportCandidate, DeepReportOutput, DeepReportStageResult, SourcePackage
from .selector import select_deep_report_candidate
from .summarizer import build_source_package

logger = logging.getLogger("pipeline")


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if netloc == "github.com":
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
            path = f"/{parts[0]}/{repo}"
    return f"{scheme}://{netloc}{path}" if netloc else url.rstrip("/")


def _resolve_article_id(candidate: DeepReportCandidate, raw_items: list[RawItem], article_ids: dict[str, int] | None) -> int | None:
    if candidate.article_id is not None:
        return candidate.article_id
    if not article_ids:
        return None

    normalized_map = {
        _normalize_url(url): article_id
        for url, article_id in article_ids.items()
        if url and article_id is not None
    }
    candidates = [candidate.repo_url]
    candidates.extend(item.url for item in raw_items if _normalize_url(item.url) == candidate.repo_url)

    for url in candidates:
        if url in article_ids:
            return article_ids[url]
        normalized = _normalize_url(url)
        if normalized in normalized_map:
            return normalized_map[normalized]
    return None


def _sum_costs(cost_records: list) -> tuple[float, int]:
    total_cost = round(sum(record.cost for record in cost_records), 10)
    total_tokens = sum(record.tokens_in + record.tokens_out for record in cost_records)
    return total_cost, total_tokens


def _failed_message(cost_records: list) -> str:
    if not cost_records:
        return "deep_report_failed"
    last = cost_records[-1]
    return last.error or last.status or "deep_report_failed"


def render_report_markdown(report: DeepReportOutput, source_package: SourcePackage) -> str:
    stack_lines = []
    if report.tech_stack:
        stack_lines.extend(f"- {item}" for item in report.tech_stack)
    for group, values in source_package.tech_stack.items():
        if not values:
            continue
        stack_lines.append(f"- {group}: {', '.join(values)}")

    evidence_lines = [
        f"- `{item.path}`: {item.reason}"
        for item in report.source_evidence
    ]

    return "\n".join(
        [
            f"# {report.title}",
            "",
            "## 概述",
            report.summary,
            "",
            "## 技术栈",
            *(stack_lines or ["- 无"]),
            "",
            "## 架构",
            f"- 模式: {report.architecture.pattern}",
            *(f"- 组件: {component}" for component in report.architecture.components),
            "",
            "## 数据流",
            *(f"- {item}" for item in report.data_flow),
            "",
            "## 场景",
            *(f"- {item}" for item in report.use_cases),
            "",
            "## 优势",
            *(f"- {item}" for item in report.strengths),
            "",
            "## 局限",
            *(f"- {item}" for item in report.limitations),
            "",
            "## 建议",
            *(f"- {item}" for item in report.actionable_takeaways),
            "",
            "## 证据",
            *(evidence_lines or ["- 无"]),
        ]
    )


async def _persist_cost_records(db: Database, run_id: str, cost_records: list) -> None:
    for cost_record in cost_records:
        await save_cost_log(db, run_id, cost_record)


async def _save_failed_report(
    db: Database,
    *,
    run_id: str,
    candidate: DeepReportCandidate,
    source_package: SourcePackage | None,
    cost_records: list,
    error: str,
) -> int | None:
    report_json = {}
    evidence_json = []
    tech_stack_json = {}
    file_tree_summary = ""
    commit_sha = ""

    if source_package is not None:
        report_json = {"source_package": source_package.model_dump(mode="json")}
        evidence_json = list(source_package.evidence)
        tech_stack_json = dict(source_package.tech_stack)
        file_tree_summary = source_package.file_tree_summary
        commit_sha = source_package.commit_sha

    total_cost, total_tokens = _sum_costs(cost_records)
    return await save_deep_report(
        db,
        repo_url=candidate.repo_url,
        repo_name=candidate.repo_name,
        article_id=candidate.article_id,
        run_id=run_id,
        commit_sha=commit_sha,
        status="failed",
        candidate_score=candidate.candidate_score,
        trigger_reason=candidate.trigger_reason,
        report_json=report_json,
        report_markdown="",
        evidence_json=evidence_json,
        tech_stack_json=tech_stack_json,
        file_tree_summary=file_tree_summary,
        analysis_cost=total_cost,
        analysis_tokens=total_tokens,
        error=error,
    )


async def _record_failed_event_safely(
    db: Database,
    *,
    run_id: str,
    candidate: DeepReportCandidate | None,
    cost_records: list,
    message: str,
    report_id: int | None,
) -> None:
    total_cost, total_tokens = _sum_costs(cost_records)
    try:
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.failed",
            level="error",
            status="failed",
            source_id=candidate.source_id if candidate else "",
            source="github" if candidate else "",
            source_detail=candidate.source_detail if candidate else "",
            ref_url=candidate.repo_url if candidate else "",
            title=candidate.title if candidate else "",
            cost=total_cost,
            tokens=total_tokens,
            message=message,
            payload={"report_id": report_id},
        )
    except Exception:
        logger.exception(
            "deep_report.failed_event_failed",
            extra={"run_id": run_id, "repo_url": candidate.repo_url if candidate else ""},
        )


async def _record_completed_event_safely(
    db: Database,
    *,
    run_id: str,
    candidate: DeepReportCandidate,
    total_cost: float,
    total_tokens: int,
    report_id: int,
) -> None:
    try:
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.persist_done",
            level="success",
            status="completed",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.source_detail,
            ref_url=candidate.repo_url,
            title=candidate.title,
            cost=total_cost,
            tokens=total_tokens,
            message="深度报告已保存",
            payload={"report_id": report_id, "candidate_score": candidate.candidate_score},
        )
    except Exception:
        logger.exception(
            "deep_report.completed_event_failed",
            extra={"run_id": run_id, "repo_url": candidate.repo_url, "report_id": report_id},
        )


async def _finalize_failure(
    db: Database,
    *,
    run_id: str,
    candidate: DeepReportCandidate | None,
    source_package: SourcePackage | None,
    cost_records: list,
    message: str,
) -> DeepReportStageResult:
    report_id = None
    if candidate is not None:
        try:
            report_id = await _save_failed_report(
                db,
                run_id=run_id,
                candidate=candidate,
                source_package=source_package,
                cost_records=cost_records,
                error=message,
            )
        except Exception:
            logger.exception(
                "deep_report.persist_failed",
                extra={"run_id": run_id, "repo_url": candidate.repo_url},
            )
    await _record_failed_event_safely(
        db,
        run_id=run_id,
        candidate=candidate,
        cost_records=cost_records,
        message=message,
        report_id=report_id,
    )
    return DeepReportStageResult(
        status="failed",
        report_id=report_id,
        repo_url=candidate.repo_url if candidate else "",
        message=message,
    )


async def run_deep_report_stage(
    db: Database,
    registry: LLMRegistry | None,
    run_id: str,
    raw_items: list[RawItem],
    analyzed_items: list[AnalyzedItem],
    reviewed_items: list[ReviewedItem],
    article_ids: dict[str, int] | None = None,
    clone_and_inspect_fn=clone_and_inspect,
    analyze_fn=analyze_deep_report,
) -> DeepReportStageResult:
    candidate: DeepReportCandidate | None = None
    source_package: SourcePackage | None = None
    cost_records: list = []

    try:
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.selector_start",
            status="running",
            message="开始选择深度报告候选",
        )
        candidate = await select_deep_report_candidate(db, raw_items, analyzed_items, reviewed_items)
        if candidate is None:
            await record_pipeline_event(
                db,
                run_id=run_id,
                phase="deep_report",
                event="deep.selector_skipped",
                status="skipped",
                message="没有满足条件的深度报告候选",
            )
            return DeepReportStageResult(status="skipped", message="no candidate")

        resolved_article_id = _resolve_article_id(candidate, raw_items, article_ids)
        if resolved_article_id is not None:
            candidate = candidate.model_copy(update={"article_id": resolved_article_id})

        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.clone_start",
            status="running",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.source_detail,
            ref_url=candidate.repo_url,
            title=candidate.title,
            message="开始 clone 并扫描仓库",
        )
        inspection = await asyncio.to_thread(clone_and_inspect_fn, candidate.repo_url, candidate.repo_name)
        source_package = build_source_package(inspection)
        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.scan_done",
            level="success",
            status="done",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.source_detail,
            ref_url=candidate.repo_url,
            title=candidate.title,
            message="源码扫描完成",
            payload={
                "commit_sha": source_package.commit_sha,
                "key_file_count": len(source_package.key_files),
            },
        )

        if registry is None or analyze_fn is None:
            raise RuntimeError("deep_report is not configured")

        await record_pipeline_event(
            db,
            run_id=run_id,
            phase="deep_report",
            event="deep.analyze_start",
            status="running",
            source_id=candidate.source_id,
            source="github",
            source_detail=candidate.source_detail,
            ref_url=candidate.repo_url,
            title=candidate.title,
            message="开始生成深度报告",
        )
        report, cost_records = await analyze_fn(candidate, source_package, registry)
        await _persist_cost_records(db, run_id, cost_records)

        total_cost, total_tokens = _sum_costs(cost_records)
        if report is None:
            error = _failed_message(cost_records)
            return await _finalize_failure(
                db,
                run_id=run_id,
                candidate=candidate,
                source_package=source_package,
                cost_records=cost_records,
                message=error,
            )

        report_id = await save_deep_report(
            db,
            repo_url=candidate.repo_url,
            repo_name=candidate.repo_name,
            article_id=candidate.article_id,
            run_id=run_id,
            commit_sha=source_package.commit_sha,
            status="completed",
            candidate_score=candidate.candidate_score,
            trigger_reason=candidate.trigger_reason,
            report_json=report.model_dump(mode="json"),
            report_markdown=render_report_markdown(report, source_package),
            evidence_json=[item.model_dump(mode="json") for item in report.source_evidence],
            tech_stack_json=source_package.tech_stack,
            file_tree_summary=source_package.file_tree_summary,
            analysis_cost=total_cost,
            analysis_tokens=total_tokens,
            error="",
        )
        await _record_completed_event_safely(
            db,
            run_id=run_id,
            candidate=candidate,
            total_cost=total_cost,
            total_tokens=total_tokens,
            report_id=report_id,
        )
        return DeepReportStageResult(
            status="completed",
            report_id=report_id,
            repo_url=candidate.repo_url,
        )
    except Exception as exc:
        return await _finalize_failure(
            run_id=run_id,
            db=db,
            candidate=candidate,
            source_package=source_package,
            cost_records=cost_records,
            message=str(exc),
        )
