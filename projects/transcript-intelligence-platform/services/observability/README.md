# Pillar 3 — Distributed observability & resilience

Production-grade guards around every external call, plus a data-quality suite and CloudWatch
alarms — the "distributed observability frameworks" and "99.9% data quality" bullet.

## Resilience primitives (`resilience/`)

| Primitive | File | Used by |
|-----------|------|---------|
| Rate limiting (token bucket) | `rate_limiter.py` | agent, analytics |
| Token budgeting (per-tenant, sliding window) | `token_budget.py` | agent (Bedrock cost control) |
| Circuit breaker (closed/open/half-open) | `circuit_breaker.py` | agent, Athena client |
| Exponential backoff + jitter | `backoff.py` | all retryable calls |
| Fallback (degraded result) | `fallback.py` | agent |

All are unit-tested in `tests/test_resilience.py` (trip + recovery, refill, window isolation,
bounded growing backoff, fallback).

## Data quality (the "99.9%")

```bash
python -m services.observability.data_quality.benchmark_quality --data data
```

Runs the rule suite (`quality_checks.py`) over **all 23,000+** conversations and writes the
**measured** pass rate to `docs/results/data_quality.json`, emitting a `PassRatePercent` metric to
CloudWatch (mock locally). With the generator's controlled defect rate the suite measures ≥99.9%.

## CloudWatch alarms (`infra/main.tf`)

Three alarms back "stabilized end-to-end daily runs": data-quality < 99.9%, agent p95 > 2s, and
any failed daily ETL run — each wired to an SNS paging topic.
