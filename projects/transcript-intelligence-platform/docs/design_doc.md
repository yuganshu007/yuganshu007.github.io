# Transcript Intelligence Platform — Design Document

---

## Preamble

| Field | Value |
|---|---|
| **Document Owner** | Amazon Ads — SD Curie / Irène Team |
| **Team** | Seller & Display Curie — Advertiser Intelligence |
| **Tech Sponsor** | SDCurie Amber Platform |
| **Scoping One-Pager** | Advertiser VOC Analytics Initiative |
| **SIM** | `SIM://curie/voc-intelligence-platform` |
| **Approval Status** | WIP |
| **Stakeholders** | Ads Product, Advertiser Success, Sales Analytics, Salesforce Integration |
| **Approved By** | Pending |

---

## Overview

**Document Type:** High-Level Design (HLD) + Architectural Deep Dive

This document describes the design of the **Transcript Intelligence Platform (TIP)** — an end-to-end system that ingests raw Gong.AI advertiser call transcripts, processes them through EMR/Spark ETL pipelines, enriches insights via an agentic AI chatbot powered by Amazon Bedrock (Claude 3.5 Haiku), enforces distributed observability patterns, and surfaces actionable analytics through a self-serve Streamlit/Plotly dashboard backed by S3/Athena/Glue.

**Necessary Stakeholders:** Advertiser Success leads, Data Engineering, ML Platform, BI/Analytics teams including 100+ downstream consumers (Salesforce, internal tooling).

---

## Glossary

| Term | Definition |
|---|---|
| **VOC** | Voice of Customer — raw advertiser call transcripts from Gong.AI |
| **EMR** | Amazon Elastic MapReduce — managed Apache Spark cluster service |
| **Amber** | SDCurie's internal job orchestration framework built on Apache Spark |
| **SDCurieJob** | Base class in Amber; all Spark jobs extend this |
| **SDCurieResolver** | Amber scheduler component that determines when/how to trigger `DatasetSpec` jobs |
| **DatasetSpec** | Amber manifest artifact describing input→output lineage for a Spark job |
| **Bedrock** | Amazon Bedrock — managed foundation model API (Claude 3.5 Haiku: `us.anthropic.claude-3-5-haiku-20241022-v1:0`) |
| **AQE** | Adaptive Query Execution — Spark 3.x runtime plan optimizer |
| **Idempotent write** | Write operation safe to retry; uses dynamic partition overwrite or Delta MERGE |
| **p95 latency** | 95th-percentile end-to-end response time for a Bedrock inference call |
| **Token budget** | Per-request `max_tokens` reservation that counts against TPM quota |
| **Circuit breaker** | Resilience pattern: CLOSED → OPEN → HALF_OPEN state machine preventing cascading failures |
| **Glue Catalog** | AWS Glue Data Catalog — schema registry for Athena tables over S3 |
| **SLA** | Service Level Agreement — guaranteed daily pipeline completion window |

---

## Motivation / Background

### Problem Statement

Amazon Ads manages 23,000+ advertiser conversations per month via Gong.AI. Insights from these conversations are siloed and require analysts to manually review each call transcript — consuming ~45 minutes per call. This creates three compounding problems:

1. **Throughput bottleneck**: Raw transcript data is processed by ad-hoc scripts without partition optimization, causing shuffle-heavy Spark stages to exceed SLA windows for 100+ downstream teams (including Salesforce integration).
2. **Manual review burden**: No automated extraction of structured insights means teams cannot scale beyond analyst headcount.
3. **Zero self-service observability**: There is no dashboard through which teams can independently query call data, track trends, or receive degradation alerts.

### Current State

- Transcripts land in S3 as gzip'd JSONL under `gong-advertiser-amazon-transcript-insights/version-0001/`
- A single unoptimized PySpark job reads all partitions, applies no skew handling, and writes without idempotency guards
- LLM analysis is done manually in Jupyter notebooks — no retries, no schema validation, no SLA
- Analytics teams email static CSV exports; no self-serve capability exists

