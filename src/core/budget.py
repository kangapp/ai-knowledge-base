from .config import BudgetConfig


class BudgetTracker:
    def __init__(self, budget_cfg: BudgetConfig):
        self.monthly_limit = budget_cfg.monthly
        self.soft_limit = budget_cfg.soft_limit
        self.hard_limit = budget_cfg.hard_limit
        self.daily_limit = budget_cfg.monthly / 30
        self._daily_spend: dict[str, float] = {}
        self._monthly_spend: dict[str, float] = {}

    def add_cost(self, provider: str, cost: float):
        self._daily_spend["__global__"] = self._daily_spend.get("__global__", 0) + cost
        self._daily_spend[provider] = self._daily_spend.get(provider, 0) + cost

    def current_daily(self) -> float:
        return self._daily_spend.get("__global__", 0.0)

    def is_soft_exceeded(self) -> bool:
        return self.current_daily() >= self.daily_limit * self.soft_limit

    def is_hard_exceeded(self) -> bool:
        return self.current_daily() >= self.daily_limit * self.hard_limit

    def reset_daily(self):
        self._daily_spend.clear()