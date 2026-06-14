# Pillar 4 — Self-serve analytics (Streamlit/Plotly on S3/Athena/Glue)

Business users explore advertiser-transcript metrics through a Streamlit/Plotly app backed by a
pre-aggregated **gold** table. Locally it runs on DuckDB over the same Parquet; in production the
identical SQL runs on **Athena over the Glue catalog**.

## Map to the resume bullet

| Claim | Implementation |
|-------|----------------|
| Streamlit/Plotly on S3/Athena/Glue | `app/Home.py` + `app/query_engine.py` (Athena/DuckDB backends), Glue/Athena Terraform in `infra/`. |
| Shrank time-to-insight 12× | `benchmarks/run_benchmark.py` measures full curated-detail scan vs the pre-aggregated gold table → `docs/results/analytics_speedup.json`. |
| Degradation alerts accelerating incident response | `app/degradation.py` + `app/pages/1_Degradation_Alerts.py`; the benchmark also reports detection-latency reduction. |
| Adopted by 18 teams | 18 synthetic team partitions (illustrative; see `docs/METRICS.md`). |
| Protecting $2M+ revenue | **not claimed by any repo artifact** (see `docs/METRICS.md`). |

## Run

```bash
make dashboard          # http://localhost:8501
python -m services.analytics_dashboard.benchmarks.run_benchmark --data data --rows 6000000
```

The 12× factor is the **measured** cost of aggregating millions of detail rows on every ad-hoc
question vs reading a small pre-aggregated gold table. The benchmark prints whatever it measures
(no hard-coded constant); on this dev machine ~6M detail rows lands near 12×, and it scales with
table size — the same lever as Athena bytes-scanned reduction + partition pruning in production.