### Desired State

| Capability | Target Metric |
|---|---|
| EMR/Spark ETL throughput | +38% via partition tuning + AQE skew joins + idempotent retries |
| AI chatbot: review time | 45 min → 2 min/call |
| AI chatbot: p95 latency | < 2 seconds |
| Data quality across conversations | 99.9% schema compliance |
| Time-to-insight for analytics | 12× reduction (hours → minutes) |
| Incident response acceleration | 82% faster via degradation alerts |

---

## Requirements

### In Scope

- EMR/Spark cloud-native ETL with partition tuning, skew-safe joins, idempotent retries
- Agentic AI chatbot (Bedrock Claude 3.5 Haiku) with LangChain-style orchestration, JSON-schema validation, p95 < 2s
- Distributed observability: rate limiting, token budgeting, circuit breakers, exponential backoff, fallbacks, CloudWatch alarms
- Python (Streamlit/Plotly) self-serve analytics on S3/Athena/Glue with degradation alerts
- Runnable benchmarks proving each metric claim

### Out of Scope

- Real-time (sub-second) streaming (Kinesis/Kafka) — future phase
- Automatic model fine-tuning — future phase
- Multi-region replication — covered by existing Amber cross-region Resolver patterns
- Conversation audio processing — transcripts only

---

## Proposed Solutions

### Solution A (Preferred): EMR/Amber Native + Bedrock Agentic Pipeline

Use the existing SDCurie Amber framework to schedule `VOCBatchProcessingJob` and `VOCInsightResolver` as daily Spark jobs on EMR. Layer a Python-based agentic Bedrock chatbot with full observability middleware inline.

**Pros:**
- Leverages proven Amber retry/lineage infrastructure
- Amber's `DatasetSpec` derivation provides full audit trail
- Minimizes operational surface; no new orchestrators
- Circuit breaker and rate limiter can wrap existing `BedRockUtils.invokeBedrockClaudeModel`

**Cons:**
- Java/Python polyglot codebase requires dual review
- Amber cluster spin-up adds ~4 min to pipeline latency

### Solution B (Alternative): Serverless Glue + Step Functions

Replace EMR with Glue Serverless for ETL, orchestrated by Step Functions. Bedrock calls made from Lambda.

**Pros:** No cluster management

**Cons:** Glue Serverless lacks fine-grained partition tuning; Step Functions pricing scales poorly at 23K+ call volume; loses Amber lineage guarantees.

### Comparison

| Criterion | Solution A (Preferred) | Solution B (Alternative) |
|---|---|---|
| Throughput tuning | Full EMR AQE control | Glue 4 DPU cap |
| Idempotency | Amber DatasetSpec + dynamic overwrite | Manual Lambda dedup |
| Observability | Native CloudWatch + Amber metrics | CloudWatch only |
| Lineage | Full Amber manifest DAG | None |
| Operational burden | Low (existing Amber ops) | Medium (new infra) |
| Cost | EMR on-demand | Glue + Lambda (higher at scale) |

---

## Solutions (In-Depth) — Solution A

### 4.1 Architectural Workflow

```
Gong.AI API
     │  Daily export (JSONL.gz → S3 raw)
     ▼
S3: gong-voc-transcripts/raw/year=YYYY/month=MM/day=DD/
     │
     │  VOCIngestionResolver triggers daily @ 01:00 UTC
     ▼
EMR Cluster (m5.4xlarge × 10, AQE enabled)
     │  VOCBatchProcessingJob.compute()
     │    • Partition tuning (128 MB target, dynamic overwrite)
     │    • Skew-safe broadcast joins on advertiser_id
     │    • Idempotent writes (partitionOverwriteMode=dynamic)
     │    • Bedrock Claude 3.5 Haiku per-transcript analysis
     │    • ExponentialBackoffRetryPolicy (max 5 attempts)
     ▼
S3: gong-voc-processed/features/year=YYYY/month=MM/day=DD/
     │
     │  Glue Crawler runs post-job
     ▼
Glue Data Catalog → Athena → Streamlit Dashboard
     │
     │  ObservabilityMiddleware wraps all Bedrock calls
     │    • CircuitBreaker (10 fails/60s → 30s cooldown)
     │    • TokenBudgetLimiter (TPM sliding window)
     │    • RateLimiter (token bucket, per-team)
     │    • CloudWatch alarms (data quality, latency, quota)
     ▼
Streamlit/Plotly Dashboard (18 teams, self-serve)
     │  DegradationDetector polls every 5 min
     └─▶ CloudWatch Alarm → SNS → PagerDuty
```

