import time
import logging
import asyncio

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, name: str, fail_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.fail_threshold = fail_threshold
        self.recovery_timeout = recovery_timeout
        self.fail_count = 0
        self.state = "closed"
        self.opened_at = 0.0
        self._lock = asyncio.Lock()

    async def call_allowed(self) -> bool:
        async with self._lock:
            if self.state == "open":
                if time.time() - self.opened_at > self.recovery_timeout:
                    self.state = "half_open"
                    logger.info(f"Circuit breaker '{self.name}' half_open, testing")
                    return True
                return False
            return True

    async def record_success(self):
        async with self._lock:
            if self.state == "half_open":
                logger.info(f"Circuit breaker '{self.name}' recovered, closing")
            self.fail_count = 0
            self.state = "closed"

    async def record_failure(self):
        async with self._lock:
            self.fail_count += 1
            if self.fail_count >= self.fail_threshold:
                self.state = "open"
                self.opened_at = time.time()
                logger.warning(f"Circuit breaker '{self.name}' opened after {self.fail_count} failures")

    def get_state(self) -> dict:
        return {
            "state": self.state,
            "fail_count": self.fail_count,
            "opened_at": self.opened_at if self.state == "open" else None,
        }


hh_breaker = CircuitBreaker("hh.ru", fail_threshold=5, recovery_timeout=60)
groq_breaker = CircuitBreaker("Groq", fail_threshold=3, recovery_timeout=30)
