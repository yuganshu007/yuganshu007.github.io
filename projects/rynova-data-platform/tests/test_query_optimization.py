"""Bullet 1 + 4 optimization sanity tests.

These exercise the same code paths the benchmarks measure, but at
unit-test scale so the suite stays fast.  They are deterministic and do
not assert latency numbers — just that the optimized path returns the
same rows as the baseline and that the index is in fact used.
"""

from __future__ import annotations

import sqlite3


def _seed(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE events ("
        "id INTEGER PRIMARY KEY, user_id INTEGER, ts INTEGER, amount REAL)"
    )
    conn.executemany(
        "INSERT INTO events(id, user_id, ts, amount) VALUES (?, ?, ?, ?)",
        [(i, i % 7, i, float(i)) for i in range(1, 201)],
    )


def test_indexed_query_returns_same_rows() -> None:
    no_idx = sqlite3.connect(":memory:")
    _seed(no_idx)
    no_idx_rows = no_idx.execute(
        "SELECT id, amount FROM events WHERE user_id = ? ORDER BY ts DESC LIMIT 5",
        (3,),
    ).fetchall()

    idx = sqlite3.connect(":memory:")
    _seed(idx)
    idx.execute("CREATE INDEX idx_events_user_ts ON events(user_id, ts)")
    idx_rows = idx.execute(
        "SELECT id, amount FROM events WHERE user_id = ? ORDER BY ts DESC LIMIT 5",
        (3,),
    ).fetchall()

    assert no_idx_rows == idx_rows


def test_explain_uses_index() -> None:
    conn = sqlite3.connect(":memory:")
    _seed(conn)
    conn.execute("CREATE INDEX idx_events_user_ts ON events(user_id, ts)")
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT id FROM events WHERE user_id = ?",
        (3,),
    ).fetchall()
    plan_text = " ".join(str(c) for row in plan for c in row).lower()
    assert "idx_events_user_ts" in plan_text


def test_keyset_pagination_equivalent_to_offset() -> None:
    from rynova_platform.sql import PageRequest, keyset_paginate, offset_paginate

    conn = sqlite3.connect(":memory:")
    _seed(conn)
    by_offset = offset_paginate(
        conn, "events", PageRequest(limit=5, offset=10)
    ).rows
    by_keyset = keyset_paginate(
        conn, "events", PageRequest(limit=5, after_id=10)
    ).rows
    assert by_offset == by_keyset