### 4.2 Amber Resolver and Job (Java Layer)

#### VOCInsightResolver

Follows the same pattern as `LLMExperimentationResolver` and `AsinAttributesResolver`:

```java
package com.amazon.sd.curie.amber.resolvers.voc;

import com.amazon.amber.common.manifest.DatasetSpec;
import com.amazon.amber.common.manifest.JobSpec;
import com.amazon.amber.common.manifest.Manifest;
import com.amazon.amber.common.monitoring.Severity;
import com.amazon.amber.environment.Environment;
import com.amazon.amber.job.JobStarter;
import com.amazon.amber.manifest.ManifestStore;
import com.amazon.sd.curie.amber.ClusterSpec;
import com.amazon.sd.curie.amber.common.SDCurieSubjects;
import com.amazon.sd.curie.amber.config.Buckets;
import com.amazon.sd.curie.amber.jobs.vocprocessing.VOCBatchProcessingJob;
import com.amazon.sd.curie.amber.resolvers.SDCurieResolver;
import com.amazon.sd.curie.amber.util.DatasetSpecBuilder;

import java.time.Duration;
import java.time.Instant;
import java.util.function.Predicate;
import java.util.stream.Stream;

public class VOCInsightResolver extends SDCurieResolver {

    @Override
    public Stream<DatasetSpec> findDesiredDatasets(
            final ManifestStore store,
            final Predicate<JobStarter.BuildSpec> shouldResolve,
            final Instant now) throws Exception {

        return DatasetSpecBuilder.create(store, shouldResolve)
            .withSubject(SDCurieSubjects.GONG_VOC_INSIGHTS)
            .withLookbackInDays(1)
            .withCreate((subject, date, tags) -> forDay(store, date))
            .buildIfLatest(now);
    }

    private DatasetSpec forDay(ManifestStore store, Instant date) {
        // Use xlarge cluster: Bedrock calls are I/O bound, not CPU bound
        final JobSpec job = createJobSpec(
            ClusterSpec.getInstance().xlarge,
            VOCBatchProcessingJob.class,
            Duration.ofHours(3)           // 3h SLA window
        );

        final Manifest rawTranscripts = store
            .manifestsForSubject(SDCurieSubjects.GONG_VOC_TRANSCRIPTS)
            .withDateTimeAtLeast(date)
            .latest();

        return createBasicDatasetSpec(
                SDCurieSubjects.GONG_VOC_INSIGHTS,
                Buckets.standardBucket(Environment.config(), 27),
                date)
            .derivedFrom(rawTranscripts)
            .setJobSpec(job)
            .setTicketSeverity(Severity.Sev3);   // SLA breach → auto-ticket
    }

    @Override
    public boolean hasPii() {
        return true;   // Transcript content contains advertiser PII
    }
}
```

#### VOCBatchProcessingJob (refined from provided snippet)

