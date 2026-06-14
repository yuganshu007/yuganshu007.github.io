"""Tests for Bullet 2: Bedrock chatbot with JSON-schema validation."""

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

VALID_RESPONSE = json.dumps({
    "key_topics":           ["roas_optimization", "budget_management"],
    "customer_pain_points": ["below_target_roas"],
    "suggested_actions":    ["enable_auto_bidding"],
    "sentiment":            "neutral",
    "urgency":              "high",
    "pricing_mentioned":    True,
    "competitor_mentioned": False,
})

INVALID_RESPONSE = '{"key_topics": [], "sentiment": "INVALID_ENUM"}'

SAMPLE_TRANSCRIPT = {
    "conversation_id": "conv_00001",
    "duration_seconds": 1200,
    "participants": [{"role": "customer"}, {"role": "amazon_rep"}],
    "transcript": "Our ROAS has been declining. Cost per click is too high. I wish we could improve our bidding.",
}


class TestSchemaValidation:
    def test_parse_valid_response(self):
        insight = parse_llm_response(VALID_RESPONSE)
        assert insight is not None
        assert isinstance(insight, TranscriptInsight)

    def test_parse_returns_correct_sentiment(self):
        insight = parse_llm_response(VALID_RESPONSE)
        assert insight.sentiment.value == "neutral"

    def test_parse_returns_correct_urgency(self):
        insight = parse_llm_response(VALID_RESPONSE)
        assert insight.urgency.value == "high"

    def test_parse_invalid_enum_returns_none(self):
        insight = parse_llm_response(INVALID_RESPONSE)
        assert insight is None

    def test_parse_empty_string_returns_none(self):
        assert parse_llm_response("") is None

    def test_parse_strips_markdown_fences(self):
        fenced = f"```json\n{VALID_RESPONSE}\n```"
        insight = parse_llm_response(fenced)
        assert insight is not None

    def test_parse_extracts_json_from_preamble(self):
        with_preamble = f"Here is the analysis: {VALID_RESPONSE}"
        insight = parse_llm_response(with_preamble)
        assert insight is not None

    def test_build_retry_prompt_contains_previous_response(self):
        prompt = build_retry_prompt("original", "bad response", "invalid JSON")
        assert "bad response" in prompt
        assert "invalid JSON" in prompt
        assert "original" in prompt

    def test_key_topics_not_empty_required(self):
        invalid = json.dumps({
            "key_topics":           [],  # min_length=1 violated
            "customer_pain_points": [],
            "suggested_actions":    [],
            "sentiment":            "positive",
            "urgency":              "low",
        })
        assert parse_llm_response(invalid) is None


class TestBedrockClient:
    def test_mock_client_returns_valid_json(self):
        client   = BedrockClient()  # uses mock when boto3 unavailable
        response = client.invoke("Analyze this transcript about ROAS")
        data     = json.loads(response)
        assert "key_topics" in data
        assert "sentiment"  in data

    def test_mock_response_contains_topic(self):
        client   = BedrockClient()
        response = client.invoke("Our ROAS is declining")
        data     = json.loads(response)
        assert len(data["key_topics"]) > 0

    def test_model_id_is_haiku(self):
        client = BedrockClient()
        assert "haiku" in client.model_id.lower()


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
        transcripts = [SAMPLE_TRANSCRIPT.copy() for _ in range(50)]
        batch_result = process_batch(transcripts)
        assert batch_result.data_quality_rate >= 0.99

    def test_batch_p95_latency_under_sla(self):
        """p95 should be well under 2s in mock mode (no network latency)."""
        transcripts = [SAMPLE_TRANSCRIPT.copy() for _ in range(100)]
        batch_result = process_batch(transcripts)
        assert batch_result.p95_latency_seconds < 2.0
