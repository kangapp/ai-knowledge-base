import argparse
import asyncio
import json
import logging
import uuid
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

from src.core.config import load_agents_config, load_llm_config
from src.core.database import Database
from src.core.llm_client import LLMRegistry
from src.core.time import run_id_bj
from src.db.operations import (
    delete_failed_deep_reports_for_repo,
    end_pipeline_run,
    list_deep_reports_for_rebuild,
    save_cost_log,
    save_deep_report,
    start_pipeline_run,
    switch_public_deep_reports_to_v2,
)
from src.site.builder import SiteBuilder

from .analyzer import analyze_deep_report
from .inspector import clone_and_inspect
from .models import DeepReportCandidate, SourcePackage
from .service import render_report_markdown
from .summarizer import build_source_package

logger = logging.getLogger(__name__)


class RebuildResult(BaseModel):
    planned: int
    completed: int
    failed: list[str]
    switched: bool


def _candidate_from_row(row: dict) -> DeepReportCandidate:
    report_json = row.get("report_json") or {}
    return DeepReportCandidate(
        repo_url=row["repo_url"],
        repo_name=row["repo_name"],
        article_id=row.get("article_id"),
        title=row["repo_name"],
        summary=str(report_json.get("summary") or ""),
        reviewer_score=0,
        candidate_score=int(row.get("candidate_score") or 0),
        trigger_reason=str(row.get("trigger_reason") or "deep report rebuild"),
        metadata={"rebuild_from_report_id": row["id"]},
    )


def _cost_totals(cost_records: list) -> tuple[float, int]:
    total_cost = round(sum(record.cost for record in cost_records), 10)
    total_tokens = sum(record.tokens_in + record.tokens_out for record in cost_records)
    return total_cost, total_tokens


async def _save_attempt_costs(
    db: Database,
    run_id: str,
    cost_records: list,
) -> tuple[float, int]:
    for record in cost_records:
        await save_cost_log(db, run_id, record)
    return _cost_totals(cost_records)


async def _save_failed_rebuild(
    db: Database,
    *,
    run_id: str,
    row: dict,
    candidate: DeepReportCandidate,
    source_package: SourcePackage | None,
    cost_records: list,
    error: str,
) -> None:
    total_cost, total_tokens = _cost_totals(cost_records)
    await save_deep_report(
        db,
        repo_url=candidate.repo_url,
        repo_name=candidate.repo_name,
        article_id=candidate.article_id,
        run_id=run_id,
        commit_sha=(
            source_package.commit_sha
            if source_package is not None
            else str(row.get("commit_sha") or "")
        ),
        status="failed",
        candidate_score=candidate.candidate_score,
        trigger_reason=candidate.trigger_reason,
        report_json=(
            {"source_package": source_package.model_dump(mode="json")}
            if source_package is not None
            else {}
        ),
        report_markdown="",
        evidence_json=(
            list(source_package.evidence)
            if source_package is not None
            else []
        ),
        tech_stack_json=(
            dict(source_package.tech_stack)
            if source_package is not None
            else {}
        ),
        file_tree_summary=(
            source_package.file_tree_summary
            if source_package is not None
            else ""
        ),
        analysis_cost=total_cost,
        analysis_tokens=total_tokens,
        error=error,
        report_version=2,
    )


