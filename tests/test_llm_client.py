import pytest
from unittest.mock import AsyncMock, MagicMock
from src.core.llm_client import LLMRegistry, AllProvidersUnavailable
from src.core.config import (
    LLMConfig, AgentsConfig, ProviderConfig, ModelInfo,
    AgentConfig, ModelBinding, ModelRef, BudgetConfig
)

@pytest.fixture
def llm_cfg():
    return LLMConfig(providers={
        "minimax": ProviderConfig(
            base_url="https://api.minimax.chat/v1", api_key="sk-test",
            models=[ModelInfo(id="MiniMax-M3", price_per_1k_in=0.0003, price_per_1k_out=0.0012, max_tokens=8192)]
        )
    })

@pytest.fixture
def agents_cfg():
    return AgentsConfig(
        agents={
            "github_analyzer": AgentConfig(
                model=ModelBinding(
                    primary=ModelRef(provider="minimax", model="MiniMax-M3"),
                    fallback=[]
                ),
                params={"temperature": 0.3, "max_tokens": 2048}
            ),
        },
        budget=BudgetConfig(monthly=10.0, soft_limit=0.8, hard_limit=1.0)
    )

def test_get_client_primary(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    client, provider, model_id, params = registry.get_client("github_analyzer")
    assert provider == "minimax"
    assert model_id == "MiniMax-M3"
    assert params["temperature"] == 0.3

def test_fallback_on_unhealthy(llm_cfg, agents_cfg):
    """无 fallback 时应该抛出异常"""
    registry = LLMRegistry(llm_cfg, agents_cfg)
    registry.health.record_failure("minimax", "500")
    registry.health.record_failure("minimax", "500")
    registry.health.record_failure("minimax", "500")  # open
    with pytest.raises(AllProvidersUnavailable):
        registry.get_client("github_analyzer")

def test_soft_limit_keeps_primary_when_no_fallback(llm_cfg, agents_cfg):
    """软限制用于切换便宜 fallback；没有 fallback 时继续 primary。"""
    registry = LLMRegistry(llm_cfg, agents_cfg)
    registry.budget._daily_spend["__global__"] = registry.budget.daily_limit * 0.85
    _, provider, model_id, _ = registry.get_client("github_analyzer")

    assert provider == "minimax"
    assert model_id == "MiniMax-M3"

def test_hard_limit_raises(llm_cfg, agents_cfg):
    """硬熔断 (100%) → 全部不可用"""
    registry = LLMRegistry(llm_cfg, agents_cfg)
    registry.budget._daily_spend["__global__"] = registry.budget.daily_limit
    with pytest.raises(AllProvidersUnavailable):
        registry.get_client("github_analyzer")

def test_all_unavailable_raises(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    for _ in range(3):
        registry.health.record_failure("minimax", "500")
    with pytest.raises(AllProvidersUnavailable):
        registry.get_client("github_analyzer")

def test_calc_cost(llm_cfg, agents_cfg):
    registry = LLMRegistry(llm_cfg, agents_cfg)
    cost = registry.calc_cost("minimax", "MiniMax-M3", 1000, 500)
    # 1000/1000 * 0.0003 + 500/1000 * 0.0012 = 0.0003 + 0.0006 = 0.0009
    assert cost == pytest.approx(0.0009, rel=1e-6)
