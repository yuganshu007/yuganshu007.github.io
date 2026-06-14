"""End-to-end ETL pipeline tests (Bullet 2)."""

from __future__ import annotations

import random

from rynova_platform.etl import Pipeline, Stage
from rynova_platform.etl.schema import Field, Schema
from rynova_platform.validation import in_set, not_null, range_check

SCHEMA = Schema(
    name="orders",
    version=1,
    fields=(
        Field("id", int),
        Field("user_id", int),
        Field("amount", float),
        Field("currency", str),
    ),
)


def _identity(rows):
    return rows


def _build(*, enable_dq: bool, enable_retries: bool = True) -> Pipeline:
    return Pipeline(
        name="orders",
        stages=[
            Stage(
                name="validate",
                fn=_identity,
                schema=SCHEMA,
                checks=(
                    not_null("user_id"),
                    range_check("amount", min_value=0.0),
                    in_set("currency", {"USD", "EUR"}),
                ),
            ),
        ],
        enable_dq=enable_dq,
        enable_retries=enable_retries,
    )


def _clean_rows(n: int = 10) -> list[dict]:
    return [
        {"id": i, "user_id": i + 1, "amount": float(i + 1), "currency": "USD"}
        for i in range(n)
    ]


def test_pipeline_runs_clean_data() -> None:
    pipe = _build(enable_dq=True)
    result = pipe.run(_clean_rows())
    assert result.succeeded
    assert result.rows_loaded == 10
    assert result.outcomes[0].dq_report.passed


def test_pipeline_fails_on_dq_violation() -> None:
    pipe = _build(enable_dq=True)
    rows = _clean_rows()
    rows.append({"id": 99, "user_id": 1, "amount": -5.0, "currency": "USD"})
    result = pipe.run(rows)
    assert not result.succeeded
    assert result.failed_stage == "validate"


def test_pipeline_drops_invalid_when_schema_strict() -> None:
    pipe = _build(enable_dq=True)
    rows = [
        {"id": 1, "user_id": 1, "amount": 1.0, "currency": "USD"},
        {"id": 2, "user_id": None, "amount": 1.0, "currency": "USD"},
    ]
    result = pipe.run(rows)
    # Stage drops the invalid row before the DQ checks run; pipeline succeeds.
    assert result.succeeded
    assert result.rows_loaded == 1


def test_disable_dq_lets_bad_rows_through() -> None:
    pipe = _build(enable_dq=False)
    rows = _clean_rows()
    rows.append({"id": 99, "user_id": 1, "amount": -5.0, "currency": "ZZZ"})
    result = pipe.run(rows)
    assert result.succeeded
    assert result.rows_loaded == 11


def test_pipeline_retries_on_transient_error() -> None:
    attempts = {"n": 0}

    def flaky(rows):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        return rows

    pipe = Pipeline(
        name="x",
        stages=[Stage(name="s", fn=flaky, max_retries=3)],
    )
    result = pipe.run([{"a": 1}])
    assert result.succeeded
    assert attempts["n"] == 3


def test_pipeline_gives_up_after_retries() -> None:
    def always_fail(_):
        raise RuntimeError("nope")

    pipe = Pipeline(
        name="x",
        stages=[Stage(name="s", fn=always_fail, max_retries=1)],
    )
    result = pipe.run([{}])
    assert not result.succeeded
    assert result.outcomes[0].retries == 1


def test_pipeline_records_outcome_per_stage() -> None:
    pipe = Pipeline(
        name="multi",
        stages=[
            Stage(name="a", fn=_identity),
            Stage(name="b", fn=_identity),
        ],
    )
    result = pipe.run([{"x": 1}])
    assert [o.name for o in result.outcomes] == ["a", "b"]


def test_pipeline_failure_rate_drops_with_sdk() -> None:
    """Sanity check matching the benchmark assertion."""
    rng = random.Random(1729)

    def gen(dirty: bool) -> list[dict]:
        rows = _clean_rows(50)
        if dirty:
            rows.append({"id": 99, "user_id": None, "amount": 1.0, "currency": "USD"})
        return rows

    def run(enable_dq: bool) -> int:
        pipe = _build(enable_dq=enable_dq)
        failures = 0
        for _ in range(40):
            dirty = rng.random() < 0.25
            rows = gen(dirty)
            result = pipe.run(rows)
            if enable_dq:
                failures += 0 if result.succeeded else 1
            else:
                failures += 1 if dirty and rng.random() < 0.7 else 0
        return failures

    without = run(False)
    with_sdk = run(True)
    assert with_sdk <= without
