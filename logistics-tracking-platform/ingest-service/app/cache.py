"""Tiny thread-safe LRU+TTL cache used in front of SQLite reads.

This is the in-process "local caching" layer from the resume bullet. Combined
with the secondary index it turns repeated GET /shipments/{id} reads into O(1)
dictionary hits instead of disk lookups.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any


class LruTtlCache:
    def __init__(self, capacity: int, ttl_ms: int) -> None:
        self._capacity = max(1, capacity)
        self._ttl_ms = ttl_ms
        self._store: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        now = time.time() * 1000
        with self._lock:
            item = self._store.get(key)
            if item is None:
                self.misses += 1
                return None
            expires_at, value = item
            if now >= expires_at:
                # Stale entry; drop it and report a miss.
                self._store.pop(key, None)
                self.misses += 1
                return None
            self._store.move_to_end(key)
            self.hits += 1
            return value

    def put(self, key: str, value: Any) -> None:
        expires_at = time.time() * 1000 + self._ttl_ms
        with self._lock:
            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)
            while len(self._store) > self._capacity:
                self._store.popitem(last=False)

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def stats(self) -> dict[str, int]:
        with self._lock:
            total = self.hits + self.misses
            ratio = (self.hits / total) if total else 0.0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "size": len(self._store),
                "hit_ratio_pct": round(ratio * 100, 2),
            }
