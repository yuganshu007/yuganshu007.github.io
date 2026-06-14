"""
Generate synthetic Gong.AI transcript data for local runs.
Creates data/sample_transcripts.jsonl with 1,000 realistic records.

Run: python scripts/generate_data.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "sample_transcripts.jsonl"
N_RECORDS   = 1_000


def generate(n: int = N_RECORDS, seed: int = 42) -> list[dict]:
    rng     = random.Random(seed)
    topics  = [
        "ROAS optimization and bidding strategy",
        "budget allocation for Sponsored Products",
        "competitor analysis comparing Google Ads performance",
        "campaign structure review and targeting improvements",
        "feature request for automated bidding rules",
        "CPC reduction and conversion rate optimization",
        "reporting enhancements for the analytics team",
        "account health and performance metrics review",
    ]
    sentiments = ["positive", "neutral", "negative"]
    campaigns  = ["Sponsored Products", "Sponsored Brands", "Sponsored Display"]
    teams      = [f"Team_{chr(65+i)}" for i in range(18)]

    records = []
    for i in range(n):
        date = datetime.now() - timedelta(days=rng.randint(0, 29))
        topic = rng.choice(topics)
        roas_current = rng.uniform(1.2, 7.5)
        roas_target  = roas_current * rng.uniform(0.8, 1.5)
        pain = "no major issues" if rng.random() > 0.5 else "budget exhaustion and low conversion rates"

        transcript_text = (
            f"Amazon Rep: Good morning! I wanted to review your campaign performance. "
            f"Customer: Yes, we're focusing on {topic}. "
            f"Our current ROAS is {roas_current:.2f} but we're targeting {roas_target:.2f}. "
            f"We're experiencing {pain}. "
            + ("I'd suggest enabling auto bidding to help optimize. " if rng.random() > 0.5 else "")
            + ("We noticed Google Ads campaigns outperforming in some segments. " if rng.random() > 0.8 else "")
            + ("The cost per click has been higher than expected. " if rng.random() > 0.5 else "")
            + f"Amazon Rep: Great, let me pull up your campaign data and we can review the budget allocation. "
            + f"I recommend we adjust your bids and revisit the targeting strategy."
        )

        records.append({
            "conversation_id":   f"conv_{i:06d}",
            "timestamp":         date.isoformat() + "Z",
            "call_date":         date.strftime("%Y-%m-%d"),
            "duration_seconds":  rng.randint(300, 3600),
            "campaign_type":     rng.choice(campaigns),
            "team":              rng.choice(teams),
            "advertiser_id":     f"adv_{rng.randint(1, 500):05d}",
            "participants": [
                {"role": "customer",    "talk_time": rng.randint(30, 60)},
                {"role": "amazon_rep",  "talk_time": rng.randint(40, 70)},
            ],
            "transcript": transcript_text,
            "transcript_segments": [
                {
                    "speaker":    "customer",
                    "text":       transcript_text[:200],
                    "timestamp":  "00:01:00",
                    "confidence": round(rng.uniform(0.88, 0.99), 2),
                }
            ],
        })

    return records


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = generate()
    with OUTPUT_PATH.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    print(f"Generated {len(records):,} records → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
