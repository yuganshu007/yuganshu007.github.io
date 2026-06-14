from __future__ import annotations

from services.observability.cloudwatch.emitter import CloudWatchEmitter
from services.observability.data_quality.quality_checks import check_record, evaluate

GOOD = {
    "call_id": "c1",
    "transcript_text": "agent: hello\nadvertiser: hi",
    "duration_sec": 120,
    "language": "en",
    "num_turns": 4,
}


def test_good_record_passes():
    assert check_record(GOOD) == []


def test_each_defect_detected():
    assert "empty_transcript" in check_record({**GOOD, "transcript_text": ""})
    assert "invalid_duration" in check_record({**GOOD, "duration_sec": -1})
    assert "unsupported_language" in check_record({**GOOD, "language": "xx"})
    assert "no_turns" in check_record({**GOOD, "num_turns": 0})
    assert "missing_call_id" in check_record({**GOOD, "call_id": ""})


def test_evaluate_pass_rate():
    records = [GOOD] * 999 + [{**GOOD, "language": "xx"}]
    report = evaluate(records)
    assert report.total == 1000
    assert report.failed == 1
    assert report.pass_rate == 0.999
    assert report.violations["unsupported_language"] == 1


def test_cloudwatch_mock_buffers_metrics():
    emitter = CloudWatchEmitter(namespace="Test")
    emitter.put_metric("PassRatePercent", 99.95, unit="Percent")
    assert emitter.buffered[0]["name"] == "PassRatePercent"
    assert emitter.buffered[0]["value"] == 99.95
