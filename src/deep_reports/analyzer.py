import json
import time
from pathlib import Path

from pydantic import ValidationError

from src.core.json_utils import extract_json_object
from src.core.llm_client import LLMRegistry
from src.deep_reports.models import DeepReportCandidate, DeepReportOutput, SourcePackage
from src.graph.state import CostRecord

DEEP_REPORT_SCHEMA_DESC = json.dumps(
    {
        "title": "string",
        "summary": "string",
        "tech_stack": ["string", "string"],
        "architecture": {"pattern": "string", "components": ["string", "string"]},
        "data_flow": ["string", "string"],
        "use_cases": ["string"],
        "strengths": ["string"],
        "limitations": ["string"],
        "actionable_takeaways": ["string"],
        "source_evidence": [{"path": "string", "reason": "string"}],
    },
    ensure_ascii=False,
)


def load_deep_report_prompt(registry: LLMRegistry) -> str:
    path = Path(registry.get_prompt_path("deep_report"))
    return path.read_text(encoding="utf-8")


def parse_deep_report_output(raw: str) -> DeepReportOutput:
    try:
        data = extract_json_object(raw)
    except ValueError as exc:
        raise ValueError("Deep report output is not valid JSON") from exc

    try:
        return DeepReportOutput.model_validate(data)
    except ValidationError as exc:
        raise ValueError("Deep report output does not match schema") from exc


def _build_candidate_context(candidate: DeepReportCandidate) -> str:
    payload = {
        "repo_name": candidate.repo_name,
        "repo_url": candidate.repo_url,
        "title": candidate.title,
        "summary": candidate.summary,
        "reviewer_score": candidate.reviewer_score,
        "candidate_score": candidate.candidate_score,
        "trigger_reason": candidate.trigger_reason,
        "source_id": candidate.source_id,
        "source_detail": candidate.source_detail,
        "metadata": candidate.metadata,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _build_source_package_payload(source_package: SourcePackage) -> str:
    return json.dumps(source_package.model_dump(), ensure_ascii=False, indent=2)


async def analyze_deep_report(
    candidate: DeepReportCandidate,
    source_package: SourcePackage,
    registry: LLMRegistry,
) -> tuple[DeepReportOutput | None, list[CostRecord]]:
    prompt_template = load_deep_report_prompt(registry)
    client, provider, model_id, params = registry.get_client("deep_report")
    user_prompt = prompt_template.format(
        repo_name=candidate.repo_name,
        repo_url=candidate.repo_url,
        candidate_context=_build_candidate_context(candidate),
        source_package=_build_source_package_payload(source_package),
        schema=DEEP_REPORT_SCHEMA_DESC,
    )

    cost_records: list[CostRecord] = []

    for attempt in range(2):
        content = ""
        started = time.perf_counter()
        try:
            kwargs = dict(
                model=model_id,
                messages=[
                    {
                        "role": "system",
                        "content": f"你是源码级 GitHub 项目研究员。只输出 JSON，格式：{DEEP_REPORT_SCHEMA_DESC}",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=params.get("temperature", 0.2),
                max_tokens=params.get("max_tokens", 4096),
            )
            if registry.supports_json_mode(provider):
                kwargs["response_format"] = {"type": "json_object"}

            response = await client.chat.completions.create(**kwargs)
            latency_ms = int((time.perf_counter() - started) * 1000)
            content = response.choices[0].message.content or "{}"

            tokens_in = response.usage.prompt_tokens if response.usage else 0
            tokens_out = response.usage.completion_tokens if response.usage else 0
            cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)

            registry.budget.add_cost(provider, cost)
            registry.health.record_success(provider, 0)

            cost_record = CostRecord(
                agent="deep_report",
                provider=provider,
                model=model_id,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost=cost,
                ref_url=candidate.repo_url,
                source="github",
                source_detail=candidate.source_detail,
                source_id=candidate.source_id,
                status="success",
                latency_ms=latency_ms,
                attempt_no=attempt + 1,
                prompt_name="deep_report",
                prompt_version="current",
            )

            try:
                report = parse_deep_report_output(content)
            except Exception as exc:
                cost_record.status = "parse_failed"
                cost_record.error = str(exc)
                cost_records.append(cost_record)
                registry.health.record_failure(provider, str(exc))
                continue

            cost_records.append(cost_record)
            return report, cost_records
        except Exception as exc:
            registry.health.record_failure(provider, str(exc))
            cost_records.append(CostRecord(
                agent="deep_report",
                provider=provider,
                model=model_id,
                tokens_in=0,
                tokens_out=0,
                cost=0.0,
                ref_url=candidate.repo_url,
                source="github",
                source_detail=candidate.source_detail,
                source_id=candidate.source_id,
                status="request_failed",
                error=str(exc),
                latency_ms=int((time.perf_counter() - started) * 1000),
                attempt_no=attempt + 1,
                prompt_name="deep_report",
                prompt_version="current",
            ))

    return None, cost_records
