from ..graph.state import ReviewedItem


def filter_sources(
    sources,
    source_filter: str | list[str] | tuple[str, ...] | set[str] | None,
):
    if source_filter is None:
        return sources
    if isinstance(source_filter, str):
        source_ids = {source_filter}
    else:
        source_ids = set(source_filter)
    return [source for source in sources if source.id in source_ids]


def group_enabled_sources_by_cron(sources) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    for source in sources:
        if not source.enabled:
            continue
        groups.setdefault(source.cron, []).append(source.id)
    return groups


def source_filter_label(source_filter) -> str:
    if source_filter is None:
        return "all"
    if isinstance(source_filter, str):
        return source_filter
    return ",".join(source_filter)


def source_filter_count(source_filter) -> int | None:
    if source_filter is None:
        return None
    if isinstance(source_filter, str):
        return 1
    return len(source_filter)


def apply_github_velocity_filter(raw_items: list, source, trending_urls: set[str]) -> list:
    return [
        item for item in raw_items
        if item.source != "github"
        or item.raw_metadata.get("source_id") != source.id
        or item.url in trending_urls
    ]


def build_cost_source_map(items: list) -> dict[str, tuple[str, str, str]]:
    source_map = {}
    for item in items:
        source_id = item.raw_metadata.get("source_id") or item.source_detail or item.source
        source_map[item.url] = (item.source, item.source_detail, source_id)
    return source_map


def summarize_item_costs(cost_records: list) -> dict[str, tuple[float, int]]:
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


def source_identity(item) -> tuple[str, str, str]:
    source_id = item.raw_metadata.get("source_id") or item.source_detail or item.source
    return source_id, item.source, item.source_detail


def build_pipeline_source_summaries(
    *,
    run_id: str,
    raw_items: list,
    new_items: list,
    analyzed_items: list,
    reviewed_items: list,
    cost_records: list,
    inserted_urls: set[str],
    failed_counts: dict[str, int] | None = None,
    active_sources: list | None = None,
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

    for source in active_sources or []:
        ensure(source.id, source.type, source.name)

    url_to_source: dict[str, tuple[str, str, str]] = {}
    for item in raw_items:
        source_id, source, source_detail = source_identity(item)
        url_to_source[item.url] = (source_id, source, source_detail)
        ensure(source_id, source, source_detail)["collected"] += 1

    new_urls = {item.url for item in new_items}
    for item in new_items:
        source_id, source, source_detail = source_identity(item)
        ensure(source_id, source, source_detail)["new_items"] += 1

    for item in raw_items:
        if item.url not in new_urls:
            source_id, source, source_detail = source_identity(item)
            ensure(source_id, source, source_detail)["dedup_skipped"] += 1

    analyzed_urls = {analyzed.ref_url for analyzed in analyzed_items}
    for item in analyzed_items:
        mapping = url_to_source.get(item.ref_url)
        if mapping:
            ensure(*mapping)["analyzed"] += 1

    for item in new_items:
        if item.url not in analyzed_urls:
            source_id, source, source_detail = source_identity(item)
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


def prepare_retry_review_items(
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


def merge_retry_review_result(
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
