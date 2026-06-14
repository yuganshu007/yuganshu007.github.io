from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.analytics_dashboard.app.degradation import (
    DegradationDetector,
    time_to_detect,
)
from services.analytics_dashboard.app.gold import build_gold
from services.analytics_dashboard.app.query_engine import QueryEngine


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("analytics_data")
    landing = d / "landing" / "tenant=salesforce" / "dt=2026-01-01"
    landing.mkdir(parents=True)
    recs = []
    for i in range(300):
        recs.append(
            {
                "call_id": f"c{i}",
                "tenant": "salesforce",
                "dt": "2026-01-01",
                "language": "en" if i % 2 else "es",
                "duration_sec": 100 + i,
                "num_turns": 5,
                "expected_sentiment": "negative" if i % 4 == 0 else "neutral",
            }
        )
    (landing / "part-000.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
    return str(d)


def test_build_gold_and_query(data_dir):
    gold = build_gold(data_dir)
    assert Path(gold).exists()
    engine = QueryEngine(data_dir=data_dir, backend="duckdb")
    res = engine.sql(f"SELECT sum(n_calls) c FROM read_parquet('{gold}')")
    assert res.rows[0]["c"] == 300


def test_gold_matches_raw_aggregate(data_dir):
    gold = build_gold(data_dir)
    engine = QueryEngine(data_dir=data_dir, backend="duckdb")
    raw = engine.sql(
        f"SELECT count(*) c FROM read_json_auto('{engine.landing_glob}', "
        f"format='newline_delimited')"
    ).rows[0]["c"]
    agg = engine.sql(f"SELECT sum(n_calls) c FROM read_parquet('{gold}')").rows[0]["c"]
    assert raw == agg == 300


def test_degradation_detects_drop():
    detector = DegradationDetector(baseline_window=5, drop_threshold_pct=20)
    series = [100, 100, 100, 100, 100, 70]
    alert = detector.check("m", series)
    assert alert is not None
    assert alert.pct_change == pytest.approx(-30.0)


def test_degradation_ignores_noise():
    detector = DegradationDetector(baseline_window=5, drop_threshold_pct=20)
    assert detector.check("m", [100, 98, 101, 99, 100, 97]) is None


def test_time_to_detect_index():
    detector = DegradationDetector(baseline_window=5, drop_threshold_pct=20)
    series = [100] * 6 + [95, 70]  # crosses on the last point
    assert time_to_detect(series, detector, "m") == len(series) - 1
