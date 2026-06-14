"""SDK-style data quality validators.

Every check is a small dataclass with two methods: ``apply`` (returns
violation count and sample violation rows) and ``description`` (a human
readable label used by structured code reviews).  The check builders
return fully-typed :class:`DataQualityCheck` instances so consumer
pipelines look like::

    pipeline = Pipeline(
        name="orders",
        stages=[
            Stage(
                name="validate",
                fn=identity,
                schema=ORDERS_SCHEMA,
                checks=(
                    not_null("user_id"),
                    range_check("amount", min_value=0),
                    in_set("currency", {"USD", "EUR", "INR"}),
                ),
            ),
            ...
        ],
    )
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from rynova_platform.etl.schema import Schema


class ValidationError(Exception):
    """Raised when a fatal schema/DQ violation is detected."""


@dataclass(frozen=True)
class DataQualityCheck:
    """One row-level or batch-level data quality assertion."""

    name: str
    fn: Callable[[list[dict[str, Any]]], list[dict[str, Any]]]
    severity: str = "error"

    def apply(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self.fn(rows)

    @staticmethod
    def run_all(
        checks: Iterable[DataQualityCheck],
        rows: list[dict[str, Any]],
    ) -> DataQualityReport:
        report = DataQualityReport()
        for check in checks:
            violations = check.apply(rows)
            report.results.append((check, violations))
        return report


@dataclass
class DataQualityReport:
    results: list[tuple[DataQualityCheck, list[dict[str, Any]]]] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(
            len(v) == 0 or c.severity == "warning"
            for c, v in self.results
        )

    def failed_check_names(self) -> list[str]:
        return [c.name for c, v in self.results if v and c.severity == "error"]

    def total_violations(self) -> int:
        return sum(len(v) for _, v in self.results)


def not_null(column: str) -> DataQualityCheck:
    def _check(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in rows if r.get(column) is None]

    return DataQualityCheck(name=f"not_null:{column}", fn=_check)


def range_check(
    column: str,
    *,
    min_value: float | None = None,
    max_value: float | None = None,
) -> DataQualityCheck:
    def _check(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        bad: list[dict[str, Any]] = []
        for r in rows:
            v = r.get(column)
            if v is None:
                continue
            if min_value is not None and v < min_value or max_value is not None and v > max_value:
                bad.append(r)
        return bad

    bounds = []
    if min_value is not None:
        bounds.append(f"≥{min_value}")
    if max_value is not None:
        bounds.append(f"≤{max_value}")
    return DataQualityCheck(
        name=f"range:{column}({','.join(bounds)})",
        fn=_check,
    )


def in_set(column: str, allowed: set[Any]) -> DataQualityCheck:
    def _check(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [r for r in rows if r.get(column) not in allowed]

    return DataQualityCheck(
        name=f"in_set:{column}({len(allowed)})",
        fn=_check,
    )


def regex_match(column: str, pattern: str) -> DataQualityCheck:
    regex = re.compile(pattern)

    def _check(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            r for r in rows
            if not isinstance(r.get(column), str) or not regex.match(r[column])
        ]

    return DataQualityCheck(
        name=f"regex:{column}({pattern})",
        fn=_check,
    )


def unique(column: str) -> DataQualityCheck:
    def _check(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[Any] = set()
        bad: list[dict[str, Any]] = []
        for r in rows:
            v = r.get(column)
            if v in seen:
                bad.append(r)
            else:
                seen.add(v)
        return bad

    return DataQualityCheck(name=f"unique:{column}", fn=_check)


def validate_batch(
    rows: list[dict[str, Any]],
    schema: Schema,
    *,
    drop_invalid: bool = False,
) -> list[dict[str, Any]]:
    """Validate every row against ``schema``.

    Returns the surviving rows when ``drop_invalid`` is true; otherwise
    raises :class:`ValidationError` on the first violation.
    """

    survivors: list[dict[str, Any]] = []
    for row in rows:
        errors = schema.validate(row)
        if errors:
            if drop_invalid:
                continue
            raise ValidationError("; ".join(errors))
        survivors.append(row)
    return survivors
