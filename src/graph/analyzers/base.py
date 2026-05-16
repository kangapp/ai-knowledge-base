import json
import re
import logging
from pathlib import Path
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

logger = logging.getLogger("pipeline")
ANALYZED_SCHEMA_DESC = '{"title": "string", "summary": "100-200字中文", "tags": ["标签1", "标签2"], "language": "zh|en", "relevance_score": 85}'


def load_prompt(agent_name: str, registry: LLMRegistry) -> str:
    """从 prompts/*.md 文件加载 prompt 模板，作为 .format() 模板使用"""
    path = Path(registry.get_prompt_path(agent_name))
    return path.read_text(encoding="utf-8")


def parse_and_validate(raw: str, ref_url: str = "") -> AnalyzedItem:
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
        # 每条独立获取 client（provider 可能随熔断状态变化）
        client, provider, model_id, params = registry.get_client(agent_name)

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
                analyzed = parse_and_validate(content, ref_url=item.url)

                tokens_in = response.usage.prompt_tokens if response.usage else 0
                tokens_out = response.usage.completion_tokens if response.usage else 0
                cost = registry.calc_cost(provider, model_id, tokens_in, tokens_out)

                registry.budget.add_cost(provider, cost)
                registry.health.record_success(provider, 0)

                results.append(analyzed)
                costs.append(CostRecord(agent=agent_name, provider=provider, model=model_id, tokens_in=tokens_in, tokens_out=tokens_out, cost=cost))
                break

            except Exception as e:
                registry.health.record_failure(provider, str(e))
                if attempt == 1:
                    logger.warning("analyzer.parse_failed", extra={"agent": agent_name, "url": item.url, "error": str(e)})
                continue

    return results, costs