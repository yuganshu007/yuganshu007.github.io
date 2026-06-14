"""Fallback execution: return a degraded result instead of failing hard."""
from __future__ import annotations

from typing import Any, Callable

from platform_common.logging import get_logger

log = get_logger("resilience.fallback")


def with_fallback(
    primary: Callable[..., Any],
    fallback: Callable[..., Any],
    exceptions: tuple[type[BaseException], ...] = (Exception,),
):
    """Run `primary`; on failure, log and run `fallback` with the same args."""

    def runner(*args, **kwargs):
        try:
            return primary(*args, **kwargs)
        except exceptions as exc:
            log.warning("fallback_triggered", error=repr(exc), primary=getattr(primary, "__name__", str(primary)))
            return fallback(*args, **kwargs)

    return runner
