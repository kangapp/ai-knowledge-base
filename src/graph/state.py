# src/graph/state.py
from pydantic import BaseModel, Field
import operator
from typing import Literal, Optional, Annotated


class RawItem(BaseModel):
    """Collector 产出 — 原始采集数据"""
    url: str
    title: str
    description: str = ""
    source: Literal["github", "rss", "feishu", "arxiv"]
    source_detail: str = ""
    published_at: str = ""
    raw_metadata: dict = {}
    collected_at: str = ""


class AnalyzedItem(BaseModel):
    """Analyzer 产出 — LLM 分析后的结构化结果"""
    ref_url: str  # 关联 RawItem.url
    title: str
    summary: str
    tags: list[str] = Field(default_factory=list, max_length=3)
    language: Literal["zh", "en"] = "zh"
    relevance_score: int = Field(default=0, ge=0, le=100)
    retry_count: int = Field(default=0, ge=0)


class ReviewedItem(BaseModel):
    """Reviewer 产出 — 四维评分 + 判决"""
    ref_url: Optional[str] = None  # LLM 输出不含此字段，由调用方补全
    total_score: int = Field(ge=0, le=100)
    dimensions: dict = {}  # {ai_relevance: {score, reason}, ...}
    verdict: Literal["approved", "retry", "discarded"]
    retry_feedback: Optional[dict] = None


class CostRecord(BaseModel):
    """单次 LLM 调用花费"""
    agent: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost: float


class PipelineState(BaseModel):
    """LangGraph 工作流全局状态"""
    raw_items: list[RawItem] = []
    routed_github: list[RawItem] = []
    routed_rss: list[RawItem] = []
    routed_feishu: list[RawItem] = []
    routed_arxiv: list[RawItem] = []
    analyzed_items: Annotated[list[AnalyzedItem], operator.add] = []
    reviewed_items: list[ReviewedItem] = []
    cost_records: Annotated[list[CostRecord], operator.add] = []
    error_log: list[dict] = []
    run_id: str = ""
    trigger: str = "cron"