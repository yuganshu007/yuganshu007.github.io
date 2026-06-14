"""
Circuit breaker pattern for Bedrock API calls.

State machine: CLOSED → OPEN → HALF_OPEN
  CLOSED:    Normal operation; failures tracked in rolling window
  OPEN:      Fast-fail for `recovery_timeout` seconds after threshold breach
  HALF_OPEN: Single probe request; success → CLOSED, failure → OPEN

Thresholds tuned for 23K+ conversation/day volume:
  failure_threshold = 10 failures in 60 seconds
  recovery_timeout  = 30 seconds
  success_threshold = 2 consecutive successes to return to CLOSED

Mirrors quangchuamz/bedrock-circuitbreaker pattern and
heqiucheng/aws-ai-observability-prompts circuit breaker design.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from enum import Enum, auto
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED    = auto()
    OPEN      = auto()
    HALF_OPEN = auto()


class CircuitBreakerOpen(Exception):
    """Raised when a call is attempted while the circuit is OPEN."""


class CircuitBreaker:
    """
    Thread-safe circuit breaker implementation.

    Usage:
        cb = CircuitBreaker(failure_threshold=10, window_seconds=60, recovery_timeout=30)

        def call_bedrock():
            return client.invoke(prompt)

        result = cb.call(call_bedrock)
    """

    def __init__(
        self,
        failure_threshold:  int   = 10,
        window_seconds:     float = 60.0,
        recovery_timeout:   float = 30.0,
        success_threshold:  int   = 2,
        name:               str   = "bedrock",
    ):
        self.failure_threshold  = failure_threshold
        self.window_seconds     = window_seconds
        self.recovery_timeout   = recovery_timeout
        self.success_threshold  = success_threshold
        self.name               = name

        self._state             = CircuitState.CLOSED
        self._lock              = threading.Lock()
        self._failure_times: deque[float] = deque()
        self._open_since:    float = 0.0
        self._half_open_successes: int = 0

    @property
    def state(self) -> CircuitState:
        return self._state

    def call(self, fn: Callable[[], T]) -> T:
        """
        Execute fn() through the circuit breaker.
        Raises CircuitBreakerOpen if state is OPEN.
        """
        with self._lock:
            self._refresh_state()

            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpen(
                    f"Circuit [{self.name}] is OPEN. Retry after "
                    f"{self._open_since + self.recovery_timeout - time.monotonic():.1f}s"
                )

        try:
            result = fn()
            self._record_success()
            return result
        except Exception as exc:
            self._record_failure()
            raise

    def _refresh_state(self) -> None:
        """Transition OPEN → HALF_OPEN after recovery_timeout."""
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._open_since >= self.recovery_timeout:
                logger.info("Circuit [%s]: OPEN → HALF_OPEN (probe allowed)", self.name)
                self._state                = CircuitState.HALF_OPEN
                self._half_open_successes  = 0

    def _record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.success_threshold:
                    logger.info("Circuit [%s]: HALF_OPEN → CLOSED", self.name)
                    self._state         = CircuitState.CLOSED
                    self._failure_times.clear()

    def _record_failure(self) -> None:
        now = time.monotonic()
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.warning("Circuit [%s]: HALF_OPEN → OPEN (probe failed)", self.name)
                self._state      = CircuitState.OPEN
                self._open_since = now
                return

            # Prune failures outside the rolling window
            cutoff = now - self.window_seconds
            while self._failure_times and self._failure_times[0] < cutoff:
                self._failure_times.popleft()

            self._failure_times.append(now)

            if (self._state == CircuitState.CLOSED and
                    len(self._failure_times) >= self.failure_threshold):
                logger.warning(
                    "Circuit [%s]: CLOSED → OPEN (%d failures in %.0fs window)",
                    self.name, len(self._failure_times), self.window_seconds,
                )
                self._state      = CircuitState.OPEN
                self._open_since = now

    def get_metrics(self) -> dict:
        """Returns current circuit breaker state for CloudWatch emission."""
        with self._lock:
            return {
                "circuit_name":        self.name,
                "state":               self._state.name,
                "failure_count":       len(self._failure_times),
                "failure_threshold":   self.failure_threshold,
                "is_open":             self._state == CircuitState.OPEN,
                "seconds_until_probe": max(
                    0.0,
                    (self._open_since + self.recovery_timeout - time.monotonic())
                    if self._state == CircuitState.OPEN else 0.0,
                ),
            }
