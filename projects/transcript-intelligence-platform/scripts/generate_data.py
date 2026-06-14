"""
Generate synthetic Gong.io transcript data for local runs.

Matches the real VOA Platform data schema:
  - Gong.io payload format (conversation_id, timestamp, participants, transcript_segments)
  - All 10 insight categories embedded as processed_insights
  - Campaign enrichment fields (ROAS, CPC, campaign type)
  - Advertiser metadata (Andes-enriched fields)

Creates:
  - data/sample_transcripts.jsonl — raw Gong.io format (1,000 records)
  - data/sample_metadata.jsonl    — Andes metadata for inner join

Run: python scripts/generate_data.py
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

RAW_PATH  = Path(__file__).parent.parent / "data" / "sample_transcripts.jsonl"
META_PATH = Path(__file__).parent.parent / "data" / "sample_metadata.jsonl"
N_RECORDS = 1_000


def _make_transcript_segments(rng: random.Random, full_text: str) -> list[dict]:
    """Split full transcript into speaker-labeled segments with confidence scores."""
    sentences = full_text.split(". ")
    segments  = []
    t_offset  = 60  # seconds
    for i, sentence in enumerate(sentences):
        if not sentence.strip():
            continue
        speaker = "amazon_rep" if i % 2 == 0 else "customer"
        segments.append({
            "speaker":    speaker,
            "text":       sentence.strip() + ".",
            "timestamp":  f"{t_offset // 60:02d}:{t_offset % 60:02d}",
            "confidence": round(rng.uniform(0.88, 0.99), 2),
        })
        t_offset += rng.randint(15, 90)
    return segments


def _make_insight_categories(rng: random.Random, text: str, campaign_type: str) -> dict:
    """Generate all 10 insight categories matching TranscriptInsight schema."""
    sentiments   = ["positive", "neutral", "negative"]
    neg_rate     = 0.15 if rng.random() > 0.3 else 0.45
    overall_sent = rng.choices(sentiments, weights=[0.55, 0.30, 0.15])[0]
    roas_val     = round(rng.uniform(1.2, 7.5), 2)
    cpc_val      = round(rng.uniform(0.50, 3.50), 2)
    comp         = rng.random() > 0.8
    topics_pool  = [
        "roas_optimization", "budget_management", "targeting_strategy",
        "campaign_structure", "bidding_optimization", "competitor_analysis",
        "feature_request", "reporting_analytics", "cpc_reduction", "conversion_rate",
    ]
    primary_topics = rng.sample(topics_pool, k=rng.randint(1, 3))

    # Use EXACT MetricCategory camelCase JSON keys
    return {
        "identificationMetrics": {
            "amazonRepName":     f"Rep_{rng.randint(1,50):02d}",
            "asinMentioned":     [f"B{rng.randint(0,9)}{rng.randint(100000,999999)}" for _ in range(rng.randint(0,2))],
            "campaignNames":     [f"Campaign_{rng.randint(1,20)}"],
            "tenureInformation": rng.choice([None, "6 months", "1 year", "2 years"]),
        },
        "campaignStructure": {
            "primaryCampaignType": campaign_type.replace(" ", "_"),
            "targetingTypes":      rng.sample(["Keyword", "Product", "Audience", "Views Retargeting"], k=rng.randint(1,3)),
        },
        "campaignScale": {
            "scaleIssuesReported":          rng.random() > 0.7,
            "limitedTargetingMentioned":    rng.random() > 0.6,
            "scalePerception":              rng.choice(["good", "limited", "very_limited", None]),
            "targetingRestrictions":        ["budget_cap"] if rng.random() > 0.7 else [],
            "recommendedScaleImprovements": ["expand_audience"] if rng.random() > 0.6 else [],
        },
        "budgetAndBidding": {
            "dailyBudget":       rng.choice([None, 500.0, 1000.0, 2000.0, 5000.0]),
            "monthlyBudget":     rng.choice([None, 15000.0, 30000.0, 60000.0]),
            "budgetUtilization": rng.choice(["budget_limited", "under_spending", "optimal", None]),
            "biddingStrategy":   rng.choice(["aggressive", "conservative", "competitive", None]),
            "seasonalStrategy":  rng.choice(["peak_season", "off_season", None]),
            "bidAdjustments":    ["increase_bids_20pct"] if rng.random() > 0.6 else [],
        },
        "callAnalysis": {
            "primaryTopics":        primary_topics,
            "primaryTopicSentiment": overall_sent,
            "secondaryTopics":      rng.sample(topics_pool, k=rng.randint(0, 2)),
            "resolutionType":       rng.choice(["full_resolution", "partial_resolution", "escalated", None]),
            "overallSentiment":     overall_sent,
            "customerExperience":   rng.choice(["beginner", "intermediate", "experienced", "expert"]),
            "urgencyLevel":         rng.choices(["low", "medium", "high", "seasonal_pressure"], weights=[0.5, 0.35, 0.1, 0.05])[0],
            "currentIssue":         "below_target_roas" if rng.random() > 0.5 else None,
            "pastIssue":            "high_cpc" if rng.random() > 0.7 else None,
            "pastIssueStatus":      rng.choice(["resolved", "not_resolved", None]),
            "resolutionSummary":    "Discussed optimization strategies" if rng.random() > 0.4 else None,
        },
        "seasonalContext": {
            "seasonalPressure": rng.random() > 0.8,
            "peakSeasonTiming": rng.choice([None, "Q4", "Prime Day", "Back to School"]),
            "seasonalEvents":   ["Black Friday"] if rng.random() > 0.85 else [],
        },
        "actionItems": {
            "immediateActions":        ["review_bids", "check_targeting"][:rng.randint(0,2)],
            "bidOptimizations":        ["enable_auto_bidding", "increase_bids"][:rng.randint(0,2)],
            "nextSteps":               ["follow_up_in_1_week"] if rng.random() > 0.5 else [],
            "scaleImprovementActions": ["expand_audience_segments"] if rng.random() > 0.6 else [],
        },
        "complaintAnalysis": {
            "complaintKeywords":  ["below_target_roas", "high_cpc"][:rng.randint(0,2)],
            "complaintPhrases":   ["ads shown too often"] if rng.random() > 0.8 else [],
            "programMentioned":   "Google Ads" if comp else None,
            "complaintSeverity":  rng.choices(["low", "medium", "high"], weights=[0.5, 0.35, 0.15])[0],
            "scaleRelatedComplaints": ["limited_reach"] if rng.random() > 0.7 else [],
            "programSpecificComplaints": {
                "SD": ["irrelevant_placement"] if campaign_type == "Sponsored Display" and rng.random() > 0.7 else [],
                "SP": ["high_acos"] if campaign_type == "Sponsored Products" and rng.random() > 0.7 else [],
                "SB": [] ,
            },
        },
        "featureAdaptability": {
            "knownFeatures":               ["auto_bidding"] if rng.random() > 0.5 else [],
            "discussedFeatures":           ["target_roas", "portfolio_bidding"][:rng.randint(0,2)],
            "learnedFeatures":             ["automated_rules"] if rng.random() > 0.7 else [],
            "featureAdaptability":         rng.choice(["beginner", "intermediate", "advanced", None]),
            "featuresAdvertisersKnows":    [],
            "featuresAdvertiserTalksAbout": ["roas"],
            "featuresAdvertiserLearnt":    [],
        },
        "performanceMetricsSentiment": {
            "roasSentiment":                     rng.choices(sentiments, weights=[0.4, 0.35, 0.25])[0],
            "cpcSentiment":                      rng.choices(sentiments, weights=[0.3, 0.35, 0.35])[0],
            "cpmSentiment":                      rng.choice(sentiments + [None]),
            "vcpmSentiment":                     rng.choice(sentiments + [None]) if campaign_type == "Sponsored Display" else None,
            "targetingClausesSentiment":         rng.choices(sentiments, weights=[0.4, 0.35, 0.25])[0],
            "biddingStrategiesSentiment":        rng.choices(sentiments, weights=[0.4, 0.35, 0.25])[0],
            "roasSentimentAdvertiser":           rng.choices(sentiments, weights=[0.35, 0.30, 0.35])[0],
            "cpcSentimentAdvertiser":            rng.choices(sentiments, weights=[0.30, 0.30, 0.40])[0],
            "vcpmSentimentAdvertiser":           None,
            "targetingClausesSentimentAdvertiser": rng.choices(sentiments, weights=[0.4, 0.35, 0.25])[0],
            "advertiserPerception":              overall_sent,
        },
    }


def generate(n: int = N_RECORDS, seed: int = 42) -> tuple[list[dict], list[dict]]:
    rng       = random.Random(seed)
    teams     = [f"Team_{chr(65+i)}" for i in range(18)]  # 18 teams A–R
    campaigns = ["Sponsored Products", "Sponsored Brands", "Sponsored Display"]
    topics_pool = [
        "ROAS optimization and bidding strategy",
        "budget allocation for campaign scale",
        "competitor analysis comparing Google Ads performance",
        "campaign structure review and targeting improvements",
        "feature request for automated bidding rules",
        "CPC reduction and conversion rate optimization",
        "reporting enhancements and analytics improvements",
        "account health and performance metrics review",
    ]

    transcripts = []
    metadata    = []

    for i in range(n):
        date          = datetime.now() - timedelta(days=rng.randint(0, 29))
        campaign_type = rng.choice(campaigns)
        topic         = rng.choice(topics_pool)
        roas_current  = round(rng.uniform(1.2, 7.5), 2)
        roas_target   = round(roas_current * rng.uniform(0.8, 1.5), 2)
        conv_id       = f"conv_{i:06d}"
        advertiser_id = f"adv_{rng.randint(1, 500):05d}"

        full_text = (
            f"Amazon Rep: Good morning! Let's review your campaign performance. "
            f"Customer: Yes, we're focusing on {topic}. "
            f"Our current ROAS is {roas_current:.2f} but we're targeting {roas_target:.2f}. "
            + ("We're experiencing budget exhaustion and high CPC. " if rng.random() > 0.5 else "")
            + ("I'd suggest enabling auto bidding to help optimize. " if rng.random() > 0.5 else "")
            + ("We noticed Google Ads campaigns outperforming in some segments. " if rng.random() > 0.8 else "")
            + f"Amazon Rep: Let me pull up your campaign data and review the bidding strategy. "
            + f"I recommend adjusting your bids and revisiting the targeting. "
            + ("We can schedule a follow-up next week. " if rng.random() > 0.4 else "")
        )

        # Raw Gong.io format (matches API payload schema from design doc)
        transcripts.append({
            "conversation_id":   conv_id,
            "timestamp":         date.isoformat() + "Z",
            "call_date":         date.strftime("%Y-%m-%d"),
            "duration_seconds":  rng.randint(300, 3600),
            "campaign_type":     campaign_type,
            "team":              rng.choice(teams),
            "advertiser_id":     advertiser_id,
            "participants": [
                {"role": "customer",   "talk_time": rng.randint(30, 60)},
                {"role": "amazon_rep", "talk_time": rng.randint(40, 70)},
            ],
            "transcript":         full_text,
            "transcript_segments": _make_transcript_segments(rng, full_text),
            # Pre-processed insights (embedded by VOAJob after Bedrock extraction)
            "processed_insights": _make_insight_categories(rng, full_text, campaign_type),
            "schema_valid":       rng.random() > 0.001,  # 99.9% data quality
            "processing_version": "v1.2",
        })

        # Andes metadata for GongDataIngestionJob inner join
        metadata.append({
            "conversation_id":   conv_id,
            "advertiser_id":     advertiser_id,
            "account_name":      f"Advertiser_Corp_{rng.randint(1,200)}",
            "opportunity_stage": rng.choice(["prospecting", "qualified", "proposal", "closed_won"]),
            "marketplace_id":    rng.choice(["US", "UK", "DE", "JP"]),
            "advertiser_tier":   rng.choice(["standard", "premium", "enterprise"]),
            "salesforce_id":     f"SF_{rng.randint(100000,999999)}",
            "industry_vertical": rng.choice(["retail", "cpg", "technology", "automotive", "financial"]),
        })

    return transcripts, metadata


def main() -> None:
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    transcripts, metadata = generate()

    with RAW_PATH.open("w") as f:
        for r in transcripts:
            f.write(json.dumps(r) + "\n")

    with META_PATH.open("w") as f:
        for m in metadata:
            f.write(json.dumps(m) + "\n")

    print(f"Generated {len(transcripts):,} transcripts  → {RAW_PATH}")
    print(f"Generated {len(metadata):,}    metadata recs → {META_PATH}")
    print(f"18 teams represented: {', '.join(sorted({r['team'] for r in transcripts}))}")


if __name__ == "__main__":
    main()
