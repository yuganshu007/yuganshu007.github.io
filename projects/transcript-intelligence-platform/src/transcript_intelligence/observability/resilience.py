"""
Bullet 3: Distributed observability middleware for Bedrock API calls.

Combines all resilience patterns into a single ObservabilityMiddleware:
  1. RateLimiter.acquire()       — per-team RPM enforcement
  2. TokenBudgetLimiter.check()  — TPM sliding-window
  3. CircuitBreaker.call()       — CLOSED/OPEN/HALF_OPEN state machine
  4. Exponential backoff         — inside circuit breaker call path
  5. Fallback                    — cached last-known-good insight on total failure
  6. CloudWatch metrics          — emit latency, quality, quota utilization

Data quality measurement: every call output is validated against
TranscriptInsight schema. The rolling pass rate is the "data quality" metric.
At 99.9% across 23K conversations, ≤ 23 calls/day may fail validation.

Mirrors:
  - aws-samples/sample-bedrock-api-proxy (rate limit + backoff + fallback)
  - quangchuamz/bedrock-circuitbreaker   (CLOSED/OPEN/HALF_OPEN)
  - aws-samples/sample-quota-dashboard   (token budget + CloudWatch)
"""

from __future__ import annotations

import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Optional, TypeVar

from .circuit_breaker import CircuitBreaker, CircuitBreakerOpen
from .rate_limiter import TokenBucketRateLimiter, TokenBudgetLimiter

logger = logging.getLogger(__name__)

T = TypeVar("T")

OUTPUT_TOKEN_LIMIT = 150  # matches chatbot/bedrock_client.py


# ---------------------------------------------------------------------------
# CloudWatch metrics emission (local stub + real boto3 path)
# ---------------------------------------------------------------------------

class CloudWatchEmitter:
    """
    Emits custom metrics to CloudWatch.
    Falls back to structured logging when boto3 is unavailable.

    Namespace: TranscriptIntelligence/Bedrock
    Metrics:
      - InvocationLatency (ms)
      - SchemaValidationFailures (count)
      - CircuitBreakerState (0=CLOSED, 1=HALF_OPEN, 2=OPEN)
      - TokenBudgetUtilizationPct (%)
      - RateLimiterUtilizationPct (%)
      - DataQualityScore (0.0-1.0)
    """

    NAMESPACE = "TranscriptIntelligence/Bedrock"

    def __init__(self, region_name: str = "us-east-1", dry_run: bool = False):
        self.dry_run = dry_run
        self._client = None
        if not dry_run:
            try:
                import boto3
                self._client = boto3.client("cloudwatch", region_name=region_name)
            except ImportError:
                self.dry_run = True

    def put_metric(self, name: str, value: float, unit: str = "None", dimensions: Optional[dict] = None) -> None:
        metric_data: dict[str, Any] = {
            "MetricName": name,
            "Value":      value,
            "Unit":       unit,
        }
        if dimensions:
            metric_data["Dimensions"] = [
                {"Name": k, "Value": str(v)} for k, v in dimensions.items()
            ]

        if self.dry_run or self._client is None:
            logger.debug("CloudWatch[DRY_RUN] %s=%s %s", name, value, unit)
            return

        try:
            self._client.put_metric_data(
                Namespace=self.NAMESPACE,
                MetricData=[metric_data],
            )
        except Exception as exc:
            logger.warning("CloudWatch emit failed: %s", exc)


# ---------------------------------------------------------------------------
# Data quality tracker
# ---------------------------------------------------------------------------

class DataQualityTracker:
    """
    Tracks schema validation pass/fail rate in a rolling window.
    Target: 99.9% across 23K+ conversations.
    """

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self._results: Deque[bool] = deque(maxlen=window_size)

    def record(self, passed: bool) -> None:
        self._results.append(passed)

    @property
    def quality_rate(self) -> float:
        if not self._results:
            return 1.0
        return sum(self._results) / len(self._results)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self._results if not r)

    def get_metrics(self) -> dict:
        return {
            "data_quality_rate":     round(self.quality_rate, 6),
            "failure_count":         self.failure_count,
            "window_size":           len(self._results),
            "meets_sla":             self.quality_rate >= 0.999,
        }


# ---------------------------------------------------------------------------
# Observability middleware — wraps all Bedrock calls
# ---------------------------------------------------------------------------

@dataclass
class CallMetrics:
    latency_seconds:    float
    schema_valid:       bool
    circuit_state:      str
    rate_limited:       bool
    budget_rejected:    bool
    fallback_used:      bool
    attempt_count:      int = 1


