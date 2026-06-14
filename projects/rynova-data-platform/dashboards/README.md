# Production Dashboards

These dashboard definitions back the "monitored distributed service
health using production dashboards" claim in resume Bullet 3.

* `grafana_health.json` — Grafana dashboard with six panels (API p95
  latency, request rate by status, Kafka consumer lag, idempotent sink
  dedupes, ETL outcomes, event-bus throughput).
* The PromQL queries in the panel JSON resolve against the metric
  names emitted by `rynova_platform.observability.MetricsRegistry`.

To preview the dashboard locally without a Grafana install, run:

```bash
python rynova/scripts/health_report.py
```

The script renders a text health snapshot built from the same metrics
the dashboard reads.