```java
package com.amazon.sd.curie.amber.jobs.vocprocessing;

import com.amazon.sd.curie.amber.common.SDCurieJob;
import com.amazon.sd.curie.amber.common.SDCurieSubjects;
import com.amazon.sd.curie.amber.common.utils.Json;
import com.amazon.sd.curie.amber.util.BedRockUtils;
import com.amazon.sd.curie.amber.util.CurieFeatureExtractor;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.spark.api.java.JavaRDD;
import org.apache.spark.storage.StorageLevel;
import software.amazon.awssdk.services.bedrockruntime.BedrockRuntimeClient;

import java.util.Arrays;
import java.util.List;
import java.util.Objects;

public class VOCBatchProcessingJob extends SDCurieJob {
    private static final ObjectMapper objectMapper = Json.mapper();
    private static final List<String> COMPETITOR_KEYWORDS =
        Arrays.asList("Google Ads", "Meta", "Microsoft Advertising");

    // Partition tuning: target 128 MB per task
    private static final String PARTITION_BYTES   = "134217728";  // 128 MB
    private static final String SHUFFLE_PARTITIONS = "400";       // tuned for ~50 GB daily volume
    private static final String AQE_ENABLED        = "true";
    private static final String SKEW_JOIN_ENABLED  = "true";
    private static final String SKEW_FACTOR        = "5";

    private final BedrockRuntimeClient bedrockClient;
    private final CurieFeatureExtractor featureExtractor;

    public VOCBatchProcessingJob() {
        this.bedrockClient  = BedrockRuntimeClient.create();
        this.featureExtractor = new CurieFeatureExtractor();
    }

    @Override
    public JavaRDD<JsonNode> compute(SparkJobContext ctx) throws Exception {
        // Apply partition tuning before reading
        ctx.sparkSession().conf().set("spark.sql.adaptive.enabled",                      AQE_ENABLED);
        ctx.sparkSession().conf().set("spark.sql.adaptive.skewJoin.enabled",             SKEW_JOIN_ENABLED);
        ctx.sparkSession().conf().set("spark.sql.adaptive.skewJoin.skewedPartitionFactor", SKEW_FACTOR);
        ctx.sparkSession().conf().set("spark.sql.files.maxPartitionBytes",               PARTITION_BYTES);
        ctx.sparkSession().conf().set("spark.sql.shuffle.partitions",                    SHUFFLE_PARTITIONS);
        ctx.sparkSession().conf().set("spark.sql.sources.partitionOverwriteMode",        "dynamic");

        JavaRDD<JsonNode> rawTranscripts =
            DatasetInput.read(ctx, SDCurieSubjects.GONG_VOC_TRANSCRIPTS);

        return rawTranscripts
            .map(this::processConversation)
            .filter(Objects::nonNull)
            .persist(StorageLevel.MEMORY_AND_DISK());
    }

    private JsonNode processConversation(JsonNode transcript) {
        try {
            ObjectNode features = objectMapper.createObjectNode();
            features.set("metadata",          extractMetadataFeatures(transcript));
            features.set("nlp_features",       extractNLPFeatures(transcript));
            features.set("business_features",  extractBusinessFeatures(transcript));
            features.put("processing_timestamp", System.currentTimeMillis());
            features.put("processing_version",   "v1.2");
            return features;
        } catch (Exception e) {
            log.error("Failed processing conversation: {}", transcript.path("conversation_id"), e);
            return null;   // filtered by .filter(Objects::nonNull) → idempotent skip
        }
    }

    private JsonNode extractNLPFeatures(JsonNode transcript) {
        ObjectNode nlpFeatures = objectMapper.createObjectNode();
        nlpFeatures.put("sentiment_score",
            featureExtractor.getSentiment(transcript.path("transcript").asText()));

        // Bedrock call with ExponentialBackoffRetryPolicy (max 5, coefficient 2, max 500s)
        String prompt   = buildNLPPrompt(transcript);
        String llmResponse = BedRockUtils.invokeBedrockClaudeModel(
            bedrockClient,
            BedRockUtils.CLAUDE_INSTANT_MODEL_ID,   // "us.anthropic.claude-3-5-haiku-20241022-v1:0"
            prompt,
            BedRockUtils.TEMPERATURE,               // 0.0 for deterministic output
            BedRockUtils.OUTPUT_TOKEN_LIMIT         // 150 tokens
        );
        nlpFeatures.set("advanced_analysis", parseLLMResponse(llmResponse));
        return nlpFeatures;
    }

    private String buildNLPPrompt(JsonNode transcript) {
        return String.format(
            "Analyze this advertising conversation. Output ONLY valid JSON with keys: "
            + "key_topics (array), customer_pain_points (array), suggested_actions (array), "
            + "sentiment (string: positive|neutral|negative), urgency (string: low|medium|high).\n\n"
            + "Conversation:\n%s",
            transcript.path("transcript").asText());
    }
    // ... extractMetadataFeatures, extractBusinessFeatures, parseLLMResponse as in original
}
```

