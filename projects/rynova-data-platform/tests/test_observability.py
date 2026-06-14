"""Observability tests (Bullet 3 — production dashboards)."""

from __future__ import annotations

import json
from pathlib import Path

from rynova_platform.observability import (
    MetricsRegistry,
    ServiceHealth,
    build_health_report,
)


def test_metrics_registry_emits_counter() -> None:
    reg = MetricsRegistry()
    reg.api_requests.labels(route="/datasets", method="GET", status="200").inc()
    samples = list(reg.api_requests.collect())[0].samples
    total = next(s for s in samples if s.name.endswith("_total"))
    assert total.value == 1.0


def test_metrics_registry_histogram_observes() -> None:
    reg = MetricsRegistry()
    reg.api_latency.labels(route="/datasets").observe(0.01)
    reg.api_latency.labels(route="/datasets").observe(0.05)
    samples = list(reg.api_latency.collect())[0].samples
    count = next(s for s in samples if s.name.endswith("_count"))
    assert count.value == 2.0


def test_health_report_overall_ok() -> None:
    s = ServiceHealth(name="x", status="ok", latency_ms_p95=10, error_rate=0.001, backlog=0)
    report = build_health_report(api=s, streaming=s, etl=s, sql=s)
    assert report["overall"] == "ok"
    assert set(report["services"]) == {"api", "streaming", "etl", "sql"}


def test_health_report_degraded_on_status() -> None:
    ok = ServiceHealth(name="x", status="ok", latency_ms_p95=10, error_rate=0.0, backlog=0)
    bad = ServiceHealth(name="x", status="degraded", latency_ms_p95=10, error_rate=0.0, backlog=0)
    report = build_health_report(api=bad, streaming=ok, etl=ok, sql=ok)
    assert report["overall"] == "degraded"


def test_health_report_degraded_on_error_rate() -> None:
    ok = ServiceHealth(name="x", status="ok", latency_ms_p95=10, error_rate=0.0, backlog=0)
    bad = ServiceHealth(name="x", status="ok", latency_ms_p95=10, error_rate=0.05, backlog=0)
    report = build_health_report(api=ok, streaming=ok, etl=ok, sql=bad)
    assert report["overall"] == "degraded"


def test_grafana_dashboard_json_loads() -> None:
    path = Path(__file__).resolve().parent.parent / "dashboards" / "grafana_health.json"
    data = json.loads(path.read_text())
    assert data["uid"] == "rynova-prod-health"
    panel_titles = {p["title"] for p in data["panels"]}
    assert "API p95 latency (ms)" in panel_titles
    assert "Kafka consumer lag" in panel_titles
    assert "Idempotent sink dedupes" in panel_titles
