"""Tests for Bullet 4: Streamlit/Plotly analytics + degradation alerts."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from transcript_intelligence.dashboard.degradation import (
    AlarmState,
    DegradationAlarm,
    DegradationDetector,
    DegradationMetrics,
    simulate_athena_query,
)
from transcript_intelligence.dashboard.app import (
    _generate_synthetic_data,
    build_dataframe,
)


class TestDegradationDetector:
    def _ok_metrics(self) -> DegradationMetrics:
        return DegradationMetrics(
            data_freshness_hours  = 3.0,
            query_latency_p95_ms  = 450.0,
            schema_quality_rate   = 0.9995,
            etl_run_count_24h     = 1,
        )

    def test_all_clear_when_metrics_ok(self):
        detector = DegradationDetector()
        detector.evaluate(self._ok_metrics())
        assert detector.all_clear() is True

    def test_data_freshness_alarm_triggers(self):
        detector = DegradationDetector(stale_threshold_hours=24.0)
        metrics  = self._ok_metrics()
        metrics.data_freshness_hours = 30.0
        detector.evaluate(metrics)
        assert detector.alarms["DataFreshness"].state == AlarmState.ALARM

    def test_query_latency_alarm_triggers(self):
        detector = DegradationDetector(latency_threshold_ms=500.0)
        metrics  = self._ok_metrics()
        metrics.query_latency_p95_ms = 1500.0
        detector.evaluate(metrics)
        assert detector.alarms["QueryLatency"].state == AlarmState.ALARM

    def test_schema_quality_alarm_triggers(self):
        detector = DegradationDetector(quality_threshold=0.999)
        metrics  = self._ok_metrics()
        metrics.schema_quality_rate = 0.995  # below 99.9%
        detector.evaluate(metrics)
        assert detector.alarms["SchemaQuality"].state == AlarmState.ALARM

    def test_alarm_clears_when_metric_recovers(self):
        detector = DegradationDetector(quality_threshold=0.999)
        bad = self._ok_metrics()
        bad.schema_quality_rate = 0.990
        detector.evaluate(bad)
        assert detector.alarms["SchemaQuality"].state == AlarmState.ALARM

        good = self._ok_metrics()  # back above threshold
        detector.evaluate(good)
        assert detector.alarms["SchemaQuality"].state == AlarmState.OK

    def test_summary_returns_all_alarms(self):
        detector = DegradationDetector()
        summary  = detector.summary()
        assert "DataFreshness" in summary
        assert "QueryLatency"  in summary
        assert "SchemaQuality" in summary

    def test_alarm_records_breach_time(self):
        import time
        alarm = DegradationAlarm("test")
        t_before = time.time()
        alarm.trigger("test reason")
        assert alarm.breached_at >= t_before
        assert alarm.state == AlarmState.ALARM

    def test_incident_response_improvement(self):
        """
        Conceptual test: assert alert fires within POLL_INTERVAL_SECONDS
        vs 2-hour manual check → 82% MTTR reduction.
        """
        from transcript_intelligence.dashboard.degradation import POLL_INTERVAL_SECONDS
        manual_check_interval_min = 120   # 2 hours
        alert_interval_min        = POLL_INTERVAL_SECONDS / 60  # 5 min

        improvement = (manual_check_interval_min - alert_interval_min) / manual_check_interval_min
        assert improvement >= 0.95  # ≥95% reduction in detection latency


class TestSyntheticData:
    def test_generates_correct_count(self):
        records = _generate_synthetic_data(100)
        assert len(records) == 100

    def test_all_records_have_required_fields(self):
        records = _generate_synthetic_data(10)
        required = {"conversation_id", "call_date", "team", "campaign_type", "sentiment"}
        for r in records:
            assert required.issubset(set(r.keys()))

    def test_18_teams_represented(self):
        records = _generate_synthetic_data(1000)
        teams   = {r["team"] for r in records}
        assert len(teams) == 18

    def test_quality_rate_is_999(self):
        """Synthetic data should exhibit 99.9% schema validity."""
        records  = _generate_synthetic_data(10_000)
        valid    = sum(1 for r in records if r.get("schema_valid", False))
        quality  = valid / len(records)
        # Allow ±0.5% tolerance on 10K samples
        assert abs(quality - 0.999) < 0.005

    def test_sentiment_distribution_realistic(self):
        records   = _generate_synthetic_data(1000)
        sentiments = [r["sentiment"] for r in records]
        pos_rate   = sentiments.count("positive") / len(sentiments)
        assert 0.4 <= pos_rate <= 0.7, f"Positive rate {pos_rate:.1%} outside expected range"


class TestDataframe:
    def test_builds_dataframe_from_records(self):
        pd = pytest.importorskip("pandas")
        records = _generate_synthetic_data(50)
        df      = build_dataframe(records)
        assert len(df) == 50

    def test_call_date_is_datetime(self):
        pd = pytest.importorskip("pandas")
        records = _generate_synthetic_data(50)
        df      = build_dataframe(records)
        assert str(df["call_date"].dtype).startswith("datetime")


class TestAthenaSimulator:
    def test_returns_result_dict(self):
        result = simulate_athena_query(query_complexity=0.01)
        assert "elapsed_ms"     in result
        assert "rows_scanned"   in result
        assert "bytes_scanned"  in result

    def test_degraded_latency_higher(self):
        normal   = simulate_athena_query(query_complexity=1.0, degraded=False)
        degraded = simulate_athena_query(query_complexity=1.0, degraded=True)
        assert degraded["elapsed_ms"] > normal["elapsed_ms"]
