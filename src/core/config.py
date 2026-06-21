import os
import re
from pathlib import Path
import yaml
from pydantic import BaseModel


# ===== LLM Config =====

class ModelInfo(BaseModel):
    id: str
    price_per_1k_in: float
    price_per_1k_out: float
    max_tokens: int


class ProviderConfig(BaseModel):
    base_url: str
    api_key: str
    supports_json_mode: bool = False
    models: list[ModelInfo]


class LLMConfig(BaseModel):
    providers: dict[str, ProviderConfig]


# ===== Sources Config =====

class SourceConfig(BaseModel):
    id: str
    name: str
    type: str  # github / rss / hotlist / feishu / arxiv
    enabled: bool
    priority: int
    cron: str
    max_items: int
    config: dict = {}


class SourceHealthRecord(BaseModel):
    source_id: str
    date: str
    total_collected: int = 0
    approved: int = 0
    rejected: int = 0
    failed: int = 0
    avg_score: float | None = None
    recorded_at: str = ""


class SourcesConfig(BaseModel):
    sources: list[SourceConfig]


# ===== Agents Config =====

class ModelRef(BaseModel):
    provider: str
    model: str


class ModelBinding(BaseModel):
    primary: ModelRef
    fallback: list[ModelRef] = []


class AgentConfig(BaseModel):
    model: ModelBinding
    params: dict = {}
    prompt: str = ""
    budget_weight: float = 1.0


class BudgetConfig(BaseModel):
    monthly: float
    soft_limit: float = 0.8
    hard_limit: float = 1.0


class AgentsConfig(BaseModel):
    agents: dict[str, AgentConfig]
    budget: BudgetConfig


def _interpolate_env(obj):
    if isinstance(obj, dict):
        return {k: _interpolate_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_interpolate_env(v) for v in obj]
    if isinstance(obj, str):
        def replacer(match):
            key = match.group(1)
            val = os.environ.get(key)
            if val is None:
                raise KeyError(f"环境变量 {key} 未设置，但配置文件引用了 ${{{key}}}")
            return val
        return re.sub(r'\$\{(\w+)\}', replacer, obj)
    return obj


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        data = yaml.safe_load(f)
    return _interpolate_env(data)


def load_llm_config(path: Path) -> LLMConfig:
    return LLMConfig(**_load_yaml(path))


def load_sources_config(path: Path) -> SourcesConfig:
    return SourcesConfig(**_load_yaml(path))


def load_agents_config(path: Path) -> AgentsConfig:
    return AgentsConfig(**_load_yaml(path))
