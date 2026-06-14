"""Tests for the data quality SDK (Bullet 2)."""

from __future__ import annotations

import pytest

from rynova_platform.etl.schema import Field, Schema
from rynova_platform.validation import (
    DataQualityCheck,
    ValidationError,
    in_set,
    not_null,
    range_check,
    regex_match,
    unique,
    validate_batch,
)

SCHEMA = Schema(
    name="orders",
    version=1,
    fields=(
        Field("id", int),
        Field("user_id", int),
        Field("amount", float),
    ),
)


def test_not_null_flags_missing_value() -> None:
    check = not_null("user_id")
    violations = check.apply([{"user_id": 1}, {"user_id": None}, {}])
    assert len(violations) == 2


def test_range_check_inclusive_lower_bound() -> None:
    check = range_check("amount", min_value=0.0)
    violations = check.apply([{"amount": 0.0}, {"amount": -0.01}])
    assert len(violations) == 1


def test_range_check_max_bound() -> None:
    check = range_check("amount", max_value=100.0)
    violations = check.apply([{"amount": 99}, {"amount": 101}])
    assert len(violations) == 1


def test_range_check_skips_missing_values() -> None:
    check = range_check("amount", min_value=0)
    violations = check.apply([{}, {"amount": None}])
    assert violations == []


def test_in_set_check() -> None:
    check = in_set("currency", {"USD", "EUR"})
    violations = check.apply([{"currency": "USD"}, {"currency": "XYZ"}])
    assert len(violations) == 1


def test_in_set_treats_none_as_violation() -> None:
    check = in_set("currency", {"USD"})
    violations = check.apply([{"currency": None}])
    assert len(violations) == 1


def test_regex_match() -> None:
    check = regex_match("email", r"^[^@]+@[^@]+\.[^@]+$")
    violations = check.apply([{"email": "a@b.com"}, {"email": "nope"}, {"email": 5}])
    assert len(violations) == 2


def test_unique_finds_duplicates() -> None:
    check = unique("id")
    violations = check.apply([{"id": 1}, {"id": 2}, {"id": 1}])
    assert len(violations) == 1


def test_run_all_passes_when_clean() -> None:
    report = DataQualityCheck.run_all(
        (not_null("amount"), range_check("amount", min_value=0)),
        [{"amount": 1.0}, {"amount": 2.0}],
    )
    assert report.passed
    assert report.total_violations() == 0


def test_run_all_collects_failures() -> None:
    report = DataQualityCheck.run_all(
        (not_null("amount"), range_check("amount", min_value=0)),
        [{"amount": None}, {"amount": -1}],
    )
    assert not report.passed
    assert report.total_violations() == 2
    assert "not_null:amount" in report.failed_check_names()
    assert any(name.startswith("range:") for name in report.failed_check_names())


def test_validate_batch_drops_invalid() -> None:
    rows = [
        {"id": 1, "user_id": 1, "amount": 1.0},
        {"id": 2, "user_id": None, "amount": 1.0},
    ]
    survivors = validate_batch(rows, SCHEMA, drop_invalid=True)
    assert len(survivors) == 1
    assert survivors[0]["id"] == 1


def test_validate_batch_raises_when_strict() -> None:
    rows = [{"id": 1, "user_id": None, "amount": 1.0}]
    with pytest.raises(ValidationError):
        validate_batch(rows, SCHEMA)


def test_warning_severity_does_not_fail_report() -> None:
    check = DataQualityCheck(
        name="warn:user_id",
        fn=lambda rows: [r for r in rows if r.get("user_id") is None],
        severity="warning",
    )
    report = DataQualityCheck.run_all((check,), [{"user_id": None}])
    assert report.passed
    assert report.total_violations() == 1
