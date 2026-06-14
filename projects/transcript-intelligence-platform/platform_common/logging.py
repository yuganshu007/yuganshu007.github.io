"""Structured JSON logging used across all services.

Production readiness signal: every service emits machine-parseable structured logs with a
consistent schema (timestamp, level, event, service, plus arbitrary key/value context), which
is what downstream log aggregation (CloudWatch Logs Insights) keys off.
"""
from __future__ import annotations

import logging
import os
import sys

import structlog

_CONFIGURED = False


def configure_logging(level: str | None = None) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    _CONFIGURED = True


def get_logger(service: str, **initial_context):
    configure_logging()
    return structlog.get_logger().bind(service=service, **initial_context)
