# src/graph/reviewer.py
import json
import re
import logging
import time
from .state import PipelineState, AnalyzedItem, ReviewedItem, CostRecord
from ..core.llm_client import LLMRegistry

logger = logging.getLogger("pipeline")
MAX_RETRIES = 2
DIMENSION_LIMITS = {
    "ai_relevance": 40,
    "content_depth": 30,
    "info_density": 15,
    "timeliness": 15,
}
DIMENSION_ALIASES = {
    "information_density": "info_density",
    "currency": "timeliness",
}


def _load_reviewer_prompt(registry: LLMRegistry) -> str:
    """从 prompts/reviewer.md 加载系统 prompt；文件缺失时使用内置默认"""
    from pathlib import Path
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


def parse_reviewer_output(raw: str) -> ReviewedItem:
    # 0. 容错：剥离 markdown ```json 包裹（优先，防止干扰后续 thinking tag 剥离）
    m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
    if m:
        return _normalize_review(json.loads(m.group(1)))

    # 1. 容错：剥离 thinking tags（包括不完整的）
    for _ in range(10):
        new_raw = re.sub(r'<think>[\s\S]*?(】|</think>)', '', raw).strip()
        if new_raw == raw:
            break
        raw = new_raw

    # 2. 尝试从第一个 { 开始提取内容
    json_start = raw.find('{')
    if json_start > 0:
        raw = raw[json_start:]

    # 3. 直接解析
    try:
        return _normalize_review(json.loads(raw))
    except json.JSONDecodeError:
        raise ValueError("Reviewer output is not valid JSON")


def _normalize_dimension(name: str, value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Reviewer dimension '{name}' must be an object")
    score = value.get("score")
    if score is None:
        raise ValueError(f"Reviewer dimension '{name}' missing score")
    max_score = DIMENSION_LIMITS[name]
    score = max(0, min(int(score), max_score))
    return {"score": score, "reason": str(value.get("reason") or "")}


def _normalize_review(data: dict) -> ReviewedItem:
    raw_dimensions = data.get("dimensions") or {}
    normalized_dimensions = {}
    for raw_key, value in raw_dimensions.items():
        key = DIMENSION_ALIASES.get(raw_key, raw_key)
        if key in DIMENSION_LIMITS and key not in normalized_dimensions:
            normalized_dimensions[key] = _normalize_dimension(key, value)

    missing = [key for key in DIMENSION_LIMITS if key not in normalized_dimensions]
    if missing:
        raise ValueError(f"Reviewer output missing dimensions: {', '.join(missing)}")

    total_score = sum(item["score"] for item in normalized_dimensions.values())
    ai_score = normalized_dimensions["ai_relevance"]["score"]
    depth_score = normalized_dimensions["content_depth"]["score"]

    verdict = _decide_verdict(total_score, ai_score, depth_score)
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


def _decide_verdict(total_score: int, ai_score: int, depth_score: int) -> str:
    if ai_score < 20:
        return "discarded"
    if total_score >= 80 and ai_score >= 30:
        return "approved"
    if total_score >= 60 and ai_score >= 25 and depth_score >= 15:
        return "retry"
    return "discarded"


async def reviewer_node(state: PipelineState, registry: LLMRegistry) -> dict:
    if not state.analyzed_items:
        return {"reviewed_items": [], "cost_records": []}

    system_prompt = _load_reviewer_prompt(registry)
    reviewed_items = []
    cost_records = []

    for item in state.analyzed_items:
        # 超过最大重试次数直接丢弃
        if item.retry_count >= MAX_RETRIES:
            reviewed_items.append(ReviewedItem(
                ref_url=item.ref_url, total_score=0, dimensions={},
                verdict="discarded",
                retry_feedback={"reason": f"exceeded max retries ({MAX_RETRIES})"}
            ))
            continue

        client, provider, model_id, params = registry.get_client("reviewer")
        user_prompt = f"标题: {item.title}\n摘要: {item.summary}\n标签: {', '.join(item.tags)}\n来源: {item.ref_url}"

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

                response = await client.chat.completions.create(**kwargs)
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
                    reviewed = parse_reviewer_output(content)
                except Exception as parse_error:
                    cost_record.status = "parse_failed"
                    cost_record.error = str(parse_error)
                    cost_records.append(cost_record)
                    raise

                cost_records.append(cost_record)
                reviewed_items.append(reviewed)
                reviewed.ref_url = item.ref_url
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
                        error=str(e),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        attempt_no=attempt + 1,
                        prompt_name="reviewer",
                        prompt_version="current",
                    ))
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

    logger.info("reviewer.done", extra={
        "total": len(reviewed_items),
        "approved": sum(1 for r in reviewed_items if r.verdict == "approved"),
        "retry": sum(1 for r in reviewed_items if r.verdict == "retry"),
        "discarded": sum(1 for r in reviewed_items if r.verdict == "discarded"),
        "tokens_in": sum(c.tokens_in for c in cost_records),
        "tokens_out": sum(c.tokens_out for c in cost_records),
        "cost_usd": round(sum(c.cost for c in cost_records), 6),
    })
    for r, c in zip(reviewed_items, cost_records):
        logger.debug("reviewer.item", extra={
            "url": r.ref_url, "verdict": r.verdict,
            "score": r.total_score, "tokens_in": c.tokens_in, "tokens_out": c.tokens_out,
        })

    return {"reviewed_items": reviewed_items, "cost_records": cost_records}
