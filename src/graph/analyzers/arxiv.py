from .base import analyze_items, load_prompt
from ..state import RawItem, AnalyzedItem, CostRecord
from ...core.llm_client import LLMRegistry

async def analyze_arxiv(items: list[RawItem], registry: LLMRegistry) -> tuple[list[AnalyzedItem], list[CostRecord]]:
    prompt = load_prompt("arxiv_analyzer", registry)
    return await analyze_items(items, "arxiv_analyzer", registry, prompt)