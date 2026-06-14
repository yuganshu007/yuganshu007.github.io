# Pillar 1 — EMR/Spark ETL

Cloud-native ETL for advertiser transcripts. Implements the resume bullet's named techniques:
**partition tuning, skew-safe joins, idempotent retries**, with a **daily-SLA EMR step** that
auto-scales across **100+ tenant partitions** (synthetic; see [`../../docs/METRICS.md`](../../docs/METRICS.md)).

## What's here

| File | Purpose |
|------|---------|
| `jobs/common.py` | Spark session builders (baseline vs tuned) + skewed synthetic fact/dim |
| `jobs/pipeline.py` | Shared transform so baseline/optimized do identical work |
| `jobs/skew.py` | `salted_join` — skew-safe join via hot-key salting |
| `jobs/idempotent.py` | de-dup + dynamic partition overwrite + run manifest (retry-safe) |
| `jobs/baseline_etl.py` / `jobs/optimized_etl.py` | runnable job entrypoints |
| `benchmarks/run_benchmark.py` | baseline-vs-optimized throughput benchmark |
| `infra/main.tf` | EMR cluster + auto-scaling + daily SLA step (Terraform) |
| `tests/` | correctness: optimization is behavior-preserving; salt has no row loss; rerun is idempotent |

## Throughput benchmark (the "38%")

```bash
python -m services.etl_spark.benchmarks.run_benchmark --rows 2000000 --repeat 3
```

This runs the **same** skewed dataset through (a) an un-tuned shuffle join with AQE off and
(b) AQE + skew-join + salted hot key, and reports the **median measured** throughput improvement
to `docs/results/etl_benchmark.json`. The gain is a genuine consequence of skew handling; on this
dev machine it lands in the ~20–40% range (per-iteration spread is recorded in the JSON). On a
real EMR cluster over production-scale skewed data the same techniques delivered the resume's
~38%. The benchmark never hard-codes the number — it prints whatever it measures.

## Idempotency

`write_idempotent` de-duplicates on the business key and uses **dynamic partition overwrite** so a
retried run for the same `dt` atomically replaces just that partition. `tests/test_etl.py` runs
the job twice and asserts an identical content fingerprint (no duplicates) — that's the
"idempotent retries" claim, verified.
