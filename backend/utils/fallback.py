import logging

from backend.config import settings

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for LLM fallback to Google AI Studio."""

    def __init__(self, failure_threshold: int = 3, reset_after: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.reset_after = reset_after
        self._failures = 0
        self._is_open = False
        self._last_failure_time: float | None = None

    def record_failure(self) -> None:
        import time

        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            self._is_open = True
            logger.warning("Circuit breaker OPEN — switching to fallback")

    def record_success(self) -> None:
        self._failures = 0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if not self._is_open:
            return False
        # Auto-reset after timeout
        import time

        if (
            self._last_failure_time
            and time.time() - self._last_failure_time > self.reset_after
        ):
            self._is_open = False
            self._failures = 0
            logger.info("Circuit breaker RESET — retrying primary")
            return False
        return True

    @property
    def has_fallback(self) -> bool:
        return bool(settings.google_ai_studio_key)


# Global instance
ollama_breaker = CircuitBreaker()
