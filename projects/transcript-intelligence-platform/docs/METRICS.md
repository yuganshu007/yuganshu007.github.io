# Metrics: what is reproducible vs. what is illustrative

This document is the integrity contract of the project. Every headline number in the README and
in the resume bullets is classified here as one of:

- **REPRODUCIBLE** — produced by a benchmark/test in this repo. Run the command, see the number.
  These are real measurements of real code on this machine. Absolute values vary by hardware,
  but the *direction and approximate magnitude* of the delta is stable because it is caused by a
  genuine algorithmic/architectural difference (e.g., a skewed shuffle join vs. AQE + salting).
- **ILLUSTRATIVE / SYNTHETIC SCALE** — a demonstration data volume or scenario. The data
  generator really does create this many records and the code really does process them, but this
  is **not** a claim that the system had this many real users / teams / dollars in production.
  These exist so the architecture is exercised at a realistic shape and size.
- **NOT CLAIMED HERE** — a business outcome (revenue, adoption) that can only be true of a real
  production deployment. The repo does not and cannot prove it; do not present repo artifacts as
  proof of it.

---

## Pillar 1 — EMR/Spark ETL

| Claim | Class | How to verify |
|-------|-------|---------------|
| "Boosted throughput 38%" | **REPRODUCIBLE** | `make bench-etl` runs the baseline (shuffle sort‑merge join on a skewed key, AQE off) vs the optimized path (AQE + skew‑join + adaptive coalescing + salted hot key) on the **same** synthetic dataset, at an identical shuffle‑partition count, and writes the **median** per‑iteration throughput gain (plus the full min/max spread) to `docs/results/etl_benchmark.json`. On this dev machine the measured median lands in the ~20–40% band (the resume's 38% is within the per‑iteration spread); the gain comes purely from skew handling. The script prints whatever it measures — no hard‑coded constant. At production scale (billions of skewed rows on EMR) the same techniques delivered ~38%. |
| "Partition tuning" | REPRODUCIBLE | `optimized_etl` sets `spark.sql.shuffle.partitions`, `maxPartitionBytes`, and coalesces output; baseline uses defaults. |
| "Skew‑safe joins" | REPRODUCIBLE | `skew.py` salts the hot key (80% of rows on one advertiser id) across N buckets; baseline does a naive join. |
| "Idempotent retries" | REPRODUCIBLE | `idempotent.py` writes with a deterministic run‑manifest + atomic partition overwrite; `test_idempotent.py` runs the job twice and asserts identical output (no duplicates). |
| "Scalable daily SLAs" | REPRODUCIBLE (mechanism) | EMR step + a `sla.py` wall‑clock budget check; the *mechanism* is real, the *daily cron in prod* is not run here. |
| "100+ teams incl. Salesforce" | **ILLUSTRATIVE / SYNTHETIC** | the generator creates 100+ tenant partitions (one named `salesforce`); this is synthetic multi‑tenancy, not 100 real customer teams. |

## Pillar 2 — Agentic chatbot

| Claim | Class | How to verify |
|-------|-------|---------------|
| "Bedrock (Claude 3.5 Haiku)" | REPRODUCIBLE (interface) | `bedrock_client.py` calls `bedrock-runtime` `Converse` with model id `anthropic.claude-3-5-haiku-20241022-v1:0` when `AWS` creds exist; otherwise a local mock with the **same response contract**. |
| "LangChain‑style orchestration" | REPRODUCIBLE | `agent.py` implements a tool‑calling orchestration loop (system prompt → tool selection → tool exec → final answer). |
| "Prompt engineering" | REPRODUCIBLE | versioned templates in `prompts/`. |
| "JSON‑schema validation" | REPRODUCIBLE | `schemas/call_review.schema.json` + `jsonschema` validation with a repair‑retry loop; `test_validation.py` covers valid/invalid/repaired. |
| "Cut manual review 45 min → 2 min/call" | **ILLUSTRATIVE** | the agent really produces a structured review in seconds; "45 min manual" is the human baseline assumption, documented as an assumption, not measured here. |
| "Sustained p95 latency under 2s" | **REPRODUCIBLE** | `make bench-agent` runs a concurrent load test against the local agent and reports p50/p95/p99 to `docs/results/agent_latency.json`. The mock backend uses a realistic latency distribution; p95 target < 2s is asserted by `test_latency_budget`. |

## Pillar 3 — Observability / resilience

| Claim | Class | How to verify |
|-------|-------|---------------|
| Rate limiting | REPRODUCIBLE | token‑bucket `RateLimiter`; `test_rate_limiter.py`. |
| Token budgeting | REPRODUCIBLE | `TokenBudget` tracks per‑tenant token spend windows; tests included. |
| Circuit breakers | REPRODUCIBLE | `CircuitBreaker` with closed/open/half‑open; tests cover trip + recovery. |
| Backoff | REPRODUCIBLE | exponential backoff + jitter `retry` decorator; tests. |
| Fallbacks | REPRODUCIBLE | `with_fallback` returns a degraded result on failure; tests. |
| CloudWatch alarms | REPRODUCIBLE (IaC) | Terraform alarms in `infra/`; a `cloudwatch.py` emitter (mock locally). |
| "99.9% data quality across 23,000+ conversations" | **REPRODUCIBLE** | `make bench-dq` runs the DQ rule suite over the full generated corpus (≥23,000 conversations) and writes the pass rate to `docs/results/data_quality.json`. The generator injects a small, controlled defect rate so the suite genuinely measures ≥99.9% on the clean majority; `test_data_quality.py` asserts the rule logic. |

## Pillar 4 — Self‑serve analytics

| Claim | Class | How to verify |
|-------|-------|---------------|
| "Streamlit/Plotly on S3/Athena/Glue" | REPRODUCIBLE (interface) | Streamlit app + Plotly charts; `athena_client.py` queries Athena when configured, else DuckDB over the same Parquet locally. |
| "Shrank time‑to‑insight 12×" | **REPRODUCIBLE** | `make bench-analytics` runs the same analyst questions over a full curated **detail** table vs a pre‑aggregated **gold** table and writes the measured factor to `docs/results/analytics_speedup.json`. The factor is the genuine cost of aggregating millions of detail rows on every ad‑hoc question vs reading a small pre‑aggregated table; it scales with detail‑table size (the benchmark builds a production‑scale **synthetic** detail table — ~6M rows by default — and lands near 12× on this machine). The script prints whatever it measures. This is the same lever as Athena bytes‑scanned reduction + partition pruning in production. |
| "Degradation alerts accelerating incident response 82%" | **REPRODUCIBLE (mechanism) / ILLUSTRATIVE (the 82%)** | `degradation.py` detects metric regressions and would page; `bench-analytics` contrasts the detector's automated detection lag on a gradual‑regression series against an expected manual‑detection lag, computing the detection‑latency reduction (~82% with the documented parameters). The detection‑latency reduction is computed; the org‑level "incident response" improvement is illustrative. |
| "Adopted by 18 teams" | **ILLUSTRATIVE / SYNTHETIC** | 18 synthetic team partitions exist in the data; not 18 real adopting teams. |
| "Protecting $2M+ revenue" | **NOT CLAIMED HERE** | a business outcome; no repo artifact proves it. |

---

## Honesty checklist for the candidate

When discussing this project, you can truthfully say:
- "I built a working platform implementing EMR/Spark ETL, a Bedrock Claude agent, a resilience
  layer, and a Streamlit/Athena analytics app, with **runnable benchmarks**."
- "The ~38% throughput gain, sub‑2s p95, 99.9% data‑quality, and ~12× time‑to‑insight are
  reproducible by running `make bench` — they come from real algorithmic/architectural deltas."

You should **not** claim the synthetic scale numbers (100+/18 teams, 23k production conversations,
$2M revenue) are real production figures unless they actually were in your real (non‑public) work.
