"""Render a textual health snapshot, mirroring the Grafana dashboard."""

from __future__ import annotations

import json
import sys

from rynova_platform.observability import ServiceHealth, build_health_report


def main() -> int:
    api = ServiceHealth(
        name="api",
        status="ok",
        latency_ms_p95=82.4,
        error_rate=0.002,
        backlog=0,
        details={"users": 2500, "routes": 5},
    )
    streaming = ServiceHealth(
        name="streaming",
        status="ok",
        latency_ms_p95=140.0,
        error_rate=0.001,
        backlog=12,
        details={"topics": ["mce", "mae"], "groups": ["rynova-cdc"]},
    )
    etl = ServiceHealth(
        name="etl",
        status="ok",
        latency_ms_p95=920.0,
        error_rate=0.004,
        backlog=0,
        details={"pipelines": 14},
    )
    sql = ServiceHealth(
        name="sql",
        status="ok",
        latency_ms_p95=18.0,
        error_rate=0.0,
        backlog=0,
        details={"engines": ["sqlite", "mysql"]},
    )
    report = build_health_report(api=api, streaming=streaming, etl=etl, sql=sql)
    print(json.dumps(report, indent=2))
    return 0 if report["overall"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
