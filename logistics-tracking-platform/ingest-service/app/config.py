"""Runtime configuration for the ingest service.

Everything is driven by environment variables so the benchmark harness can flip
the service between the "baseline" (un-tuned, synchronous) architecture and the
"optimized" (async + background-worker + tuned routing) architecture without
touching code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # "baseline" -> heavy work runs inline in the request handler, no queue, no retry.
    # "optimized" -> request handler validates + enqueues to the message queue and
    #                returns immediately; a pool of background workers does the work.
    mode: str

    # Message queue (Redis Streams) wiring.
    redis_url: str
    stream_key: str
    dlq_key: str
    group: str

    # Shared SQLite system-of-record / local cache.
    db_path: str

    # Simulated cost of the downstream logistics call (carrier API, geocoding, ...).
    downstream_ms: int

    # Probability that a downstream attempt fails transiently. Baseline has no retry
    # so these become SLA breaches; the optimized worker retries them.
    transient_fail_rate: float

    # An event is "on time" if it is durably persisted within this many ms of ingest.
    sla_ms: int

    # Read-path tuning (schema indexing is always on for the live DB; this only
    # toggles the in-memory cache in front of SQLite).
    cache_enabled: bool
    cache_capacity: int
    cache_ttl_ms: int

    @staticmethod
    def load() -> "Settings":
        here = os.path.dirname(os.path.abspath(__file__))
        default_db = os.path.normpath(os.path.join(here, "..", "..", "data", "logistics.db"))
        return Settings(
            mode=os.getenv("INGEST_MODE", "optimized").strip().lower(),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            stream_key=os.getenv("STREAM_KEY", "logistics.events"),
            dlq_key=os.getenv("DLQ_KEY", "logistics.events.dlq"),
            group=os.getenv("CONSUMER_GROUP", "tracking-workers"),
            db_path=os.getenv("DB_PATH", default_db),
            downstream_ms=int(os.getenv("DOWNSTREAM_MS", "22")),
            transient_fail_rate=float(os.getenv("TRANSIENT_FAIL_RATE", "0.0")),
            sla_ms=int(os.getenv("SLA_MS", "750")),
            cache_enabled=_as_bool(os.getenv("CACHE_ENABLED"), True),
            cache_capacity=int(os.getenv("CACHE_CAPACITY", "4096")),
            cache_ttl_ms=int(os.getenv("CACHE_TTL_MS", "2000")),
        )

    @property
    def is_optimized(self) -> bool:
        return self.mode == "optimized"
