import logging
import time
from pathlib import Path
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry
from ...core.json_utils import extract_json_object

logger = logging.getLogger("pipeline")
ANALYZED_SCHEMA_DESC = '{"title": "string", "summary": "100-200字中文", "tags": ["标签1", "标签2"], "language": "zh|en"}'


def load_prompt(agent_name: str, registry: LLMRegistry) -> str:
    """从 prompts/*.md 文件加载 prompt 模板，作为 .format() 模板使用"""
    path = Path(registry.get_prompt_path(agent_name))
    return path.read_text(encoding="utf-8")


def parse_and_validate(raw: str, ref_url: str = "", source_item: RawItem | None = None) -> AnalyzedItem:
    try:
        data = extract_json_object(raw)
    except ValueError:
        raise ValueError("LLM output is not valid JSON")

    # ref_url 由调用方赋值
    data["ref_url"] = ref_url
    if source_item is not None:
        data["source"] = source_item.source
        data["source_detail"] = source_item.source_detail
        data["source_id"] = source_item.raw_metadata.get("source_id", source_item.source_detail or source_item.source)
        data["metadata"] = source_item.raw_metadata

    # 容错：tags 超过 3 个时裁剪
    if "tags" in data and isinstance(data["tags"], list) and len(data["tags"]) > 3:
        data["tags"] = data["tags"][:3]

    return AnalyzedItem.model_validate(data)


async def analyze_items(
    items: list[RawItem], agent_name: str, registry: LLMRegistry,
    prompt_template: str, system_prompt: str = ""
) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    if not items:
        return [], []

    results = []
    costs = []

    for item in items:
        try:
            client, provider, model_id, params = registry.get_client(agent_name)
        except Exception as e:
            logger.warning("analyzer.get_client_failed", extra={"agent": agent_name, "url": item.url, "error": str(e)})
            continue

        user_prompt = prompt_template.format(
            title=item.title, description=item.description,
            url=item.url, metadata=str(item.raw_metadata),
            schema=ANALYZED_SCHEMA_DESC,
        )

        for attempt in range(2):
            content = ""
            cost_record = None
            started = time.perf_counter()
            try:
                kwargs = dict(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt or f"你是一个技术分析助手。只输出 JSON，格式：{ANALYZED_SCHEMA_DESC}"},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=params.get("temperature", 0.3),
                    max_tokens=params.get("max_tokens", 2048),
                )
                # 仅 provider 支持 JSON mode 时才传 response_format
                if registry.supports_json_mode(provider):
                    kwargs["response_format"] = {"type": "json_object"}

                response = await client.chat.completions.create(**kwargs)
                latency_ms = int((time.perf_counter() - started) * 1000)
                content = response.choices[0].message.content or "{}"

                # 立即提取 tokens 并计算 cost，无论 parse 是否成功都记录
                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)

                # 先更新熔断统计（无论 parse 是否成功）
                registry.budget.add_cost(provider, cost)
                registry.health.record_success(provider, 0)

                cost_record = CostRecord(
                    agent=agent_name,
                    provider=provider,
                    model=model_id,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost=cost,
                    ref_url=item.url,
                    source=item.source,
                    source_detail=item.source_detail,
                    source_id=item.raw_metadata.get("source_id", item.source_detail or item.source),
                    status="success",
                    latency_ms=latency_ms,
                    attempt_no=attempt + 1,
                    prompt_name=agent_name,
                    prompt_version="current",
                )

                # 再 parse，parse 失败会抛出异常
                try:
                    analyzed = parse_and_validate(content, ref_url=item.url, source_item=item)
                except Exception as parse_error:
                    cost_record.status = "parse_failed"
                    cost_record.error = str(parse_error)
                    costs.append(cost_record)
                    raise

                costs.append(cost_record)

                # parse 成功后记录分析结果并 break；费用已按真实 LLM 调用记录
                results.append(analyzed)
                logger.debug("analyzer.item", extra={
                    "agent": agent_name,
                    "url": item.url,
                    "input_prompt": user_prompt,
                    "raw_output": content,
                })
                break

            except Exception as e:
                if cost_record is None:
                    costs.append(CostRecord(
                        agent=agent_name,
                        provider=provider,
                        model=model_id,
                        tokens_in=0,
                        tokens_out=0,
                        cost=0.0,
                        ref_url=item.url,
                        source=item.source,
                        source_detail=item.source_detail,
                        source_id=item.raw_metadata.get("source_id", item.source_detail or item.source),
                        status="request_failed",
                        error=str(e),
                        latency_ms=int((time.perf_counter() - started) * 1000),
                        attempt_no=attempt + 1,
                        prompt_name=agent_name,
                        prompt_version="current",
                    ))
                # parse 失败，仍需记录熔断统计（cost 已在上方 try 块记录）
                registry.health.record_failure(provider, str(e))
                if attempt == 1:
                    logger.warning("analyzer.parse_failed", extra={
                        "agent": agent_name, "url": item.url, "error": str(e),
                        "input_prompt": user_prompt, "raw_output": content,
                    })
                    continue  # 继续处理下一个 item，而不是 raise

    total_costs = sum(cost.cost for cost in costs) if costs else 0
    total_tokens_in = sum(cost.tokens_in for cost in costs) if costs else 0
    total_tokens_out = sum(cost.tokens_out for cost in costs) if costs else 0
    failed = len(items) - len(results)

    logger.info("analyzer.done", extra={
        "agent": agent_name,
        "total": len(items),
        "succeeded": len(results),
        "failed": failed,
        "tokens_in": total_tokens_in,
        "tokens_out": total_tokens_out,
        "cost_usd": round(total_costs, 6),
    })

    return results, costs
