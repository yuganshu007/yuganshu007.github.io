"""Bullet 2 benchmark — ≥30% reduction in pipeline failures.

The benchmark simulates a realistic ETL job: an extract stage that
occasionally raises a transient error, followed by a loader stage that
crashes if it sees a malformed row.  ``DIRTY_RATE`` controls how often
upstream sends bad rows; ``FLAKE_RATE`` controls how often the extract
stage hits a transient network blip.

Two configurations run back-to-back over the same RNG seed:

* ``without_sdk`` — no schema validation, no DQ checks, no retries.
  Bad rows leak to the loader (it crashes) and transient errors are
  fatal.
* ``with_sdk``    — the rynova validation SDK + structured retries.
  Bad rows are quarantined before they reach the loader and transient
  errors are retried.

The benchmark asserts the ``with_sdk`` failure rate is ≥30% lower.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks._common import (  # noqa: E402
    assert_pass,
    banner,
    pct_reduction,
    quick_mode,
)
from rynova_platform.etl import Pipeline, Stage  # noqa: E402
from rynova_platform.etl.schema import Field, Schema  # noqa: E402
from rynova_platform.validation import in_set, not_null, range_check  # noqa: E402

N_JOBS = 100 if quick_mode() else 300
ROWS_PER_JOB = 200 if quick_mode() else 500
DIRTY_RATE = 0.30
FLAKE_RATE = 0.15
REQUIRED_REDUCTION_PCT = 30.0

ORDERS_SCHEMA = Schema(
    name="orders",
    version=1,
    fields=(
        Field("id", int),
        Field("user_id", int),
        Field("amount", float),
        Field("currency", str),
    ),
)

ALLOWED_CURRENCIES = {"USD", "EUR", "INR", "GBP", "JPY"}


def _generate_job(rng: random.Random, dirty: bool) -> list[dict]:
    rows: list[dict] = []
    for i in range(ROWS_PER_JOB):
        row = {
            "id": i,
            "user_id": rng.randint(1, 1000),
            "amount": round(rng.uniform(0.5, 500.0), 2),
            "currency": rng.choice(list(ALLOWED_CURRENCIES)),
        }
        if dirty and rng.random() < 0.10:
            corruption = rng.random()
            if corruption < 0.34:
                row["user_id"] = None  # type: ignore[assignment]
            elif corruption < 0.67:
                row["amount"] = -abs(row["amount"])
            else:
                row["currency"] = "XYZ"
        rows.append(row)
    return rows


def _extract_stage(flake_rate: float, rng: random.Random) -> Stage:
    def extract(rows: list[dict]) -> list[dict]:
        if rng.random() < flake_rate:
            raise ConnectionError("upstream transient blip")
        return rows

    return Stage(name="extract", fn=extract, max_retries=3)


def _loader_stage() -> Stage:
    def load(rows: list[dict]) -> list[dict]:
        for row in rows:
            if row.get("user_id") is None:
                raise RuntimeError("loader: NOT NULL user_id violated")
            if not isinstance(row.get("amount"), (int, float)):
                raise RuntimeError("loader: amount must be numeric")
            if row.get("amount", 0) < 0:
                raise RuntimeError("loader: amount must be ≥ 0")
            if row.get("currency") not in ALLOWED_CURRENCIES:
                raise RuntimeError("loader: unknown currency")
        return rows

    return Stage(name="load", fn=load, max_retries=0)


def _validate_stage() -> Stage:
    """Quarantining validate stage — bad rows are dropped, not crashed on.

    The function itself filters via the SDK so the pipeline keeps going
    on clean rows.  Schema validation in the runner removes type errors;
    here we strip semantically-bad rows (negative amount, unknown
    currency) that survived schema validation but would crash the loader.
    """

    not_null_check = not_null("user_id")
    range_check_amount = range_check("amount", min_value=0.0)
    in_set_currency = in_set("currency", ALLOWED_CURRENCIES)

    def quarantine(rows: list[dict]) -> list[dict]:
        bad: set[int] = set()
        for r in not_null_check.apply(rows):
            bad.add(id(r))
        for r in range_check_amount.apply(rows):
            bad.add(id(r))
        for r in in_set_currency.apply(rows):
            bad.add(id(r))
        return [r for r in rows if id(r) not in bad]

    return Stage(
        name="validate",
        fn=quarantine,
        schema=ORDERS_SCHEMA,
        max_retries=0,
    )


def _build_pipeline(*, enable_dq: bool, rng: random.Random) -> Pipeline:
    stages: list[Stage] = [_extract_stage(FLAKE_RATE, rng)]
    if enable_dq:
        stages.append(_validate_stage())
    stages.append(_loader_stage())
    return Pipeline(
        name="orders",
        stages=stages,
        enable_dq=enable_dq,
        enable_retries=enable_dq,
    )


def _run_suite(*, enable_dq: bool, seed: int) -> tuple[int, int]:
    rng = random.Random(seed)
    failures = 0
    for _ in range(N_JOBS):
        # Reseed the extract-stage RNG per job so the flake schedule is
        # the same in both configurations — the only thing that changes
        # is whether the SDK is on.
        extract_rng = random.Random(rng.random())
        pipeline = _build_pipeline(enable_dq=enable_dq, rng=extract_rng)
        dirty = rng.random() < DIRTY_RATE
        rows = _generate_job(rng, dirty)
        result = pipeline.run(rows)
        if not result.succeeded:
            failures += 1
    return failures, N_JOBS


def main() -> int:
    banner("Bullet 2 — ETL: ≥30% pipeline failure reduction")

    without, total = _run_suite(enable_dq=False, seed=1729)
    with_sdk, _ = _run_suite(enable_dq=True, seed=1729)

    without_rate = without / total * 100.0
    with_rate = with_sdk / total * 100.0
    reduction = pct_reduction(without_rate, with_rate)

    print(f"Failure rate without SDK : {without_rate:.2f}% ({without}/{total})")
    print(f"Failure rate with SDK    : {with_rate:.2f}% ({with_sdk}/{total})")
    print(f"Reduction                : {reduction:.1f}%")

    return assert_pass(
        reduction >= REQUIRED_REDUCTION_PCT,
        f"Pipeline failure rate cut by {reduction:.1f}% (target ≥ {REQUIRED_REDUCTION_PCT}%)",
    )


if __name__ == "__main__":
    sys.exit(main())
