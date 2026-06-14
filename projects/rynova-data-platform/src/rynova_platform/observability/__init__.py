"""Production dashboard + health monitoring (Bullet 3).

Exposes a :class:`MetricsRegistry` (Prometheus-backed) and a
:func:`build_health_report` helper used by the dashboard JSON in
``rynova/dashboards/grafana_health.json``.
"""

from rynova_platform.observability.metrics import (
    MetricsRegistry,
    ServiceHealth,
    build_health_report,
)

__all__ = ["MetricsRegistry", "ServiceHealth", "build_health_report"]
