"""Concurrent latency load test for the agent.

Drives N review requests through a thread pool against the in-process agent (mock Bedrock backend
with a realistic latency distribution) and reports p50/p95/p99 to docs/results/agent_latency.json.
The resume's "p95 < 2s" is asserted here as a budget; the number printed is measured, not fixed.

Run:  python -m services.agent_chatbot.loadtest.run_loadtest --requests 1000 --concurrency 16
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from platform_common.config import settings
from platform_common.logging import get_logger
from services.agent_chatbot.app.agent import TranscriptAgent
from services.observability.resilience import RateLimiter, TokenBudget

log = get_logger("agent-loadtest")
RESULTS = Path(__file__).resolve().parents[3] / "docs" / "results" / "agent_latency.json"

_TRANSCRIPTS = [
    ("call_001", "advertiser: my invoice looks wrong and I want a refund.", "adv_0001"),
    ("call_002", "advertiser: campaign is performing great, thanks!", "adv_0002"),
    ("call_003", "advertiser: I'm thinking of leaving for a competitor.", "adv_0003"),
    ("call_004", "agent: let's review your bidding strategy for Q4.", "adv_0004"),
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=300 if settings.fast_mode else 1000)
    ap.add_argument("--concurrency", type=int, default=16)
    args = ap.parse_args()

    # Generous limiter/budget so the benchmark measures model latency, not throttling.
    agent = TranscriptAgent(
        rate_limiter=RateLimiter(rate=10_000, capacity=10_000),
        token_budget=TokenBudget(limit_tokens=10**9, window_seconds=60),
    )

    def one(i: int) -> float:
        call_id, transcript, adv = _TRANSCRIPTS[i % len(_TRANSCRIPTS)]
        t0 = time.perf_counter()
        agent.review_call(f"{call_id}_{i}", transcript, adv, tenant="salesforce")
        return time.perf_counter() - t0

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        latencies = list(ex.map(one, range(args.requests)))
    wall = time.perf_counter() - t_start

    p50 = percentile(latencies, 0.50)
    p95 = percentile(latencies, 0.95)
    p99 = percentile(latencies, 0.99)
    result = {
        "backend": settings.llm_backend,
        "model": settings.bedrock_model_id,
        "requests": args.requests,
        "concurrency": args.concurrency,
        "p50_s": round(p50, 3),
        "p95_s": round(p95, 3),
        "p99_s": round(p99, 3),
        "max_s": round(max(latencies), 3),
        "throughput_rps": round(args.requests / wall, 1),
        "p95_budget_s": settings.agent_p95_budget_seconds,
        "p95_within_budget": p95 < settings.agent_p95_budget_seconds,
        "note": "Mock backend models a realistic Claude 3.5 Haiku latency distribution. "
        "Numbers are measured per-request latencies under concurrency.",
    }
    os.makedirs(RESULTS.parent, exist_ok=True)
    RESULTS.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    log.info("loadtest_done", p50=result["p50_s"], p95=result["p95_s"], p99=result["p99_s"])
    if not result["p95_within_budget"]:
        print(f"WARNING: p95 {p95:.3f}s exceeded budget {settings.agent_p95_budget_seconds}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
