"""Tests for the SQL planner, partitioning, and pagination helpers."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from rynova_platform.sql import (
    DateShardedTable,
    Page,
    PageRequest,
    QueryPlanner,
    ShardKey,
    keyset_paginate,
    offset_paginate,
)


def _seed(planner: QueryPlanner) -> None:
    planner.executescript(
        """
        CREATE TABLE t (id INTEGER PRIMARY KEY, v INTEGER);
        """
    )
    planner._conn.executemany(
        "INSERT INTO t(id, v) VALUES (?, ?)", [(i, i * 2) for i in range(1, 101)]
    )


def test_planner_execute_sync_returns_rows(in_memory_planner: QueryPlanner) -> None:
    _seed(in_memory_planner)
    rows = in_memory_planner.execute_sync("SELECT id, v FROM t WHERE id <= 3 ORDER BY id")
    assert rows == [(1, 2), (2, 4), (3, 6)]


def test_planner_explain_includes_table_name(in_memory_planner: QueryPlanner) -> None:
    _seed(in_memory_planner)
    plan = in_memory_planner.explain("SELECT * FROM t WHERE id = ?", (1,))
    assert any("t" in line for line in plan)


def test_planner_switch_mode_round_trip(in_memory_planner: QueryPlanner) -> None:
    assert in_memory_planner.mode == "optimized"
    in_memory_planner.switch_mode("baseline")
    assert in_memory_planner.mode == "baseline"
    in_memory_planner.switch_mode("optimized")
    assert in_memory_planner.mode == "optimized"


def test_planner_switch_mode_rejects_unknown(in_memory_planner: QueryPlanner) -> None:
    with pytest.raises(AssertionError):
        in_memory_planner.switch_mode("hyper")


async def test_planner_execute_returns_latency(in_memory_planner: QueryPlanner) -> None:
    _seed(in_memory_planner)
    result = await in_memory_planner.execute("SELECT COUNT(*) FROM t")
    assert result.rows[0][0] == 100
    assert result.latency_ms >= 0
    assert result.plan


def test_optimized_pragmas_are_applied(in_memory_planner: QueryPlanner) -> None:
    journal = in_memory_planner._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert journal in {"wal", "memory"}
    sync = in_memory_planner._conn.execute("PRAGMA synchronous").fetchone()[0]
    assert sync in (1, 2)  # NORMAL or FULL (in-memory has no WAL)


def test_baseline_pragmas_are_applied(baseline_planner: QueryPlanner) -> None:
    sync = baseline_planner._conn.execute("PRAGMA synchronous").fetchone()[0]
    assert sync == 2  # FULL


def test_keyset_paginate_walks_forward() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE x (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany("INSERT INTO x(id, v) VALUES (?, ?)", [(i, f"v{i}") for i in range(1, 21)])

    page1 = keyset_paginate(conn, "x", PageRequest(limit=5, after_id=0))
    assert isinstance(page1, Page)
    assert [r[0] for r in page1.rows] == [1, 2, 3, 4, 5]
    page2 = keyset_paginate(conn, "x", PageRequest(limit=5, after_id=page1.next_after_id or 0))
    assert [r[0] for r in page2.rows] == [6, 7, 8, 9, 10]


def test_offset_paginate_returns_window() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE x (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany("INSERT INTO x(id, v) VALUES (?, ?)", [(i, f"v{i}") for i in range(1, 21)])
    page = offset_paginate(conn, "x", PageRequest(limit=5, offset=10))
    assert [r[0] for r in page.rows] == [11, 12, 13, 14, 15]


def test_keyset_paginate_returns_empty_when_exhausted() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE x (id INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO x(id) VALUES (?)", [(i,) for i in range(1, 6)])
    page = keyset_paginate(conn, "x", PageRequest(limit=10, after_id=5))
    assert page.rows == []
    assert page.next_after_id is None


def test_date_sharded_table_creates_shards() -> None:
    conn = sqlite3.connect(":memory:")
    table = DateShardedTable(conn)
    shard = ShardKey(day=date(2024, 1, 1))
    table.insert(shard, [(1, 1, 10.0, 0), (2, 2, 20.0, 0)])
    rows = table.read_range(date(2024, 1, 1), date(2024, 1, 2))
    assert len(rows) == 2


def test_date_sharded_table_prunes_outside_range() -> None:
    conn = sqlite3.connect(":memory:")
    table = DateShardedTable(conn)
    for d in (date(2024, 1, 1), date(2024, 1, 5), date(2024, 1, 10)):
        table.insert(ShardKey(day=d), [(int(d.toordinal()), 1, 1.0, 0)])
    rows = table.read_range(date(2024, 1, 1), date(2024, 1, 6))
    assert len(rows) == 2


def test_date_sharded_full_scan_returns_all() -> None:
    conn = sqlite3.connect(":memory:")
    table = DateShardedTable(conn)
    for d in (date(2024, 1, 1), date(2024, 1, 5)):
        table.insert(ShardKey(day=d), [(int(d.toordinal()), 7, 1.0, 0)])
    rows = table.full_scan(user_id=7)
    assert len(rows) == 2


def test_shard_table_filters_by_user() -> None:
    conn = sqlite3.connect(":memory:")
    table = DateShardedTable(conn)
    shard = ShardKey(day=date(2024, 2, 1))
    table.insert(shard, [(1, 100, 1.0, 0), (2, 200, 2.0, 0), (3, 100, 3.0, 0)])
    rows = table.read_range(date(2024, 2, 1), date(2024, 2, 1), user_id=100)
    assert {r[0] for r in rows} == {1, 3}


def test_shard_key_table_name_format() -> None:
    key = ShardKey(day=date(2024, 3, 14))
    assert key.table == "events_2024_03_14"
