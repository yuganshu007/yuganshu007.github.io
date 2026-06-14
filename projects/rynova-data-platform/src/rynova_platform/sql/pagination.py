"""Keyset vs offset pagination helpers (Bullet 4).

The benchmark in :mod:`benchmarks.bench_bullet4_sql_plans` proves that
keyset pagination at deep offsets is ≥25% faster than ``LIMIT/OFFSET``
on the same data — the "pagination" component of the 25% SQL latency
reduction.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class PageRequest:
    limit: int = 50
    after_id: int = 0
    offset: int = 0


@dataclass(frozen=True)
class Page:
    rows: list[tuple]
    next_after_id: int | None


def keyset_paginate(
    conn: sqlite3.Connection,
    table: str,
    request: PageRequest,
    *,
    id_column: str = "id",
) -> Page:
    """Paginate via ``WHERE id > ?`` ordered by id (index seek)."""

    cur = conn.execute(
        f"SELECT * FROM {table} WHERE {id_column} > ? "
        f"ORDER BY {id_column} ASC LIMIT ?",
        (request.after_id, request.limit),
    )
    rows = cur.fetchall()
    next_id = rows[-1][0] if rows else None
    return Page(rows=rows, next_after_id=next_id)


def offset_paginate(
    conn: sqlite3.Connection,
    table: str,
    request: PageRequest,
    *,
    id_column: str = "id",
) -> Page:
    """Paginate via ``LIMIT N OFFSET M`` (must scan + discard M rows)."""

    cur = conn.execute(
        f"SELECT * FROM {table} ORDER BY {id_column} ASC LIMIT ? OFFSET ?",
        (request.limit, request.offset),
    )
    rows = cur.fetchall()
    next_id = rows[-1][0] if rows else None
    return Page(rows=rows, next_after_id=next_id)
