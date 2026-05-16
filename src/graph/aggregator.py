# src/graph/aggregator.py
from .state import PipelineState

async def aggregator_node(state: PipelineState) -> dict:
    return {}  # analyzed_items 和 cost_records 由 operator.add reducer 自动累积