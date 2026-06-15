#!/usr/bin/env python3
"""Metric 1 (routing) - "tuned request routing" under peak load.

Builds a peak-load backlog of mixed-urgency traffic and compares two routing
tiers on the *same* event-driven pipeline:

  * fifo  : every request goes to one queue lane (un-tuned routing). Urgent
            events wait behind the whole backlog.
  * tuned : urgent events (EXCEPTION / DELIVERED) are routed to a high-priority
            lane that workers drain first.

It reports the end-to-end response time (ingest -> durably processed) for the
*urgent* traffic in each mode and the improvement from tuned routing. This is the
"improved end-to-end response times ... via tuned request routing" claim.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sqlite3
import statistics
import subprocess
import time

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INGEST_DIR = os.path.join(ROOT, "ingest-service")
WORKER_JAR = os.path.join(ROOT, "tracking-worker", "target", "tracking-worker.jar")
DB_PATH = os.path.join(ROOT, "data", "logistics.db")
BASE_URL = "http://127.0.0.1:8080"

URGENT_TYPE = "EXCEPTION"      # routed to the high lane in tuned mode
NORMAL_TYPE = "IN_TRANSIT"     # routed to the normal lane


def env_for(mode: str, downstream_ms: int, threads: int) -> dict:
    env = dict(os.environ)
    env.update(
        DB_PATH=DB_PATH, REDIS_URL="redis://localhost:6379/0",
        REDIS_HOST="localhost", REDIS_PORT="6379",
        STREAM_KEY="logistics.events", DLQ_KEY="logistics.events.dlq",
        INGEST_MODE="optimized", ROUTING_MODE=mode,
        DOWNSTREAM_MS=str(downstream_ms), TRANSIENT_FAIL_RATE="0.0",
        WORKER_THREADS=str(threads), SLA_MS="750",
    )
    return env


def start_ingest(env: dict) -> subprocess.Popen:
    cmd = [os.path.join(ROOT, ".venv", "bin", "uvicorn"), "app.main:app",
           "--host", "127.0.0.1", "--port", "8080", "--loop", "uvloop", "--log-level", "warning"]
    return subprocess.Popen(cmd, cwd=INGEST_DIR, env=env)


def start_worker(env: dict) -> subprocess.Popen:
    return subprocess.Popen(["java", "-jar", WORKER_JAR], cwd=ROOT, env=env)


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


async def wait_healthy(timeout_s: float = 30.0) -> None:
    async with httpx.AsyncClient() as client:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                if (await client.get(f"{BASE_URL}/healthz", timeout=2.0)).status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.3)
    raise RuntimeError("ingest did not become healthy")


async def seed_shipments(n: int) -> list[str]:
    ids: list[str] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for _ in range(n):
            r = await client.post(f"{BASE_URL}/shipments", json={
                "origin": "NYC", "destination": "Boston", "carrier": "ACME"})
            ids.append(r.json()["shipment_id"])
    return ids


async def burst(shipment_ids: list[str], total: int, high_frac: float) -> None:
    """Fire `total` events as fast as possible (peak load) to build a backlog.

    Urgent events are spread uniformly through the arrival stream so that, under
    FIFO routing, they end up stuck at all depths of the backlog.
    """
    sem = asyncio.Semaphore(200)
    limits = httpx.Limits(max_connections=256, max_keepalive_connections=256)
    every = max(1, int(1 / high_frac))

    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        async def one(i: int) -> None:
            etype = URGENT_TYPE if (i % every == 0) else NORMAL_TYPE
            sid = shipment_ids[i % len(shipment_ids)]
            async with sem:
                try:
                    await client.post(f"{BASE_URL}/shipments/{sid}/events",
                                      json={"event_type": etype, "location": "Hub"})
                except Exception:
                    pass

        await asyncio.gather(*[one(i) for i in range(total)])


def processed_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM tracking_events WHERE outcome='OK'").fetchone()[0]
    finally:
        conn.close()


async def wait_drain(total: int) -> None:
    last, stable = -1, 0
    for _ in range(2400):  # up to ~240s
        done = processed_count()
        if done >= total:
            return
        if done == last:
            stable += 1
            if stable > 100:
                return
        else:
            stable, last = 0, done
        await asyncio.sleep(0.1)


def latency_by_type(event_type: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT processed_at_ms - ingested_at_ms FROM tracking_events "
            "WHERE event_type=? AND outcome='OK'", (event_type,)).fetchall()
    finally:
        conn.close()
    lat = [float(r[0]) for r in rows]
    if not lat:
        return {"count": 0, "mean_ms": 0, "p95_ms": 0}
    s = sorted(lat)
    return {
        "count": len(lat),
        "mean_ms": round(statistics.mean(lat), 1),
        "p95_ms": round(s[int(len(s) * 0.95)], 1),
    }


async def run_phase(mode: str, args) -> dict:
    env = env_for(mode, args.downstream_ms, args.worker_threads)
    ingest = worker = None
    try:
        ingest = start_ingest(env)
        await wait_healthy()
        async with httpx.AsyncClient(timeout=10.0) as c:
            await c.post(f"{BASE_URL}/admin/reset")
        worker = start_worker(env)
        await asyncio.sleep(2.0)
        ids = await seed_shipments(args.shipments)
        await burst(ids, args.events, args.high_frac)
        await wait_drain(args.events)
        return {"urgent": latency_by_type(URGENT_TYPE), "normal": latency_by_type(NORMAL_TYPE)}
    finally:
        stop(worker)
        stop(ingest)
        await asyncio.sleep(1.0)


async def main_async(args) -> None:
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
    print(f"=== FIFO routing (single lane), backlog={args.events} events, "
          f"workers={args.worker_threads} ===")
    fifo = await run_phase("fifo", args)
    print(f"  urgent end-to-end: mean={fifo['urgent']['mean_ms']}ms p95={fifo['urgent']['p95_ms']}ms "
          f"(n={fifo['urgent']['count']})")

    print(f"=== TUNED routing (high-priority lane) ===")
    tuned = await run_phase("tuned", args)
    print(f"  urgent end-to-end: mean={tuned['urgent']['mean_ms']}ms p95={tuned['urgent']['p95_ms']}ms "
          f"(n={tuned['urgent']['count']})")

    f_mean = fifo["urgent"]["mean_ms"]
    t_mean = tuned["urgent"]["mean_ms"]
    f_p95 = fifo["urgent"]["p95_ms"]
    t_p95 = tuned["urgent"]["p95_ms"]
    impr_mean = round((f_mean - t_mean) / f_mean * 100, 1) if f_mean else 0
    impr_p95 = round((f_p95 - t_p95) / f_p95 * 100, 1) if f_p95 else 0

    report = {
        "config": {"events": args.events, "high_frac": args.high_frac,
                   "worker_threads": args.worker_threads, "downstream_ms": args.downstream_ms,
                   "shipments": args.shipments},
        "fifo": fifo, "tuned": tuned,
        "urgent_response_time_improvement_mean_pct": impr_mean,
        "urgent_response_time_improvement_p95_pct": impr_p95,
    }
    print("\n================ ROUTING RESULTS ================")
    print(f"urgent-traffic end-to-end response time:")
    print(f"  fifo  routing: mean={f_mean}ms  p95={f_p95}ms")
    print(f"  tuned routing: mean={t_mean}ms  p95={t_p95}ms")
    print(f"  -> improvement from tuned request routing: mean {impr_mean}%  p95 {impr_p95}%")
    out = os.path.join(ROOT, "data", "metric1_routing.json")
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"wrote {os.path.relpath(out, os.getcwd())}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=4000)
    ap.add_argument("--high-frac", type=float, default=0.1)
    ap.add_argument("--worker-threads", type=int, default=4)
    ap.add_argument("--downstream-ms", type=int, default=20)
    ap.add_argument("--shipments", type=int, default=200)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
