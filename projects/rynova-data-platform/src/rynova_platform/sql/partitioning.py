"""Date-shard partitioning helper used by Bullet 4.

Each daily partition is materialized as its own SQLite table.  Reads
that supply a date range are pruned to the matching shards, which is the
"partitioning" half of the "indexes, partitioning, pagination" claim in
Bullet 4.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ShardKey:
    day: date

    @property
    def table(self) -> str:
        return f"events_{self.day.year:04d}_{self.day.month:02d}_{self.day.day:02d}"


class DateShardedTable:
    """Manages a family of physical tables, one per UTC day.

    The table list is kept in a single metadata row so ``read_range`` only
    scans the shards that overlap the requested window.
    """

    DDL = """
        CREATE TABLE IF NOT EXISTS shard_catalog (
            day TEXT PRIMARY KEY,
            row_count INTEGER NOT NULL DEFAULT 0
        );
    """

    SHARD_DDL = """
        CREATE TABLE IF NOT EXISTS {table} (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            ts INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_{table}_user
            ON {table}(user_id, id);
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._conn.executescript(self.DDL)

    def ensure_shard(self, key: ShardKey) -> None:
        self._conn.executescript(self.SHARD_DDL.format(table=key.table))
        self._conn.execute(
            "INSERT OR IGNORE INTO shard_catalog(day, row_count) VALUES (?, 0)",
            (key.day.isoformat(),),
        )

    def insert(self, key: ShardKey, rows: Sequence[tuple[int, int, float, int]]) -> None:
        self.ensure_shard(key)
        self._conn.executemany(
            f"INSERT INTO {key.table}(id, user_id, amount, ts) VALUES (?, ?, ?, ?)",
            rows,
        )
        self._conn.execute(
            "UPDATE shard_catalog SET row_count = row_count + ? WHERE day = ?",
            (len(rows), key.day.isoformat()),
        )

    def shards_in_range(self, start: date, end: date) -> list[ShardKey]:
        cur = self._conn.execute(
            "SELECT day FROM shard_catalog WHERE day BETWEEN ? AND ? ORDER BY day",
            (start.isoformat(), end.isoformat()),
        )
        days = [date.fromisoformat(row[0]) for row in cur.fetchall()]
        return [ShardKey(day=d) for d in days]

    def read_range(
        self,
        start: date,
        end: date,
        *,
        user_id: int | None = None,
    ) -> list[tuple]:
        results: list[tuple] = []
        for shard in self.shards_in_range(start, end):
            if user_id is None:
                cur = self._conn.execute(
                    f"SELECT id, user_id, amount, ts FROM {shard.table}"
                )
            else:
                cur = self._conn.execute(
                    f"SELECT id, user_id, amount, ts FROM {shard.table} "
                    "WHERE user_id = ? ORDER BY id",
                    (user_id,),
                )
            results.extend(cur.fetchall())
        return results

    def full_scan(self, *, user_id: int | None = None) -> list[tuple]:
        # The "before" picture: every shard read regardless of filter.
        results: list[tuple] = []
        for shard in self.shards_in_range(date(1900, 1, 1), date(2999, 12, 31)):
            cur = self._conn.execute(
                f"SELECT id, user_id, amount, ts FROM {shard.table}"
            )
            rows = cur.fetchall()
            if user_id is not None:
                rows = [r for r in rows if r[1] == user_id]
            results.extend(rows)
        return results

    def all_shards(self) -> Iterable[ShardKey]:
        return self.shards_in_range(date(1900, 1, 1), date(2999, 12, 31))
