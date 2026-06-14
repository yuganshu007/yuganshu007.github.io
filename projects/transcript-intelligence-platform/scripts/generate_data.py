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

    return {
        "identification_metrics": {
            "amazon_rep_name":  f"Rep_{rng.randint(1,50):02d}",
            "asin_mentions":    [f"B{rng.randint(0,9)}{rng.randint(100000,999999)}" for _ in range(rng.randint(0,2))],
            "campaign_names":   [f"Campaign_{rng.randint(1,20)}"],
            "marketplace_id":   "US",
        },
        "campaign_structure": {
            "primary_campaign_type": campaign_type,
            "targeting_methods":     rng.sample(["keyword", "product", "audience"], k=rng.randint(1,2)),
            "campaign_count":        rng.randint(1, 12),
        },
        "campaign_scale": {
            "scale_issues_identified": rng.random() > 0.7,
            "targeting_limitations":   ["budget_cap"] if rng.random() > 0.7 else [],
            "reach_concerns":          rng.random() > 0.75,
        },
        "budget_bidding": {
            "bidding_strategy_discussed":  rng.random() > 0.4,
            "budget_utilization_concern":  rng.random() > 0.5,
            "seasonal_adjustment_needed":  rng.random() > 0.7,
            "auto_bidding_requested":      rng.random() > 0.5,
            "cpc_concern":                 rng.random() > 0.4,
            "budget_exhaustion":           rng.random() > 0.6,
        },
        "call_analysis": {
            "overall_sentiment":  overall_sent,
            "urgency":            rng.choices(["low", "medium", "high"], weights=[0.5, 0.35, 0.15])[0],
            "primary_topics":     primary_topics,
            "secondary_topics":   rng.sample(topics_pool, k=rng.randint(0, 2)),
            "call_resolution":    rng.random() > 0.3,
            "follow_up_required": rng.random() > 0.4,
        },
        "seasonal_context": {
            "peak_season_discussed": rng.random() > 0.8,
            "seasonal_pressure":     rng.random() > 0.75,
            "q4_mentioned":          rng.random() > 0.85,
        },
        "action_items": {
            "immediate_actions":   ["review_bids", "check_targeting"][:rng.randint(0,2)],
            "optimization_recs":   ["enable_auto_bidding", "expand_audience"][:rng.randint(0,2)],
            "commitments_made":    ["follow_up_in_1_week"] if rng.random() > 0.5 else [],
            "follow_up_date_mentioned": rng.random() > 0.4,
        },
        "complaint_analysis": {
            "complaint_keywords":   ["below_target_roas", "high_cpc"][:rng.randint(0,2)],
            "severity":             rng.choices(["low","medium","high","critical"], weights=[0.5,0.3,0.15,0.05])[0],
            "competitor_mentioned": comp,
            "competitor_names":     (["Google Ads"] if comp else []),
            "pricing_complaint":    rng.random() > 0.5,
            "feature_gap_complaint": rng.random() > 0.6,
        },
        "feature_adaptability": {
            "knowledge_gaps_identified": ["auto_bidding_setup"] if rng.random() > 0.6 else [],
            "feature_requests":          ["automated_reporting"] if rng.random() > 0.5 else [],
            "learning_opportunity":      rng.random() > 0.5,
            "onboarding_issue":          rng.random() > 0.75,
        },
        "performance_metrics_sentiment": {
            "roas_sentiment":          rng.choices(sentiments, weights=[0.4, 0.35, 0.25])[0],
            "cpc_sentiment":           rng.choices(sentiments, weights=[0.3, 0.35, 0.35])[0],
            "targeting_effectiveness": rng.choices(sentiments, weights=[0.4, 0.35, 0.25])[0],
            "roas_value_mentioned":    roas_val,
            "cpc_value_mentioned":     cpc_val,
            "amazon_rep_sentiment":    "positive",
            "advertiser_sentiment":    overall_sent,
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
