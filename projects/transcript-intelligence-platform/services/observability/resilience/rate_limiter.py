"""Token-bucket rate limiter (thread-safe)."""
from __future__ import annotations

import threading
import time


class RateLimitExceeded(Exception):
    pass


class RateLimiter:
    """Classic token bucket: `rate` tokens/sec, burst capacity `capacity`."""

    def __init__(self, rate: float, capacity: float | None = None):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self._tokens = self.capacity
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def acquire(self, tokens: float = 1.0, timeout: float | None = None) -> None:
        """Block until tokens are available or raise RateLimitExceeded after timeout."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            if self.try_acquire(tokens):
                return
            if deadline is not None and time.monotonic() >= deadline:
                raise RateLimitExceeded("rate limit timeout")
            time.sleep(min(0.01, tokens / self.rate))
