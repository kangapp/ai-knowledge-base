from .base import analyze_items, load_prompt
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

async def analyze_rss(items: list[RawItem], registry: LLMRegistry) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    prompt = load_prompt("rss_analyzer", registry)
    return await analyze_items(items, "rss_analyzer", registry, prompt)