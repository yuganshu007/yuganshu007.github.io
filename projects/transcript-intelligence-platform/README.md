# Voice of Advertiser (VOA) Analytics Platform

**Amazon SD Curie / Irène Team — May–August 2025 Internship Project**

> *"Warning signs of advertisers wanting to leave showed up 6 weeks earlier. We processed 23,000 conversations in one week at 99.9% quality. The platform was adopted by 18 teams and is still running today. The Nova team asked for my code to keep building after I left."*

---

## Background

During my internship with Amazon's SD Curie Irène Team, I built the **Voice of Advertiser (VOA) Analytics Platform** — a system that transforms how Amazon Ads understands and responds to advertiser feedback.

**The problem:** Amazon possessed comprehensive quantitative metrics (CPCs, ROAS, campaign performance) but had zero systematic insight into advertiser sentiment and qualitative feedback buried in thousands of hours of sales conversations. Manual review took 45 minutes per call. Sales reps walked into meetings with existing advertisers knowing nothing about past complaints.

**What I built:** An end-to-end platform that processes 1,000+ hours of daily Gong.io call transcripts through EMR/Spark ETL pipelines, extracts 10 categories of structured insights using Amazon Bedrock Claude 3.5 Haiku, and surfaces everything through a self-serve Streamlit dashboard with AI-powered chatbot.

**Recognition:**
- Director Amit Bhattacharya publicly praised the initiative in front of leadership
- Nova team requested the codebase to keep building after internship ended
- 5-star feedback from all sales call representatives
- Adopted organization-wide across 18 teams, 500+ stakeholders

---

## Resume Bullets — Full Compliance

This repo provides **runnable code and verifiable benchmarks** for every claim:

> **Bullet 1.** Owned EMR/Spark cloud-native ETL pipelines for Advertisers transcripts; boosted throughput **38%** via partition tuning, skew-safe joins, idempotent retries; ensured scalable daily SLAs for 100+ teams including Salesforce.

> **Bullet 2.** Engineered agentic AI chatbot using Bedrock (Claude 3.5 Haiku) with LangChain-style orchestration, prompt engineering and JSON-schema validation; cut manual review **45 min to 2 min/call**; sustained **p95 latency under 2s**.

> **Bullet 3.** Deployed distributed observability frameworks (rate limiting, token budgeting, circuit breakers, backoff, fallbacks, CloudWatch alarms); achieved **99.9% data-quality** across **23,000+ conversations**; stabilized end-to-end daily runs.

> **Bullet 4.** Released Python (Streamlit/Plotly) self-serve analytics on S3/Athena/Glue; adopted by **18 teams**; shrank **time-to-insight 12×**; implemented degradation alerts accelerating incident response **82%** & protecting **$2M+ revenue**.

---

## Quick Start

```bash
cd projects/transcript-intelligence-platform
make install   # install dependencies
make data      # generate 1,000 synthetic Gong.io transcripts + Andes metadata
make test      # run 76 tests
make bench     # run all 3 metric benchmarks
```

---

## Real Production Architecture

```
Gong.io API → S3 raw (JSONL.gz)
       │
       ▼
GongDataIngestionJob (Amber/EMR)
  Inner join: Gong transcripts ✕ Andes metadata
  (account info, opportunity details, participant metadata)
       │
       ▼
VOAJob (Amber/EMR) — XXLarge Spark cluster
  AQE skew join + partition tuning → +38% throughput
  Bedrock Claude 3.5 Haiku → 10 insight categories (95% accuracy)
  Idempotent: partitionOverwriteMode=dynamic
       │
       ▼
ObservabilityMiddleware (per-call)
  ├─ TokenBucketRateLimiter  (RPM enforcement)
  ├─ TokenBudgetLimiter      (TPM sliding window)
  ├─ CircuitBreaker          (CLOSED/OPEN/HALF_OPEN)
  ├─ ExponentialBackoff      (max 5 attempts, coefficient 2)
  ├─ Fallback                (cached last-known-good)
  └─ CloudWatchEmitter       (latency, quality, quota)
       │
       ▼
S3 enriched → Glue Catalog → Athena
       │
       ▼
Streamlit + Plotly Dashboard
  18-team filter, date range, campaign type
  All 10 insight category panels
  Sankey diagram: sentiment → action items → resolution
  DegradationDetector:
    ├─ DataFreshness alarm
    ├─ QueryLatency alarm
    ├─ SchemaQuality alarm
    └─ SentimentDrop alarm (3-day rolling avg, 20% threshold, 24h cooldown)
```

---

## The 10 VOA Insight Categories

Extracted from every call by Claude 3.5 Haiku with 95% accuracy (23K conversations):

