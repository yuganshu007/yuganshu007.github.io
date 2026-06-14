"""
JSON-schema validation for Bedrock outputs.

Mirrors the Pydantic-based output structuring pattern used in
aws-samples/customer-service-transcript-analysis and the Java parseLLMResponse()
method in VOCBatchProcessingJob.

Every Bedrock response is validated against a strict Pydantic schema before
being stored.  Invalid responses trigger the ADDITIONAL_PROMPT_FOR_RETRY path
(mirroring BedRockUtils.ADDITIONAL_PROMPT_FOR_RETRY in Java).
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SentimentEnum(str, Enum):
    positive = "positive"
    neutral  = "neutral"
    negative = "negative"


class UrgencyEnum(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class TranscriptInsight(BaseModel):
    """
    Schema for a single call transcript analysis.
    Validated against every Claude 3.5 Haiku response.
    Validation failure → retry with ADDITIONAL_PROMPT_FOR_RETRY.
    """
    key_topics:           List[str]      = Field(..., min_length=1, max_length=10)
    customer_pain_points: List[str]      = Field(default_factory=list)
    suggested_actions:    List[str]      = Field(default_factory=list)
    sentiment:            SentimentEnum
    urgency:              UrgencyEnum
    pricing_mentioned:    bool           = False
    competitor_mentioned: bool           = False

    @field_validator("key_topics", "customer_pain_points", "suggested_actions", mode="before")
    @classmethod
    def coerce_to_list(cls, v):
        if isinstance(v, str):
            return [v]
        return v


class BatchInsightSummary(BaseModel):
    """Aggregated summary across all calls in a daily batch."""
    total_calls:          int
    processed_calls:      int
    failed_calls:         int
    data_quality_rate:    float = Field(..., ge=0.0, le=1.0)
    positive_sentiment_pct: float
    high_urgency_pct:     float
    top_topics:           List[str]
    top_pain_points:      List[str]
    avg_processing_seconds: float
    p95_latency_seconds:  float


# ---------------------------------------------------------------------------
# Response parsing — mirrors VOCBatchProcessingJob.parseLLMResponse()
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def parse_llm_response(raw: str) -> Optional[TranscriptInsight]:
    """
    Extract and validate JSON from a raw LLM response.
    Mirrors BedRockUtils JSON_PATTERN and parseLLMResponse() in Java.

    Returns None if parsing or validation fails (caller should retry).
    """
    # Strip markdown fences if present
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned).rstrip("`").strip()

    # Try full response first
    try:
        data = json.loads(cleaned)
        return TranscriptInsight(**data)
    except Exception:
        pass

    # Fall back to first JSON object in response (matches Java JSON_PATTERN)
    match = _JSON_RE.search(cleaned)
    if match:
        try:
            data = json.loads(match.group())
            return TranscriptInsight(**data)
        except Exception:
            pass

    return None


def build_retry_prompt(original_prompt: str, previous_response: str, invalid_reason: str) -> str:
    """
    Mirror of BedRockUtils.ADDITIONAL_PROMPT_FOR_RETRY template.
    Injects the previous invalid response and reason so the model self-corrects.
    """
    retry_header = (
        f"Your previous response <previous_response>{previous_response}</previous_response> "
        f"was deemed invalid due to <invalid_reason>{invalid_reason}</invalid_reason>. "
        "Please re-evaluate carefully and provide an updated response that fully aligns "
        "with the given instructions and requirements. "
    )
    return retry_header + original_prompt
