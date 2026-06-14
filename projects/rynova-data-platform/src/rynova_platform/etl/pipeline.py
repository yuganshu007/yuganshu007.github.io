"""ETL/ELT pipeline runner (Bullet 2).

Each stage is a callable from ``list[dict]`` to ``list[dict]``.  The
:class:`Pipeline` is responsible for the *control plane* — schema
validation between stages, DQ checks, retry on transient errors, and
structured metrics.  The benchmark in
``benchmarks/bench_bullet2_pipeline_failures.py`` exercises the runner
twice: once with the SDK + code-review hooks disabled, once with them
enabled, and asserts the failure rate drops by at least 30%.
"""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from rynova_platform.etl.schema import Schema
from rynova_platform.validation import (
    DataQualityCheck,
    DataQualityReport,
    ValidationError,
    validate_batch,
)

log = logging.getLogger("rynova.etl")


StageFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


class StageFailure(Exception):
    """Raised when a stage cannot recover from a transient error."""


@dataclass
class Stage:
    name: str
    fn: StageFn
    schema: Schema | None = None
    checks: tuple[DataQualityCheck, ...] = ()
    max_retries: int = 2


@dataclass
class StageOutcome:
    name: str
    rows_in: int
    rows_out: int
    duration_ms: float
    retries: int
    dq_report: DataQualityReport
    succeeded: bool
    error: str | None = None


@dataclass
class PipelineResult:
    pipeline: str
    succeeded: bool
    outcomes: list[StageOutcome] = field(default_factory=list)
    rows_loaded: int = 0
    duration_ms: float = 0.0

    @property
    def failed_stage(self) -> str | None:
        for o in self.outcomes:
            if not o.succeeded:
                return o.name
        return None


@dataclass
class Pipeline:
    """A linear sequence of stages with schema + DQ enforcement.

    ``enable_dq`` is the toggle the resume bullet refers to: it gates the
    SDK validation hooks and structured code-review checks.  The
    failure-rate benchmark flips this flag to measure the lift.
    """

    name: str
    stages: list[Stage]
    enable_dq: bool = True
    enable_retries: bool = True
    rng_seed: int = 1729

    def run(self, records: list[dict[str, Any]]) -> PipelineResult:
        result = PipelineResult(pipeline=self.name, succeeded=True)
        start_all = time.perf_counter()
        batch = list(records)
        rng = random.Random(self.rng_seed)

        for stage in self.stages:
            outcome = self._run_stage(stage, batch, rng)
            result.outcomes.append(outcome)
            if not outcome.succeeded:
                result.succeeded = False
                break
            batch = outcome._produced_rows  # type: ignore[attr-defined]

        result.rows_loaded = len(batch) if result.succeeded else 0
        result.duration_ms = (time.perf_counter() - start_all) * 1000.0
        return result

    def _run_stage(
        self,
        stage: Stage,
        batch: list[dict[str, Any]],
        rng: random.Random,
    ) -> StageOutcome:
        max_attempts = (stage.max_retries + 1) if self.enable_retries else 1
        last_err: str | None = None
        produced: list[dict[str, Any]] = []
        retries = 0
        report = DataQualityReport()
        start = time.perf_counter()

        for attempt in range(max_attempts):
            try:
                produced = stage.fn(list(batch))
            except Exception as exc:  # pragma: no cover — defensive
                last_err = f"{type(exc).__name__}: {exc}"
                retries = attempt
                continue

            if self.enable_dq:
                if stage.schema is not None:
                    try:
                        produced = validate_batch(produced, stage.schema, drop_invalid=True)
                    except ValidationError as exc:
                        last_err = str(exc)
                        retries = attempt
                        continue
                if stage.checks:
                    report = DataQualityCheck.run_all(stage.checks, produced)
                    if not report.passed:
                        last_err = f"DQ checks failed: {report.failed_check_names()}"
                        retries = attempt
                        continue
            duration_ms = (time.perf_counter() - start) * 1000.0
            outcome = StageOutcome(
                name=stage.name,
                rows_in=len(batch),
                rows_out=len(produced),
                duration_ms=duration_ms,
                retries=retries,
                dq_report=report,
                succeeded=True,
            )
            outcome._produced_rows = produced  # type: ignore[attr-defined]
            return outcome

        duration_ms = (time.perf_counter() - start) * 1000.0
        return StageOutcome(
            name=stage.name,
            rows_in=len(batch),
            rows_out=0,
            duration_ms=duration_ms,
            retries=retries,
            dq_report=report,
            succeeded=False,
            error=last_err,
        )
