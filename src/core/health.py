import time

class HealthTracker:
    BASE_COOLDOWN = 60
    MAX_COOLDOWN = 600
    FAILURE_THRESHOLD = 3

    def __init__(self):
        self._state: dict[str, dict] = {}

    def _ensure(self, provider: str):
        if provider not in self._state:
            self._state[provider] = {
                "status": "healthy",
                "error_count": 0,
                "last_error": None,
                "latency_ms": None,
                "circuit": "closed",
                "cooldown_level": 1,
                "opened_at": 0.0,
                "last_check": None,
            }

    def _cooldown_seconds(self, provider: str) -> int:
        self._ensure(provider)
        level = self._state[provider].get("cooldown_level", 1)
        return min(self.BASE_COOLDOWN * (2 ** (level - 1)), self.MAX_COOLDOWN)

    def is_healthy(self, provider: str) -> bool:
        self._ensure(provider)
        s = self._state[provider]
        if s["circuit"] == "closed":
            return True
        if s["circuit"] == "open":
            elapsed = time.time() - s["opened_at"]
            if elapsed >= self._cooldown_seconds(provider):
                s["circuit"] = "half_open"
                return True
            return False
        # half_open
        return True

    def circuit_is_open(self, provider: str) -> bool:
        return not self.is_healthy(provider)

    def record_success(self, provider: str, latency_ms: int):
        self._ensure(provider)
        s = self._state[provider]
        s["error_count"] = 0
        s["cooldown_level"] = 1
        s["latency_ms"] = latency_ms
        s["status"] = "healthy"
        s["last_check"] = time.time()
        if s["circuit"] == "half_open":
            s["circuit"] = "closed"

    def record_failure(self, provider: str, error: str):
        self._ensure(provider)
        s = self._state[provider]
        s["error_count"] += 1
        s["last_error"] = error
        s["last_check"] = time.time()

        if s["circuit"] == "half_open":
            s["circuit"] = "open"
            s["cooldown_level"] += 1
            s["opened_at"] = time.time()
            s["status"] = "unhealthy"
        elif s["error_count"] >= self.FAILURE_THRESHOLD and s["circuit"] == "closed":
            s["circuit"] = "open"
            s["opened_at"] = time.time()
            s["status"] = "unhealthy"