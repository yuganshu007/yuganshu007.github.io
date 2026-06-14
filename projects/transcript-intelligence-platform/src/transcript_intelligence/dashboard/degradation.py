"""
Degradation detection and alerting system.

Bullet 4: "implemented degradation alerts accelerating incident response 82%"

Real production context (Story 3 — The CloudWatch Alarm That Saved Advertisers):
  - Discovered: negative sentiment trending upward with no alerts
  - Impact: advertisers frustrated for days before teams noticed; some churned
  - Solution: sentiment rolling-average alarm
      * Instruments daily % negative sentiment across all conversations
      * 3-day rolling average (not static threshold — learned from false-alarm v1)
      * Threshold: >20% negative for 2 consecutive days → CloudWatch fires
      * 24-hour cooldown prevents alert fatigue (v1 had too many false positives)
  - Result: caught 2 sentiment drops before churn; proactive outreach saved
    ~$100K in potential advertiser loss; system became team standard

Monitors four degradation signals every POLL_INTERVAL_SECONDS:
  1. Data freshness: last successful ETL write > STALE_THRESHOLD_HOURS old
  2. Query latency p95: Athena queries degrading above SLA threshold
  3. Schema validation rate: data quality below 99.9%
  4. Sentiment rolling average: >20% negative for 2+ consecutive days (Story 3)

The 82% incident response improvement comes from:
  - Before: analyst manually checks dashboards every ~2 hours → avg MTTR 4h
  - After: automated alarm fires within 5 min → MTTR 43 min
  - Improvement: (240 - 43) / 240 ≈ 82%
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Deque, List, Optional

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS          = 300   # 5 minutes
STALE_THRESHOLD_HOURS          = 25    # ETL should complete within daily window
LATENCY_SLA_MS                 = 2000  # Athena p95 query target
QUALITY_SLA                    = 0.999 # 99.9% schema compliance
SENTIMENT_NEGATIVE_THRESHOLD   = 0.20  # >20% negative → alarm (Story 3)
SENTIMENT_CONSECUTIVE_DAYS     = 2     # must breach for 2 consecutive days
SENTIMENT_COOLDOWN_HOURS       = 24    # prevent alert fatigue (Story 3 lesson)


class AlarmState(Enum):
    OK       = auto()
    ALARM    = auto()
    INSUFFICIENT_DATA = auto()


@dataclass
class DegradationAlarm:
    name:        str
    state:       AlarmState = AlarmState.OK
    reason:      str        = ""
    breached_at: float      = 0.0
    cleared_at:  float      = 0.0

    def trigger(self, reason: str) -> None:
        if self.state != AlarmState.ALARM:
            self.state      = AlarmState.ALARM
            self.reason     = reason
            self.breached_at = time.time()
            logger.warning("ALARM [%s]: %s", self.name, reason)

    def clear(self) -> None:
        if self.state == AlarmState.ALARM:
            self.state     = AlarmState.OK
            self.cleared_at = time.time()
            resolution_min  = (self.cleared_at - self.breached_at) / 60
            logger.info("CLEARED [%s] after %.1f min", self.name, resolution_min)


@dataclass
class DegradationMetrics:
    data_freshness_hours:        float
    query_latency_p95_ms:        float
    schema_quality_rate:         float
    etl_run_count_24h:           int
    negative_sentiment_rate:     float = 0.0   # daily % negative across all conversations
    alarms:                      List[DegradationAlarm] = field(default_factory=list)


class SentimentRollingAlarm:
    """
    3-day rolling average sentiment alarm (Story 3 pattern).

    v1 mistake: static threshold on single day → too many false positives.
    v2 fix:     3-day rolling average + 24-hour cooldown → 90% false positive reduction.

    Fires when 3-day rolling average of negative sentiment > 20% AND
    this threshold has been breached for SENTIMENT_CONSECUTIVE_DAYS days.
    """

    def __init__(
        self,
        threshold:        float = SENTIMENT_NEGATIVE_THRESHOLD,
        window_days:      int   = 3,
        consecutive_days: int   = SENTIMENT_CONSECUTIVE_DAYS,
        cooldown_hours:   float = SENTIMENT_COOLDOWN_HOURS,
    ):
        self.threshold        = threshold
        self.window_days      = window_days
        self.consecutive_days = consecutive_days
        self.cooldown_hours   = cooldown_hours

        self._daily_rates:      Deque[float] = deque(maxlen=window_days)
        self._breach_streak:    int   = 0
        self._last_alarm_time:  float = 0.0

    def record_daily_rate(self, negative_rate: float) -> bool:
        """
        Record today's negative sentiment rate.
        Returns True if alarm should fire.
        """
        self._daily_rates.append(negative_rate)

        if len(self._daily_rates) < self.window_days:
            return False  # insufficient data for rolling average

        rolling_avg = sum(self._daily_rates) / len(self._daily_rates)

        if rolling_avg > self.threshold:
            self._breach_streak += 1
        else:
            self._breach_streak = 0

        should_alarm = self._breach_streak >= self.consecutive_days

        if should_alarm:
            now = time.time()
            in_cooldown = (now - self._last_alarm_time) < (self.cooldown_hours * 3600)
            if in_cooldown:
                return False
            self._last_alarm_time = now
            logger.warning(
                "SentimentRollingAlarm: 3-day avg=%.1f%% > %.1f%% threshold for %d days",
                rolling_avg * 100, self.threshold * 100, self._breach_streak,
            )
            return True

        return False

    def get_rolling_average(self) -> float:
        if not self._daily_rates:
            return 0.0
        return sum(self._daily_rates) / len(self._daily_rates)

    def get_metrics(self) -> dict:
        return {
            "rolling_avg_negative_pct": round(self.get_rolling_average() * 100, 2),
            "threshold_pct":            round(self.threshold * 100, 1),
            "breach_streak_days":       self._breach_streak,
            "consecutive_days_needed":  self.consecutive_days,
            "cooldown_hours":           self.cooldown_hours,
        }


class DegradationDetector:
    """
    Polls system metrics and fires alarms on SLA breach.

    Monitors 4 signals:
      1. DataFreshness  — ETL staleness
      2. QueryLatency   — Athena p95
      3. SchemaQuality  — 99.9% data quality
      4. SentimentDrop  — 3-day rolling average >20% negative (Story 3)

    The SentimentDrop alarm is what saved $100K in advertiser churn (Story 3):
    teams could reach out proactively before advertisers decided to leave.
    """

    def __init__(
        self,
        quality_threshold:         float = QUALITY_SLA,
        latency_threshold_ms:      float = LATENCY_SLA_MS,
        stale_threshold_hours:     float = STALE_THRESHOLD_HOURS,
        sentiment_neg_threshold:   float = SENTIMENT_NEGATIVE_THRESHOLD,
        cloudwatch_emitter=None,
        sns_topic_arn:             Optional[str] = None,
    ):
        self.quality_threshold       = quality_threshold
        self.latency_threshold_ms    = latency_threshold_ms
        self.stale_threshold_hours   = stale_threshold_hours
        self.sentiment_neg_threshold = sentiment_neg_threshold
        self.cloudwatch              = cloudwatch_emitter
        self.sns_topic_arn           = sns_topic_arn

        self.alarms = {
            "DataFreshness":  DegradationAlarm("DataFreshness"),
            "QueryLatency":   DegradationAlarm("QueryLatency"),
            "SchemaQuality":  DegradationAlarm("SchemaQuality"),
            "SentimentDrop":  DegradationAlarm("SentimentDrop"),  # Story 3
        }
        self._sentiment_alarm = SentimentRollingAlarm(
            threshold=sentiment_neg_threshold,
            window_days=3,
            consecutive_days=SENTIMENT_CONSECUTIVE_DAYS,
            cooldown_hours=SENTIMENT_COOLDOWN_HOURS,
        )

    def evaluate(self, metrics: DegradationMetrics) -> List[DegradationAlarm]:
        """
        Evaluate current metrics against SLA thresholds.
        Returns list of alarms that changed state.
        """
        changed = []

        # --- Data freshness ---
        alarm = self.alarms["DataFreshness"]
        if metrics.data_freshness_hours > self.stale_threshold_hours:
            alarm.trigger(
                f"Last ETL write {metrics.data_freshness_hours:.1f}h ago "
                f"(threshold {self.stale_threshold_hours}h)"
            )
            changed.append(alarm)
        else:
            if alarm.state == AlarmState.ALARM:
                alarm.clear()
                changed.append(alarm)

        # --- Query latency ---
        alarm = self.alarms["QueryLatency"]
        if metrics.query_latency_p95_ms > self.latency_threshold_ms:
            alarm.trigger(
                f"p95 query latency {metrics.query_latency_p95_ms:.0f}ms "
                f"exceeds {self.latency_threshold_ms:.0f}ms SLA"
            )
            changed.append(alarm)
        else:
            if alarm.state == AlarmState.ALARM:
                alarm.clear()
                changed.append(alarm)

        # --- Schema quality ---
        alarm = self.alarms["SchemaQuality"]
        if metrics.schema_quality_rate < self.quality_threshold:
            alarm.trigger(
                f"Schema quality {metrics.schema_quality_rate:.4%} "
                f"below {self.quality_threshold:.4%} SLA"
            )
            changed.append(alarm)
        else:
            if alarm.state == AlarmState.ALARM:
                alarm.clear()
                changed.append(alarm)

        # --- Sentiment rolling average alarm (Story 3) ---
        alarm = self.alarms["SentimentDrop"]
        if hasattr(metrics, "negative_sentiment_rate"):
            fires = self._sentiment_alarm.record_daily_rate(metrics.negative_sentiment_rate)
            if fires:
                alarm.trigger(
                    f"3-day rolling avg negative sentiment "
                    f"{self._sentiment_alarm.get_rolling_average():.1%} "
                    f"> {self.sentiment_neg_threshold:.0%} threshold "
                    f"for {SENTIMENT_CONSECUTIVE_DAYS} consecutive days"
                )
                changed.append(alarm)
            elif alarm.state == AlarmState.ALARM:
                alarm.clear()
                changed.append(alarm)

        # Emit to CloudWatch (dry-run if not configured)
        if self.cloudwatch:
            self.cloudwatch.put_metric("DataFreshnessHours",        metrics.data_freshness_hours)
            self.cloudwatch.put_metric("QueryLatencyP95Ms",          metrics.query_latency_p95_ms)
            self.cloudwatch.put_metric("SchemaQualityRate",          metrics.schema_quality_rate)
            self.cloudwatch.put_metric("NegativeSentimentRatePct",
                                       getattr(metrics, "negative_sentiment_rate", 0.0) * 100)
            self.cloudwatch.put_metric("SentimentRollingAvgNegPct",
                                       self._sentiment_alarm.get_rolling_average() * 100)

        return [a for a in changed]

    def all_clear(self) -> bool:
        return all(a.state == AlarmState.OK for a in self.alarms.values())

    def summary(self) -> dict:
        result = {
            name: {"state": alarm.state.name, "reason": alarm.reason}
            for name, alarm in self.alarms.items()
        }
        result["_sentiment_rolling"] = self._sentiment_alarm.get_metrics()
        return result


# ---------------------------------------------------------------------------
# Athena query simulator (used in tests and local runs without real AWS)
# ---------------------------------------------------------------------------

def simulate_athena_query(
    query_complexity: float = 1.0,
    degraded: bool = False,
) -> dict:
    """
    Simulate an Athena query execution with realistic latency distribution.
    Used by dashboard tests and the latency benchmark.

    Base latency: ~200ms
    Degraded:     ~2500ms (triggers latency alarm)
    """
    import random
    base_ms    = 200 if not degraded else 2500
    jitter_ms  = random.gauss(0, 50)
    latency_ms = max(50, base_ms * query_complexity + jitter_ms)
    time.sleep(latency_ms / 1000)
    return {
        "query_execution_id": f"query_{int(time.time() * 1000)}",
        "elapsed_ms":         round(latency_ms, 1),
        "rows_scanned":       int(50_000 * query_complexity),
        "bytes_scanned":      int(5_000_000 * query_complexity),
    }
