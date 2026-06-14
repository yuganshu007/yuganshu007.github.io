"""Tests for Bullet 1: EMR/Spark ETL pipeline — GongDataIngestionJob + VOAJob."""

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
    gong_data_ingestion_job,
    process_conversation,
    run_pipeline_simulated,
)


SAMPLE_TRANSCRIPT = {
    "conversation_id": "conv_00001",
    "duration_seconds": 1920,
    "participants": [{"role": "customer"}, {"role": "amazon_rep"}],
    "transcript_segments": [
        {"speaker": "customer", "text": "We're struggling with our ROAS.", "confidence": 0.94},
    ],
    "transcript": (
        "We're struggling with our ROAS. The cost per click is too high. "
        "I wish we could automate the bidding. Google Ads seems to be outperforming."
    ),
}

SAMPLE_METADATA = [
    {
        "conversation_id": "conv_00001",
        "account_name":    "Acme Corp",
        "opportunity_stage": "qualified",
        "marketplace_id":  "US",
        "advertiser_tier": "premium",
        "salesforce_id":   "SF_123456",
    }
]


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

    def test_nlp_returns_call_analysis(self):
        """NLP features now include nested call_analysis matching 10-category schema."""
        nlp = extract_nlp_features_local(SAMPLE_TRANSCRIPT)
        aa  = nlp["advanced_analysis"]
        assert "call_analysis" in aa
        assert "primary_topics" in aa["call_analysis"]

    def test_nlp_returns_complaint_analysis(self):
        nlp = extract_nlp_features_local(SAMPLE_TRANSCRIPT)
        aa  = nlp["advanced_analysis"]
        assert "complaint_analysis" in aa

    def test_nlp_returns_performance_metrics(self):
        nlp = extract_nlp_features_local(SAMPLE_TRANSCRIPT)
        aa  = nlp["advanced_analysis"]
        assert "performance_metrics_sentiment" in aa


class TestGongDataIngestionJob:
    """Tests for the GongDataIngestionJob inner-join pattern."""

    def test_inner_join_enriches_matching_transcript(self):
        result = gong_data_ingestion_job([SAMPLE_TRANSCRIPT], SAMPLE_METADATA)
        assert len(result) == 1
        assert result[0]["account_name"] == "Acme Corp"

    def test_inner_join_drops_unmatched_transcripts(self):
        """Transcripts without matching metadata are dropped (inner join)."""
        unmatched = {**SAMPLE_TRANSCRIPT, "conversation_id": "conv_99999"}
        result    = gong_data_ingestion_job([unmatched], SAMPLE_METADATA)
        assert len(result) == 0

    def test_enrichment_adds_marketplace_id(self):
        result = gong_data_ingestion_job([SAMPLE_TRANSCRIPT], SAMPLE_METADATA)
        assert result[0]["marketplace_id"] == "US"

    def test_enrichment_adds_advertiser_tier(self):
        result = gong_data_ingestion_job([SAMPLE_TRANSCRIPT], SAMPLE_METADATA)
        assert result[0]["advertiser_tier"] == "premium"

    def test_html_entity_decoding(self):
        """HTML entities in transcript text are decoded (Java HTMLEntityDecoder pattern)."""
        html_transcript = {**SAMPLE_TRANSCRIPT, "transcript": "ROAS &gt; 3.0 &amp; CPC &lt; 2.0"}
        result = gong_data_ingestion_job([html_transcript], SAMPLE_METADATA)
        assert "&gt;" not in result[0]["transcript"]
        assert ">" in result[0]["transcript"]

    def test_ingestion_enriched_flag_set(self):
        result = gong_data_ingestion_job([SAMPLE_TRANSCRIPT], SAMPLE_METADATA)
        assert result[0]["ingestion_enriched"] is True

    def test_empty_metadata_drops_all_transcripts(self):
        result = gong_data_ingestion_job([SAMPLE_TRANSCRIPT], [])
        assert len(result) == 0

    def test_multiple_transcripts_join_correctly(self):
        more_transcripts = [
            {**SAMPLE_TRANSCRIPT, "conversation_id": f"conv_{i:05d}"}
            for i in range(5)
        ]
        more_meta = [
            {**SAMPLE_METADATA[0], "conversation_id": f"conv_{i:05d}"}
            for i in range(3)  # only 3 match → inner join drops 2
        ]
        result = gong_data_ingestion_job(more_transcripts, more_meta)
        assert len(result) == 3


class TestProcessConversation:
    def test_returns_all_keys(self):
        result = process_conversation(SAMPLE_TRANSCRIPT)
        assert result is not None
        assert "metadata"          in result
        assert "nlp_features"      in result
        assert "business_features" in result
        assert "processing_version" in result

    def test_idempotent_on_same_input(self):
        """Same input should always produce structurally identical output."""
        r1 = process_conversation(SAMPLE_TRANSCRIPT)
        r2 = process_conversation(SAMPLE_TRANSCRIPT)
        assert r1["metadata"]          == r2["metadata"]
        assert r1["business_features"] == r2["business_features"]

    def test_processing_version_set(self):
        result = process_conversation(SAMPLE_TRANSCRIPT)
        assert result["processing_version"] == "v1.2"

    def test_does_not_raise_on_empty_transcript(self):
        result = process_conversation({})
        assert result is not None or result is None  # no exception


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
        batch     = self._make_batch(500)
        baseline  = run_pipeline_simulated(batch, SPARK_CONF_BASELINE)
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
