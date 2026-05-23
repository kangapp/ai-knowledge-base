import json
import re
import logging
from pathlib import Path
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

logger = logging.getLogger("pipeline")
ANALYZED_SCHEMA_DESC = '{"title": "string", "summary": "100-200字中文", "tags": ["标签1", "标签2"], "language": "zh|en"}'


def load_prompt(agent_name: str, registry: LLMRegistry) -> str:
    """从 prompts/*.md 文件加载 prompt 模板，作为 .format() 模板使用"""
    path = Path(registry.get_prompt_path(agent_name))
    return path.read_text(encoding="utf-8")


def parse_and_validate(raw: str, ref_url: str = "") -> AnalyzedItem:
    # 0. 容错：剥离所有 thinking tags（包括不完整的）
    # 先剥离所有 ```json ... ``` 包裹（markdown 格式）
    m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    else:
        # MiniMax 的 thinking 标签格式：<think> ... (有时没有结束标签)
        # 尝试剥离完整的<think>...】对
        for _ in range(10):
            new_raw = re.sub(r'<think>[\s\S]*?】', '', raw).strip()
            if new_raw == raw:
                break
            raw = new_raw
        # 如果没有找到有效的 JSON，尝试从第一个 { 开始提取
        json_start = raw.find('{')
        if json_start > 0:
            raw = raw[json_start:]

    # 1. 尝试直接解析
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # 2. 容错：剥离 markdown ```json 包裹
        m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
        else:
            raise ValueError("LLM output is not valid JSON")

    # ref_url 由调用方赋值
    data["ref_url"] = ref_url

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
                content = response.choices[0].message.content or "{}"

                # 立即提取 tokens 并计算 cost，无论 parse 是否成功都记录
                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)

                # 先更新熔断统计（无论 parse 是否成功）
                registry.budget.add_cost(provider, cost)
                registry.health.record_success(provider, 0)

                # 再 parse，parse 失败会抛出异常
                analyzed = parse_and_validate(content, ref_url=item.url)

                # parse 成功，记录 CostRecord 并 break
                results.append(analyzed)
                costs.append(CostRecord(agent=agent_name, provider=provider, model=model_id, tokens_in=tokens_in, tokens_out=tokens_out, cost=cost, ref_url=item.url))
                logger.debug("analyzer.item", extra={
                    "agent": agent_name,
                    "url": item.url,
                    "input_prompt": user_prompt,
                    "raw_output": content,
                })
                break

            except Exception as e:
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