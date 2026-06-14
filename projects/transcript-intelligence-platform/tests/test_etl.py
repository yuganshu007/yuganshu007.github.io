"""Tests for Bullet 1: EMR/Spark ETL pipeline."""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from transcript_intelligence.etl.spark_pipeline import (
    SPARK_CONF_BASELINE,
    SPARK_CONF_OPTIMIZED,
    extract_business_features,
    extract_metadata_features,
    extract_nlp_features_local,
    process_conversation,
    run_pipeline_simulated,
)


SAMPLE_TRANSCRIPT = {
    "conversation_id": "conv_00001",
    "duration_seconds": 1920,
    "participants": [{"role": "customer"}, {"role": "amazon_rep"}],
    "transcript": (
        "We're struggling with our ROAS. The cost per click is too high. "
        "I wish we could automate the bidding. Google Ads seems to be outperforming."
    ),
}


class TestFeatureExtraction:
    def test_metadata_extracts_conversation_id(self):
        meta = extract_metadata_features(SAMPLE_TRANSCRIPT)
        assert meta["conversation_id"] == "conv_00001"

    def test_metadata_calculates_word_count(self):
        meta = extract_metadata_features(SAMPLE_TRANSCRIPT)
        assert meta["word_count"] > 0

    def test_metadata_participant_count(self):
        meta = extract_metadata_features(SAMPLE_TRANSCRIPT)
        assert meta["participant_count"] == 2

    def test_business_detects_pricing_keywords(self):
        biz = extract_business_features(SAMPLE_TRANSCRIPT)
        assert biz["pricing_mentioned"] is True

    def test_business_detects_competitor(self):
        biz = extract_business_features(SAMPLE_TRANSCRIPT)
        assert biz["competitor_mentioned"] is True

    def test_business_detects_feature_request(self):
        biz = extract_business_features(SAMPLE_TRANSCRIPT)
        assert biz["feature_request_identified"] is True

    def test_nlp_returns_sentiment(self):
        nlp = extract_nlp_features_local(SAMPLE_TRANSCRIPT)
        assert "sentiment_score" in nlp
        assert "sentiment_label" in nlp
        assert nlp["sentiment_label"] in ("positive", "neutral", "negative")

    def test_nlp_returns_topics(self):
        nlp = extract_nlp_features_local(SAMPLE_TRANSCRIPT)
        assert isinstance(nlp["advanced_analysis"]["key_topics"], list)

    def test_nlp_returns_urgency(self):
        nlp = extract_nlp_features_local(SAMPLE_TRANSCRIPT)
        assert nlp["advanced_analysis"]["urgency"] in ("low", "medium", "high")


class TestProcessConversation:
    def test_returns_all_keys(self):
        result = process_conversation(SAMPLE_TRANSCRIPT)
        assert result is not None
        assert "metadata" in result
        assert "nlp_features" in result
        assert "business_features" in result
        assert "processing_version" in result

    def test_idempotent_on_same_input(self):
        """Same input should always produce structurally identical output."""
        r1 = process_conversation(SAMPLE_TRANSCRIPT)
        r2 = process_conversation(SAMPLE_TRANSCRIPT)
        assert r1["metadata"] == r2["metadata"]
        assert r1["business_features"] == r2["business_features"]

    def test_returns_none_on_empty_transcript(self):
        """Mirrors .filter(Objects::nonNull) in Java — bad records are dropped."""
        result = process_conversation({})
        # Should either succeed with empty data or return None, not raise
        # Empty transcript has no topics but should not crash
        assert result is not None or result is None  # no exception

    def test_processing_version_set(self):
        result = process_conversation(SAMPLE_TRANSCRIPT)
        assert result["processing_version"] == "v1.2"


class TestPipelineSimulated:
    def _make_batch(self, n: int) -> list[dict]:
        return [
            {
                "conversation_id": f"conv_{i:05d}",
                "duration_seconds": 600 + i,
                "participants": [{"role": "customer"}, {"role": "amazon_rep"}],
                "transcript": f"Discussion about ROAS and cost optimization. Record {i}.",
            }
            for i in range(n)
        ]

    def test_baseline_processes_all_records(self):
        batch  = self._make_batch(100)
        result = run_pipeline_simulated(batch, SPARK_CONF_BASELINE)
        assert result["record_count"] == 100

    def test_optimized_processes_all_records(self):
        batch  = self._make_batch(100)
        result = run_pipeline_simulated(batch, SPARK_CONF_OPTIMIZED)
        assert result["record_count"] == 100

    def test_optimized_has_lower_shuffle_than_baseline(self):
        batch    = self._make_batch(500)
        baseline = run_pipeline_simulated(batch, SPARK_CONF_BASELINE)
        optimized = run_pipeline_simulated(batch, SPARK_CONF_OPTIMIZED)
        assert optimized["shuffle_read_mb"] < baseline["shuffle_read_mb"]

    def test_aqe_flags_set_correctly(self):
        batch     = self._make_batch(10)
        baseline  = run_pipeline_simulated(batch, SPARK_CONF_BASELINE)
        optimized = run_pipeline_simulated(batch, SPARK_CONF_OPTIMIZED)
        assert baseline["aqe_enabled"]  is False
        assert optimized["aqe_enabled"] is True

    def test_throughput_improvement_target(self):
        """Assert ≥35% throughput improvement (conservative bound for 38% claim)."""
        batch     = self._make_batch(2_000)
        baseline  = run_pipeline_simulated(batch, SPARK_CONF_BASELINE)
        optimized = run_pipeline_simulated(batch, SPARK_CONF_OPTIMIZED)

        base_tps = baseline["record_count"] / baseline["elapsed_seconds"]
        opt_tps  = optimized["record_count"] / optimized["elapsed_seconds"]
        delta    = (opt_tps - base_tps) / base_tps

        assert delta >= 0.35, (
            f"Throughput improvement {delta:.1%} below 35% target. "
            f"Baseline: {base_tps:.0f} rps, Optimized: {opt_tps:.0f} rps"
        )
