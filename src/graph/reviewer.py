# src/graph/reviewer.py
import asyncio
import logging
import time
from pathlib import Path
from .state import PipelineState, AnalyzedItem, ReviewedItem, CostRecord
from ..core.llm_client import LLMRegistry
from ..core.json_utils import extract_json_object

logger = logging.getLogger("pipeline")
MAX_RETRIES = 2
DEFAULT_REVIEWER_CONCURRENCY = 3
DEFAULT_REVIEWER_TIMEOUT_SECONDS = 60.0
ARTICLE_DIMENSION_LIMITS = {
    "ai_relevance": 40,
    "content_depth": 30,
    "info_density": 15,
    "timeliness": 15,
}
GITHUB_DIMENSION_LIMITS = {
    "ai_relevance": 35,
    "developer_utility": 30,
    "project_signal": 20,
    "content_clarity": 15,
}
DIMENSION_ALIASES = {
    "information_density": "info_density",
    "currency": "timeliness",
}
GITHUB_REVIEWER_FALLBACK_PROMPT = """你是 AI 开源项目审核员。只根据用户给出的 GitHub 仓库标题、摘要、标签、URL 和仓库元数据评分。

评分维度：
- ai_relevance(0-35): 核心 AI/LLM/Agent/MCP/RAG/代码理解工具=30-35；AI 开发辅助或知识库工具=24-29；仅泛泛使用 AI 标签=10-23；无关=0-9。
- developer_utility(0-30): 明确解决开发者工作流痛点且可直接使用=22-30；用途清晰但细节一般=15-21；概念模糊或偏展示=5-14；无实用价值=0-4。
- project_signal(0-20): stars/forks/topics/source_id 显示强社区或趋势信号=15-20；有一定关注度或专业 topic=8-14；信号弱=0-7。
- content_clarity(0-15): 摘要清楚说明做什么、给谁用、如何接入=11-15；基本清楚=7-10；含糊=0-6。

强约束：
- dimensions 只能包含 ai_relevance、developer_utility、project_signal、content_clarity 四个 key。
- total_score 必须等于四个维度 score 之和。
- 如果 source_id 是 github_ai_devtools，且仓库围绕 AI 编程助手、代码理解、知识图谱、RAG、Agent 工具链，ai_relevance 通常不低于 28。
- GitHub repo 不要求具备文章式深度；请重点判断项目是否值得作为 AI 工具被收录。

输出 JSON:
{ "total_score": 78, "dimensions": { "ai_relevance": {"score": 32, "reason": "..."}, "developer_utility": {"score": 23, "reason": "..."}, "project_signal": {"score": 15, "reason": "..."}, "content_clarity": {"score": 8, "reason": "..."} }, "verdict": "approved"|"retry"|"discarded", "retry_feedback": null|{"suggestions": ["..."]} }"""


def review_kind(item: AnalyzedItem) -> str:
    if item.source == "github":
        return "github_repo"
    if item.source == "arxiv":
        return "paper"
    return "article"


def build_reviewer_user_prompt(item: AnalyzedItem) -> str:
    kind = review_kind(item)
    if kind != "github_repo":
        return f"标题: {item.title}\n摘要: {item.summary}\n标签: {', '.join(item.tags)}\n来源: {item.ref_url}"

    metadata = item.metadata or {}
    topics = metadata.get("topics") or []
    topics_text = ", ".join(str(topic) for topic in topics[:12])
    return "\n".join([
        "内容类型: github_repo",
        f"标题: {item.title}",
        f"摘要: {item.summary}",
        f"标签: {', '.join(item.tags)}",
        f"来源: {item.ref_url}",
        f"source_id: {item.source_id}",
        f"repo: {item.source_detail}",
        f"stars: {metadata.get('stars', 0)}",
        f"forks: {metadata.get('forks', 0)}",
        f"language: {metadata.get('language', '')}",
        f"topics: {topics_text}",
    ])


def _load_reviewer_prompt(registry: LLMRegistry) -> str:
    """从 prompts/reviewer.md 加载系统 prompt；文件缺失时使用内置默认"""
    try:
        path = Path(registry.get_prompt_path("reviewer"))
        return path.read_text(encoding="utf-8")
    except Exception:
        return """你是内容审核员。对文章按四维评分（0-100）:
- AI相关度(0-40): 核心AI/LLM/Agent/MCP/RAG=35-40, AI基础设施=25-34, 泛技术提及=10-24, 无关=0-9
- 内容深度(0-30): 深度原创=25-30, 有细节=15-24, 简要=5-14, 空内容=0-4
- 信息密度info_density(0-15): 新颖独家=12-15, 有信息量=7-11, 重复营销=0-6
- 时效性(0-15): 本周内=12-15, 本月=7-11, 较早=0-6
dimensions 只能包含 ai_relevance、content_depth、info_density、timeliness 四个 key。total_score 必须等于四个维度 score 之和。

输出 JSON:
{"total_score": 85, "dimensions": {"ai_relevance": {"score": 35, "reason": "..."}, "content_depth": {"score": 25, "reason": "..."}, "info_density": {"score": 12, "reason": "..."}, "timeliness": {"score": 13, "reason": "..."}}, "verdict": "approved"|"retry"|"discarded", "retry_feedback": null|{"suggestions": ["..."]}}"""


