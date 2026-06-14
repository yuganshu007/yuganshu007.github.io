"""Tests for Bullet 2: Bedrock chatbot with 10-category JSON-schema validation."""

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
    TranscriptInsight,
    build_retry_prompt,
    parse_llm_response,
)
from transcript_intelligence.chatbot.agent import TranscriptAgent, process_batch

# Minimal valid response (nested schema — all 10 categories)
VALID_NESTED_RESPONSE = json.dumps({
    "call_analysis": {
        "overall_sentiment":  "neutral",
        "urgency":            "high",
        "primary_topics":     ["roas_optimization", "budget_management"],
        "secondary_topics":   [],
        "call_resolution":    False,
        "follow_up_required": True,
    },
    "complaint_analysis": {
        "complaint_keywords":  ["below_target_roas"],
        "severity":            "medium",
        "competitor_mentioned": False,
        "pricing_complaint":   True,
    },
    "performance_metrics_sentiment": {
        "roas_sentiment":         "neutral",
        "cpc_sentiment":          "negative",
        "targeting_effectiveness": "neutral",
        "amazon_rep_sentiment":   "positive",
        "advertiser_sentiment":   "neutral",
    },
})

# Old flat response (backward compatible)
VALID_FLAT_RESPONSE = json.dumps({
    "key_topics":           ["roas_optimization", "budget_management"],
    "customer_pain_points": ["below_target_roas"],
    "suggested_actions":    ["enable_auto_bidding"],
    "sentiment":            "neutral",
    "urgency":              "high",
    "pricing_mentioned":    True,
    "competitor_mentioned": False,
})

INVALID_RESPONSE = '{"call_analysis": {"overall_sentiment": "INVALID_ENUM", "primary_topics": []}}'

SAMPLE_TRANSCRIPT = {
    "conversation_id": "conv_00001",
    "duration_seconds": 1200,
    "participants": [{"role": "customer"}, {"role": "amazon_rep"}],
    "transcript": "Our ROAS has been declining. Cost per click is too high. I wish we could improve our bidding.",
}


class TestSchemaValidation:
    def test_parse_nested_response(self):
        insight = parse_llm_response(VALID_NESTED_RESPONSE)
        assert insight is not None
        assert isinstance(insight, TranscriptInsight)

    def test_parse_flat_response_backward_compat(self):
        """Old flat-schema responses still parse via _coerce_call_analysis."""
        insight = parse_llm_response(VALID_FLAT_RESPONSE)
        assert insight is not None

    def test_nested_sentiment_correct(self):
        insight = parse_llm_response(VALID_NESTED_RESPONSE)
        assert insight.call_analysis.overall_sentiment.value == "neutral"

    def test_nested_urgency_correct(self):
        insight = parse_llm_response(VALID_NESTED_RESPONSE)
        assert insight.call_analysis.urgency.value == "high"

    def test_convenience_property_key_topics(self):
        insight = parse_llm_response(VALID_NESTED_RESPONSE)
        assert "roas_optimization" in insight.key_topics

    def test_convenience_property_sentiment(self):
        insight = parse_llm_response(VALID_NESTED_RESPONSE)
        assert insight.sentiment.value == "neutral"

    def test_convenience_property_pricing_mentioned(self):
        insight = parse_llm_response(VALID_NESTED_RESPONSE)
        assert insight.pricing_mentioned is True

    def test_parse_invalid_enum_returns_none(self):
        insight = parse_llm_response(INVALID_RESPONSE)
        assert insight is None

    def test_parse_empty_string_returns_none(self):
        assert parse_llm_response("") is None

    def test_parse_strips_markdown_fences(self):
        fenced = f"```json\n{VALID_NESTED_RESPONSE}\n```"
        insight = parse_llm_response(fenced)
        assert insight is not None

    def test_parse_extracts_json_from_preamble(self):
        with_preamble = f"Here is the analysis: {VALID_FLAT_RESPONSE}"
        insight = parse_llm_response(with_preamble)
        assert insight is not None

    def test_build_retry_prompt_contains_previous_response(self):
        prompt = build_retry_prompt("original", "bad response", "invalid JSON")
        assert "bad response" in prompt
        assert "invalid JSON" in prompt
        assert "original" in prompt

    def test_all_10_categories_in_full_mock_response(self):
        """Mock Bedrock response includes all 10 insight categories."""
        client   = BedrockClient()
        raw      = client.invoke("ROAS is declining and CPC is too high. Suggest auto bidding.")
        data     = json.loads(raw)
        assert "call_analysis"                 in data
        assert "complaint_analysis"            in data
        assert "performance_metrics_sentiment" in data
        assert "identification_metrics"        in data
        assert "campaign_structure"            in data
        assert "budget_bidding"                in data
        assert "action_items"                  in data


class TestBedrockClient:
    def test_mock_client_returns_valid_json(self):
        client   = BedrockClient()
        response = client.invoke("Analyze this transcript about ROAS")
        data     = json.loads(response)
        assert "call_analysis" in data

    def test_mock_response_parses_to_schema(self):
        client   = BedrockClient()
        response = client.invoke("Our ROAS declining, CPC too high")
        insight  = parse_llm_response(response)
        assert insight is not None
        assert len(insight.key_topics) > 0

    def test_model_id_is_haiku(self):
        client = BedrockClient()
        assert "haiku" in client.model_id.lower()

    def test_performance_config_latency_optimized(self):
        client = BedrockClient()
        assert client.performance_config.get("latency") == "optimized"


class TestTranscriptAgent:
    def test_agent_processes_transcript_successfully(self):
        agent  = TranscriptAgent()
        result = agent.run(SAMPLE_TRANSCRIPT)
        assert result.success is True
        assert result.insight is not None

    def test_agent_returns_valid_insight(self):
        agent  = TranscriptAgent()
        result = agent.run(SAMPLE_TRANSCRIPT)
        assert isinstance(result.insight, TranscriptInsight)

    def test_agent_insight_has_call_analysis(self):
        agent  = TranscriptAgent()
        result = agent.run(SAMPLE_TRANSCRIPT)
        assert result.insight.call_analysis is not None
        assert len(result.insight.call_analysis.primary_topics) > 0

    def test_agent_insight_has_complaint_analysis(self):
        agent  = TranscriptAgent()
        result = agent.run(SAMPLE_TRANSCRIPT)
        assert result.insight.complaint_analysis is not None

    def test_agent_insight_has_performance_metrics(self):
        agent  = TranscriptAgent()
        result = agent.run(SAMPLE_TRANSCRIPT)
        pm = result.insight.performance_metrics_sentiment
        assert pm.roas_sentiment is not None
        assert pm.cpc_sentiment  is not None

    def test_agent_latency_measured(self):
        agent  = TranscriptAgent()
        result = agent.run(SAMPLE_TRANSCRIPT)
        assert result.latency_seconds >= 0.0

    def test_agent_attempt_count_starts_at_1(self):
        agent  = TranscriptAgent()
        result = agent.run(SAMPLE_TRANSCRIPT)
        assert result.attempts >= 1

    def test_batch_processing_quality_rate(self):
        """Batch of 50 calls should achieve >99% quality in mock mode."""
        transcripts  = [SAMPLE_TRANSCRIPT.copy() for _ in range(50)]
        batch_result = process_batch(transcripts)
        assert batch_result.data_quality_rate >= 0.99

    def test_batch_p95_latency_under_sla(self):
        """p95 should be well under 2s in mock mode."""
        transcripts  = [SAMPLE_TRANSCRIPT.copy() for _ in range(100)]
        batch_result = process_batch(transcripts)
        assert batch_result.p95_latency_seconds < 2.0
