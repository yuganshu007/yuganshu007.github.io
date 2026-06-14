"""Synthetic transcript corpus model + generator.

Everything generated here is **synthetic**. See docs/METRICS.md: data volumes (e.g. 23,000+
conversations, 100+ tenants, one named ``salesforce``) are *illustrative scale*, not a claim of
real production adoption.

The generator deliberately:
  * skews advertiser ids (one "hot" advertiser gets the majority of rows) so the Spark
    skew-safe-join optimization has something real to fix;
  * injects a small, controlled defect rate so the data-quality suite genuinely measures a
    pass rate at/above 99.9% on the clean majority.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, asdict, field
from datetime import date, timedelta
from typing import Iterator

LANGUAGES = ["en", "en", "en", "es", "fr", "de"]
CHANNELS = ["phone", "chat", "email"]
SENTIMENTS = ["positive", "neutral", "negative"]

# A handful of tenants get explicit names; one is `salesforce` per the bullet point.
NAMED_TENANTS = ["salesforce", "acme_ads", "globex", "initech", "umbrella", "hooli"]

# Controlled fraction of records that are intentionally defective. 0.0005 => ~99.95% clean,
# comfortably supporting a >= 99.9% data-quality target while remaining a *measured* number.
DEFECT_RATE = 0.0005

_SNIPPETS = [
    "Thanks for calling about your advertising campaign performance this quarter.",
    "We noticed your click-through rate dropped after the budget change.",
    "I can help you reallocate spend toward the higher-converting audience.",
    "Your invoice reflects the prorated charges from the mid-cycle upgrade.",
    "Let me pull up the attribution report for the last 30 days.",
    "We recommend enabling automated bidding for the holiday window.",
    "The creative was rejected for a policy issue; here is how to fix it.",
    "I have escalated the billing discrepancy to our finance team.",
]


@dataclass
class Conversation:
    call_id: str
    tenant: str
    advertiser_id: str
    dt: str
    agent_id: str
    channel: str
    language: str
    duration_sec: int
    num_turns: int
    transcript_text: str
    expected_sentiment: str
    is_defective: bool = False
    defect_reason: str | None = None


@dataclass
class GenConfig:
    conversations: int = 23000
    tenants: int = 100
    days: int = 14
    hot_advertiser_fraction: float = 0.8  # share of rows on the single hot advertiser id
    advertisers: int = 500
    seed: int = 1337
    defect_rate: float = DEFECT_RATE


def _tenant_name(i: int) -> str:
    if i < len(NAMED_TENANTS):
        return NAMED_TENANTS[i]
    return f"team_{i:03d}"


def _make_transcript(rng: random.Random) -> tuple[str, int]:
    n_turns = rng.randint(4, 18)
    lines = []
    for t in range(n_turns):
        speaker = "agent" if t % 2 == 0 else "advertiser"
        lines.append(f"{speaker}: {rng.choice(_SNIPPETS)}")
    return "\n".join(lines), n_turns


def generate_conversations(cfg: GenConfig) -> Iterator[Conversation]:
    rng = random.Random(cfg.seed)
    start = date(2026, 1, 1)
    hot_advertiser = "adv_HOT_0001"
    for i in range(cfg.conversations):
        tenant = _tenant_name(rng.randrange(cfg.tenants))
        # Skewed advertiser distribution: hot key dominates.
        if rng.random() < cfg.hot_advertiser_fraction:
            advertiser_id = hot_advertiser
        else:
            advertiser_id = f"adv_{rng.randrange(cfg.advertisers):04d}"
        dt = (start + timedelta(days=rng.randrange(cfg.days))).isoformat()
        transcript, n_turns = _make_transcript(rng)
        conv = Conversation(
            call_id=f"call_{i:09d}",
            tenant=tenant,
            advertiser_id=advertiser_id,
            dt=dt,
            agent_id=f"agent_{rng.randrange(50):03d}",
            channel=rng.choice(CHANNELS),
            language=rng.choice(LANGUAGES),
            duration_sec=rng.randint(30, 1800),
            num_turns=n_turns,
            transcript_text=transcript,
            expected_sentiment=rng.choice(SENTIMENTS),
        )
        if rng.random() < cfg.defect_rate:
            _inject_defect(conv, rng)
        yield conv


def _inject_defect(conv: Conversation, rng: random.Random) -> None:
    conv.is_defective = True
    kind = rng.choice(["empty_transcript", "negative_duration", "bad_language", "no_turns"])
    conv.defect_reason = kind
    if kind == "empty_transcript":
        conv.transcript_text = ""
    elif kind == "negative_duration":
        conv.duration_sec = -1
    elif kind == "bad_language":
        conv.language = "xx"
    elif kind == "no_turns":
        conv.num_turns = 0


def write_corpus(cfg: GenConfig, out_dir: str) -> dict:
    """Write JSONL transcripts partitioned by tenant/dt and a summary meta.json."""
    landing = os.path.join(out_dir, "landing")
    os.makedirs(landing, exist_ok=True)
    buffers: dict[tuple[str, str], list[str]] = {}
    counts = {"total": 0, "defective": 0, "by_tenant": {}}
    tenants_seen: set[str] = set()

    for conv in generate_conversations(cfg):
        key = (conv.tenant, conv.dt)
        buffers.setdefault(key, []).append(json.dumps(asdict(conv)))
        counts["total"] += 1
        counts["defective"] += int(conv.is_defective)
        counts["by_tenant"][conv.tenant] = counts["by_tenant"].get(conv.tenant, 0) + 1
        tenants_seen.add(conv.tenant)

    for (tenant, dt), lines in buffers.items():
        d = os.path.join(landing, f"tenant={tenant}", f"dt={dt}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "part-000.jsonl"), "w") as f:
            f.write("\n".join(lines))

    # 18 "adopting" analytics teams — illustrative (see METRICS.md).
    adopting_teams = sorted(tenants_seen)[:18]
    meta = {
        "config": asdict(cfg),
        "counts": counts,
        "n_tenants": len(tenants_seen),
        "adopting_analytics_teams": adopting_teams,
        "clean_rate": 1 - (counts["defective"] / max(counts["total"], 1)),
    }
    with open(os.path.join(out_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta
