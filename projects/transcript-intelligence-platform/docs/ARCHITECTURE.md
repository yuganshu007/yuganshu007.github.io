# Architecture

## End-to-end data flow

1. **Landing** — raw advertiser call transcripts arrive as JSONL in an S3 landing prefix,
   partitioned by `tenant` and `dt` (date). Locally this is `data/landing/`.
2. **ETL (Pillar 1)** — a daily EMR/Spark job reads the landing zone, joins transcripts to a
   small advertiser dimension (skew‑safe), de‑duplicates, computes per‑call features, and writes
   **curated Parquet** to the Glue‑cataloged `curated` zone. Writes are **idempotent** (a run
   re‑executed for the same `dt` produces identical output, no dupes).
3. **Agent (Pillar 2)** — for each curated call, the Bedrock Claude 3.5 Haiku agent produces a
   structured "call review" (summary, sentiment, action items, risk flags) validated against a
   JSON schema. Outputs land in the `reviews` zone.
4. **Observability (Pillar 3)** — every external/LLM call is wrapped with rate limiting, a
   per‑tenant token budget, a circuit breaker, exponential backoff, and a fallback. Pipeline
   health and a data‑quality rule suite emit CloudWatch metrics/alarms.
5. **Analytics (Pillar 4)** — a Streamlit/Plotly app queries the curated + reviews zones through
   Athena (Glue catalog). A pre‑aggregated **gold** table powers fast dashboards; degradation
   alerts watch for metric regressions.

## Why the metrics are real (not asserted)

The throughput, latency, data‑quality, and time‑to‑insight numbers are not hard‑coded. Each is
the output of a benchmark that runs two genuinely different code paths over the **same** data and
reports the delta. See [`METRICS.md`](METRICS.md).

## Production deployment (AWS)

| Pillar | Local | AWS |
|--------|-------|-----|
| ETL | PySpark `local[*]` | EMR on EC2 (Terraform `services/etl_spark/infra`) |
| Agent | mock Bedrock backend | `bedrock-runtime` Converse, Lambda/Fargate |
| Observability | in‑process + log emitter | CloudWatch alarms (Terraform `services/observability/infra`) |
| Analytics | DuckDB over Parquet | Athena + Glue (Terraform `services/analytics_dashboard/infra`), ECS Fargate + ALB |

## Resilience boundaries

```
caller ──► RateLimiter ──► TokenBudget ──► CircuitBreaker ──► retry(backoff) ──► [LLM/Athena]
                                                   │ open / exhausted / failure
                                                   ▼
                                              fallback result
```
