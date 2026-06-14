"""Per-tenant token budgeting with a sliding time window.

LLM cost control: each tenant gets a token allowance per rolling window. Exceeding it raises so
callers can shed load / fall back instead of running up an unbounded Bedrock bill.
"""
from __future__ import annotations

import threading
import time
from collections import deque


class TokenBudgetExceeded(Exception):
    pass


class TokenBudget:
    def __init__(self, limit_tokens: int, window_seconds: float = 60.0):
        self.limit = limit_tokens
        self.window = window_seconds
        self._events: dict[str, deque[tuple[float, int]]] = {}
        self._lock = threading.Lock()

    def _evict(self, tenant: str, now: float) -> int:
        dq = self._events.setdefault(tenant, deque())
        while dq and dq[0][0] < now - self.window:
            dq.popleft()
        return sum(t for _, t in dq)

    def remaining(self, tenant: str) -> int:
        with self._lock:
            return max(0, self.limit - self._evict(tenant, time.monotonic()))

    def charge(self, tenant: str, tokens: int) -> None:
        """Record token usage; raise TokenBudgetExceeded if it would exceed the window budget."""
        with self._lock:
            now = time.monotonic()
            used = self._evict(tenant, now)
            if used + tokens > self.limit:
                raise TokenBudgetExceeded(
                    f"tenant={tenant} would use {used + tokens} > budget {self.limit}"
                )
            self._events[tenant].append((now, tokens))
