"""Bullet 4 benchmark — SQL query plans cut latency by ≥25%.

Builds a ~50k row events table, then runs three workloads back-to-back:

1. **Indexing** — same hot query with and without a composite index.
2. **Partitioning** — same date-range read with and without
   :class:`DateShardedTable` pruning.
3. **Pagination** — keyset vs ``LIMIT/OFFSET`` at deep offsets.

For each workload the optimized path must beat the baseline by ≥25%.
The script also checks ``deliverables/deliveries.csv`` to assert that
100% of the recorded deliveries shipped on time.
"""

from __future__ import annotations

import csv
import random
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks._common import (  # noqa: E402
    assert_pass,
    banner,
    measure,
    pct_reduction,
    quick_mode,
)
from rynova_platform.sql import (  # noqa: E402
    DateShardedTable,
    PageRequest,
    ShardKey,
    keyset_paginate,
    offset_paginate,
)

ROWS = 5_000 if quick_mode() else 50_000
ITER = 60 if quick_mode() else 150
REQUIRED_REDUCTION_PCT = 25.0


def _seed(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE events (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL,
            amount REAL NOT NULL,
            ts INTEGER NOT NULL
        );
        """
    )
    rng = random.Random(1729)
    rows = [
        (
            i,
            rng.randint(1, 5_000),
            rng.choice(("click", "view", "purchase")),
            round(rng.uniform(1, 500), 2),
            rng.randint(0, 365),
        )
        for i in range(1, ROWS + 1)
    ]
    conn.executemany(
        "INSERT INTO events(id, user_id, kind, amount, ts) VALUES (?, ?, ?, ?, ?)",
        rows,
    )


def _seed_shards(conn: sqlite3.Connection) -> DateShardedTable:
    table = DateShardedTable(conn)
    today = date(2024, 6, 1)
    rng = random.Random(11)
    per_day = ROWS // 30
    for offset in range(30):
        day = today - timedelta(days=offset)
        shard = ShardKey(day=day)
        rows = [
            (
                offset * per_day + i + 1,
                rng.randint(1, 5_000),
                round(rng.uniform(1, 500), 2),
                rng.randint(0, 86_400),
            )
            for i in range(per_day)
        ]
        table.insert(shard, rows)
    return table


def _indexing_pass() -> float:
    baseline = sqlite3.connect(":memory:")
    _seed(baseline)
    rng = random.Random(7)

    def baseline_query() -> None:
        uid = rng.randint(1, 5_000)
        baseline.execute(
            "SELECT id, amount FROM events WHERE user_id = ? ORDER BY ts DESC LIMIT 20",
            (uid,),
        ).fetchall()

    baseline_summary = measure(baseline_query, iterations=ITER)
    baseline.close()

    optimized = sqlite3.connect(":memory:")
    _seed(optimized)
    optimized.execute("CREATE INDEX idx_events_user_ts ON events(user_id, ts)")
    optimized.execute("ANALYZE")

    rng2 = random.Random(7)

    def optimized_query() -> None:
        uid = rng2.randint(1, 5_000)
        optimized.execute(
            "SELECT id, amount FROM events WHERE user_id = ? ORDER BY ts DESC LIMIT 20",
            (uid,),
        ).fetchall()

    optimized_summary = measure(optimized_query, iterations=ITER)
    optimized.close()

    reduction = pct_reduction(baseline_summary.p50_ms, optimized_summary.p50_ms)
    print(f"  indexing      baseline={baseline_summary.p50_ms:.3f}ms "
          f"optimized={optimized_summary.p50_ms:.3f}ms reduction={reduction:.1f}%")
    return reduction


def _partition_pass() -> float:
    optimized_conn = sqlite3.connect(":memory:")
    optimized_table = _seed_shards(optimized_conn)
    start = date(2024, 5, 28)
    end = date(2024, 6, 1)

    def optimized_read() -> None:
        optimized_table.read_range(start, end, user_id=42)

    optimized_summary = measure(optimized_read, iterations=ITER)

    baseline_conn = sqlite3.connect(":memory:")
    baseline_table = _seed_shards(baseline_conn)

    def baseline_read() -> None:
        baseline_table.full_scan(user_id=42)

    baseline_summary = measure(baseline_read, iterations=ITER)

    reduction = pct_reduction(baseline_summary.p50_ms, optimized_summary.p50_ms)
    print(f"  partitioning  baseline={baseline_summary.p50_ms:.3f}ms "
          f"optimized={optimized_summary.p50_ms:.3f}ms reduction={reduction:.1f}%")
    optimized_conn.close()
    baseline_conn.close()
    return reduction


def _pagination_pass() -> float:
    conn = sqlite3.connect(":memory:")
    _seed(conn)

    deep_offset = ROWS - 100

    def offset_call() -> None:
        offset_paginate(conn, "events", PageRequest(limit=50, offset=deep_offset))

    def keyset_call() -> None:
        keyset_paginate(conn, "events", PageRequest(limit=50, after_id=deep_offset))

    baseline_summary = measure(offset_call, iterations=ITER)
    optimized_summary = measure(keyset_call, iterations=ITER)

    reduction = pct_reduction(baseline_summary.p50_ms, optimized_summary.p50_ms)
    print(f"  pagination    baseline={baseline_summary.p50_ms:.3f}ms "
          f"optimized={optimized_summary.p50_ms:.3f}ms reduction={reduction:.1f}%")
    conn.close()
    return reduction


def _on_time_rate() -> float:
    path = ROOT / "deliverables" / "deliveries.csv"
    with path.open() as fp:
        reader = csv.DictReader(fp)
        rows = list(reader)
    on_time = sum(1 for r in rows if r["on_time"].lower() == "true")
    return on_time / len(rows) * 100.0


def main() -> int:
    banner("Bullet 4 — SQL plans: ≥25% latency cut + 100% on-time")

    print("Per-workload latency reductions:")
    reductions = {
        "indexing": _indexing_pass(),
        "partitioning": _partition_pass(),
        "pagination": _pagination_pass(),
    }

    failures = 0
    for label, r in reductions.items():
        failures += assert_pass(
            r >= REQUIRED_REDUCTION_PCT,
            f"{label}: {r:.1f}% reduction (target ≥ {REQUIRED_REDUCTION_PCT}%)",
        )

    on_time = _on_time_rate()
    print(f"On-time delivery rate: {on_time:.1f}%")
    failures += assert_pass(
        on_time == 100.0,
        f"100% on-time deliveries (observed {on_time:.1f}%)",
    )
    return failures


if __name__ == "__main__":
    sys.exit(main())
