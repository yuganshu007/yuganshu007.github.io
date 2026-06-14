"""Exactly-once-effective sink for the Kafka streaming workflow (Bullet 3).

The sink keeps a SQLite-backed dedupe table keyed by a stable
:class:`IdempotencyKey` derived from ``(topic, partition, key, value)``.
``apply`` is therefore safe to call repeatedly with the same message —
the second call is observed as a no-op even though the consumer may
have re-read the partition after a rebalance.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass

from rynova_platform.streaming.broker import KafkaMessage


@dataclass(frozen=True)
class IdempotencyKey:
    topic: str
    partition: int
    fingerprint: str

    @classmethod
    def for_message(cls, msg: KafkaMessage) -> IdempotencyKey:
        h = hashlib.sha256()
        if msg.key is not None:
            h.update(msg.key)
        h.update(b"|")
        h.update(msg.value)
        return cls(topic=msg.topic, partition=msg.partition, fingerprint=h.hexdigest())


class IdempotentSink:
    """A sink that dedupes by :class:`IdempotencyKey`."""

    DDL = """
        CREATE TABLE IF NOT EXISTS sink_dedupe (
            topic TEXT NOT NULL,
            partition INTEGER NOT NULL,
            fingerprint TEXT NOT NULL,
            applied_at INTEGER NOT NULL,
            PRIMARY KEY (topic, partition, fingerprint)
        );
        CREATE TABLE IF NOT EXISTS sink_state (
            topic TEXT NOT NULL,
            partition INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (topic, partition, key)
        );
    """

    def __init__(
        self,
        db_path: str = ":memory:",
        *,
        apply_fn: Callable[[KafkaMessage], None] | None = None,
    ) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        self._conn.executescript(self.DDL)
        self._lock = threading.Lock()
        self._apply_fn = apply_fn or self._default_apply
        self._applied = 0
        self._duplicates = 0

    @property
    def applied(self) -> int:
        return self._applied

    @property
    def duplicates(self) -> int:
        return self._duplicates

    def _default_apply(self, msg: KafkaMessage) -> None:
        key = msg.key.decode("utf-8") if msg.key else ""
        value = msg.value.decode("utf-8", errors="replace")
        self._conn.execute(
            "INSERT OR REPLACE INTO sink_state(topic, partition, key, value) "
            "VALUES (?, ?, ?, ?)",
            (msg.topic, msg.partition, key, value),
        )

    def apply(self, message: KafkaMessage) -> bool:
        """Apply ``message`` exactly once.  Returns ``True`` if applied,
        ``False`` if the call was deduped."""

        key = IdempotencyKey.for_message(message)
        with self._lock:
            cur = self._conn.execute(
                "SELECT 1 FROM sink_dedupe WHERE topic=? AND partition=? AND fingerprint=?",
                (key.topic, key.partition, key.fingerprint),
            )
            if cur.fetchone():
                self._duplicates += 1
                return False
            self._apply_fn(message)
            self._conn.execute(
                "INSERT INTO sink_dedupe(topic, partition, fingerprint, applied_at) "
                "VALUES (?, ?, ?, strftime('%s','now'))",
                (key.topic, key.partition, key.fingerprint),
            )
            self._applied += 1
            return True

    def snapshot(self) -> dict[tuple[str, int, str], str]:
        cur = self._conn.execute(
            "SELECT topic, partition, key, value FROM sink_state ORDER BY topic, partition, key"
        )
        return {(r[0], r[1], r[2]): r[3] for r in cur.fetchall()}

    def close(self) -> None:
        import contextlib

        with contextlib.suppress(sqlite3.Error):
            self._conn.close()
