import pytest
from src.core.config import BudgetConfig
from src.core.budget import BudgetTracker


@pytest.fixture
def tracker():
    return BudgetTracker(BudgetConfig(monthly=10.0, soft_limit=0.8, hard_limit=1.0))


def test_initial_state(tracker):
    assert tracker.current_daily() == 0.0
    assert not tracker.is_soft_exceeded()


def test_add_cost(tracker):
    tracker.add_cost("minimax", 0.5)
    assert tracker.current_daily() == 0.5


def test_soft_exceeded(tracker):
    tracker._daily_spend["__global__"] = tracker.daily_limit * 0.85
    assert tracker.is_soft_exceeded()
    assert not tracker.is_hard_exceeded()


def test_hard_exceeded(tracker):
    tracker._daily_spend["__global__"] = tracker.daily_limit
    assert tracker.is_hard_exceeded()


def test_per_provider_tracking(tracker):
    tracker.add_cost("minimax", 1.0)
    assert tracker.current_daily() == 1.0


def test_reset_daily(tracker):
    tracker.add_cost("minimax", 5.0)
    tracker.reset_daily()
    assert tracker.current_daily() == 0.0