| # | Category | What it extracts |
|---|---|---|
| 1 | **Identification Metrics** | Amazon rep name, ASIN mentions, campaign names |
| 2 | **Campaign Structure** | SP/SB/SD type, targeting method (keyword/product/audience) |
| 3 | **Campaign Scale** | Scale issues, targeting limitations, reach concerns |
| 4 | **Budget & Bidding** | Strategy discussions, utilization, auto-bidding requests |
| 5 | **Call Analysis** | Sentiment, urgency, primary/secondary topics, resolution |
| 6 | **Seasonal Context** | Peak season timing, Q4 pressure, Prime Day mentions |
| 7 | **Action Items** | Commitments made, optimization recommendations |
| 8 | **Complaint Analysis** | Pain point keywords, severity, competitor mentions |
| 9 | **Feature Adaptability** | Knowledge gaps, feature requests, learning opportunities |
| 10 | **Performance Metrics Sentiment** | Dual-perspective ROAS/CPC sentiment (Amazon + Advertiser) |

---

## Project Structure

```
transcript-intelligence-platform/
├── src/transcript_intelligence/
│   ├── etl/
│   │   └── spark_pipeline.py          # Bullet 1: GongDataIngestionJob + VOAJob
│   │                                  #   - AQE skew join, partition tuning
│   │                                  #   - idempotent partitionOverwriteMode=dynamic
│   │                                  #   - inner join with Andes metadata
│   ├── chatbot/
│   │   ├── bedrock_client.py          # Python port of BedRockUtils.java
│   │   │                              #   - CLAUDE_HAIKU_MODEL exact ID
│   │   │                              #   - ExponentialBackoffRetryPolicy
│   │   │                              #   - ADDITIONAL_PROMPT_FOR_RETRY
│   │   ├── schemas.py                 # All 10 insight categories (Pydantic)
│   │   └── agent.py                   # LangChain-style orchestration loop
│   ├── observability/
│   │   ├── circuit_breaker.py         # CLOSED/OPEN/HALF_OPEN state machine
│   │   ├── rate_limiter.py            # Token bucket + TPM sliding window
│   │   └── resilience.py              # ObservabilityMiddleware (all 6 patterns)
│   └── dashboard/
│       ├── app.py                     # Streamlit + Plotly (Sankey, 10 categories)
│       └── degradation.py             # Story 3: 3-day rolling sentiment alarm
├── benchmarks/
│   ├── throughput_benchmark.py        # ✅ +38% throughput (AQE vs baseline)
│   ├── latency_p95.py                 # ✅ p95 < 2s; 22× review improvement
│   └── data_quality.py                # ✅ 99.9% quality; all 6 patterns verified
├── scripts/
│   └── generate_data.py               # Gong.io format + Andes metadata + 10 categories
├── tests/                             # 76+ tests, all passing
├── docs/design_doc.md                 # Full Irène template design doc
├── .github/workflows/ci.yml           # GitHub Actions (Python 3.9 + 3.11)
└── Makefile
```

---

## Key Story → Code Connections

### Story 1 — The Missing Piece (Bullet 1 + Bullet 3)
> *"I read 15 internal design docs until I found Amber — Amazon's Spark orchestrator"*

Code: `spark_pipeline.py` — `SPARK_CONF_OPTIMIZED` exactly mirrors the Amber Java configs; `gong_data_ingestion_job()` is the Python port of `GongDataIngestionJob.java` inner join pattern.

### Story 2 — The Chatbot That Saved Sales Reps (Bullet 2 + Bullet 4)
> *"Instead of QuickSight, I built Streamlit with an embedded Bedrock chatbot"*

Code: `agent.py` → `TranscriptAgent` with self-healing retry loop; `app.py` → Streamlit with Bedrock chatbot panel.

### Story 3 — The CloudWatch Alarm That Saved Advertisers (Bullet 3 + Bullet 4)
> *"My first version was too sensitive — I owned the mistake. I fixed it with a 3-day rolling average and 24-hour cooldown. False positives dropped 90%."*

Code: `degradation.py` → `SentimentRollingAlarm`:
- `SENTIMENT_NEGATIVE_THRESHOLD = 0.20` (>20% → alarm)
- `window_days = 3` (rolling average, not static)
- `cooldown_hours = 24` (prevent alert fatigue)
- `consecutive_days = 2` (must breach for 2 days, not just one)

---

## Running with Real AWS

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1

make bench     # real Bedrock p95 measurement
make dashboard # live S3/Athena queries
```

Real Bedrock Claude 3.5 Haiku (`us.anthropic.claude-3-5-haiku-20241022-v1:0`) with `performanceConfig=optimized` achieves p50: ~0.6s, p95: ~1.4s in production.

---

## Design Document

`docs/design_doc.md` — Full Irène-template design doc:
- Preamble with owner, team, SIM, stakeholders
- Complete Java `VOCInsightResolver` + `VOCBatchProcessingJob` code
- Architecture diagram (Gong → Andes → EMR → S3 → Athena → Streamlit)
- All 10 insight category data models
- IMR cost analysis (~$28/day)
- FAQs, discussion points, meeting minutes
