"""SQLite access layer.

The schema is intentionally created with explicit secondary indexes so the read
path (GET /shipments/{id}) can do index seeks instead of full table scans. The
``benchmark/read_latency.py`` script measures the with/without-index delta in
isolation; here we always run the indexed (production) schema.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (
    id            TEXT PRIMARY KEY,
    origin        TEXT NOT NULL,
    destination   TEXT NOT NULL,
    carrier       TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'CREATED',
    created_at_ms INTEGER NOT NULL,
    updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tracking_events (
    event_id        TEXT PRIMARY KEY,
    shipment_id     TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    location        TEXT NOT NULL,
    note            TEXT,
    ingested_at_ms  INTEGER NOT NULL,
    processed_at_ms INTEGER,
    attempts        INTEGER NOT NULL DEFAULT 0,
    outcome         TEXT NOT NULL DEFAULT 'PENDING'
);
"""

# Secondary indexes are the "schema indexing" referenced on the resume. The hot
# read query filters tracking_events by shipment_id and orders by ingest time.
INDEXES = """
CREATE INDEX IF NOT EXISTS idx_events_shipment
    ON tracking_events (shipment_id, ingested_at_ms DESC);
CREATE INDEX IF NOT EXISTS idx_events_outcome
    ON tracking_events (outcome);
CREATE INDEX IF NOT EXISTS idx_shipments_status
    ON shipments (status);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    # WAL lets the Python reader and the Java writer hit the same file concurrently.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def init_db(db_path: str, with_indexes: bool = True) -> None:
    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        if with_indexes:
            conn.executescript(INDEXES)
    finally:
        conn.close()


def now_ms() -> int:
    return int(time.time() * 1000)


def insert_shipment(conn: sqlite3.Connection, shipment_id: str, origin: str,
                    destination: str, carrier: str) -> None:
    ts = now_ms()
    conn.execute(
        "INSERT INTO shipments (id, origin, destination, carrier, status, "
        "created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, 'CREATED', ?, ?)",
        (shipment_id, origin, destination, carrier, ts, ts),
    )


def persist_event(conn: sqlite3.Connection, event: dict[str, Any], *,
                  processed_at_ms: int, attempts: int, outcome: str) -> None:
    """Upsert a tracking event and roll the parent shipment's status forward."""
    conn.execute(
        "INSERT INTO tracking_events (event_id, shipment_id, event_type, location, "
        "note, ingested_at_ms, processed_at_ms, attempts, outcome) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(event_id) DO UPDATE SET processed_at_ms=excluded.processed_at_ms, "
        "attempts=excluded.attempts, outcome=excluded.outcome",
        (
            event["event_id"], event["shipment_id"], event["event_type"],
            event["location"], event.get("note"), int(event["ingested_at_ms"]),
            processed_at_ms, attempts, outcome,
        ),
    )
    # Advance status monotonically by event ingest time so the latest event wins
    # regardless of the (parallel) processing order.
    ingested = int(event["ingested_at_ms"])
    conn.execute(
        "UPDATE shipments SET status=?, updated_at_ms=? WHERE id=? AND ? >= updated_at_ms",
        (event["event_type"], ingested, event["shipment_id"], ingested),
    )


def read_shipment(conn: sqlite3.Connection, shipment_id: str,
                  event_limit: int = 20) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT id, origin, destination, carrier, status, created_at_ms, updated_at_ms "
        "FROM shipments WHERE id = ?",
        (shipment_id,),
    ).fetchone()
    if row is None:
        return None
    events: Iterable[sqlite3.Row] = conn.execute(
        "SELECT event_id, event_type, location, note, ingested_at_ms, processed_at_ms, "
        "outcome FROM tracking_events WHERE shipment_id = ? "
        "ORDER BY ingested_at_ms DESC LIMIT ?",
        (shipment_id, event_limit),
    ).fetchall()
    return {
        "shipment": dict(row),
        "events": [dict(e) for e in events],
    }
