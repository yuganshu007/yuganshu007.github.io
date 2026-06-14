"""CloudWatch metric emitter with a local mock.

When AWS creds + CLOUDWATCH_BACKEND=cloudwatch are present, metrics go to CloudWatch via boto3.
Otherwise they are logged as structured events (and buffered in-memory for tests/inspection).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from platform_common.config import settings
from platform_common.logging import get_logger

log = get_logger("cloudwatch")


@dataclass
class CloudWatchEmitter:
    namespace: str = "TranscriptIntelligence"
    backend: str = field(default_factory=lambda: os.getenv("CLOUDWATCH_BACKEND", "mock"))
    _buffer: list[dict] = field(default_factory=list)
    _client: object | None = None

    def __post_init__(self):
        if self.backend == "cloudwatch":
            import boto3

            self._client = boto3.client("cloudwatch", region_name=settings.aws_region)

    def put_metric(self, name: str, value: float, unit: str = "Count", **dims) -> None:
        if self.backend == "cloudwatch":
            self._client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[
                    {
                        "MetricName": name,
                        "Value": value,
                        "Unit": unit,
                        "Dimensions": [{"Name": k, "Value": str(v)} for k, v in dims.items()],
                    }
                ],
            )
        else:
            self._buffer.append({"name": name, "value": value, "unit": unit, "dims": dims})
            log.info("metric", namespace=self.namespace, name=name, value=value, unit=unit, **dims)

    @property
    def buffered(self) -> list[dict]:
        return list(self._buffer)
