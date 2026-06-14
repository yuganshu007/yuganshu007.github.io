"""Circuit breaker with closed / open / half-open states."""
from __future__ import annotations

import threading
import time
from enum import Enum


class State(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    """Trips OPEN after `failure_threshold` consecutive failures; after `reset_timeout` seconds
    moves to HALF_OPEN and allows a trial call; a success closes it, a failure re-opens it.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.name = name
        self._state = State.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> State:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _maybe_half_open(self) -> None:
        if self._state == State.OPEN and time.monotonic() - self._opened_at >= self.reset_timeout:
            self._state = State.HALF_OPEN

    def _on_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = State.CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == State.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = State.OPEN
                self._opened_at = time.monotonic()

    def call(self, fn, *args, **kwargs):
        with self._lock:
            self._maybe_half_open()
            if self._state == State.OPEN:
                raise CircuitOpenError(f"circuit '{self.name}' is open")
        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result
