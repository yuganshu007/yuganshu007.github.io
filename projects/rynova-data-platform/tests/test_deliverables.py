"""Deliverables tracker tests (Bullet 4 — 100% on-time)."""

from __future__ import annotations

import csv
from pathlib import Path


def _rows() -> list[dict]:
    path = Path(__file__).resolve().parent.parent / "deliverables" / "deliveries.csv"
    with path.open() as fp:
        return list(csv.DictReader(fp))


def test_csv_has_rows() -> None:
    rows = _rows()
    assert len(rows) >= 20


def test_every_row_on_time() -> None:
    for row in _rows():
        assert row["on_time"].lower() == "true", row


def test_every_row_has_bullet_label() -> None:
    for row in _rows():
        assert row["bullet"] in {"1", "2", "3", "4"}


def test_each_bullet_has_deliverables() -> None:
    by_bullet: dict[str, int] = {}
    for row in _rows():
        by_bullet[row["bullet"]] = by_bullet.get(row["bullet"], 0) + 1
    assert set(by_bullet) == {"1", "2", "3", "4"}
    for count in by_bullet.values():
        assert count >= 4


def test_delivered_date_not_after_planned_plus_one_day() -> None:
    from datetime import date

    for row in _rows():
        planned = date.fromisoformat(row["planned_date"])
        delivered = date.fromisoformat(row["delivered_date"])
        # On-time means delivered on or before planned date.
        assert delivered <= planned, row
