"""Prometheus-backed metrics + health snapshot.

The metric names mirror the Grafana panel queries in
``rynova/dashboards/grafana_health.json``; ``build_health_report`` is
the function the on-call dashboard renders each minute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram


@dataclass
class ServiceHealth:
    name: str
    status: str
    latency_ms_p95: float
    error_rate: float
    backlog: int
    details: dict[str, Any] = field(default_factory=dict)


class MetricsRegistry:
    """One Prometheus registry per service.

    Tests instantiate a fresh registry per case so collector state does
    not bleed between unit tests.
    """

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.api_requests = Counter(
            "rynova_api_requests_total",
            "REST API request counter",
            labelnames=("route", "method", "status"),
            registry=self.registry,
        )
        self.api_latency = Histogram(
            "rynova_api_latency_seconds",
            "REST API latency histogram",
            labelnames=("route",),
            registry=self.registry,
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
        )
        self.events_published = Counter(
            "rynova_events_published_total",
            "Async events published on the bus",
            labelnames=("topic",),
            registry=self.registry,
        )
        self.stream_lag = Gauge(
            "rynova_stream_lag_messages",
            "Kafka consumer lag in messages",
            labelnames=("topic", "group"),
            registry=self.registry,
        )
        self.sink_dedupes = Counter(
            "rynova_sink_dedupes_total",
            "Number of duplicate messages dropped by the idempotent sink",
            labelnames=("topic",),
            registry=self.registry,
        )
        self.pipeline_runs = Counter(
            "rynova_pipeline_runs_total",
            "ETL pipeline executions by outcome",
            labelnames=("pipeline", "result"),
            registry=self.registry,
        )


def build_health_report(
    *,
    api: ServiceHealth,
    streaming: ServiceHealth,
    etl: ServiceHealth,
    sql: ServiceHealth,
) -> dict[str, Any]:
    """Assemble the on-call dashboard report.

    The dashboard considers the platform "healthy" iff every service is
    ``ok`` and no error rate exceeds 1%.
    """

    services = {
        "api": api,
        "streaming": streaming,
        "etl": etl,
        "sql": sql,
    }
    overall = "ok"
    for s in services.values():
        if s.status != "ok" or s.error_rate > 0.01:
            overall = "degraded"
            break
    return {
        "overall": overall,
        "services": {
            k: {
                "status": v.status,
                "latency_ms_p95": v.latency_ms_p95,
                "error_rate": v.error_rate,
                "backlog": v.backlog,
                "details": v.details,
            }
            for k, v in services.items()
        },
    }
