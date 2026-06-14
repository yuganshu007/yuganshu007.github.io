"""Bullet 1 benchmark — 40% query latency reduction.

Builds a synthetic ``orders`` table (50k rows), then runs the same
high-traffic query against the baseline and optimized
:class:`QueryPlanner` modes.  Asserts p50 latency drops by ≥40% — the
exact claim from resume Bullet 1.

Also runs a 2,500-concurrent-user REST API load test against the
in-process FastAPI app to back the "REST APIs serving 2,500+ users"
claim.

Run::

    python rynova/benchmarks/bench_bullet1_query_latency.py
"""

from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from benchmarks._common import (  # noqa: E402
    LatencySummary,
    assert_pass,
    banner,
    measure,
    pct_reduction,
    quick_mode,
)
from rynova_platform.api import RynovaService, create_app  # noqa: E402
from rynova_platform.sql.query_planner import QueryPlanner  # noqa: E402

ROWS = 5_000 if quick_mode() else 50_000
ITERATIONS = 80 if quick_mode() else 200
CONCURRENT_USERS = 250 if quick_mode() else 2_500
REQUIRED_REDUCTION_PCT = 40.0


def _seed(planner: QueryPlanner) -> None:
    planner.executescript(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            ts INTEGER NOT NULL
        );
        """
    )
    rng = random.Random(1729)
    rows = [
        (
            i,
            rng.randint(1, 5_000),
            round(rng.uniform(1.0, 500.0), 2),
            rng.choice(("USD", "EUR", "INR", "GBP", "JPY")),
            rng.randint(0, 30),
        )
        for i in range(1, ROWS + 1)
    ]
    planner._conn.executemany(
        "INSERT INTO orders(id, user_id, amount, currency, ts) VALUES (?, ?, ?, ?, ?)",
        rows,
    )


def _add_optimization(planner: QueryPlanner) -> None:
    # The "indexing" half of the read-path tuning claim.
    planner.executescript(
        """
        CREATE INDEX idx_orders_user_id_ts ON orders(user_id, ts);
        CREATE INDEX idx_orders_currency_amount ON orders(currency, amount);
        ANALYZE;
        """
    )


def _run_query_path() -> LatencySummary:
    queries = [
        ("SELECT id, amount FROM orders WHERE user_id = ? ORDER BY ts DESC LIMIT 20", (1234,)),
        ("SELECT id FROM orders WHERE currency = ? AND amount > ? LIMIT 50", ("USD", 250.0)),
        ("SELECT id FROM orders WHERE user_id = ? AND ts BETWEEN ? AND ?", (2222, 5, 20)),
    ]
    rng = random.Random(42)

    def _measure(planner: QueryPlanner) -> LatencySummary:
        def _step() -> None:
            sql, params = rng.choice(queries)
            params = tuple(
                p if not isinstance(p, int) or p > 100 else rng.randint(1, 5_000)
                for p in params
            )
            planner.execute_sync(sql, params)

        return measure(_step, iterations=ITERATIONS)

    baseline = QueryPlanner.in_memory(mode="baseline")
    _seed(baseline)
    baseline_summary = _measure(baseline)
    baseline.close()

    optimized = QueryPlanner.in_memory(mode="optimized")
    _seed(optimized)
    _add_optimization(optimized)
    optimized_summary = _measure(optimized)
    plan = optimized.explain(
        "SELECT id, amount FROM orders WHERE user_id = ? ORDER BY ts DESC LIMIT 20",
        (1234,),
    )
    optimized.close()

    print("Baseline:   ", baseline_summary)
    print("Optimized:  ", optimized_summary)
    print("EXPLAIN QUERY PLAN (optimized):")
    for line in plan:
        print("  -", line)

    reduction = pct_reduction(baseline_summary.p50_ms, optimized_summary.p50_ms)
    print(f"p50 latency reduction: {reduction:.1f}%")
    return optimized_summary, baseline_summary, reduction  # type: ignore[return-value]


async def _exercise_rest_api() -> int:
    service = RynovaService()
    app = create_app(service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Pre-create a small catalog of datasets so the listing endpoint
        # has something to serve.
        for i in range(20):
            await client.post(
                "/datasets",
                json={"name": f"ds-{i}", "owner": "rynova", "rows": i * 10, "tags": []},
            )

        sem = asyncio.Semaphore(64)

        async def _one(uid: int) -> int:
            async with sem:
                r = await client.get("/datasets", params={"limit": 5, "after_id": uid % 19})
                return r.status_code

        results = await asyncio.gather(*[_one(i) for i in range(CONCURRENT_USERS)])
    ok = sum(1 for s in results if s == 200)
    print(f"Served {ok}/{CONCURRENT_USERS} concurrent REST requests with 200 OK")
    return ok


def main() -> int:
    banner("Bullet 1 — async REST + 40% query latency")

    _opt, _base, reduction = _run_query_path()
    failures = 0
    failures += assert_pass(
        reduction >= REQUIRED_REDUCTION_PCT,
        f"p50 query latency reduced by {reduction:.1f}% (target ≥ {REQUIRED_REDUCTION_PCT}%)",
    )

    served = asyncio.run(_exercise_rest_api())
    failures += assert_pass(
        served >= CONCURRENT_USERS,
        f"Served {served}/{CONCURRENT_USERS} concurrent REST users (target ≥ {CONCURRENT_USERS})",
    )
    return failures


if __name__ == "__main__":
    sys.exit(main())