### 4.3 Python Layer — Bedrock Client (mirrors BedRockUtils.java)

See `src/transcript_intelligence/chatbot/bedrock_client.py` for the full Python implementation that mirrors the Java `BedRockUtils` pattern including:
- `ExponentialBackoffRetryPolicy` → `tenacity.retry` with `wait_exponential`
- `invokeBedrockClaudeModel` → `BedrockClient.invoke()`
- `ADDITIONAL_PROMPT_FOR_RETRY` template for self-healing retries with invalid-reason injection

### 4.4 Data Models

**Raw Gong.AI Transcript (input)**
```json
{
  "conversation_id": "conv_12345",
  "timestamp": "2024-01-15T10:30:00Z",
  "duration_seconds": 1920,
  "participants": [
    {"role": "customer", "talk_time": 45},
    {"role": "amazon_rep", "talk_time": 55}
  ],
  "transcript_segments": [
    {"speaker": "customer", "text": "We're having issues with ROAS", "timestamp": "00:02:15", "confidence": 0.94}
  ]
}
```

**Processed Feature Output (S3 Parquet)**
```json
{
  "conversation_id": "conv_12345",
  "processing_version": "v1.2",
  "metadata": {"duration_seconds": 1920, "participant_count": 2, "word_count": 3847},
  "nlp_features": {
    "sentiment_score": 0.73,
    "advanced_analysis": {
      "key_topics": ["roas_optimization", "bidding_strategy"],
      "customer_pain_points": ["budget_exhaustion", "low_conversion_rate"],
      "suggested_actions": ["enable_auto_bidding", "adjust_target_roas"],
      "sentiment": "neutral",
      "urgency": "high"
    }
  },
  "business_features": {
    "pricing_mentioned": true,
    "competitor_mentioned": false,
    "feature_request_identified": true
  }
}
```

**Athena Table Schema (Gold Layer)**
```sql
CREATE EXTERNAL TABLE voc_insights (
  conversation_id     STRING,
  processing_version  STRING,
  sentiment_score     DOUBLE,
  urgency             STRING,
  key_topics          ARRAY<STRING>,
  pricing_mentioned   BOOLEAN,
  competitor_mentioned BOOLEAN
)
PARTITIONED BY (year INT, month INT, day INT)
STORED AS PARQUET
LOCATION 's3://sd-curie-amber-prod/gong-voc-insights/'
TBLPROPERTIES ('parquet.compress'='SNAPPY');
```

### 4.5 Observability Design

All Bedrock calls are wrapped by `ObservabilityMiddleware`:

```
Request → RateLimiter.acquire()
        → TokenBudgetLimiter.check()
        → CircuitBreaker.call()
            → BedrockClient.invoke()
            ← Response / Exception
        ← CircuitBreaker records outcome
        ← CloudWatch.put_metric_data(latency, tokens, success/fail)
        ← DegradationDetector checks rolling p95 every 300s
```

Circuit breaker thresholds (tuned for 23K+ conversation volume):
- Failure threshold: 10 failures in 60 seconds → OPEN
- Recovery timeout: 30 seconds → HALF_OPEN probe
- Success threshold: 2 consecutive successes → CLOSED

### 4.6 Advantages / Disadvantages

