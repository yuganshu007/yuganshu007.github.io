"""Priority-based request router (the "tuned request routing" layer).

Incoming tracking events are not all equally urgent: an ``EXCEPTION`` (lost /
damaged / mis-routed shipment) or a ``DELIVERED`` confirmation needs to be
reflected fast, while routine ``IN_TRANSIT`` scans can tolerate more queueing.

The router makes an O(1) in-memory decision and dispatches each request to a
dedicated message-queue lane:

  * tuned : urgent event types -> ``<stream>.high`` ; everything else -> ``<stream>.normal``.
            Workers drain the high lane first, so urgent traffic is not stuck
            behind a backlog of normal traffic under peak load.
  * fifo  : every event -> ``<stream>.normal`` (single lane, no prioritization).
            This models the un-tuned routing tier used as the A/B baseline.

This is intentionally a pure, side-effect-free policy object so it is trivial to
unit test and to reason about on the hot request path.
"""
from __future__ import annotations

from typing import Iterable

# Event types whose end-to-end latency matters most to customers/ops.
HIGH_PRIORITY_TYPES: frozenset[str] = frozenset({"EXCEPTION", "DELIVERED"})


class PriorityRouter:
    def __init__(self, base_stream: str, mode: str = "tuned") -> None:
        self.base_stream = base_stream
        self.mode = mode if mode in {"tuned", "fifo"} else "tuned"

    def priority(self, event_type: str) -> str:
        if self.mode == "tuned" and event_type in HIGH_PRIORITY_TYPES:
            return "high"
        return "normal"

    def lane_stream(self, priority: str) -> str:
        return f"{self.base_stream}.{priority}"

    def route(self, event: dict) -> str:
        """Return the queue lane for an event and stamp it with its priority."""
        priority = self.priority(event.get("event_type", ""))
        event["priority"] = priority
        return self.lane_stream(priority)

    def lanes(self) -> list[str]:
        """All lanes this router can dispatch to, ordered high-priority first."""
        if self.mode == "tuned":
            return [self.lane_stream("high"), self.lane_stream("normal")]
        return [self.lane_stream("normal")]

    @staticmethod
    def all_possible_lanes(base_stream: str) -> Iterable[str]:
        """Every lane name either mode could create (used for cleanup/reset)."""
        return (f"{base_stream}.high", f"{base_stream}.normal")
