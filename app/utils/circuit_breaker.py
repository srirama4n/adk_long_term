"""Simple in-memory circuit breaker for external/tool calls."""

from __future__ import annotations

import time
from typing import Callable, TypeVar

from app.config import get_settings

T = TypeVar("T")


class CircuitBreaker:
    """Circuit breaker: open after N failures, recover after a cooldown."""

    def __init__(
        self,
        failure_threshold: int | None = None,
        recovery_seconds: int | None = None,
    ) -> None:
        s = get_settings()
        self.failure_threshold = failure_threshold or s.circuit_breaker_failure_threshold
        self.recovery_seconds = recovery_seconds or s.circuit_breaker_recovery_seconds
        self.failures = 0
        self.last_failure_time: float | None = None
        self.state = "closed"  # closed | open | half_open

    def _maybe_recover(self) -> None:
        if self.state != "open" or self.last_failure_time is None:
            return
        if time.monotonic() - self.last_failure_time >= self.recovery_seconds:
            self.state = "half_open"
            self.failures = 0

    def record_success(self) -> None:
        if self.state == "half_open":
            self.state = "closed"
        self.failures = 0

    def record_failure(self) -> None:
        self.failures += 1
        self.last_failure_time = time.monotonic()
        if self.failures >= self.failure_threshold:
            self.state = "open"

    def can_execute(self) -> bool:
        self._maybe_recover()
        return self.state in ("closed", "half_open")

    def call_sync(self, fn: Callable[..., T], *args: object, **kwargs: object) -> T:
        """Execute a synchronous call with circuit breaker."""
        if not self.can_execute():
            raise RuntimeError("Circuit breaker is open")
        try:
            result = fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise
