from openai import AsyncOpenAI
from .config import LLMConfig, AgentsConfig, ModelRef
from .budget import BudgetTracker
from .health import HealthTracker

class AllProvidersUnavailable(Exception):
    pass

class LLMRegistry:
    def __init__(self, llm_cfg: LLMConfig, agents_cfg: AgentsConfig):
        self._clients: dict[str, AsyncOpenAI] = {}
        self._models: dict[str, list] = {}

        for name, p in llm_cfg.providers.items():
            self._clients[name] = AsyncOpenAI(base_url=p.base_url, api_key=p.api_key)
            self._models[name] = p.models

        self._llm_cfg = llm_cfg
        self._agents = agents_cfg.agents
        self.budget = BudgetTracker(agents_cfg.budget)
        self.health = HealthTracker()

    def get_client(self, agent_name: str) -> tuple[AsyncOpenAI, str, str, dict]:
        """返回 (client, provider_name, model_id, params)。

        预算控制：
        - 硬熔断 (100%): 全部不可用 → AllProvidersUnavailable
        - 软熔断 (80%):  跳过 primary，只用 fallback[]（切便宜模型）
        """
        agent = self._agents[agent_name]

        if self.budget.is_hard_exceeded():
            raise AllProvidersUnavailable(f"Budget hard limit reached")

        chain = [agent.model.primary] + agent.model.fallback

        if self.budget.is_soft_exceeded() and agent.model.fallback:
            chain = agent.model.fallback  # 软熔断：只用 fallback

        for ref in chain:
            if self.health.circuit_is_open(ref.provider):
                continue
            return (
                self._clients[ref.provider],
                ref.provider,
                ref.model,
                agent.params,
            )

        raise AllProvidersUnavailable(f"No available provider for '{agent_name}'")

    def supports_json_mode(self, provider_name: str) -> bool:
        cfg = self._llm_cfg.providers.get(provider_name)
        return cfg.supports_json_mode if cfg else False

    def get_prompt_path(self, agent_name: str) -> str:
        """返回 agent 配置的 prompt 文件路径"""
        return self._agents[agent_name].prompt

    def calc_cost(self, provider: str, model_id: str, tokens_in: int, tokens_out: int) -> float:
        models = self._models.get(provider, [])
        for m in models:
            if m.id == model_id:
                return (tokens_in * m.price_per_1k_in + tokens_out * m.price_per_1k_out) / 1000
        return 0.0
