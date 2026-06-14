from __future__ import annotations

import os

import pytest

from services.agent_chatbot.app.agent import TranscriptAgent, route_tools
from services.agent_chatbot.app.bedrock_client import BedrockClient
from services.agent_chatbot.app.validation import validate
from services.observability.resilience import CircuitBreaker, RateLimiter, TokenBudget


@pytest.fixture(autouse=True)
def _fast_mock():
    os.environ["MOCK_NO_SLEEP"] = "1"
    yield
    os.environ.pop("MOCK_NO_SLEEP", None)


def _agent() -> TranscriptAgent:
    return TranscriptAgent(
        client=BedrockClient(backend="mock"),
        rate_limiter=RateLimiter(rate=10_000, capacity=10_000),
        token_budget=TokenBudget(limit_tokens=10**9),
    )


def test_review_always_schema_valid():
    agent = _agent()
    for i in range(200):  # includes the ~3% intentionally-malformed responses -> repair loop
        res = agent.review_call(f"call_{i}", "advertiser: my invoice is wrong", "adv_1", "salesforce")
        assert validate(res.review) == [], f"invalid review: {res.review}"


def test_billing_routes_billing_tool():
    assert "get_billing_summary" in route_tools("my invoice charge is wrong")
    assert "get_billing_summary" not in route_tools("campaign looks great")


def test_token_budget_triggers_fallback():
    agent = TranscriptAgent(
        client=BedrockClient(backend="mock"),
        rate_limiter=RateLimiter(rate=10_000, capacity=10_000),
        token_budget=TokenBudget(limit_tokens=1, window_seconds=60),  # immediately exhausted
    )
    res = agent.review_call("call_x", "advertiser: hello", "adv_1", "salesforce")
    assert res.used_fallback is True
    assert validate(res.review) == []


def test_open_circuit_triggers_fallback():
    breaker = CircuitBreaker(failure_threshold=1, reset_timeout=999, name="t")

    class Boom(BedrockClient):
        def converse(self, *a, **k):
            raise RuntimeError("bedrock down")

    agent = TranscriptAgent(
        client=Boom(backend="mock"),
        rate_limiter=RateLimiter(rate=10_000, capacity=10_000),
        token_budget=TokenBudget(limit_tokens=10**9),
        breaker=breaker,
    )
    res = agent.review_call("call_y", "advertiser: hello", "adv_1", "salesforce")
    assert res.used_fallback is True
    assert validate(res.review) == []
