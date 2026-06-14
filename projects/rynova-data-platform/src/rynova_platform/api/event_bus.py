"""In-process async event bus used by the REST API layer (Bullet 1).

The bus is intentionally tiny: it is just enough to demonstrate the
event-driven architecture claim without dragging in a broker dependency
for unit tests.  Production deployments wire the same publish/subscribe
interface to the Kafka transport in :mod:`rynova_platform.streaming`.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

Handler = Callable[["Event"], Awaitable[None]]


@dataclass(frozen=True)
class Event:
    """Immutable record describing something that happened in the platform."""

    topic: str
    payload: dict[str, Any]
    key: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


class AsyncEventBus:
    """Pub/sub bus with at-least-once, in-order delivery per topic.

    Handlers are invoked concurrently across topics but sequentially
    within a single topic so that downstream consumers observe events in
    the order they were produced — a precondition for the idempotency
    semantics asserted by Bullet 3.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._delivered: int = 0

    @property
    def delivered(self) -> int:
        return self._delivered

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers[topic].append(handler)

    async def publish(self, event: Event) -> int:
        """Publish ``event``; returns number of handlers that observed it."""
        async with self._locks[event.topic]:
            handlers = list(self._subscribers.get(event.topic, ()))
            for handler in handlers:
                await handler(event)
                self._delivered += 1
            return len(handlers)

    async def publish_many(self, events: list[Event]) -> int:
        total = 0
        for event in events:
            total += await self.publish(event)
        return total
