from __future__ import annotations

import time

import pytest

from services.observability.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    RateLimiter,
    RateLimitExceeded,
    TokenBudget,
    TokenBudgetExceeded,
    compute_delay,
    retry,
    with_fallback,
)


def test_rate_limiter_allows_burst_then_blocks():
    rl = RateLimiter(rate=10, capacity=3)
    assert rl.try_acquire() and rl.try_acquire() and rl.try_acquire()
    assert rl.try_acquire() is False  # burst exhausted


def test_rate_limiter_refills():
    rl = RateLimiter(rate=100, capacity=1)
    assert rl.try_acquire()
    assert rl.try_acquire() is False
    time.sleep(0.05)  # ~5 tokens refilled
    assert rl.try_acquire()


def test_rate_limiter_acquire_timeout():
    rl = RateLimiter(rate=1, capacity=1)
    rl.try_acquire()
    with pytest.raises(RateLimitExceeded):
        rl.acquire(timeout=0.05)


def test_token_budget_window():
    tb = TokenBudget(limit_tokens=100, window_seconds=60)
    tb.charge("t1", 60)
    assert tb.remaining("t1") == 40
    with pytest.raises(TokenBudgetExceeded):
        tb.charge("t1", 50)
    tb.charge("t2", 90)  # other tenant isolated
    assert tb.remaining("t2") == 10


def test_circuit_breaker_trips_and_recovers():
    cb = CircuitBreaker(failure_threshold=2, reset_timeout=0.1)

    def boom():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(boom)
    assert cb.state.value == "open"
    with pytest.raises(CircuitOpenError):
        cb.call(lambda: 1)
    time.sleep(0.12)
    assert cb.state.value == "half_open"
    assert cb.call(lambda: 42) == 42  # success closes it
    assert cb.state.value == "closed"


def test_backoff_delays_are_bounded_and_growing():
    d0 = compute_delay(0, base=0.1, factor=2, cap=5, jitter=False)
    d3 = compute_delay(3, base=0.1, factor=2, cap=5, jitter=False)
    assert d0 == pytest.approx(0.1)
    assert d3 == pytest.approx(0.8)
    assert compute_delay(10, base=0.1, factor=2, cap=5, jitter=False) == 5  # capped


def test_retry_eventually_succeeds():
    calls = {"n": 0}

    @retry(max_attempts=4, base=0, jitter=False, sleep=lambda s: None)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("not yet")
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3


def test_fallback_returns_degraded():
    def primary(x):
        raise RuntimeError("down")

    runner = with_fallback(primary, lambda x: f"degraded:{x}")
    assert runner("v") == "degraded:v"
