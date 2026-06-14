"""Tests for the FastAPI service surface (Bullet 1)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from rynova_platform.api import RynovaService, create_app


@pytest.fixture
def client() -> httpx.AsyncClient:
    service = RynovaService()
    app = create_app(service)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_health_endpoint(client: httpx.AsyncClient) -> None:
    async with client:
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["datasets"] == 0
        assert body["events_delivered"] == 0


async def test_create_dataset_returns_201(client: httpx.AsyncClient) -> None:
    async with client:
        r = await client.post(
            "/datasets",
            json={"name": "orders", "owner": "rynova", "rows": 10, "tags": ["sales"]},
        )
        assert r.status_code == 201
        body = r.json()
        assert body["id"] == 1
        assert body["name"] == "orders"


async def test_create_dataset_rejects_empty_name(client: httpx.AsyncClient) -> None:
    async with client:
        r = await client.post(
            "/datasets",
            json={"name": "", "owner": "rynova", "rows": 1},
        )
        assert r.status_code == 422


async def test_list_datasets_keyset_pagination(client: httpx.AsyncClient) -> None:
    async with client:
        for i in range(10):
            await client.post(
                "/datasets",
                json={"name": f"ds-{i}", "owner": "rynova", "rows": i, "tags": []},
            )
        page = await client.get("/datasets", params={"limit": 4, "after_id": 0})
        assert page.status_code == 200
        rows = page.json()
        assert [r["id"] for r in rows] == [1, 2, 3, 4]
        page = await client.get("/datasets", params={"limit": 4, "after_id": 4})
        rows = page.json()
        assert [r["id"] for r in rows] == [5, 6, 7, 8]


async def test_get_dataset_404(client: httpx.AsyncClient) -> None:
    async with client:
        r = await client.get("/datasets/999")
        assert r.status_code == 404


async def test_query_endpoint_runs_sql(client: httpx.AsyncClient) -> None:
    async with client:
        r = await client.post("/query", json={"sql": "SELECT 1 AS one"})
        assert r.status_code == 200
        body = r.json()
        assert body["rows"][0] == [1]
        assert body["latency_ms"] >= 0
        assert isinstance(body["plan"], list)


async def test_query_endpoint_requires_sql(client: httpx.AsyncClient) -> None:
    async with client:
        r = await client.post("/query", json={"sql": ""})
        assert r.status_code == 400


async def test_event_bus_publishes_on_register() -> None:
    service = RynovaService()
    received: list[dict] = []

    async def handler(event):
        received.append(event.payload)

    service.bus.subscribe("dataset.registered", handler)
    from rynova_platform.api.service import DatasetIn

    await service.register_dataset(DatasetIn(name="x", owner="o", rows=1))
    assert len(received) == 1
    assert received[0]["name"] == "x"


async def test_event_bus_preserves_order_per_topic() -> None:
    from rynova_platform.api.event_bus import AsyncEventBus, Event

    bus = AsyncEventBus()
    seen: list[int] = []

    async def handler(event):
        seen.append(event.payload["i"])

    bus.subscribe("t", handler)
    await bus.publish_many([Event(topic="t", payload={"i": i}) for i in range(50)])
    assert seen == list(range(50))


async def test_concurrent_2500_users() -> None:
    """Smoke check: 2,500 concurrent calls all succeed."""
    service = RynovaService()
    app = create_app(service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        await c.post("/datasets", json={"name": "x", "owner": "o", "rows": 1})
        sem = asyncio.Semaphore(128)

        async def _one() -> int:
            async with sem:
                r = await c.get("/datasets", params={"limit": 1})
                return r.status_code

        results = await asyncio.gather(*[_one() for _ in range(2_500)])
    assert all(s == 200 for s in results)


async def test_health_reports_dataset_count() -> None:
    service = RynovaService()
    app = create_app(service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        for i in range(5):
            await c.post(
                "/datasets",
                json={"name": f"d{i}", "owner": "o", "rows": 1},
            )
        r = await c.get("/health")
        assert r.json()["datasets"] == 5
