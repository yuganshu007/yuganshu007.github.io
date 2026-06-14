"""Tests for Bullet 2: Bedrock chatbot — MetricCategory schema + 10 categories."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from transcript_intelligence.chatbot.bedrock_client import (
    CLAUDE_HAIKU_MODEL,
    BedrockClient,
)
from transcript_intelligence.chatbot.schemas import (
    MetricCategory,
    TranscriptInsight,
    build_retry_prompt,
    parse_llm_response,
)
from transcript_intelligence.chatbot.agent import TranscriptAgent, process_batch

# Minimal valid nested response using camelCase MetricCategory keys
VALID_CAMELCASE_RESPONSE = json.dumps({
    "callAnalysis": {
        "primaryTopics":        ["Performance Metrics", "Budget Optimization"],
        "primaryTopicSentiment": "neutral",
        "secondaryTopics":      ["Targeting Issues"],
        "resolutionType":       "partial",
        "overallSentiment":     "neutral",
        "customerExperience":   "intermediate",
        "urgencyLevel":         "high",
        "currentIssue":         "below_target_roas",
        "pastIssue":            None,
        "pastIssueStatus":      None,
        "resolutionSummary":    "Discussed bid optimization",
    },
    "complaintAnalysis": {
        "complaintKeywords":  ["below_target_roas"],
        "complaintPhrases":   [],
        "programMentioned":   None,
        "complaintSeverity":  "medium",
        "scaleRelatedComplaints": [],
        "programSpecificComplaints": {"SD": [], "SP": [], "SB": []},
    },
    "performanceMetricsSentiment": {
        "roasSentiment":    "negative",
        "cpcSentiment":     "neutral",
        "advertiserPerception": "neutral",
    },
})

VALID_FLAT_RESPONSE = json.dumps({
    "key_topics":           ["Performance Metrics", "Budget Optimization"],
    "sentiment":            "neutral",
    "urgency":              "high",
    "pricing_mentioned":    True,
    "competitor_mentioned": False,
})

INVALID_RESPONSE = '{"callAnalysis": {"overallSentiment": "INVALID_ENUM", "primaryTopics": []}}'

SAMPLE_TRANSCRIPT = {
    "conversation_id": "conv_00001",
    "duration_seconds": 1200,
    "participants": [{"role": "customer"}, {"role": "amazon_rep"}],
    "transcript": "Our ROAS has been declining. Cost per click is too high. I wish we could improve our bidding.",
}


class TestMetricCategoryEnum:
    """MetricCategory enum must mirror the Java enum exactly."""

    def test_all_10_categories_present(self):
        keys = [m.json_key for m in MetricCategory]
        assert "identificationMetrics"      in keys
        assert "campaignStructure"          in keys
        assert "campaignScale"              in keys
        assert "budgetAndBidding"           in keys
        assert "callAnalysis"               in keys
        assert "seasonalContext"            in keys
        assert "actionItems"                in keys
        assert "complaintAnalysis"          in keys
        assert "featureAdaptability"        in keys
        assert "performanceMetricsSentiment" in keys

    def test_each_category_has_instructions(self):
        for cat in MetricCategory:
            assert len(cat.instructions) > 50, f"{cat.name} instructions too short"

    def test_each_category_has_schema(self):
        for cat in MetricCategory:
            assert cat.schema.startswith("{"), f"{cat.name} schema must be JSON"

    def test_call_analysis_prompt_mentions_urgency_levels(self):
        ca = MetricCategory.CALL_ANALYSIS
        assert "seasonal_pressure" in ca.schema

    def test_performance_metrics_mentions_vcpm(self):
        pm = MetricCategory.PERFORMANCE_METRICS_SENTIMENT
        assert "vcpmSentiment" in pm.schema

    def test_complaint_analysis_mentions_sd_sp_sb(self):
        ca = MetricCategory.COMPLAINT_ANALYSIS
        assert '"SD"' in ca.schema
        assert '"SP"' in ca.schema
        assert '"SB"' in ca.schema


class TestSchemaValidation:
    def test_parse_camelcase_response(self):
        insight = parse_llm_response(VALID_CAMELCASE_RESPONSE)
        assert insight is not None
        assert isinstance(insight, TranscriptInsight)

    def test_parse_flat_response_backward_compat(self):
        """Old flat-schema responses still parse via _coerce_call_analysis."""
        insight = parse_llm_response(VALID_FLAT_RESPONSE)
        assert insight is not None

    def test_camelcase_sentiment_correct(self):
        insight = parse_llm_response(VALID_CAMELCASE_RESPONSE)
        assert insight.callAnalysis.overallSentiment.value == "neutral"

    def test_camelcase_urgency_correct(self):
        insight = parse_llm_response(VALID_CAMELCASE_RESPONSE)
        assert insight.callAnalysis.urgencyLevel.value == "high"

    def test_camelcase_primary_topics(self):
        insight = parse_llm_response(VALID_CAMELCASE_RESPONSE)
        assert "Performance Metrics" in insight.callAnalysis.primaryTopics

    def test_key_topics_convenience_property(self):
        insight = parse_llm_response(VALID_CAMELCASE_RESPONSE)
        assert len(insight.key_topics) > 0

    def test_sentiment_convenience_property(self):
        insight = parse_llm_response(VALID_CAMELCASE_RESPONSE)
        assert insight.sentiment.value == "neutral"

    def test_invalid_enum_returns_none(self):
        assert parse_llm_response(INVALID_RESPONSE) is None

    def test_empty_string_returns_none(self):
        assert parse_llm_response("") is None

    def test_strips_markdown_fences(self):
        fenced = f"```json\n{VALID_CAMELCASE_RESPONSE}\n```"
        assert parse_llm_response(fenced) is not None

    def test_extracts_json_from_preamble(self):
        assert parse_llm_response(f"Here is the analysis: {VALID_FLAT_RESPONSE}") is not None

    def test_build_retry_prompt_contains_reason(self):
        p = build_retry_prompt("original", "bad resp", "invalid JSON")
        assert "bad resp" in p and "invalid JSON" in p

    def test_customer_experience_enum_values(self):
        """CustomerExperienceEnum must have beginner/intermediate/experienced/expert."""
        from transcript_intelligence.chatbot.schemas import CustomerExperienceEnum
        vals = {e.value for e in CustomerExperienceEnum}
        assert vals == {"beginner", "intermediate", "experienced", "expert"}

    def test_urgency_includes_seasonal_pressure(self):
        """UrgencyEnum must include seasonal_pressure (new value from MetricCategory)."""
        from transcript_intelligence.chatbot.schemas import UrgencyEnum
        assert "seasonal_pressure" in {e.value for e in UrgencyEnum}

    def test_10_categories_in_mock_bedrock_response(self):
        client = BedrockClient()
        raw    = client.invoke("ROAS declining and CPC too high. Suggest auto bidding.")
        data   = json.loads(raw)
        required_keys = [
            "identificationMetrics", "campaignStructure", "campaignScale",
            "budgetAndBidding", "callAnalysis", "seasonalContext",
            "actionItems", "complaintAnalysis", "featureAdaptability",
            "performanceMetricsSentiment",
        ]
        for k in required_keys:
            assert k in data, f"Missing MetricCategory key: {k}"

    def test_mock_response_uses_camelcase_keys(self):
        client = BedrockClient()
        raw    = client.invoke("Our ROAS is declining")
        data   = json.loads(raw)
        ca     = data.get("callAnalysis", {})
        assert "primaryTopics"    in ca
        assert "overallSentiment" in ca
        assert "urgencyLevel"     in ca


class TestBedrockClient:
    def test_mock_client_returns_valid_json(self):
        client   = BedrockClient()
        response = client.invoke("Analyze this transcript about ROAS")
        assert json.loads(response)  # must be valid JSON

    def test_mock_response_parses_to_schema(self):
        client   = BedrockClient()
        response = client.invoke("Our ROAS declining, CPC too high")
        insight  = parse_llm_response(response)
        assert insight is not None
        assert len(insight.key_topics) > 0

    def test_model_id_is_haiku(self):
        assert "haiku" in BedrockClient().model_id.lower()

    def test_performance_config_latency_optimized(self):
        assert BedrockClient().performance_config.get("latency") == "optimized"


class TestTranscriptAgent:
    def test_agent_processes_transcript_successfully(self):
        result = TranscriptAgent().run(SAMPLE_TRANSCRIPT)
        assert result.success is True

    def test_agent_insight_has_call_analysis(self):
        result = TranscriptAgent().run(SAMPLE_TRANSCRIPT)
        assert result.insight.callAnalysis is not None
        assert len(result.insight.callAnalysis.primaryTopics) > 0

    def test_agent_insight_has_complaint_analysis(self):
        result = TranscriptAgent().run(SAMPLE_TRANSCRIPT)
        assert result.insight.complaintAnalysis is not None

    def test_agent_insight_has_performance_metrics(self):
        result = TranscriptAgent().run(SAMPLE_TRANSCRIPT)
        pm = result.insight.performanceMetricsSentiment
        assert pm is not None

    def test_agent_insight_has_action_items(self):
        result = TranscriptAgent().run(SAMPLE_TRANSCRIPT)
        ai = result.insight.actionItems
        assert isinstance(ai.immediateActions, list)
        assert isinstance(ai.bidOptimizations, list)

    def test_batch_quality_rate_above_99pct(self):
        batch  = [SAMPLE_TRANSCRIPT.copy() for _ in range(50)]
        result = process_batch(batch)
        assert result.data_quality_rate >= 0.99

    def test_batch_p95_latency_under_2s(self):
        batch  = [SAMPLE_TRANSCRIPT.copy() for _ in range(100)]
        result = process_batch(batch)
        assert result.p95_latency_seconds < 2.0