async def rebuild_deep_reports(
    db: Database,
    registry: LLMRegistry | None,
    *,
    dry_run: bool,
    max_reports: int | None,
    repo_url: str | None,
    max_cost: float | None = None,
    clone_and_inspect_fn=clone_and_inspect,
    analyze_fn=analyze_deep_report,
) -> RebuildResult:
    rows = await list_deep_reports_for_rebuild(
        db,
        repo_url=repo_url,
        limit=max_reports,
    )
    result = RebuildResult(
        planned=len(rows),
        completed=0,
        failed=[],
        switched=False,
    )
    if dry_run:
        return result
    if registry is None:
        raise RuntimeError("deep_report rebuild requires an LLM registry")

    run_id = f"{run_id_bj('deep_rebuild')}_{uuid.uuid4().hex[:8]}"
    await start_pipeline_run(db, run_id, "deep_report_rebuild")
    total_cost = 0.0
    cost_limit_reached = False

    try:
        for row in rows:
            candidate = _candidate_from_row(row)
            source_package = None
            cost_records = []
            try:
                inspection = await asyncio.to_thread(
                    clone_and_inspect_fn,
                    candidate.repo_url,
                    candidate.repo_name,
                )
                source_package = build_source_package(inspection)
                report, cost_records = await analyze_fn(
                    candidate,
                    source_package,
                    registry,
                )
                attempt_cost, total_tokens = await _save_attempt_costs(
                    db,
                    run_id,
                    cost_records,
                )
                total_cost += attempt_cost
                if report is None:
                    error = (
                        cost_records[-1].error or cost_records[-1].status
                        if cost_records
                        else "deep_report_failed"
                    )
                    await _save_failed_rebuild(
                        db,
                        run_id=run_id,
                        row=row,
                        candidate=candidate,
                        source_package=source_package,
                        cost_records=cost_records,
                        error=error,
                    )
                    result.failed.append(candidate.repo_url)
                else:
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
                        report_markdown=render_report_markdown(
                            report,
                            source_package,
                        ),
                        evidence_json=[
                            item.model_dump(mode="json")
                            for item in report.source_evidence
                        ],
                        tech_stack_json=source_package.tech_stack,
                        file_tree_summary=source_package.file_tree_summary,
                        analysis_cost=attempt_cost,
                        analysis_tokens=total_tokens,
                        error="",
                        report_version=2,
                    )
                    await delete_failed_deep_reports_for_repo(
                        db,
                        candidate.repo_url,
                        keep_report_id=report_id,
                    )
                    result.completed += 1
            except Exception as exc:
                await _save_failed_rebuild(
                    db,
                    run_id=run_id,
                    row=row,
                    candidate=candidate,
                    source_package=source_package,
                    cost_records=cost_records,
                    error=str(exc),
                )
                result.failed.append(candidate.repo_url)

            if max_cost is not None and total_cost >= max_cost:
                cost_limit_reached = True
                break

        should_switch = (
            max_reports is None
            and repo_url is None
            and not cost_limit_reached
        )
        if should_switch:
            await switch_public_deep_reports_to_v2(db)
            result.switched = True

        await end_pipeline_run(
            db,
            run_id,
            "completed",
            result.model_dump_json(),
        )
        return result
    except Exception as exc:
        await end_pipeline_run(db, run_id, "failed", str(exc))
        raise


async def _run_cli(args) -> RebuildResult:
    base_dir = Path(__file__).resolve().parents[2]
    load_dotenv(base_dir / ".env")

    db = Database(
        base_dir / "data" / "kb.db",
        base_dir / "src" / "db" / "migrations",
    )
    await db.initialize()
    try:
        registry = None
        if not args.dry_run:
            registry = LLMRegistry(
                load_llm_config(base_dir / "config" / "llm.yaml"),
                load_agents_config(base_dir / "config" / "agents.yaml"),
            )
            registry.health._db = db

        result = await rebuild_deep_reports(
            db,
            registry,
            dry_run=args.dry_run,
            max_reports=args.max_reports,
            repo_url=args.repo,
            max_cost=args.max_cost,
        )
        if result.switched:
            builder = SiteBuilder(
                db,
                base_dir / "output",
                base_dir / "src" / "site" / "templates",
            )
            await builder.build()
        return result
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="重建深度报告 V2")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-reports", type=int)
    parser.add_argument("--max-cost", type=float)
    parser.add_argument("--repo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = asyncio.run(_run_cli(args))
    logger.info(
        "planned=%s completed=%s failed=%s switched=%s",
        result.planned,
        result.completed,
        len(result.failed),
        str(result.switched).lower(),
    )
    if result.failed:
        logger.info("failed_repos=%s", json.dumps(result.failed, ensure_ascii=False))


if __name__ == "__main__":
    main()
