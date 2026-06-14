"""
JSON-schema validation for Bedrock outputs.

All 10 insight categories extracted by VOAJob from Gong.io transcripts,
as specified in the Amazon SD Curie Irène VOA Analytics Platform (May–Aug 2025).

Category reference (from PDF §AI/ML Integration):
  1.  Identification Metrics  — amazon_rep, ASIN mentions, campaign names
  2.  Campaign Structure      — SP/SB/SD type, targeting method
  3.  Campaign Scale          — scale issues, targeting limitations
  4.  Budget & Bidding        — strategy, utilization, seasonal adjustments
  5.  Call Analysis           — sentiment, topics, urgency classification
  6.  Seasonal Context        — peak season timing, seasonal pressure
  7.  Action Items            — commitment tracking, optimization recs
  8.  Complaint Analysis      — pain point categorization, severity
  9.  Feature Adaptability    — knowledge gaps, learning progression
  10. Performance Metrics Sentiment — dual-perspective ROAS/CPC sentiment

Validation failure → retry via ADDITIONAL_PROMPT_FOR_RETRY (mirrors BedRockUtils.java).
95% extraction accuracy achieved in production (PDF §AI/ML Integration).
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared enumerations
# ---------------------------------------------------------------------------

class SentimentEnum(str, Enum):
    positive = "positive"
    neutral  = "neutral"
    negative = "negative"


class UrgencyEnum(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


class SeverityEnum(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"
    critical = "critical"


class CampaignTypeEnum(str, Enum):
    sponsored_products = "Sponsored Products"
    sponsored_brands   = "Sponsored Brands"
    sponsored_display  = "Sponsored Display"
    unknown            = "unknown"


# ---------------------------------------------------------------------------
# Category 1 — Identification Metrics
# ---------------------------------------------------------------------------

class IdentificationMetrics(BaseModel):
    amazon_rep_name:    Optional[str]       = None
    asin_mentions:      List[str]           = Field(default_factory=list)
    campaign_names:     List[str]           = Field(default_factory=list)
    advertiser_id:      Optional[str]       = None
    marketplace_id:     Optional[str]       = None


# ---------------------------------------------------------------------------
# Category 2 — Campaign Structure
# ---------------------------------------------------------------------------

class CampaignStructure(BaseModel):
    primary_campaign_type: CampaignTypeEnum     = CampaignTypeEnum.unknown
    secondary_types:        List[str]           = Field(default_factory=list)
    targeting_methods:      List[str]           = Field(default_factory=list)  # keyword, product, audience
    campaign_count:         int                 = 0


# ---------------------------------------------------------------------------
# Category 3 — Campaign Scale
# ---------------------------------------------------------------------------

class CampaignScale(BaseModel):
    scale_issues_identified:     bool       = False
    targeting_limitations:       List[str]  = Field(default_factory=list)
    reach_concerns:              bool       = False
    impression_share_mentioned:  bool       = False


# ---------------------------------------------------------------------------
# Category 4 — Budget & Bidding
# ---------------------------------------------------------------------------

class BudgetBidding(BaseModel):
    bidding_strategy_discussed:   bool            = False
    budget_utilization_concern:   bool            = False
    seasonal_adjustment_needed:   bool            = False
    auto_bidding_requested:       bool            = False
    cpc_concern:                  bool            = False
    budget_exhaustion:            bool            = False


# ---------------------------------------------------------------------------
# Category 5 — Call Analysis (core — required fields)
# ---------------------------------------------------------------------------

class CallAnalysis(BaseModel):
    overall_sentiment:    SentimentEnum     = SentimentEnum.neutral
    urgency:              UrgencyEnum       = UrgencyEnum.low
    primary_topics:       List[str]         = Field(..., min_length=1)
    secondary_topics:     List[str]         = Field(default_factory=list)
    call_resolution:      bool              = False
    follow_up_required:   bool              = False

    @field_validator("primary_topics", mode="before")
    @classmethod
    def coerce_to_list(cls, v):
        return [v] if isinstance(v, str) else v


# ---------------------------------------------------------------------------
# Category 6 — Seasonal Context
# ---------------------------------------------------------------------------

class SeasonalContext(BaseModel):
    peak_season_discussed:    bool       = False
    seasonal_pressure:        bool       = False
    q4_mentioned:             bool       = False
    prime_day_mentioned:      bool       = False


# ---------------------------------------------------------------------------
# Category 7 — Action Items
# ---------------------------------------------------------------------------

class ActionItems(BaseModel):
    immediate_actions:        List[str]  = Field(default_factory=list)
    optimization_recs:        List[str]  = Field(default_factory=list)
    commitments_made:         List[str]  = Field(default_factory=list)
    follow_up_date_mentioned: bool       = False


# ---------------------------------------------------------------------------
# Category 8 — Complaint Analysis
# ---------------------------------------------------------------------------

class ComplaintAnalysis(BaseModel):
    complaint_keywords:       List[str]      = Field(default_factory=list)
    severity:                 SeverityEnum   = SeverityEnum.low
    competitor_mentioned:     bool           = False
    competitor_names:         List[str]      = Field(default_factory=list)
    pricing_complaint:        bool           = False
    feature_gap_complaint:    bool           = False


# ---------------------------------------------------------------------------
# Category 9 — Feature Adaptability
# ---------------------------------------------------------------------------

class FeatureAdaptability(BaseModel):
    knowledge_gaps_identified:  List[str]  = Field(default_factory=list)
    feature_requests:           List[str]  = Field(default_factory=list)
    learning_opportunity:       bool       = False
    onboarding_issue:           bool       = False


# ---------------------------------------------------------------------------
# Category 10 — Performance Metrics Sentiment
# ---------------------------------------------------------------------------

class PerformanceMetricsSentiment(BaseModel):
    roas_sentiment:           SentimentEnum   = SentimentEnum.neutral
    cpc_sentiment:            SentimentEnum   = SentimentEnum.neutral
    targeting_effectiveness:  SentimentEnum   = SentimentEnum.neutral
    roas_value_mentioned:     Optional[float] = None
    cpc_value_mentioned:      Optional[float] = None
    amazon_rep_sentiment:     SentimentEnum   = SentimentEnum.neutral
    advertiser_sentiment:     SentimentEnum   = SentimentEnum.neutral


# ---------------------------------------------------------------------------
# Full TranscriptInsight — all 10 categories
# ---------------------------------------------------------------------------

class TranscriptInsight(BaseModel):
    """
    Complete structured output for one Gong.io call transcript.
    Validated against every Claude 3.5 Haiku response (95% extraction accuracy
    in production per VOA Platform PDF §AI/ML Integration).

    Minimal required set for fast extraction:
      - call_analysis.primary_topics (category 5)
      - call_analysis.overall_sentiment
      - complaint_analysis.severity
      - performance_metrics_sentiment.roas_sentiment

    All other categories default to safe empty values on partial extraction.
    """

    # Category 1
    identification_metrics:       IdentificationMetrics         = Field(default_factory=IdentificationMetrics)
    # Category 2
    campaign_structure:           CampaignStructure             = Field(default_factory=CampaignStructure)
    # Category 3
    campaign_scale:               CampaignScale                 = Field(default_factory=CampaignScale)
    # Category 4
    budget_bidding:               BudgetBidding                 = Field(default_factory=BudgetBidding)
    # Category 5 — required
    call_analysis:                CallAnalysis
    # Category 6
    seasonal_context:             SeasonalContext               = Field(default_factory=SeasonalContext)
    # Category 7
    action_items:                 ActionItems                   = Field(default_factory=ActionItems)
    # Category 8
    complaint_analysis:           ComplaintAnalysis             = Field(default_factory=ComplaintAnalysis)
    # Category 9
    feature_adaptability:         FeatureAdaptability           = Field(default_factory=FeatureAdaptability)
    # Category 10
    performance_metrics_sentiment: PerformanceMetricsSentiment  = Field(default_factory=PerformanceMetricsSentiment)

    # Convenience aliases used by existing code
    @property
    def key_topics(self) -> List[str]:
        return self.call_analysis.primary_topics

    @property
    def sentiment(self) -> SentimentEnum:
        return self.call_analysis.overall_sentiment

    @property
    def urgency(self) -> UrgencyEnum:
        return self.call_analysis.urgency

    @property
    def pricing_mentioned(self) -> bool:
        return self.budget_bidding.cpc_concern or self.complaint_analysis.pricing_complaint

    @property
    def competitor_mentioned(self) -> bool:
        return self.complaint_analysis.competitor_mentioned


class BatchInsightSummary(BaseModel):
    """Aggregated summary across all calls in a daily batch."""
    total_calls:              int
    processed_calls:          int
    failed_calls:             int
    data_quality_rate:        float   = Field(..., ge=0.0, le=1.0)
    positive_sentiment_pct:   float
    high_urgency_pct:         float
    top_topics:               List[str]
    top_complaints:           List[str]
    avg_processing_seconds:   float
    p95_latency_seconds:      float
    negative_sentiment_pct:   float   = 0.0   # used by CloudWatch alarm (Story 3)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _coerce_call_analysis(data: dict) -> dict:
    """
    Build a CallAnalysis-compatible dict from a raw LLM response that may
    use the old flat schema (key_topics, sentiment, urgency) or the new
    nested schema.
    """
    if "call_analysis" in data:
        return data

    # Flat schema compatibility (old format / mock responses)
    ca = {
        "overall_sentiment": data.get("sentiment", "neutral"),
        "urgency":           data.get("urgency", "low"),
        "primary_topics":    data.get("key_topics", data.get("primary_topics", ["general"])),
        "call_resolution":   data.get("call_resolution", False),
        "follow_up_required": data.get("follow_up_required", False),
    }
    out = dict(data)
    out["call_analysis"] = ca
    return out


def parse_llm_response(raw: str) -> Optional[TranscriptInsight]:
    """
    Extract and validate JSON from a raw LLM response against TranscriptInsight.
    Mirrors VOCBatchProcessingJob.parseLLMResponse() and BedRockUtils.JSON_PATTERN.
    Returns None if parsing or validation fails (caller triggers retry).
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned).rstrip("`").strip()

    for attempt in [cleaned, None]:
        try:
            text = attempt or (_JSON_RE.search(cleaned) or type('', (), {'group': lambda s: ''})()).group()
            if not text:
                break
            data = json.loads(text if attempt else _JSON_RE.search(cleaned).group())
            data = _coerce_call_analysis(data)
            return TranscriptInsight(**data)
        except Exception:
            if attempt is None:
                break

    return None


def build_retry_prompt(original_prompt: str, previous_response: str, invalid_reason: str) -> str:
    """
    Mirror of BedRockUtils.ADDITIONAL_PROMPT_FOR_RETRY — injects previous
    invalid response and validation reason for self-healing retry.
    """
    return (
        f"Your previous response <previous_response>{previous_response}</previous_response> "
        f"was deemed invalid due to <invalid_reason>{invalid_reason}</invalid_reason>. "
        "Please re-evaluate carefully and provide an updated response that fully aligns "
        "with the given instructions and requirements. "
        + original_prompt
    )
