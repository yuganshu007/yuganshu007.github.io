"""Async event bus unit tests."""

from __future__ import annotations

import asyncio

import pytest

from rynova_platform.api.event_bus import AsyncEventBus, Event


async def test_subscribe_and_publish_returns_handler_count() -> None:
    bus = AsyncEventBus()
    seen: list[Event] = []

    async def h1(event):
        seen.append(event)

    async def h2(event):
        seen.append(event)

    bus.subscribe("t", h1)
    bus.subscribe("t", h2)
    count = await bus.publish(Event(topic="t", payload={}))
    assert count == 2
    assert len(seen) == 2


async def test_publish_with_no_subscribers() -> None:
    bus = AsyncEventBus()
    count = await bus.publish(Event(topic="missing", payload={}))
    assert count == 0


async def test_topic_isolation() -> None:
    bus = AsyncEventBus()
    a: list[int] = []
    b: list[int] = []

    async def ha(e):
        a.append(e.payload["v"])

    async def hb(e):
        b.append(e.payload["v"])

    bus.subscribe("a", ha)
    bus.subscribe("b", hb)
    await bus.publish(Event(topic="a", payload={"v": 1}))
    await bus.publish(Event(topic="b", payload={"v": 2}))
    assert a == [1]
    assert b == [2]


async def test_delivered_counter_increments() -> None:
    bus = AsyncEventBus()

    async def h(_):
        await asyncio.sleep(0)

    bus.subscribe("t", h)
    await bus.publish_many([Event(topic="t", payload={}) for _ in range(7)])
    assert bus.delivered == 7


async def test_per_topic_order_under_concurrency() -> None:
    bus = AsyncEventBus()
    out: list[int] = []

    async def h(event):
        await asyncio.sleep(0)
        out.append(event.payload["i"])

    bus.subscribe("t", h)
    await asyncio.gather(
        *[bus.publish(Event(topic="t", payload={"i": i})) for i in range(100)]
    )
    # Order within a topic must be preserved because of the per-topic lock.
    assert sorted(out) == out


async def test_event_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    e = Event(topic="t", payload={"a": 1})
    with pytest.raises(FrozenInstanceError):
        e.topic = "other"  # type: ignore[misc]