def _load_reviewer_prompt_for_item(registry: LLMRegistry, item: AnalyzedItem) -> str:
    if review_kind(item) != "github_repo":
        return _load_reviewer_prompt(registry)
    try:
        return Path("prompts/github_reviewer.md").read_text(encoding="utf-8")
    except Exception:
        return GITHUB_REVIEWER_FALLBACK_PROMPT


def parse_reviewer_output(raw: str, review_kind: str = "article") -> ReviewedItem:
    try:
        return _normalize_review(extract_json_object(raw), review_kind)
    except ValueError:
        raise ValueError("Reviewer output is not valid JSON")


def _normalize_dimension(name: str, value: dict, dimension_limits: dict[str, int]) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Reviewer dimension '{name}' must be an object")
    score = value.get("score")
    if score is None:
        raise ValueError(f"Reviewer dimension '{name}' missing score")
    max_score = dimension_limits[name]
    score = max(0, min(int(score), max_score))
    return {"score": score, "reason": str(value.get("reason") or "")}


def _normalize_review(data: dict, kind: str = "article") -> ReviewedItem:
    dimension_limits = GITHUB_DIMENSION_LIMITS if kind == "github_repo" else ARTICLE_DIMENSION_LIMITS
    raw_dimensions = data.get("dimensions") or {}
    normalized_dimensions = {}
    for raw_key, value in raw_dimensions.items():
        key = DIMENSION_ALIASES.get(raw_key, raw_key)
        if key in dimension_limits and key not in normalized_dimensions:
            normalized_dimensions[key] = _normalize_dimension(key, value, dimension_limits)

    missing = [key for key in dimension_limits if key not in normalized_dimensions]
    if missing:
        raise ValueError(f"Reviewer output missing dimensions: {', '.join(missing)}")

    total_score = sum(item["score"] for item in normalized_dimensions.values())
    ai_score = normalized_dimensions["ai_relevance"]["score"]

    if kind == "github_repo":
        verdict = _decide_github_verdict(
            total_score,
            ai_score,
            normalized_dimensions["developer_utility"]["score"],
            normalized_dimensions["project_signal"]["score"],
        )
    else:
        verdict = _decide_article_verdict(
            total_score,
            ai_score,
            normalized_dimensions["content_depth"]["score"],
        )
    retry_feedback = None
    if verdict == "retry":
        retry_feedback = data.get("retry_feedback") or {"suggestions": ["补充 AI 相关性和技术细节证据后重新分析"]}

    return ReviewedItem.model_validate({
        "ref_url": data.get("ref_url"),
        "total_score": total_score,
        "dimensions": normalized_dimensions,
        "verdict": verdict,
        "retry_feedback": retry_feedback,
    })


def _decide_article_verdict(total_score: int, ai_score: int, depth_score: int) -> str:
    if ai_score < 20:
        return "discarded"
    if total_score >= 80 and ai_score >= 30:
        return "approved"
    if total_score >= 60 and ai_score >= 25 and depth_score >= 15:
        return "retry"
    return "discarded"


def _decide_github_verdict(total_score: int, ai_score: int, utility_score: int, signal_score: int) -> str:
    if ai_score < 25:
        return "discarded"
    if total_score >= 65 and ai_score >= 28 and utility_score >= 15:
        return "approved"
    if total_score >= 55 and ai_score >= 25:
        return "retry"
    return "discarded"


def _positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


