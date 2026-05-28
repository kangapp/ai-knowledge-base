import time
from src.core.health import HealthTracker

def test_initial_healthy():
    ht = HealthTracker()
    assert ht.is_healthy("minimax")

def test_consecutive_failures_open_circuit():
    ht = HealthTracker()
    ht.record_failure("minimax", "500")
    ht.record_failure("minimax", "500")
    ht.record_failure("minimax", "timeout")  # 3rd → open
    assert ht._state["minimax"]["circuit"] == "open"
    assert not ht.is_healthy("minimax")

def test_half_open_trial_success():
    ht = HealthTracker()
    ht._state["minimax"] = {"circuit": "open", "error_count": 3, "cooldown_level": 1, "opened_at": time.time() - 999, "status": "unhealthy", "last_error": "timeout"}
    # 冷却时间过 → half_open
    assert ht.is_healthy("minimax")  # half_open allows
    ht.record_success("minimax", 100)
    assert ht._state["minimax"]["circuit"] == "closed"

def test_exponential_backoff():
    ht = HealthTracker()
    assert ht._cooldown_seconds("minimax") == 60   # level 1 (default)
    ht._state["minimax"]["cooldown_level"] = 2
    assert ht._cooldown_seconds("minimax") == 120
    ht._state["minimax"]["cooldown_level"] = 3
    assert ht._cooldown_seconds("minimax") == 240
    ht._state["minimax"]["cooldown_level"] = 5
    assert ht._cooldown_seconds("minimax") == 600  # capped

def test_record_success_resets():
    ht = HealthTracker()
    ht.is_healthy("minimax")  # 初始化 provider
    ht._state["minimax"]["error_count"] = 2
    ht.record_success("minimax", 150)
    assert ht._state["minimax"]["error_count"] == 0
    assert ht._state["minimax"]["cooldown_level"] == 1

def test_half_open_failure_back_to_open():
    ht = HealthTracker()
    ht._state["minimax"] = {"circuit": "half_open", "error_count": 0, "cooldown_level": 1, "opened_at": time.time(), "status": "healthy", "last_error": None}
    ht.record_failure("minimax", "still failing")
    assert ht._state["minimax"]["circuit"] == "open"
    assert ht._state["minimax"]["cooldown_level"] == 2