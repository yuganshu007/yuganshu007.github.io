"""
JSON-schema validation for Bedrock outputs.

This module mirrors the real production Java enum:
  com.amazon.sd.curie.amber.jobs.voa.analysis.MetricCategory

The MetricCategory enum defines the exact 10 insight categories, their
extraction prompts, and their JSON schemas used by VOAJob in production.
Python field names use camelCase to match the Java enum's JSON keys exactly.

Categories (verbatim from the Java enum):
  1.  identificationMetrics
  2.  campaignStructure
  3.  campaignScale
  4.  budgetAndBidding
  5.  callAnalysis
  6.  seasonalContext
  7.  actionItems
  8.  complaintAnalysis
  9.  featureAdaptability
  10. performanceMetricsSentiment
"""

from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# MetricCategory — Python mirror of the Java enum
# Contains the exact extraction prompts and JSON schemas used in production
# ---------------------------------------------------------------------------

class MetricCategory(Enum):
    """
    Mirror of com.amazon.sd.curie.amber.jobs.voa.analysis.MetricCategory.

    Each member holds: (json_key, extraction_instructions, output_schema)
    These are the EXACT prompts sent to Claude 3.5 Haiku in production.
    """

    IDENTIFICATION_METRICS = (
        "identificationMetrics",
        (
            "IDENTIFICATION METRICS EXTRACTION: Extract Amazon representative name from transcript "
            "introductions, ASINs mentioned, campaign names mentioned, and tenure information "
            "discussed. Only extract values explicitly mentioned in the transcript."
        ),
        '{"identificationMetrics": {"amazonRepName": "string|null", "asinMentioned": ["string"],'
        ' "campaignNames": ["string"], "tenureInformation": "string|null"}}',
    )

    CAMPAIGN_STRUCTURE = (
        "campaignStructure",
        (
            "CAMPAIGN STRUCTURE EXTRACTION: Extract the primary campaign type (Sponsored Products, "
            "Sponsored Brands, or Sponsored Display) and targeting types mentioned (Keyword, Product, "
            "Category, ASIN, Dynamic, Audience, Views Retargeting, Purchase Retargeting). Only extract "
            "campaign types and targeting methods explicitly discussed in the call."
        ),
        '{"campaignStructure": {"primaryCampaignType": '
        '"Sponsored_Products|Sponsored_Brands|Sponsored_Display|null", "targetingTypes": ["string"]}}',
    )

    CAMPAIGN_SCALE = (
        "campaignScale",
        (
            "CAMPAIGN SCALE EXTRACTION: Extract information about campaign scale including impression "
            "volume, reach, frequency, budget utilization, and advertiser perception of scale. Pay "
            "special attention to any mentions of limited scale, scale issues, or targeting restrictions "
            "that might be limiting campaign performance."
        ),
        '{"campaignScale": {"scaleIssuesReported": "boolean", "limitedTargetingMentioned": "boolean",'
        ' "scalePerception": "good|limited|very_limited|null", "targetingRestrictions": ["string"],'
        ' "recommendedScaleImprovements": ["string"]}}',
    )

    BUDGET_AND_BIDDING = (
        "budgetAndBidding",
        (
            "BUDGET AND BIDDING EXTRACTION: Extract daily budget, monthly budget, budget utilization "
            "status, bidding strategy, seasonal strategy, and bid adjustments. For budgets, extract "
            "specific amounts only if explicitly mentioned. For bidding strategy, only classify as "
            "aggressive, conservative, or competitive if explicitly stated."
        ),
        '{"budgetAndBidding": {"dailyBudget": "number|null", "monthlyBudget": "number|null",'
        ' "budgetUtilization": "budget_limited|under_spending|optimal|null", "biddingStrategy":'
        ' "aggressive|conservative|competitive|null", "seasonalStrategy":'
        ' "peak_season|off_season|null", "bidAdjustments": ["string"]}}',
    )

    CALL_ANALYSIS = (
        "callAnalysis",
        (
            "CALL ANALYSIS EXTRACTION: Extract primary topics discussed, primary topic sentiment, "
            "secondary topics, resolution type, overall sentiment, customer experience level, urgency "
            "level, current issues, past issues, past issue status, and resolution summary. For "
            "sentiment, experience levels, and urgency, use null unless explicitly stated."
        ),
        '{"callAnalysis": {"primaryTopics": ["string"], "primaryTopicSentiment":'
        ' "positive|negative|neutral|mixed|null", "secondaryTopics": ["string"], "resolutionType":'
        ' "string|null", "overallSentiment": "positive|neutral|negative|null", "customerExperience":'
        ' "beginner|intermediate|experienced|expert|null", "urgencyLevel":'
        ' "low|medium|high|seasonal_pressure|null", "currentIssue": "string|null", "pastIssue":'
        ' "string|null", "pastIssueStatus": "resolved|not_resolved|null", "resolutionSummary":'
        ' "string|null"}}',
    )

    SEASONAL_CONTEXT = (
        "seasonalContext",
        (
            "SEASONAL CONTEXT EXTRACTION: Extract seasonal pressure (true/false), peak season timing, "
            "and seasonal events mentioned. Only mark seasonal pressure as true if explicitly confirmed. "
            "Extract peak season timing only if specific dates or periods are mentioned."
        ),
        '{"seasonalContext": {"seasonalPressure": "boolean", "peakSeasonTiming": "string|null",'
        ' "seasonalEvents": ["string"]}}',
    )

    ACTION_ITEMS = (
        "actionItems",
        (
            "ACTION ITEMS EXTRACTION: Extract immediate actions, bid optimizations, scale improvement "
            "actions, and next steps agreed upon in the call. Only include actions that were explicitly "
            "agreed upon or committed to during the conversation."
        ),
        '{"actionItems": {"immediateActions": ["string"], "bidOptimizations": ["string"], "nextSteps":'
        ' ["string"], "scaleImprovementActions": ["string"]}}',
    )

    COMPLAINT_ANALYSIS = (
        "complaintAnalysis",
        (
            "COMPLAINT ANALYSIS EXTRACTION: Extract complaint keywords, complaint phrases, program "
            "mentioned in complaints, complaint severity, scale-related complaints, and program-specific "
            "complaints. Look for terms like: 'ads shown too often', 'irrelevant ads', 'poor targeting', "
            "'wasted spend'."
        ),
        '{"complaintAnalysis": {"complaintKeywords": ["string"], "complaintPhrases": ["string"],'
        ' "programMentioned": "string|null", "complaintSeverity": "low|medium|high|null",'
        ' "scaleRelatedComplaints": ["string"], "programSpecificComplaints": {"SD": ["string"],'
        ' "SP": ["string"], "SB": ["string"]}}}',
    )

    FEATURE_ADAPTABILITY = (
        "featureAdaptability",
        (
            "FEATURE ADAPTABILITY EXTRACTION: Extract known features, discussed features, learned "
            "features, feature adaptability level, features advertiser knows, features advertiser talks "
            "about, and features advertiser learned during the call."
        ),
        '{"featureAdaptability": {"knownFeatures": ["string"], "discussedFeatures": ["string"],'
        ' "learnedFeatures": ["string"], "featureAdaptability": "string|null",'
        ' "featuresAdvertisersKnows": ["string"], "featuresAdvertiserTalksAbout": ["string"],'
        ' "featuresAdvertiserLearnt": ["string"]}}',
    )

    PERFORMANCE_METRICS_SENTIMENT = (
        "performanceMetricsSentiment",
        (
            "PERFORMANCE METRICS SENTIMENT EXTRACTION: Extract sentiment for ROAS, CPC, CPM, vCPM, "
            "targeting clauses, and bidding strategies from both Amazon and advertiser perspectives. "
            "Also extract overall advertiser perception of campaign performance."
        ),
        '{"performanceMetricsSentiment": {"roasSentiment": "positive|negative|neutral|null",'
        ' "cpcSentiment": "positive|negative|neutral|null", "cpmSentiment":'
        ' "positive|negative|neutral|null", "vcpmSentiment": "positive|negative|neutral|null",'
        ' "targetingClausesSentiment": "positive|negative|neutral|null", "biddingStrategiesSentiment":'
        ' "positive|negative|neutral|null", "roasSentimentAdvertiser": "positive|negative|neutral|null",'
        ' "cpcSentimentAdvertiser": "positive|negative|neutral|null", "vcpmSentimentAdvertiser":'
        ' "positive|negative|neutral|null", "targetingClausesSentimentAdvertiser":'
        ' "positive|negative|neutral|null", "advertiserPerception": "positive|negative|neutral|null"}}',
    )

    def __init__(self, json_key: str, instructions: str, schema: str):
        self.json_key     = json_key
        self.instructions = instructions
        self.schema       = schema


