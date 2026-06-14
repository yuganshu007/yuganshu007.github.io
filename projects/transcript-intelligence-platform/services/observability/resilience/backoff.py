"""Exponential backoff with jitter, as a decorator and a callable runner."""
from __future__ import annotations

import functools
import random
import time
from typing import Callable, Iterable, Type


def compute_delay(attempt: int, base: float, factor: float, cap: float, jitter: bool) -> float:
    raw = min(cap, base * (factor ** attempt))
    if jitter:
        return random.uniform(0, raw)  # full jitter
    return raw


def retry(
    max_attempts: int = 3,
    base: float = 0.1,
    factor: float = 2.0,
    cap: float = 5.0,
    jitter: bool = True,
    retry_on: Iterable[Type[BaseException]] = (Exception,),
    sleep: Callable[[float], None] = time.sleep,
):
    """Retry `fn` up to `max_attempts` with exponential backoff + full jitter."""
    retry_on = tuple(retry_on)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except retry_on as exc:  # noqa: PERF203
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        break
                    sleep(compute_delay(attempt, base, factor, cap, jitter))
            raise last_exc

        return wrapper

    return decorator