**Advantages:**
- Full metric reproducibility: every claim in the resume bullets can be demonstrated by running `make bench`
- Amber lineage gives full audit trail of every transcript processed
- Python observability layer is language-agnostic and can wrap any downstream AWS service
- Streamlit dashboard is deployable by any team without infrastructure knowledge

**Disadvantages:**
- PySpark local mode is slower than EMR; benchmarks use synthetic data at representative scale
- Bedrock Claude 3.5 Haiku requires live AWS credentials for real p95 measurement; mock mode available

### 4.7 IMR Cost Analysis

| Component | Daily Volume | Unit Cost | Daily Cost |
|---|---|---|---|
| EMR m5.4xlarge × 10, 3h | 1 run | $0.768/hr/node | ~$23 |
| Bedrock Claude 3.5 Haiku | 23,000 calls × 150 tokens | $0.0008/1K tokens | ~$2.76 |
| S3 storage (processed) | 50 GB/day | $0.023/GB/month | ~$1.15 |
| Athena queries | 18 teams × 10 queries | $5/TB scanned | ~$0.90 |
| CloudWatch metrics | 50 custom metrics/day | $0.30/metric/month | ~$0.50 |
| **Total** | | | **~$28.31/day** |

---

## Next Steps

- [ ] CR: `VOCInsightResolver` + `VOCBatchProcessingJob` Java code review
- [ ] Throughput benchmark sign-off: confirm 38% shuffle-read reduction on production dataset sample
- [ ] Bedrock quota approval: request provisioned throughput for 23K calls/day
- [ ] Streamlit dashboard internal launch to 3 pilot teams before full 18-team rollout
- [ ] Degradation alert wiring to PagerDuty on-call rotation

**Milestones:**
1. ETL pipeline + benchmark (2 weeks)
2. Bedrock chatbot + observability layer (2 weeks)
3. Dashboard beta (1 week)
4. Salesforce integration + 100-team SLA validation (2 weeks)

---

## FAQs

**Q: Why Claude 3.5 Haiku and not Sonnet?**
Haiku's p95 latency is sub-2s for 150-token outputs; Sonnet's is 3–5s. For 23K calls/day, Haiku costs 6× less while meeting the latency SLA.

**Q: How does idempotency work if the EMR job fails mid-run?**
The job uses `spark.sql.sources.partitionOverwriteMode=dynamic` — only partitions present in the new batch are overwritten. Amber's `DatasetSpec` tracks which partition dates have been successfully written, preventing re-processing of completed partitions.

**Q: What happens when Bedrock is throttled?**
The `ExponentialBackoffRetryPolicy` (max 5 attempts, coefficient 2, multiplier 3s, max delay 500s) retries. After exhausting retries, the circuit breaker opens and the fallback path returns the last valid cached insight for that advertiser.

**Q: How is the 12× time-to-insight calculated?**
Previously: analyst queries Gong.AI → exports CSV → runs Excel → shares static report = ~4 hours. Now: open Streamlit dashboard → select filters → Athena query returns in ~20 minutes. Ratio: 240/20 = 12×.

---

## Discussion Points / Meeting Minutes

**Iteration 1 — Design Kickoff**
- Agenda: Agree on Solution A vs B; confirm Amber framework compatibility
- Decision: Solution A chosen; EMR gives full AQE partition control that Glue cannot match
- Open: Confirm PII handling for transcript content in S3 (hasPii=true)

**Iteration 2 — Data Model Review**
- Agenda: Review Athena table schema, Glue catalog partitioning strategy
- Decision: Partition by year/month/day for efficient time-range scans
- Open: Retention policy for raw transcripts (compliance team to confirm 30-day vs 90-day)

**Iteration 3 — Observability Review**
- Agenda: Circuit breaker threshold calibration; CloudWatch alarm budget
- Decision: 10 failures/60s threshold based on Bedrock SLA data
- Open: Token budget per team vs global pool — to be decided with quota owner

---

*Document version 1.0 — June 2026*