# ---------------------------------------------------------------------------
# Pydantic models — matching MetricCategory JSON schemas exactly
# ---------------------------------------------------------------------------

class SentimentEnum(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral  = "neutral"
    mixed    = "mixed"


class UrgencyEnum(str, Enum):
    low              = "low"
    medium           = "medium"
    high             = "high"
    seasonal_pressure = "seasonal_pressure"


class CustomerExperienceEnum(str, Enum):
    beginner     = "beginner"
    intermediate = "intermediate"
    experienced  = "experienced"
    expert       = "expert"


class ScalePerceptionEnum(str, Enum):
    good         = "good"
    limited      = "limited"
    very_limited = "very_limited"


class CampaignTypeEnum(str, Enum):
    sponsored_products = "Sponsored_Products"
    sponsored_brands   = "Sponsored_Brands"
    sponsored_display  = "Sponsored_Display"


class BudgetUtilizationEnum(str, Enum):
    budget_limited = "budget_limited"
    under_spending = "under_spending"
    optimal        = "optimal"


class BiddingStrategyEnum(str, Enum):
    aggressive  = "aggressive"
    conservative = "conservative"
    competitive  = "competitive"


class ComplaintSeverityEnum(str, Enum):
    low    = "low"
    medium = "medium"
    high   = "high"


# ---------------------------------------------------------------------------
# Category 1 — identificationMetrics
# ---------------------------------------------------------------------------

class IdentificationMetrics(BaseModel):
    amazonRepName:     Optional[str]   = None
    asinMentioned:     List[str]       = Field(default_factory=list)
    campaignNames:     List[str]       = Field(default_factory=list)
    tenureInformation: Optional[str]   = None


# ---------------------------------------------------------------------------
# Category 2 — campaignStructure
# ---------------------------------------------------------------------------

class CampaignStructure(BaseModel):
    primaryCampaignType: Optional[CampaignTypeEnum] = None
    targetingTypes:      List[str]                  = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Category 3 — campaignScale
# ---------------------------------------------------------------------------

class CampaignScale(BaseModel):
    scaleIssuesReported:          bool                        = False
    limitedTargetingMentioned:    bool                        = False
    scalePerception:              Optional[ScalePerceptionEnum] = None
    targetingRestrictions:        List[str]                   = Field(default_factory=list)
    recommendedScaleImprovements: List[str]                   = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Category 4 — budgetAndBidding
# ---------------------------------------------------------------------------

class BudgetAndBidding(BaseModel):
    dailyBudget:      Optional[float]                  = None
    monthlyBudget:    Optional[float]                  = None
    budgetUtilization: Optional[BudgetUtilizationEnum] = None
    biddingStrategy:  Optional[BiddingStrategyEnum]    = None
    seasonalStrategy: Optional[str]                    = None
    bidAdjustments:   List[str]                        = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Category 5 — callAnalysis (required)
# ---------------------------------------------------------------------------

class CallAnalysis(BaseModel):
    primaryTopics:         List[str]                        = Field(..., min_length=1)
    primaryTopicSentiment: Optional[SentimentEnum]          = None
    secondaryTopics:       List[str]                        = Field(default_factory=list)
    resolutionType:        Optional[str]                    = None
    overallSentiment:      Optional[SentimentEnum]          = SentimentEnum.neutral
    customerExperience:    Optional[CustomerExperienceEnum] = None
    urgencyLevel:          Optional[UrgencyEnum]            = None
    currentIssue:          Optional[str]                    = None
    pastIssue:             Optional[str]                    = None
    pastIssueStatus:       Optional[str]                    = None
    resolutionSummary:     Optional[str]                    = None

    @field_validator("primaryTopics", mode="before")
    @classmethod
    def coerce_to_list(cls, v):
        return [v] if isinstance(v, str) else (v or ["general"])


# ---------------------------------------------------------------------------
# Category 6 — seasonalContext
# ---------------------------------------------------------------------------

class SeasonalContext(BaseModel):
    seasonalPressure: bool       = False
    peakSeasonTiming: Optional[str] = None
    seasonalEvents:   List[str]  = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Category 7 — actionItems
# ---------------------------------------------------------------------------

class ActionItems(BaseModel):
    immediateActions:       List[str] = Field(default_factory=list)
    bidOptimizations:       List[str] = Field(default_factory=list)
    nextSteps:              List[str] = Field(default_factory=list)
    scaleImprovementActions: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Category 8 — complaintAnalysis
# ---------------------------------------------------------------------------

class ProgramSpecificComplaints(BaseModel):
    SD: List[str] = Field(default_factory=list)
    SP: List[str] = Field(default_factory=list)
    SB: List[str] = Field(default_factory=list)


class ComplaintAnalysis(BaseModel):
    complaintKeywords:        List[str]                       = Field(default_factory=list)
    complaintPhrases:         List[str]                       = Field(default_factory=list)
    programMentioned:         Optional[str]                   = None
    complaintSeverity:        Optional[ComplaintSeverityEnum] = None
    scaleRelatedComplaints:   List[str]                       = Field(default_factory=list)
    programSpecificComplaints: ProgramSpecificComplaints      = Field(default_factory=ProgramSpecificComplaints)


# ---------------------------------------------------------------------------
# Category 9 — featureAdaptability
# ---------------------------------------------------------------------------

class FeatureAdaptability(BaseModel):
    knownFeatures:              List[str]      = Field(default_factory=list)
    discussedFeatures:          List[str]      = Field(default_factory=list)
    learnedFeatures:            List[str]      = Field(default_factory=list)
    featureAdaptability:        Optional[str]  = None
    featuresAdvertisersKnows:   List[str]      = Field(default_factory=list)
    featuresAdvertiserTalksAbout: List[str]    = Field(default_factory=list)
    featuresAdvertiserLearnt:   List[str]      = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Category 10 — performanceMetricsSentiment
# ---------------------------------------------------------------------------

class PerformanceMetricsSentiment(BaseModel):
    roasSentiment:                      Optional[SentimentEnum] = None
    cpcSentiment:                       Optional[SentimentEnum] = None
    cpmSentiment:                       Optional[SentimentEnum] = None
    vcpmSentiment:                      Optional[SentimentEnum] = None
    targetingClausesSentiment:          Optional[SentimentEnum] = None
    biddingStrategiesSentiment:         Optional[SentimentEnum] = None
    roasSentimentAdvertiser:            Optional[SentimentEnum] = None
    cpcSentimentAdvertiser:             Optional[SentimentEnum] = None
    vcpmSentimentAdvertiser:            Optional[SentimentEnum] = None
    targetingClausesSentimentAdvertiser: Optional[SentimentEnum] = None
    advertiserPerception:               Optional[SentimentEnum] = None


# ---------------------------------------------------------------------------
# Full TranscriptInsight — all 10 MetricCategory categories
# ---------------------------------------------------------------------------

class TranscriptInsight(BaseModel):
    """
    Complete structured output for one Gong.io call transcript.
    Field names match the Java MetricCategory enum JSON keys exactly.
    Achieves 95% extraction accuracy in production (VOA Platform PDF).

    The only required field is callAnalysis.primaryTopics — all others
    default to safe empty values to handle partial LLM responses gracefully.
    """

    identificationMetrics:      IdentificationMetrics      = Field(default_factory=IdentificationMetrics)
    campaignStructure:          CampaignStructure           = Field(default_factory=CampaignStructure)
    campaignScale:              CampaignScale               = Field(default_factory=CampaignScale)
    budgetAndBidding:           BudgetAndBidding            = Field(default_factory=BudgetAndBidding)
    callAnalysis:               CallAnalysis                # REQUIRED
    seasonalContext:            SeasonalContext             = Field(default_factory=SeasonalContext)
    actionItems:                ActionItems                 = Field(default_factory=ActionItems)
    complaintAnalysis:          ComplaintAnalysis           = Field(default_factory=ComplaintAnalysis)
    featureAdaptability:        FeatureAdaptability         = Field(default_factory=FeatureAdaptability)
    performanceMetricsSentiment: PerformanceMetricsSentiment = Field(default_factory=PerformanceMetricsSentiment)

    # Convenience aliases used by existing code and dashboard
    @property
    def key_topics(self) -> List[str]:
        return self.callAnalysis.primaryTopics

    @property
    def sentiment(self) -> Optional[SentimentEnum]:
        return self.callAnalysis.overallSentiment

    @property
    def urgency(self) -> Optional[UrgencyEnum]:
        return self.callAnalysis.urgencyLevel

    @property
    def pricing_mentioned(self) -> bool:
        return (
            self.budgetAndBidding.budgetUtilization is not None
            or bool(self.complaintAnalysis.complaintKeywords)
        )

    @property
    def competitor_mentioned(self) -> bool:
        return self.complaintAnalysis.programMentioned is not None


class BatchInsightSummary(BaseModel):
    """Aggregated summary across all calls in a daily batch."""
    total_calls:             int
    processed_calls:         int
    failed_calls:            int
    data_quality_rate:       float = Field(..., ge=0.0, le=1.0)
    positive_sentiment_pct:  float
    high_urgency_pct:        float
    top_topics:              List[str]
    top_complaints:          List[str]
    avg_processing_seconds:  float
    p95_latency_seconds:     float
    negative_sentiment_pct:  float = 0.0


# ---------------------------------------------------------------------------
# Response parsing — mirrors VOCBatchProcessingJob.parseLLMResponse()
# ---------------------------------------------------------------------------

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _coerce_call_analysis(data: dict) -> dict:
    """
    Build a callAnalysis-compatible dict from a raw LLM response.
    Handles flat schema (old format) and nested schema (new format).
    """
    if "callAnalysis" in data:
        return data

    # Flat compatibility (old format: key_topics, sentiment, urgency at top level)
    ca: Dict[str, Any] = {
        "overallSentiment":  data.get("sentiment", "neutral"),
        "urgencyLevel":      data.get("urgency", "low"),
        "primaryTopics":     data.get("key_topics", data.get("primary_topics", ["general"])),
        "secondaryTopics":   [],
        "resolutionType":    None,
        "currentIssue":      None,
        "pastIssue":         None,
        "resolutionSummary": None,
    }
    out = dict(data)
    out["callAnalysis"] = ca
    return out


def parse_llm_response(raw: str) -> Optional[TranscriptInsight]:
    """
    Extract and validate JSON from a raw LLM response against TranscriptInsight.
    Mirrors VOCBatchProcessingJob.parseLLMResponse() and BedRockUtils.JSON_PATTERN.
    Returns None if parsing or validation fails (caller triggers ADDITIONAL_PROMPT_FOR_RETRY).
    """
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned).rstrip("`").strip()

    candidates = [cleaned]
    match = _JSON_RE.search(cleaned)
    if match:
        candidates.append(match.group())

    for candidate in candidates:
        try:
            data    = json.loads(candidate)
            data    = _coerce_call_analysis(data)
            return TranscriptInsight(**data)
        except Exception:
            continue

    return None


