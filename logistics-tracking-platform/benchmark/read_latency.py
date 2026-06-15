#!/usr/bin/env python3
"""Metric 3 - SQLite read latency: schema indexing + local cache.

Builds a realistic tracking dataset and measures GET-by-shipment read latency in
three configurations:

  1. baseline   : no secondary index, no cache  (full table scan every read)
  2. indexed    : secondary index, no cache       (index seek)
  3. optimized  : secondary index + LRU cache     (index seek + memory hits)

It prints the measured latencies and the percentage reduction from baseline,
which is the "cut read latency 40%" claim. Pure-SQLite, no services required.
"""
from __future__ import annotations

import argparse
import os
import random
import sqlite3
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingest-service"))
from app.cache import LruTtlCache  # noqa: E402

EVENT_TYPES = ("PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION")
CITIES = ("NYC", "Newark", "Boston", "Chicago", "Dallas", "Denver", "Seattle", "Atlanta")


def build_dataset(conn: sqlite3.Connection, shipments: int, events_per: int) -> list[str]:
    conn.executescript(
        """
        CREATE TABLE shipments (id TEXT PRIMARY KEY, origin TEXT, destination TEXT,
            carrier TEXT, status TEXT, created_at_ms INTEGER, updated_at_ms INTEGER);
        CREATE TABLE tracking_events (event_id TEXT PRIMARY KEY, shipment_id TEXT,
            event_type TEXT, location TEXT, note TEXT, ingested_at_ms INTEGER,
            processed_at_ms INTEGER, attempts INTEGER, outcome TEXT);
        """
    )
    ids: list[str] = []
    now = int(time.time() * 1000)
    conn.execute("BEGIN")
    for s in range(shipments):
        sid = f"ship-{s:07d}"
        ids.append(sid)
        conn.execute(
            "INSERT INTO shipments VALUES (?,?,?,?,?,?,?)",
            (sid, random.choice(CITIES), random.choice(CITIES), "ACME", "IN_TRANSIT", now, now),
        )
    eid = 0
    for s in range(shipments):
        sid = f"ship-{s:07d}"
        for _ in range(events_per):
            conn.execute(
                "INSERT INTO tracking_events VALUES (?,?,?,?,?,?,?,?,?)",
                (f"evt-{eid:09d}", sid, random.choice(EVENT_TYPES), random.choice(CITIES),
                 None, now, now, 1, "OK"),
            )
            eid += 1
    conn.execute("COMMIT")
    return ids


def read_once(conn: sqlite3.Connection, sid: str) -> int:
    conn.execute("SELECT id, status FROM shipments WHERE id = ?", (sid,)).fetchone()
    rows = conn.execute(
        "SELECT event_id, event_type, location, ingested_at_ms FROM tracking_events "
        "WHERE shipment_id = ? ORDER BY ingested_at_ms DESC LIMIT 20",
        (sid,),
    ).fetchall()
    return len(rows)


def time_reads(conn: sqlite3.Connection, ids: list[str], iterations: int,
               cache: LruTtlCache | None) -> list[float]:
    latencies: list[float] = []
    rnd = random.Random(1234)
    # Zipf-ish access: a hot subset of shipments is read most often, which is
    # what makes the cache realistic.
    hot = ids[: max(1, len(ids) // 20)]
    for _ in range(iterations):
        sid = rnd.choice(hot) if rnd.random() < 0.8 else rnd.choice(ids)
        t0 = time.perf_counter()
        if cache is not None:
            cached = cache.get(sid)
            if cached is None:
                cached = read_once(conn, sid)
                cache.put(sid, cached)
        else:
            read_once(conn, sid)
        latencies.append((time.perf_counter() - t0) * 1_000_000)  # microseconds
    return latencies


def summarize(name: str, lat: list[float]) -> dict:
    lat_sorted = sorted(lat)
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)]
    return {
        "config": name,
        "mean_us": round(statistics.mean(lat), 2),
        "median_us": round(statistics.median(lat), 2),
        "p95_us": round(p95, 2),
    }


def run(shipments: int, events_per: int, iterations: int, scan_iterations: int) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="readbench-")
    db_no_idx = os.path.join(tmpdir, "no_index.db")
    db_idx = os.path.join(tmpdir, "indexed.db")

    conn_no = sqlite3.connect(db_no_idx)
    ids = build_dataset(conn_no, shipments, events_per)

    conn_idx = sqlite3.connect(db_idx)
    build_dataset(conn_idx, shipments, events_per)
    conn_idx.execute(
        "CREATE INDEX idx_events_shipment ON tracking_events (shipment_id, ingested_at_ms DESC)"
    )
    conn_idx.execute("ANALYZE")

    # Warm the OS/page cache equally for both DBs.
    time_reads(conn_no, ids, 200, None)
    time_reads(conn_idx, ids, 200, None)

    # The un-indexed scan is intentionally O(events); use fewer iterations so the
    # benchmark stays quick while still measuring representative latency.
    baseline = summarize("baseline (no index, no cache)",
                         time_reads(conn_no, ids, scan_iterations, None))
    indexed = summarize("indexed (no cache)", time_reads(conn_idx, ids, iterations, None))
    cache = LruTtlCache(capacity=shipments, ttl_ms=60_000)
    optimized = summarize("optimized (index + cache)", time_reads(conn_idx, ids, iterations, cache))

    def reduction(before: float, after: float) -> float:
        return round((before - after) / before * 100, 1)

    report = {
        "dataset": {"shipments": shipments, "events_per_shipment": events_per,
                    "total_events": shipments * events_per, "iterations": iterations},
        "results": [baseline, indexed, optimized],
        "cache_stats": cache.stats(),
        "reductions_pct": {
            "indexing_only": reduction(baseline["mean_us"], indexed["mean_us"]),
            "index_plus_cache": reduction(baseline["mean_us"], optimized["mean_us"]),
        },
    }
    conn_no.close()
    conn_idx.close()
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shipments", type=int, default=8000)
    ap.add_argument("--events-per", type=int, default=10)
    ap.add_argument("--iterations", type=int, default=20000)
    ap.add_argument("--scan-iterations", type=int, default=3000)
    args = ap.parse_args()

    report = run(args.shipments, args.events_per, args.iterations, args.scan_iterations)

    print("\n=== Metric 3: SQLite read latency ===")
    print(f"dataset: {report['dataset']['shipments']} shipments, "
          f"{report['dataset']['total_events']} events")
    for r in report["results"]:
        print(f"  {r['config']:<32} mean={r['mean_us']:>9.2f} us  "
              f"median={r['median_us']:>9.2f} us  p95={r['p95_us']:>9.2f} us")
    print(f"cache hit ratio: {report['cache_stats']['hit_ratio_pct']}%")
    print(f"read-latency reduction (indexing only):     "
          f"{report['reductions_pct']['indexing_only']}%")
    print(f"read-latency reduction (index + cache):      "
          f"{report['reductions_pct']['index_plus_cache']}%")

    import json
    out = os.path.join(os.path.dirname(__file__), "..", "data", "metric3_read_latency.json")
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {os.path.relpath(out)}")


if __name__ == "__main__":
    main()
