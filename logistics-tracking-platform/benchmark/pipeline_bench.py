#!/usr/bin/env python3
"""Metrics 1 & 2 - end-to-end pipeline A/B benchmark.

Runs the same closed workload against two architectures and compares them:

  * baseline  : the ingest API does the downstream call + DB write *inline* in
                the request handler, with no message queue and no retry.
  * optimized : async handlers validate + publish to the Redis Streams queue and
                return immediately; a pool of Java background workers does the
                downstream call, retries transient failures and persists results.

Measured:
  Metric 1 - end-to-end API response time under peak load (improvement %).
  Metric 2 - SLA-breach rate (an event must be durably persisted within SLA_MS).

The downstream cost and transient-failure rate are identical across both modes,
so the only thing being compared is the architecture.
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
import sys
import time
from dataclasses import dataclass, field

import httpx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INGEST_DIR = os.path.join(ROOT, "ingest-service")
WORKER_JAR = os.path.join(ROOT, "tracking-worker", "target", "tracking-worker.jar")
DB_PATH = os.path.join(ROOT, "data", "logistics.db")
VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
BASE_URL = "http://127.0.0.1:8080"

EVENT_TYPES = ("PICKUP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION")


@dataclass
class LoadResult:
    latencies_ms: list[float] = field(default_factory=list)
    statuses: dict[int, int] = field(default_factory=dict)
    sent: int = 0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * pct))]


def base_env(downstream_ms: int, fail_rate: float, sla_ms: int) -> dict:
    env = dict(os.environ)
    env.update(
        DB_PATH=DB_PATH,
        REDIS_URL="redis://localhost:6379/0",
        REDIS_HOST="localhost",
        REDIS_PORT="6379",
        STREAM_KEY="logistics.events",
        DLQ_KEY="logistics.events.dlq",
        DOWNSTREAM_MS=str(downstream_ms),
        TRANSIENT_FAIL_RATE=str(fail_rate),
        SLA_MS=str(sla_ms),
        ROUTING_MODE=os.getenv("ROUTING_MODE", "tuned"),
    )
    return env


def start_ingest(mode: str, env: dict) -> subprocess.Popen:
    env = dict(env)
    env["INGEST_MODE"] = mode
    loop = "uvloop" if mode == "optimized" else "asyncio"
    cmd = [
        os.path.join(ROOT, ".venv", "bin", "uvicorn"), "app.main:app",
        "--host", "127.0.0.1", "--port", "8080", "--loop", loop,
        "--log-level", "warning",
    ]
    return subprocess.Popen(cmd, cwd=INGEST_DIR, env=env)


def start_worker(env: dict, threads: int, max_attempts: int, backoff_ms: int) -> subprocess.Popen:
    env = dict(env)
    env.update(WORKER_THREADS=str(threads), MAX_ATTEMPTS=str(max_attempts),
               BACKOFF_MS=str(backoff_ms))
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
                r = await client.get(f"{BASE_URL}/healthz", timeout=2.0)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.3)
    raise RuntimeError("ingest service did not become healthy")


async def seed_shipments(n: int) -> list[str]:
    ids: list[str] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for i in range(n):
            r = await client.post(f"{BASE_URL}/shipments", json={
                "origin": "NYC", "destination": "Boston", "carrier": "ACME"})
            ids.append(r.json()["shipment_id"])
    return ids


async def run_load(shipment_ids: list[str], rps: int, duration_s: int) -> LoadResult:
    """Open-loop load generator: fire one request every 1/rps seconds."""
    result = LoadResult()
    interval = 1.0 / rps
    total = rps * duration_s
    sem = asyncio.Semaphore(4000)
    limits = httpx.Limits(max_connections=512, max_keepalive_connections=512)

    async with httpx.AsyncClient(timeout=30.0, limits=limits) as client:
        async def one(i: int) -> None:
            sid = shipment_ids[i % len(shipment_ids)]
            etype = EVENT_TYPES[i % len(EVENT_TYPES)]
            async with sem:
                t0 = time.perf_counter()
                try:
                    r = await client.post(
                        f"{BASE_URL}/shipments/{sid}/events",
                        json={"event_type": etype, "location": "Hub-%d" % (i % 7)},
                    )
                    status = r.status_code
                except Exception:
                    status = -1
                result.latencies_ms.append((time.perf_counter() - t0) * 1000.0)
                result.statuses[status] = result.statuses.get(status, 0) + 1

        tasks: list[asyncio.Task] = []
        start = time.perf_counter()
        for i in range(total):
            tasks.append(asyncio.create_task(one(i)))
            target = start + (i + 1) * interval
            now = time.perf_counter()
            if target > now:
                await asyncio.sleep(target - now)
        await asyncio.gather(*tasks)
    result.sent = total
    return result


def _processed_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM tracking_events WHERE outcome IN ('OK','FAILED','INVALID')"
        ).fetchone()[0]
    finally:
        conn.close()


async def drain_queue(total_sent: int, grace_ms: int) -> None:
    """Wait until the worker pool has persisted every event (or progress stalls)."""
    last = -1
    stable = 0
    for _ in range(1200):  # up to ~120s
        done = _processed_count()
        if done >= total_sent:
            break
        if done == last:
            stable += 1
            if stable > 50:  # ~5s with no progress -> assume drained
                break
        else:
            stable = 0
            last = done
        await asyncio.sleep(0.1)
    # Give in-flight retries time to settle before measuring.
    await asyncio.sleep(grace_ms / 1000.0)


def sla_stats(total_sent: int, sla_ms: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        on_time = conn.execute(
            "SELECT COUNT(*) FROM tracking_events WHERE outcome='OK' "
            "AND processed_at_ms - ingested_at_ms <= ?", (sla_ms,)).fetchone()[0]
        ok_total = conn.execute(
            "SELECT COUNT(*) FROM tracking_events WHERE outcome='OK'").fetchone()[0]
        failed = conn.execute(
            "SELECT COUNT(*) FROM tracking_events WHERE outcome IN ('FAILED','INVALID')"
        ).fetchone()[0]
    finally:
        conn.close()
    breaches = total_sent - on_time
    return {
        "total_sent": total_sent,
        "persisted_ok": ok_total,
        "on_time": on_time,
        "failed_or_invalid": failed,
        "breaches": breaches,
        "breach_rate_pct": round(breaches / total_sent * 100, 2) if total_sent else 0.0,
    }


async def reset() -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(f"{BASE_URL}/admin/reset")


def summarize_latency(name: str, lat: list[float]) -> dict:
    return {
        "mode": name,
        "count": len(lat),
        "mean_ms": round(statistics.mean(lat), 3) if lat else 0,
        "median_ms": round(statistics.median(lat), 3) if lat else 0,
        "p95_ms": round(_percentile(lat, 0.95), 3),
        "p99_ms": round(_percentile(lat, 0.99), 3),
    }


async def run_phase(mode: str, args, env: dict) -> dict:
    ingest = None
    worker = None
    try:
        ingest = start_ingest(mode, env)
        await wait_healthy()
        await reset()
        if mode == "optimized":
            worker = start_worker(env, args.worker_threads, args.max_attempts, args.backoff_ms)
            await asyncio.sleep(2.0)  # let the worker create the consumer group
        ids = await seed_shipments(args.shipments)
        load = await run_load(ids, args.rps, args.duration)
        if mode == "optimized":
            grace = (args.max_attempts * args.backoff_ms) + (args.max_attempts * env_int(env, "DOWNSTREAM_MS")) + 1500
            await drain_queue(load.sent, grace)
        else:
            await asyncio.sleep(0.5)
        sla = sla_stats(load.sent, int(env["SLA_MS"]))
        lat = summarize_latency(mode, load.latencies_ms)
        return {"latency": lat, "sla": sla, "statuses": load.statuses}
    finally:
        stop(worker)
        stop(ingest)
        await asyncio.sleep(1.0)


def env_int(env: dict, key: str) -> int:
    return int(env[key])


async def main_async(args) -> None:
    env = base_env(args.downstream_ms, args.fail_rate, args.sla_ms)
    os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)

    print("=== Running BASELINE phase (sync inline, no queue, no retry) ===")
    baseline = await run_phase("baseline", args, env)
    print(f"  response: mean={baseline['latency']['mean_ms']}ms "
          f"p95={baseline['latency']['p95_ms']}ms | breach_rate={baseline['sla']['breach_rate_pct']}%")

    print("=== Running OPTIMIZED phase (async + queue + worker pool + retry) ===")
    optimized = await run_phase("optimized", args, env)
    print(f"  response: mean={optimized['latency']['mean_ms']}ms "
          f"p95={optimized['latency']['p95_ms']}ms | breach_rate={optimized['sla']['breach_rate_pct']}%")

    b_lat = baseline["latency"]["mean_ms"]
    o_lat = optimized["latency"]["mean_ms"]
    b_p95 = baseline["latency"]["p95_ms"]
    o_p95 = optimized["latency"]["p95_ms"]
    b_breach = baseline["sla"]["breach_rate_pct"]
    o_breach = optimized["sla"]["breach_rate_pct"]

    resp_impr_mean = round((b_lat - o_lat) / b_lat * 100, 1) if b_lat else 0
    resp_impr_p95 = round((b_p95 - o_p95) / b_p95 * 100, 1) if b_p95 else 0
    breach_abs = round(b_breach - o_breach, 2)
    breach_rel = round((b_breach - o_breach) / b_breach * 100, 1) if b_breach else 0

    report = {
        "config": {
            "rps": args.rps, "duration_s": args.duration, "shipments": args.shipments,
            "downstream_ms": args.downstream_ms, "transient_fail_rate": args.fail_rate,
            "sla_ms": args.sla_ms, "worker_threads": args.worker_threads,
            "max_attempts": args.max_attempts, "backoff_ms": args.backoff_ms,
        },
        "baseline": baseline,
        "optimized": optimized,
        "metric_1_response_time": {
            "baseline_mean_ms": b_lat, "optimized_mean_ms": o_lat,
            "improvement_mean_pct": resp_impr_mean,
            "baseline_p95_ms": b_p95, "optimized_p95_ms": o_p95,
            "improvement_p95_pct": resp_impr_p95,
        },
        "metric_2_sla_breaches": {
            "baseline_breach_rate_pct": b_breach, "optimized_breach_rate_pct": o_breach,
            "absolute_reduction_pct_points": breach_abs,
            "relative_reduction_pct": breach_rel,
        },
    }

    print("\n================ RESULTS ================")
    print(f"Metric 1 - end-to-end response time under peak load ({args.rps} rps):")
    print(f"  baseline  mean={b_lat:.2f}ms  p95={b_p95:.2f}ms")
    print(f"  optimized mean={o_lat:.2f}ms  p95={o_p95:.2f}ms")
    print(f"  -> mean improvement: {resp_impr_mean}%   p95 improvement: {resp_impr_p95}%")
    print(f"Metric 2 - SLA breach rate (SLA={args.sla_ms}ms):")
    print(f"  baseline  {b_breach}%   optimized {o_breach}%")
    print(f"  -> reduction: {breach_abs} percentage points ({breach_rel}% relative)")

    out = os.path.join(ROOT, "data", "metrics12_pipeline.json")
    with open(out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {os.path.relpath(out, os.getcwd())}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rps", type=int, default=200)
    ap.add_argument("--duration", type=int, default=20)
    ap.add_argument("--shipments", type=int, default=200)
    ap.add_argument("--downstream-ms", type=int, default=20)
    ap.add_argument("--fail-rate", type=float, default=0.20)
    ap.add_argument("--sla-ms", type=int, default=750)
    ap.add_argument("--worker-threads", type=int, default=12)
    ap.add_argument("--max-attempts", type=int, default=5)
    ap.add_argument("--backoff-ms", type=int, default=40)
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