def build_retry_prompt(original_prompt: str, previous_response: str, invalid_reason: str) -> str:
    """
    Mirror of BedRockUtils.ADDITIONAL_PROMPT_FOR_RETRY — injects previous
    invalid response and validation reason so Claude 3.5 Haiku self-corrects.
    """
    return (
        f"Your previous response <previous_response>{previous_response}</previous_response> "
        f"was deemed invalid due to <invalid_reason>{invalid_reason}</invalid_reason>. "
        "Please re-evaluate carefully and provide an updated response that fully aligns "
        "with the given instructions and requirements. "
        + original_prompt
    )


def build_full_extraction_prompt(transcript_text: str) -> str:
    """
    Build the combined extraction prompt for all 10 MetricCategory categories.
    This is the actual prompt structure used by VOAJob in production.
    """
    category_instructions = "\n\n".join(
        f"--- {cat.json_key} ---\n{cat.instructions}\nOutput schema: {cat.schema}"
        for cat in MetricCategory
    )
    return (
        "You are analyzing an Amazon Ads advertiser call transcript. "
        "Extract all 10 insight categories. "
        "Output a single valid JSON object with all 10 keys at the top level.\n\n"
        + category_instructions
        + f"\n\nConversation:\n{transcript_text[:4000]}"
    )
