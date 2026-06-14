"""Amazon Bedrock client wrapper for Claude 3.5 Haiku.

Two backends behind one interface:
  * "bedrock": real `bedrock-runtime` Converse API (used when AWS creds + LLM_BACKEND=bedrock).
  * "mock":    a faithful local stand-in with the SAME response contract and a realistic latency
               distribution, so the agent, validation, and load test all run without AWS.

The mock is deterministic given the transcript, lets us exercise the schema-validation repair
loop (it can emit a malformed response on demand), and models p50/p95 latency so the latency
benchmark is meaningful.
"""
from __future__ import annotations

import json
import os
import random
import re
import time
from dataclasses import dataclass

from platform_common.config import settings
from platform_common.logging import get_logger

log = get_logger("bedrock-client")


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float


class BedrockClient:
    def __init__(self, model_id: str | None = None, backend: str | None = None):
        self.model_id = model_id or settings.bedrock_model_id
        self.backend = backend or settings.llm_backend
        self._rt = None
        if self.backend == "bedrock":
            import boto3  # imported lazily so mock mode needs no AWS deps configured

            self._rt = boto3.client("bedrock-runtime", region_name=settings.aws_region)

    # --- public API -----------------------------------------------------------------
    def converse(self, system: str, messages: list[dict], max_tokens: int = 512) -> LLMResponse:
        if self.backend == "bedrock":
            return self._converse_bedrock(system, messages, max_tokens)
        return self._converse_mock(system, messages, max_tokens)

    # --- real Bedrock ---------------------------------------------------------------
    def _converse_bedrock(self, system, messages, max_tokens) -> LLMResponse:
        t0 = time.perf_counter()
        resp = self._rt.converse(
            modelId=self.model_id,
            system=[{"text": system}],
            messages=[{"role": m["role"], "content": [{"text": m["content"]}]} for m in messages],
            inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0},
        )
        latency = time.perf_counter() - t0
        text = resp["output"]["message"]["content"][0]["text"]
        usage = resp.get("usage", {})
        return LLMResponse(
            text=text,
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            latency_s=latency,
        )

    # --- faithful local mock --------------------------------------------------------
    def _converse_mock(self, system, messages, max_tokens) -> LLMResponse:
        user = messages[-1]["content"]
        call_id = _extract_call_id(user)
        rng = random.Random(hash(user) & 0xFFFFFFFF)

        # Realistic latency: log-normal-ish, p50 ~0.35s, occasional slow tail < 2s.
        latency = min(1.9, abs(rng.gauss(0.35, 0.18)) + rng.random() * 0.25)
        if os.getenv("MOCK_NO_SLEEP") != "1":
            time.sleep(latency)

        review = _mock_review(call_id, user, rng)
        # ~3% of the time emit a schema-violating response to exercise the repair loop.
        if rng.random() < 0.03 and os.getenv("MOCK_FORCE_VALID") != "1":
            review.pop("confidence", None)
        text = json.dumps(review)
        return LLMResponse(
            text=text,
            input_tokens=len(user) // 4,
            output_tokens=len(text) // 4,
            latency_s=latency,
        )


def _extract_call_id(user: str) -> str:
    m = re.search(r"call_id=([\w\-]+)", user)
    return m.group(1) if m else "unknown"


def _mock_review(call_id: str, user: str, rng: random.Random) -> dict:
    low = user.lower()
    if "invoice" in low or "billing" in low:
        sentiment, flags = "negative", ["billing_dispute"]
        items = ["Open a billing review"]
    elif "leaving" in low or "cancel" in low or "churn" in low:
        sentiment, flags = "negative", ["churn_risk"]
        items = ["Schedule a retention follow-up"]
    else:
        sentiment = rng.choice(["positive", "neutral"])
        flags, items = ["none"], []
    return {
        "call_id": call_id,
        "summary": "Advertiser discussed campaign performance and next steps with the rep.",
        "sentiment": sentiment,
        "action_items": items,
        "risk_flags": flags,
        "confidence": round(rng.uniform(0.6, 0.95), 2),
    }
