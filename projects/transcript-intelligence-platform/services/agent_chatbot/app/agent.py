"""Agentic orchestration over Bedrock Claude 3.5 Haiku.

LangChain-style loop:
  1. system prompt + few-shot establish the output contract (prompt engineering),
  2. a router selects tools (enrichment) based on the transcript,
  3. tool results are appended to the context,
  4. the model produces a structured CallReview,
  5. the output is JSON-schema validated with a bounded repair round-trip,
  6. every model call is guarded by rate limiting, token budgeting, a circuit breaker,
     exponential backoff, and a deterministic fallback (Pillar 3).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from platform_common.logging import get_logger
from services.agent_chatbot.app.bedrock_client import BedrockClient, LLMResponse
from services.agent_chatbot.app.validation import (
    SchemaValidationError,
    parse_and_validate,
)
from services.agent_chatbot.prompts import (
    FEW_SHOT_ASSISTANT,
    FEW_SHOT_USER,
    SYSTEM_PROMPT,
    build_user_prompt,
)
from services.observability.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    RateLimiter,
    TokenBudget,
    TokenBudgetExceeded,
    retry,
)

log = get_logger("agent")


# --- tools (LangChain-style) --------------------------------------------------------
def tool_get_account_status(advertiser_id: str) -> str:
    """Mock enrichment tool. In production this hits an internal account API."""
    return f"account {advertiser_id}: status=active, tier=standard, open_tickets=0"


def tool_get_billing_summary(advertiser_id: str) -> str:
    return f"billing {advertiser_id}: last_invoice=ok, disputes=0"


TOOLS: dict[str, Callable[[str], str]] = {
    "get_account_status": tool_get_account_status,
    "get_billing_summary": tool_get_billing_summary,
}


def route_tools(transcript: str) -> list[str]:
    """Decide which tools to call (a real agent would let the model choose; we route on cues)."""
    low = transcript.lower()
    selected = ["get_account_status"]
    if "invoice" in low or "billing" in low or "charge" in low:
        selected.append("get_billing_summary")
    return selected


@dataclass
class AgentResult:
    review: dict
    latency_s: float
    input_tokens: int
    output_tokens: int
    tools_used: list[str] = field(default_factory=list)
    repaired: bool = False
    used_fallback: bool = False


class TranscriptAgent:
    def __init__(
        self,
        client: BedrockClient | None = None,
        rate_limiter: RateLimiter | None = None,
        token_budget: TokenBudget | None = None,
        breaker: CircuitBreaker | None = None,
    ):
        self.client = client or BedrockClient()
        self.rate_limiter = rate_limiter or RateLimiter(rate=50, capacity=50)
        self.token_budget = token_budget or TokenBudget(limit_tokens=1_000_000, window_seconds=60)
        self.breaker = breaker or CircuitBreaker(failure_threshold=5, reset_timeout=10, name="bedrock")

    def _guarded_converse(self, tenant: str, system: str, messages: list[dict]) -> LLMResponse:
        # 1) rate limit, 2) circuit breaker + retry/backoff around the model call.
        self.rate_limiter.acquire(1.0, timeout=2.0)

        @retry(max_attempts=3, base=0.05, cap=0.5)
        def _call() -> LLMResponse:
            return self.breaker.call(self.client.converse, system, messages)

        resp = _call()
        # 3) token budgeting (charge after we know usage).
        self.token_budget.charge(tenant, resp.input_tokens + resp.output_tokens)
        return resp

    def review_call(self, call_id: str, transcript: str, advertiser_id: str, tenant: str) -> AgentResult:
        t0 = time.perf_counter()
        tools_used = route_tools(transcript)
        tool_context = "\n".join(f"[tool:{t}] {TOOLS[t](advertiser_id)}" for t in tools_used)

        user = build_user_prompt(call_id, transcript) + "\n\nContext:\n" + tool_context
        messages = [
            {"role": "user", "content": FEW_SHOT_USER},
            {"role": "assistant", "content": FEW_SHOT_ASSISTANT},
            {"role": "user", "content": user},
        ]

        repaired = False
        used_fallback = False
        in_tok = out_tok = 0
        try:
            resp = self._guarded_converse(tenant, SYSTEM_PROMPT, messages)
            in_tok, out_tok = resp.input_tokens, resp.output_tokens
            try:
                review = parse_and_validate(resp.text)
            except SchemaValidationError as exc:
                # One repair round-trip: tell the model exactly what was wrong.
                repaired = True
                repair_msg = messages + [
                    {"role": "assistant", "content": resp.text},
                    {
                        "role": "user",
                        "content": "Your JSON was invalid: "
                        + "; ".join(exc.errors)
                        + ". Return ONLY corrected JSON.",
                    },
                ]
                resp2 = self._guarded_converse(tenant, SYSTEM_PROMPT, repair_msg)
                in_tok += resp2.input_tokens
                out_tok += resp2.output_tokens
                review = parse_and_validate(resp2.text)
        except (CircuitOpenError, TokenBudgetExceeded, SchemaValidationError, Exception) as exc:
            log.warning("agent_fallback", call_id=call_id, error=repr(exc))
            used_fallback = True
            review = _fallback_review(call_id)

        return AgentResult(
            review=review,
            latency_s=time.perf_counter() - t0,
            input_tokens=in_tok,
            output_tokens=out_tok,
            tools_used=tools_used,
            repaired=repaired,
            used_fallback=used_fallback,
        )


def _fallback_review(call_id: str) -> dict:
    """Schema-valid degraded result used when the model path is unavailable."""
    return {
        "call_id": call_id,
        "summary": "Automated review unavailable; flagged for manual follow-up.",
        "sentiment": "neutral",
        "action_items": ["Manual review required"],
        "risk_flags": ["none"],
        "confidence": 0.0,
    }