def _positive_float(value, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


async def _review_one_item(
    index: int,
    item: AnalyzedItem,
    registry: LLMRegistry,
    semaphore: asyncio.Semaphore,
) -> tuple[int, list[ReviewedItem], list[CostRecord]]:
    if item.retry_count >= MAX_RETRIES:
        return index, [ReviewedItem(
            ref_url=item.ref_url, total_score=0, dimensions={},
            verdict="discarded",
            retry_feedback={"reason": f"exceeded max retries ({MAX_RETRIES})"}
        )], []

    async with semaphore:
        client, provider, model_id, params = registry.get_client("reviewer")
        timeout_seconds = _positive_float(params.get("timeout_seconds"), DEFAULT_REVIEWER_TIMEOUT_SECONDS)
        kind = review_kind(item)
        system_prompt = _load_reviewer_prompt_for_item(registry, item)
        user_prompt = build_reviewer_user_prompt(item)
        reviewed_items = []
        cost_records = []

        logger.debug("reviewer.item_start", extra={
            "url": item.ref_url,
            "review_kind": kind,
            "timeout_seconds": timeout_seconds,
        })

        for attempt in range(2):
            content = ""
            cost_record = None
            started = time.perf_counter()
            try:
                kwargs = dict(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.0,
                    max_tokens=params.get("max_tokens", 1024),
                )
                if registry.supports_json_mode(provider):
                    kwargs["response_format"] = {"type": "json_object"}

                response = await asyncio.wait_for(
                    client.chat.completions.create(**kwargs),
                    timeout=timeout_seconds,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                content = response.choices[0].message.content or "{}"

                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)
                registry.budget.add_cost(provider, cost)
                registry.health.record_success(provider, 0)

                cost_record = CostRecord(
                    agent="reviewer", provider=provider, model=model_id,
                    tokens_in=tokens_in, tokens_out=tokens_out, cost=cost,
                    ref_url=item.ref_url,
                    status="success",
                    latency_ms=latency_ms,
                    attempt_no=attempt + 1,
                    prompt_name="reviewer",
                    prompt_version="current",
                )

                try:
                    reviewed = parse_reviewer_output(content, review_kind=kind)
                except Exception as parse_error:
                    cost_record.status = "parse_failed"
                    cost_record.error = str(parse_error)
                    cost_records.append(cost_record)
                    raise

                cost_records.append(cost_record)
                reviewed.ref_url = item.ref_url
                reviewed_items.append(reviewed)
                logger.debug("reviewer.item", extra={
                    "url": item.ref_url,
                    "input_prompt": user_prompt,
                    "raw_output": content,
                })
                break

            except Exception as e:
                if cost_record is None:
                    cost_records.append(CostRecord(
                        agent="reviewer",
                        provider=provider,
                        model=model_id,
                        tokens_in=0,
                        tokens_out=0,
                        cost=0.0,
                        ref_url=item.ref_url,
                        status="request_failed",
                        error=type(e).__name__ if isinstance(e, asyncio.TimeoutError) else str(e),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        attempt_no=attempt + 1,
                        prompt_name="reviewer",
                        prompt_version="current",
                    ))
                if cost_record is None:
                    registry.health.record_failure(provider, str(e))
                if attempt == 1:
                    logger.warning("reviewer.parse_failed", extra={
                        "url": item.ref_url, "error": str(e),
                        "input_prompt": user_prompt, "raw_output": content,
                    })
                    reviewed_items.append(ReviewedItem(
                        ref_url=item.ref_url, total_score=0, dimensions={},
                        verdict="discarded",
                        retry_feedback={"reason": f"parse failed after 2 attempts: {str(e)}"}
                    ))

        logger.debug("reviewer.item_done", extra={
            "url": item.ref_url,
            "review_kind": kind,
            "verdict": reviewed_items[-1].verdict if reviewed_items else "none",
            "attempts": len([record for record in cost_records if record.ref_url == item.ref_url]),
        })
        return index, reviewed_items, cost_records


async def reviewer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.analyzed_items:
        return {"reviewed_items": [], "cost_records": []}

    _, _, _, params = registry.get_client("reviewer")
    concurrency = _positive_int(params.get("concurrency"), DEFAULT_REVIEWER_CONCURRENCY)
    semaphore = asyncio.Semaphore(concurrency)
    tasks = [
        _review_one_item(index, item, registry, semaphore)
        for index, item in enumerate(state.analyzed_items)
    ]
    item_results = sorted(await asyncio.gather(*tasks), key=lambda result: result[0])
    reviewed_items = []
    cost_records = []
    for _, item_reviewed, item_costs in item_results:
        reviewed_items.extend(item_reviewed)
        cost_records.extend(item_costs)

    logger.info("reviewer.done", extra={
        "total": len(reviewed_items),
        "approved": sum(1 for r in reviewed_items if r.verdict == "approved"),
        "retry": sum(1 for r in reviewed_items if r.verdict == "retry"),
        "discarded": sum(1 for r in reviewed_items if r.verdict == "discarded"),
        "concurrency": concurrency,
        "tokens_in": sum(c.tokens_in for c in cost_records),
        "tokens_out": sum(c.tokens_out for c in cost_records),
        "cost_usd": round(sum(c.cost for c in cost_records), 6),
    })
    cost_by_url = {}
    for cost in cost_records:
        stats = cost_by_url.setdefault(cost.ref_url, {"tokens_in": 0, "tokens_out": 0})
        stats["tokens_in"] += cost.tokens_in
        stats["tokens_out"] += cost.tokens_out
    for r in reviewed_items:
        stats = cost_by_url.get(r.ref_url, {"tokens_in": 0, "tokens_out": 0})
        logger.debug("reviewer.item", extra={
            "url": r.ref_url, "verdict": r.verdict,
            "score": r.total_score, "tokens_in": stats["tokens_in"], "tokens_out": stats["tokens_out"],
        })

    return {"reviewed_items": reviewed_items, "cost_records": cost_records}
