"""
Rate limiting and token budgeting for Bedrock API calls.

Two complementary components:
  1. TokenBucketRateLimiter  — per-team RPM (requests/min) enforcement
  2. TokenBudgetLimiter      — TPM (tokens/min) sliding-window enforcement

Both mirror the patterns from:
  - aws-samples/sample-bedrock-api-proxy (token bucket, per-API-key)
  - aws-samples/sample-quota-dashboard-for-amazon-bedrock (TPM monitoring)
  - zeroae/zae-limiter (DynamoDB-backed token bucket for distributed deployments)

In production this is backed by DynamoDB for cross-process coordination.
In local/test mode it uses in-memory state.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token bucket rate limiter — per-team RPM
# ---------------------------------------------------------------------------

class TokenBucketRateLimiter:
    """
    Classic token bucket algorithm.

    capacity   = max burst (tokens)
    refill_rate = tokens added per second

    For Bedrock at 23K calls/day across 18 teams:
      capacity    = 60   (max 60 requests/min per team, burst to 60)
      refill_rate = 1.0  (1 token/second = 60 RPM steady-state)
    """

    def __init__(
        self,
        capacity:    float = 60.0,
        refill_rate: float = 1.0,
        name:        str   = "default",
    ):
        self.capacity    = capacity
        self.refill_rate = refill_rate
        self.name        = name
        self._tokens     = capacity
        self._last_refill = time.monotonic()
        self._lock       = threading.Lock()

    def acquire(self, tokens: float = 1.0, timeout: float = 5.0) -> bool:
        """
        Attempt to consume `tokens` from the bucket.
        Blocks up to `timeout` seconds waiting for tokens.
        Returns True if acquired, False if timeout exceeded.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
            time.sleep(0.05)
        logger.warning("RateLimiter [%s]: timeout waiting for %s token(s)", self.name, tokens)
        return False

    def _refill(self) -> None:
        now     = time.monotonic()
        elapsed = now - self._last_refill
        added   = elapsed * self.refill_rate
        self._tokens      = min(self.capacity, self._tokens + added)
        self._last_refill = now

    def get_metrics(self) -> dict:
        with self._lock:
            self._refill()
            return {
                "limiter_name":  self.name,
                "tokens_available": round(self._tokens, 2),
                "capacity":      self.capacity,
                "refill_rate_rps": self.refill_rate,
                "utilization_pct": round((1 - self._tokens / self.capacity) * 100, 1),
            }


# ---------------------------------------------------------------------------
# Token budget limiter — TPM sliding window
# ---------------------------------------------------------------------------

@dataclass
class TokenUsageRecord:
    timestamp:    float
    input_tokens: int
    output_tokens: int
    max_tokens:   int  # reservation at request start (causes throttling)


class TokenBudgetLimiter:
    """
    Sliding-window TPM (tokens-per-minute) budget enforcer.

    Bedrock reserves quota based on max_tokens at request start, then applies
    a burndown rate. For Claude 3.5 Haiku the burndown rate is 1x.

    At 23K calls/day with OUTPUT_TOKEN_LIMIT=150:
      avg_tpm = (23000 * 150) / (24 * 60) ≈ 2,395 TPM
      budget  = 10,000 TPM (leave headroom for spikes)

    Mirrors aws-samples/sample-quota-dashboard-for-amazon-bedrock logic.
    """

    def __init__(
        self,
        tpm_budget:      int   = 10_000,
        window_seconds:  float = 60.0,
        burndown_rate:   float = 1.0,   # 1x for Haiku; 5x for Claude 4+
    ):
        self.tpm_budget     = tpm_budget
        self.window_seconds = window_seconds
        self.burndown_rate  = burndown_rate
        self._records:  deque[TokenUsageRecord] = deque()
        self._lock = threading.Lock()

    def check_and_reserve(self, max_tokens: int) -> bool:
        """
        Check if a new request with max_tokens reservation would exceed the budget.
        Returns True if the request is allowed.
        """
        with self._lock:
            self._prune_old_records()
            current_consumption = self._calculate_consumption()
            projected = current_consumption + max_tokens * self.burndown_rate
            if projected > self.tpm_budget:
                logger.warning(
                    "TokenBudget: projected %.0f TPM exceeds budget %d TPM",
                    projected, self.tpm_budget,
                )
                return False
            return True

    def record_usage(self, input_tokens: int, output_tokens: int, max_tokens: int) -> None:
        """Record actual token usage after a completed call."""
        with self._lock:
            self._records.append(TokenUsageRecord(
                timestamp=time.monotonic(),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                max_tokens=max_tokens,
            ))

    def _prune_old_records(self) -> None:
        cutoff = time.monotonic() - self.window_seconds
        while self._records and self._records[0].timestamp < cutoff:
            self._records.popleft()

    def _calculate_consumption(self) -> float:
        return sum(
            (r.input_tokens + r.output_tokens) * self.burndown_rate
            for r in self._records
        )

    def get_metrics(self) -> dict:
        with self._lock:
            self._prune_old_records()
            consumption = self._calculate_consumption()
            return {
                "tpm_consumed":   round(consumption, 0),
                "tpm_budget":     self.tpm_budget,
                "utilization_pct": round(consumption / self.tpm_budget * 100, 1),
                "records_in_window": len(self._records),
            }
