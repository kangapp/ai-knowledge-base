# src/graph/reviewer.py
import json
import re
import logging
from .state import PipelineState, AnalyzedItem, ReviewedItem, CostRecord
from ..core.llm_client import LLMRegistry

logger = logging.getLogger("pipeline")
MAX_RETRIES = 2


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
- 信息密度(0-15): 新颖独家=12-15, 有信息量=7-11, 重复营销=0-6
- 时效性(0-15): 本周内=12-15, 本月=7-11, 较早=0-6

输出 JSON:
{"total_score": 85, "dimensions": {"ai_relevance": {"score": 35, "reason": "..."}, "content_depth": {"score": 25, "reason": "..."}, "info_density": {"score": 12, "reason": "..."}, "timeliness": {"score": 13, "reason": "..."}}, "verdict": "approved"|"retry"|"discarded", "retry_feedback": null|{"suggestions": ["..."]}}"""


def parse_reviewer_output(raw: str) -> ReviewedItem:
    # 0. 容错：剥离 markdown ```json 包裹（优先，防止干扰后续 thinking tag 剥离）
    m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
    if m:
        return ReviewedItem.model_validate(json.loads(m.group(1)))

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
        return ReviewedItem.model_validate(json.loads(raw))
    except json.JSONDecodeError:
        raise ValueError("Reviewer output is not valid JSON")


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
                content = response.choices[0].message.content or "{}"

                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)
                registry.budget.add_cost(provider, cost)
                registry.health.record_success(provider, 0)

                reviewed = parse_reviewer_output(content)
                reviewed_items.append(reviewed)
                reviewed.ref_url = item.ref_url
                cost_records.append(CostRecord(
                    agent="reviewer", provider=provider, model=model_id,
                    tokens_in=tokens_in, tokens_out=tokens_out, cost=cost,
                    ref_url=item.ref_url
                ))
                break

            except Exception as e:
                registry.health.record_failure(provider, str(e))
                if attempt == 1:
                    logger.warning("reviewer.parse_failed", extra={"url": item.ref_url, "error": str(e)})
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