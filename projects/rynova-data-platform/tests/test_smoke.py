"""Smoke tests that walk each top-level package import."""

from __future__ import annotations


def test_package_version() -> None:
    import rynova_platform

    assert rynova_platform.__version__


def test_imports_api() -> None:
    from rynova_platform.api import RynovaService, create_app  # noqa: F401


def test_imports_etl() -> None:
    from rynova_platform.etl import Field, Pipeline, Schema, Stage  # noqa: F401


def test_imports_streaming() -> None:
    from rynova_platform.streaming import (  # noqa: F401
        DQRegistry,
        IdempotentSink,
        InMemoryKafka,
        KafkaConsumer,
        KafkaProducer,
    )


def test_imports_sql() -> None:
    from rynova_platform.sql import (  # noqa: F401
        DateShardedTable,
        Page,
        PageRequest,
        QueryPlanner,
        ShardKey,
        keyset_paginate,
        offset_paginate,
    )


def test_imports_validation() -> None:
    from rynova_platform.validation import (  # noqa: F401
        DataQualityCheck,
        ValidationError,
        in_set,
        not_null,
        range_check,
        regex_match,
        unique,
        validate_batch,
    )


def test_imports_observability() -> None:
    from rynova_platform.observability import (  # noqa: F401
        MetricsRegistry,
        ServiceHealth,
        build_health_report,
    )
