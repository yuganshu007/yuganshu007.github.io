"""Shared helpers for benchmark scripts."""

from __future__ import annotations

import os
import statistics
import sys
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass(frozen=True)
class LatencySummary:
    samples: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float

    def __str__(self) -> str:
        return (
            f"n={self.samples} p50={self.p50_ms:.2f}ms "
            f"p95={self.p95_ms:.2f}ms p99={self.p99_ms:.2f}ms "
            f"mean={self.mean_ms:.2f}ms"
        )


def measure(fn: Callable[[], object], *, iterations: int) -> LatencySummary:
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    samples.sort()
    return LatencySummary(
        samples=len(samples),
        p50_ms=statistics.median(samples),
        p95_ms=samples[max(0, int(len(samples) * 0.95) - 1)],
        p99_ms=samples[max(0, int(len(samples) * 0.99) - 1)],
        mean_ms=statistics.fmean(samples),
    )


def pct_reduction(before: float, after: float) -> float:
    if before <= 0:
        return 0.0
    return (before - after) / before * 100.0


def banner(title: str) -> None:
    bar = "=" * len(title)
    print(bar)
    print(title)
    print(bar)


def assert_pass(condition: bool, message: str) -> int:
    if condition:
        print(f"PASS — {message}")
        return 0
    print(f"FAIL — {message}", file=sys.stderr)
    return 1


def quick_mode() -> bool:
    return bool(os.environ.get("RYNOVA_QUICK"))


@contextmanager
def timed(label: str):
    start = time.perf_counter()
    yield
    elapsed = (time.perf_counter() - start) * 1000.0
    print(f"{label}: {elapsed:.2f}ms")


def chunked(iterable: Iterable, size: int):
    batch: list = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch
