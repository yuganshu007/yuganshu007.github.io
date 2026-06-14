"""Degradation detection + alerting.

Watches a rolling metric series; when the latest window regresses beyond a threshold vs the
recent baseline, it raises an alert (which would page via SNS / CloudWatch in production). This is
what "accelerates incident response": regressions are caught automatically instead of waiting for
someone to notice on a dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.observability.cloudwatch.emitter import CloudWatchEmitter


@dataclass
class Alert:
    metric: str
    baseline: float
    current: float
    pct_change: float
    severity: str


class DegradationDetector:
    def __init__(
        self,
        baseline_window: int = 7,
        drop_threshold_pct: float = 20.0,
        emitter: CloudWatchEmitter | None = None,
    ):
        self.baseline_window = baseline_window
        self.drop_threshold_pct = drop_threshold_pct
        self.emitter = emitter or CloudWatchEmitter(namespace="TranscriptIntelligence/Analytics")

    def check(self, metric: str, series: list[float], higher_is_better: bool = True) -> Alert | None:
        """Compare the latest value against the mean of the preceding `baseline_window` values."""
        if len(series) < 2:
            return None
        current = series[-1]
        history = series[-(self.baseline_window + 1):-1] or series[:-1]
        baseline = sum(history) / len(history)
        if baseline == 0:
            return None
        pct_change = (current - baseline) / baseline * 100.0
        regressed = (pct_change <= -self.drop_threshold_pct) if higher_is_better else (
            pct_change >= self.drop_threshold_pct
        )
        if not regressed:
            return None
        severity = "critical" if abs(pct_change) >= 2 * self.drop_threshold_pct else "warning"
        self.emitter.put_metric("DegradationDetected", 1, unit="Count", metric=metric)
        return Alert(
            metric=metric,
            baseline=round(baseline, 3),
            current=round(current, 3),
            pct_change=round(pct_change, 1),
            severity=severity,
        )


def time_to_detect(series: list[float], detector: DegradationDetector, metric: str) -> int | None:
    """Index of the first point where the detector would have alerted (None if never).

    Used by the benchmark to contrast automated detection vs a manual baseline.
    """
    for i in range(2, len(series) + 1):
        if detector.check(metric, series[:i]) is not None:
            return i - 1
    return None
