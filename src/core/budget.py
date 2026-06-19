from collections.abc import Callable
from datetime import date

from .config import BudgetConfig
from .time import today_bj


class BudgetTracker:
    def __init__(
        self,
        budget_cfg: BudgetConfig,
        date_provider: Callable[[], str | date] = today_bj,
    ):
        self.monthly_limit = budget_cfg.monthly
        self.soft_limit = budget_cfg.soft_limit
        self.hard_limit = budget_cfg.hard_limit
        self.daily_limit = budget_cfg.monthly / 30
        self._daily_spend: dict[str, float] = {}
        self._date_provider = date_provider
        self._spend_date = self._date_provider()

    def _reset_if_new_day(self) -> None:
        current_date = self._date_provider()
        if current_date != self._spend_date:
            self._daily_spend.clear()
            self._spend_date = current_date

    def add_cost(self, provider: str, cost: float):
        self._reset_if_new_day()
        self._daily_spend["__global__"] = self._daily_spend.get("__global__", 0) + cost
        self._daily_spend[provider] = self._daily_spend.get(provider, 0) + cost

    def current_daily(self) -> float:
        self._reset_if_new_day()
        return self._daily_spend.get("__global__", 0.0)

    def provider_daily(self, provider: str) -> float:
        self._reset_if_new_day()
        return self._daily_spend.get(provider, 0.0)

    def is_soft_exceeded(self) -> bool:
        return self.current_daily() >= self.daily_limit * self.soft_limit

    def is_hard_exceeded(self) -> bool:
        return self.current_daily() >= self.daily_limit * self.hard_limit

    def reset_daily(self):
        self._daily_spend.clear()
        self._spend_date = self._date_provider()

    def set_daily_spend(
        self,
        total: float,
        provider_spend: dict[str, float] | None = None,
    ) -> None:
        self._spend_date = self._date_provider()
        self._daily_spend = {"__global__": max(float(total), 0.0)}
        for provider, cost in (provider_spend or {}).items():
            self._daily_spend[provider] = max(float(cost), 0.0)