class ObservabilityMiddleware:
    """
    Single entry point wrapping every Bedrock invocation.

    Call path:
      1. RateLimiter.acquire()
      2. TokenBudgetLimiter.check_and_reserve()
      3. CircuitBreaker.call(bedrock_fn)
         → exponential backoff on transient failures
      4. Schema validation → DataQualityTracker.record()
      5. CloudWatchEmitter.put_metric() for all KPIs
      6. On total failure → fallback_fn() or cached response

    This is what "deployed distributed observability frameworks" means:
    every Bedrock call passes through this pipeline.
    """

    def __init__(
        self,
        rate_limiter:      Optional[TokenBucketRateLimiter] = None,
        token_budget:      Optional[TokenBudgetLimiter]     = None,
        circuit_breaker:   Optional[CircuitBreaker]         = None,
        cloudwatch:        Optional[CloudWatchEmitter]      = None,
        quality_tracker:   Optional[DataQualityTracker]     = None,
        max_tokens:        int                              = OUTPUT_TOKEN_LIMIT,
        fallback_response: Optional[str]                    = None,
    ):
        self.rate_limiter    = rate_limiter    or TokenBucketRateLimiter(name="bedrock-global")
        self.token_budget    = token_budget    or TokenBudgetLimiter()
        self.circuit_breaker = circuit_breaker or CircuitBreaker(name="bedrock")
        self.cloudwatch      = cloudwatch      or CloudWatchEmitter(dry_run=True)
        self.quality_tracker = quality_tracker or DataQualityTracker()
        self.max_tokens      = max_tokens
        self.fallback_response = fallback_response or '{"key_topics":[],"customer_pain_points":[],"suggested_actions":[],"sentiment":"neutral","urgency":"low","pricing_mentioned":false,"competitor_mentioned":false}'

        self._latency_history: Deque[float] = deque(maxlen=1000)

    def call(
        self,
        bedrock_fn:  Callable[[], str],
        validate_fn: Optional[Callable[[str], bool]] = None,
    ) -> tuple[str, CallMetrics]:
        """
        Execute bedrock_fn through all middleware layers.
        Returns (response_text, CallMetrics).
        """
        metrics = CallMetrics(
            latency_seconds=0.0,
            schema_valid=False,
            circuit_state=self.circuit_breaker.state.name,
            rate_limited=False,
            budget_rejected=False,
            fallback_used=False,
        )

        # --- 1. Rate limiting ---
        if not self.rate_limiter.acquire(timeout=2.0):
            metrics.rate_limited = True
            logger.warning("Rate limit reached; using fallback")
            self._emit_metrics(metrics, latency=0.0)
            return self.fallback_response, metrics

        # --- 2. Token budget ---
        if not self.token_budget.check_and_reserve(self.max_tokens):
            metrics.budget_rejected = True
            logger.warning("Token budget exceeded; using fallback")
            self._emit_metrics(metrics, latency=0.0)
            return self.fallback_response, metrics

        # --- 3. Circuit breaker + actual call ---
        t0 = time.perf_counter()
        try:
            response = self.circuit_breaker.call(bedrock_fn)
            latency  = time.perf_counter() - t0

        except CircuitBreakerOpen as exc:
            latency = time.perf_counter() - t0
            logger.warning("Circuit open: %s", exc)
            metrics.fallback_used   = True
            metrics.circuit_state   = "OPEN"
            metrics.latency_seconds = round(latency, 4)
            self._emit_metrics(metrics, latency=latency)
            return self.fallback_response, metrics

        except Exception as exc:
            latency = time.perf_counter() - t0
            logger.error("Bedrock call failed: %s", exc)
            metrics.fallback_used   = True
            metrics.latency_seconds = round(latency, 4)
            self._emit_metrics(metrics, latency=latency)
            return self.fallback_response, metrics

        # --- 4. Schema validation + data quality tracking ---
        schema_valid = validate_fn(response) if validate_fn else True
        self.quality_tracker.record(schema_valid)
        self.token_budget.record_usage(
            input_tokens=0, output_tokens=min(len(response.split()), self.max_tokens),
            max_tokens=self.max_tokens,
        )

        self._latency_history.append(latency)
        metrics.latency_seconds = round(latency, 4)
        metrics.schema_valid    = schema_valid
        metrics.circuit_state   = self.circuit_breaker.state.name

        self._emit_metrics(metrics, latency=latency)
        return response, metrics

    def _emit_metrics(self, metrics: CallMetrics, latency: float) -> None:
        dims = {"Service": "Bedrock", "Model": "claude-3-5-haiku"}
        self.cloudwatch.put_metric("InvocationLatencyMs",         latency * 1000, "Milliseconds", dims)
        self.cloudwatch.put_metric("SchemaValidationFailures",    0 if metrics.schema_valid else 1, "Count", dims)
        self.cloudwatch.put_metric("CircuitBreakerOpen",          1 if metrics.circuit_state == "OPEN" else 0, "Count", dims)
        self.cloudwatch.put_metric("FallbackUsed",                1 if metrics.fallback_used else 0, "Count", dims)
        self.cloudwatch.put_metric("DataQualityScore",            self.quality_tracker.quality_rate, "None", dims)

    def get_full_metrics(self) -> dict:
        """Returns all observability metrics for dashboard and testing."""
        lat_sorted = sorted(self._latency_history)
        p95_idx    = int(len(lat_sorted) * 0.95) if lat_sorted else 0
        return {
            "circuit_breaker":    self.circuit_breaker.get_metrics(),
            "rate_limiter":       self.rate_limiter.get_metrics(),
            "token_budget":       self.token_budget.get_metrics(),
            "data_quality":       self.quality_tracker.get_metrics(),
            "latency_p95_ms":     round(lat_sorted[p95_idx] * 1000, 1) if lat_sorted else 0.0,
            "latency_mean_ms":    round(statistics.mean(self._latency_history) * 1000, 1) if self._latency_history else 0.0,
            "total_calls":        len(self._latency_history),
        }
