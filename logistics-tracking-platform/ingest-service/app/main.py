"""Logistics ingest microservice (Python / FastAPI).

Responsibilities
----------------
* REST API for creating shipments, ingesting tracking events and reading status.
* Async request handlers. In ``optimized`` mode the hot POST path only validates
  and publishes to the Redis Streams message queue, handing the heavy work to the
  Java background-worker pool. In ``baseline`` mode the same handler does the
  downstream call + DB write inline (the "before" architecture).
* Read path backed by SQLite with an in-memory LRU+TTL cache.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Literal

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .cache import LruTtlCache
from . import db
from .config import Settings

SETTINGS = Settings.load()

EVENT_TYPES = ("PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION")

_thread_local = threading.local()


def _conn() -> "db.sqlite3.Connection":
    conn = getattr(_thread_local, "conn", None)
    if conn is None:
        conn = db.connect(SETTINGS.db_path)
        _thread_local.conn = conn
    return conn


class ShipmentIn(BaseModel):
    origin: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=120)
    carrier: str = Field(min_length=1, max_length=80)


class EventIn(BaseModel):
    # Pydantic enforces the validation rules referenced in the resume bullet.
    event_type: Literal["PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION"]
    location: str = Field(min_length=1, max_length=160)
    note: str | None = Field(default=None, max_length=500)


class Metrics:
    def __init__(self) -> None:
        self.events_accepted = 0
        self.events_enqueued = 0
        self.events_processed_inline = 0
        self.inline_failures = 0
        self.lock = threading.Lock()

    def snapshot(self) -> dict[str, int]:
        with self.lock:
            return {
                "events_accepted": self.events_accepted,
                "events_enqueued": self.events_enqueued,
                "events_processed_inline": self.events_processed_inline,
                "inline_failures": self.inline_failures,
            }


metrics = Metrics()
cache = LruTtlCache(SETTINGS.cache_capacity, SETTINGS.cache_ttl_ms)
_redis: aioredis.Redis | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis
    os.makedirs(os.path.dirname(SETTINGS.db_path), exist_ok=True)
    db.init_db(SETTINGS.db_path, with_indexes=True)
    if SETTINGS.is_optimized:
        _redis = aioredis.from_url(SETTINGS.redis_url, decode_responses=True)
        await _redis.ping()
    yield
    if _redis is not None:
        await _redis.aclose()


app = FastAPI(title="Logistics Ingest Service", version="1.0.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "mode": SETTINGS.mode}


@app.get("/metrics")
async def get_metrics() -> dict[str, object]:
    stream_len = 0
    backlog = 0  # entries not yet delivered + delivered-but-unacked (pending)
    if SETTINGS.is_optimized and _redis is not None:
        try:
            stream_len = await _redis.xlen(SETTINGS.stream_key)
            groups = await _redis.xinfo_groups(SETTINGS.stream_key)
            for g in groups:
                if g.get("name") == SETTINGS.group:
                    backlog = int(g.get("lag") or 0) + int(g.get("pending") or 0)
                    break
        except Exception:  # pragma: no cover - stream/group may not exist yet
            backlog = 0
    return {
        "mode": SETTINGS.mode,
        "ingest": metrics.snapshot(),
        "cache": cache.stats(),
        "stream_len": stream_len,
        "queue_backlog": backlog,
    }


@app.post("/shipments", status_code=201)
async def create_shipment(body: ShipmentIn) -> dict[str, str]:
    shipment_id = uuid.uuid4().hex

    def _write() -> None:
        _conn().execute("BEGIN")
        db.insert_shipment(_conn(), shipment_id, body.origin, body.destination, body.carrier)
        _conn().execute("COMMIT")

    await asyncio.to_thread(_write)
    cache.invalidate(shipment_id)
    return {"shipment_id": shipment_id, "status": "CREATED"}


async def _process_inline(event: dict) -> JSONResponse:
    """Baseline architecture: do the downstream call + persist in the request path."""
    # Simulated downstream logistics/geocoding call.
    await asyncio.sleep(SETTINGS.downstream_ms / 1000.0)
    if random.random() < SETTINGS.transient_fail_rate:
        # No retry in the baseline design -> the event is dropped -> SLA breach.
        with metrics.lock:
            metrics.inline_failures += 1
        raise HTTPException(status_code=503, detail="downstream unavailable")

    def _write() -> None:
        c = _conn()
        c.execute("BEGIN")
        db.persist_event(c, event, processed_at_ms=db.now_ms(), attempts=1, outcome="OK")
        c.execute("COMMIT")

    await asyncio.to_thread(_write)
    cache.invalidate(event["shipment_id"])
    with metrics.lock:
        metrics.events_processed_inline += 1
    return JSONResponse(status_code=201, content={"event_id": event["event_id"], "status": "PROCESSED"})


async def _enqueue(event: dict) -> JSONResponse:
    """Optimized architecture: validate + publish, let the worker pool do the work."""
    assert _redis is not None
    await _redis.xadd(SETTINGS.stream_key, {"data": json.dumps(event)})
    with metrics.lock:
        metrics.events_enqueued += 1
    return JSONResponse(status_code=202, content={"event_id": event["event_id"], "status": "QUEUED"})


@app.post("/shipments/{shipment_id}/events")
async def ingest_event(shipment_id: str, body: EventIn) -> JSONResponse:
    event = {
        "event_id": uuid.uuid4().hex,
        "shipment_id": shipment_id,
        "event_type": body.event_type,
        "location": body.location,
        "note": body.note,
        "ingested_at_ms": db.now_ms(),
    }
    with metrics.lock:
        metrics.events_accepted += 1
    if SETTINGS.is_optimized:
        return await _enqueue(event)
    return await _process_inline(event)


@app.get("/shipments/{shipment_id}")
async def get_shipment(shipment_id: str) -> dict:
    if SETTINGS.cache_enabled:
        cached = cache.get(shipment_id)
        if cached is not None:
            return {"cached": True, **cached}

    def _read() -> dict | None:
        return db.read_shipment(_conn(), shipment_id)

    result = await asyncio.to_thread(_read)
    if result is None:
        raise HTTPException(status_code=404, detail="shipment not found")
    if SETTINGS.cache_enabled:
        cache.put(shipment_id, result)
    return {"cached": False, **result}


@app.post("/admin/reset")
async def admin_reset() -> dict[str, str]:
    """Benchmark helper: truncate tables, clear the cache and drain the stream."""
    def _truncate() -> None:
        c = _conn()
        c.execute("BEGIN")
        c.execute("DELETE FROM tracking_events")
        c.execute("DELETE FROM shipments")
        c.execute("COMMIT")

    await asyncio.to_thread(_truncate)
    cache._store.clear()  # noqa: SLF001 - intentional full clear for benchmarks
    cache.hits = 0
    cache.misses = 0
    with metrics.lock:
        metrics.events_accepted = 0
        metrics.events_enqueued = 0
        metrics.events_processed_inline = 0
        metrics.inline_failures = 0
    if SETTINGS.is_optimized and _redis is not None:
        await _redis.delete(SETTINGS.stream_key)
        await _redis.delete(SETTINGS.dlq_key)
    return {"status": "reset"}
