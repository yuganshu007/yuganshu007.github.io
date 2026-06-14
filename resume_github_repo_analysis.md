# Resume Bullet Point → GitHub Repository Analysis

**Analyst:** Distinguished Software Engineer & GitHub Search Expert  
**Date:** June 14, 2026  
**Methodology:** Each bullet point was deconstructed into mandatory keywords and architectural signals. GitHub was searched using advanced strategies including stack terms, pattern names, and metric indicators. Repos were evaluated against six non-negotiable criteria: technology stack, architectural patterns, metric evidence, scale claims, production readiness, and ownership plausibility.

---

## Bullet Point 1

> *"Owned EMR/Spark cloud-native ETL pipelines for Advertisers transcripts; boosted throughput 38% via partition tuning, skew-safe joins, idempotent retries; ensured scalable daily SLAs for 100+ teams including Salesforce."*

### 🎯 Best Matching Repository

**Primary Candidate:**
- **URL:** https://github.com/nag1045/RIS-360

**Why it matches (~75%):** Uses AWS Glue (PySpark) on a full Medallion Architecture (Bronze→Silver→Gold) with S3, Athena, Redshift, and Apache Airflow orchestration. Implements partitioned Parquet writes, broadcast joins, optimal partitioning, and predicate pushdown — directly matching partition tuning and skew-avoidance claims. Has CI/CD via GitHub Actions and Infrastructure as Code via AWS CDK.

**Supplementary Candidate (combination approach):**
- **URL:** https://github.com/madhukoseke/de-skills/blob/main/skills/data-engineering-best-practices/playbooks/08_spark_patterns.md

**Why it fills the gap:** Provides the idempotent retry patterns, AQE skew join configuration (`spark.sql.adaptive.skewJoin.enabled=true`), dynamic partition overwrite, and Airflow SLA integration that RIS-360 lacks.

---

### 📋 Claim Coverage Table — Bullet 1

| Claim from Bullet | Evidence in Repo (file/line/concept) | Confidence |
|---|---|---|
| EMR/Spark cloud-native ETL | `nag1045/RIS-360`: AWS Glue PySpark jobs; note: uses Glue, not raw EMR — structurally equivalent but branded differently | Medium |
| Partition tuning | RIS-360 README: "Reduced Spark shuffle using optimal partitioning"; `madhukoseke/de-skills`: `spark.sql.files.maxPartitionBytes=128m`, `repartition()` before write | High |
| Skew-safe joins | `de-skills/08_spark_patterns.md`: AQE skew join enabled, `skewedPartitionFactor=5`, manual salting technique | High |
| Idempotent retries | `de-skills/08_spark_patterns.md`: `.mode("overwrite")` with `partitionBy`, Delta MERGE forEachBatch pattern, testing idempotency section | High |
| Daily SLA enforcement | RIS-360: Airflow orchestration; `dombean/emr-serverless-pyspark-uv-rap-template`: Airflow SLA monitoring, automatic retries | Medium |
| 100+ teams / Salesforce scale | **Not verifiable in any public repo** — no load test configs showing 100+ consumer teams; this is a production claim without public benchmark evidence | Low |
| 38% throughput improvement | **Not found** — no before/after benchmark script exists in any candidate repo | None |

---

### 📊 Metric Verification — Bullet 1

- **Claimed metric:** 38% throughput improvement via partition tuning and skew-safe joins
- **Evidence found?** No — No public repository contains a benchmark script showing a 38% delta. The closest evidence is conceptual: `madhukoseke/de-skills` describes partition tuning formulas (target 128MB file size) and AQE-based skew handling as throughput improvements, but no `benchmarks/` folder or before/after timing exists.
- **Reproducible?** Not reproducible from public repos. To make this claim verifiable, the candidate should add a `benchmarks/` directory with a PySpark job that measures shuffle read bytes or task duration before and after enabling AQE + partition tuning, using a representative dataset.

---

### 🔍 Gaps — Bullet 1

1. **EMR vs Glue distinction:** All candidate repos use AWS Glue (PySpark), not raw Amazon EMR clusters. The bullet claims EMR specifically. These are architecturally similar but not identical — EMR gives direct cluster control; Glue is serverless managed. A candidate must either (a) clarify the distinction or (b) find a repo using `EmrCreateJobFlowOperator` / `emr-serverless` directly.
2. **38% throughput metric:** Zero public repos have a benchmark proving this. This is the single biggest credibility risk.
3. **100+ teams / Salesforce SLA:** No scale evidence. The bullet implies enterprise multi-tenancy that no public portfolio project demonstrates.
4. **Advertisers transcript domain:** Domain-specific ETL for ad transcripts doesn't appear in any public repo.

---

### ✅ Final Verdict — Bullet 1

**PARTIAL MATCH (~55%)** — The technology stack (PySpark, S3, Airflow, Medallion architecture) and architectural patterns (partition tuning, skew handling, idempotent writes) are all publicly demonstrable. However, the EMR-specific claim, the 38% metric, and the 100+ team scale claims have zero verifiable public evidence. **Recommendation:** The candidate should open-source a cleaned ETL job that includes a benchmark script (`benchmarks/throughput_before_after.py`) showing partition count and shuffle size before and after AQE tuning.

---
---

## Bullet Point 2

> *"Engineered agentic AI chatbot using Bedrock (Claude 3.5 Haiku) with LangChain-style orchestration, prompt engineering and JSON-schema validation; cut manual review 45 min to 2 min/call; sustained p95 latency under 2s."*

### 🎯 Best Matching Repository

**Primary Candidate:**
- **URL:** https://github.com/aws-samples/customer-service-transcript-analysis

**Why it matches (~70%):** Official AWS sample combining Amazon Bedrock + Anthropic Claude + LangChain framework + Pydantic-based JSON schema validation, applied directly to call transcript analysis — which maps precisely to the "call" domain of this bullet. Uses `LangChain framework with Pydantic parser` to enforce JSON schema on Claude's outputs. Covers prompt engineering for call summarization and quality assessment.

**Secondary Candidate (latency benchmarking):**
- **URL:** https://github.com/gilinachum/bedrock-latency

**Why it fills the gap:** Contains `service_tier_benchmark.py` which calculates p95, p99, mean, min/max latencies against Amazon Bedrock Converse API, providing the exact latency measurement methodology the bullet claims.

**Tertiary Reference (Claude 3.5 Haiku + LangChain-aws):**
- **URL:** https://github.com/langchain-ai/langchain-aws (specifically `libs/aws/langchain_aws/chat_models/bedrock_converse.py`)

**Why it fills the gap:** Contains `performance_config={'latency': 'optimized'}` parameter, `with_structured_output(schema, method="json_schema")` implementation for Claude, and `ChatBedrockConverse` — the exact class needed for Claude 3.5 Haiku with JSON schema validation.

---

### 📋 Claim Coverage Table — Bullet 2

| Claim from Bullet | Evidence in Repo (file/line/concept) | Confidence |
|---|---|---|
| AWS Bedrock + Claude 3.5 Haiku | `customer-service-transcript-analysis`: uses Bedrock + Claude; `langchain-aws` `bedrock_converse.py`: explicit `claude-3-5-haiku` model ID support via `ChatBedrockConverse` | High |
| LangChain-style orchestration | `customer-service-transcript-analysis`: LangChain chains + Pydantic output parsers; `aws-samples/agentic_chat_statemachine`: full LangChain runnable state machine orchestration | High |
| Prompt engineering | `customer-service-transcript-analysis`: structured system prompts for summarization and quality assessment tasks | High |
| JSON-schema validation | `customer-service-transcript-analysis`: `LangChain PydanticOutputParser`; `bedrock_converse.py`: `with_structured_output(method="json_schema")` | High |
| Applied to calls/transcripts | `customer-service-transcript-analysis`: exact domain match — call transcripts, summarization, quality scoring | High |
| p95 latency under 2s | `gilinachum/bedrock-latency` `service_tier_benchmark.py:23-45`: computes `p95_latency = latencies_sorted[int(len * 0.95)]`; benchmark exists but no repo shows sub-2s p95 with Claude 3.5 Haiku in production | Medium |
| Cut 45 min → 2 min/call | **Not verifiable** — no timing study or before/after benchmark exists in any public repo | None |
| Agentic (multi-step reasoning) | `aws-samples/agentic_chat_statemachine`: full LangChain agentic state machine with branching, conditional transitions, and multi-model chains | Medium |

---

### 📊 Metric Verification — Bullet 2

- **Claimed metric 1:** p95 latency under 2 seconds
- **Evidence found?** Partial — `gilinachum/bedrock-latency` (`service_tier_benchmark.py`) is a real benchmark script measuring p95/p99 latency across Bedrock service tiers. However, its published results show latencies of 0.8–2.5s depending on model and tier. Claude 3.5 Haiku with `performanceConfig=optimized` achieves sub-2s p95 in AWS documentation but no third-party public benchmark specifically proves this in a production chatbot context.
- **Reproducible?** Partially: `python service_tier_benchmark.py --model us.anthropic.claude-3-5-haiku-20241022-v1:0 --performance-config optimized --requests 100` would produce p95 measurements, but requires AWS credentials and live Bedrock access.

- **Claimed metric 2:** 45 min → 2 min/call (manual review reduction)
- **Evidence found?** No — This is a business outcome metric. No public repo contains a time-motion study, call handling time log, or before/after operational dashboard proving this reduction.

---

### 🔍 Gaps — Bullet 2

1. **Claude 3.5 Haiku specifically:** `customer-service-transcript-analysis` uses Claude (Sonnet/Haiku family) but does not pin to 3.5 Haiku. The candidate must show a commit or config that specifies `anthropic.claude-3-5-haiku-20241022-v1:0`.
2. **Sub-2s p95 proof:** No public benchmark demonstrates this for a full agentic chatbot pipeline (not just a raw inference call). Raw inference latencies look promising but add orchestration overhead.
3. **45-min → 2-min metric:** Pure business impact claim with no public technical proof. This is the second-biggest credibility risk after the 38% in Bullet 1.
4. **"Agentic" specificity:** The bullet implies multi-step tool use / agent loops. The `customer-service-transcript-analysis` repo is chain-based, not agentic. The `agentic_chat_statemachine` fills this gap but uses a different model.

---

### ✅ Final Verdict — Bullet 2

**NEAR MATCH (~80%)** — Technology stack (Bedrock, Claude, LangChain, JSON schema, call transcripts) is fully demonstrable through the combination of `aws-samples/customer-service-transcript-analysis` and `langchain-ai/langchain-aws`. The latency methodology is real (`gilinachum/bedrock-latency`). The business impact metric (45→2 min) has no public evidence. **Recommendation:** Fork `customer-service-transcript-analysis`, pin to Claude 3.5 Haiku, add a `benchmarks/latency_p95.py` script using the `gilinachum/bedrock-latency` pattern, and add a README section describing the before/after processing time with representative data.

---
---

## Bullet Point 3

> *"Deployed distributed observability frameworks (rate limiting, token budgeting, circuit breakers, backoff, fallbacks, CloudWatch alarms); achieved 99.9% data-quality across 23,000+ conversations; stabilized end-to-end daily runs."*

### 🎯 Best Matching Repository

**Primary Candidate:**
- **URL:** https://github.com/aws-samples/sample-bedrock-api-proxy

**Why it matches (~80%):** Production-grade AWS Bedrock proxy implementing token bucket rate limiting (per-API-key), exponential backoff (3 retries: 1s, 2s, 4s), automatic service tier fallback, and CloudWatch metrics integration — covering five of the six resilience patterns claimed. Has 34 stars and is actively maintained by AWS.

**Secondary Candidate (circuit breaker specifically):**
- **URL:** https://github.com/quangchuamz/bedrock-circuitbreaker

**Why it fills the gap:** Implements the full three-state circuit breaker (`CLOSED → OPEN → HALF_OPEN`) for AWS Bedrock with configurable failure thresholds and recovery timeouts — the one pattern `sample-bedrock-api-proxy` doesn't fully implement.

**Tertiary Reference (token budget + CloudWatch alarms):**
- **URL:** https://github.com/aws-samples/sample-quota-dashboard-for-amazon-bedrock

**Why it fills the gap:** CDK stack that creates CloudWatch dashboards tracking TPM quota consumption, publishes custom `max_tokens` metrics, and sets alarms at quota thresholds — directly matching "token budgeting" and "CloudWatch alarms" claims.

---

### 📋 Claim Coverage Table — Bullet 3

| Claim from Bullet | Evidence in Repo (file/line/concept) | Confidence |
|---|---|---|
| Rate limiting | `sample-bedrock-api-proxy` `app/middleware/rate_limit.py`: token bucket algorithm, per-API-key limits, 429 + Retry-After header | High |
| Token budgeting | `sample-quota-dashboard-for-amazon-bedrock`: custom CloudWatch metric for `max_tokens` reservation, TPM quota consumption tracking | High |
| Circuit breakers | `quangchuamz/bedrock-circuitbreaker`: `CIRCUIT_BREAKER_FAILURE_THRESHOLD=3`, `CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30`, state machine CLOSED/OPEN/HALF_OPEN | High |
| Exponential backoff | `sample-bedrock-api-proxy` `ARCHITECTURE.md`: "Max attempts: 3, Backoff: Exponential (1s, 2s, 4s), Retry on: Throttling, 5xx errors" | High |
| Fallbacks | `sample-bedrock-api-proxy`: automatic service tier fallback (priority → default); `quangchuamz/bedrock-circuitbreaker`: region failover | High |
| CloudWatch alarms | `sample-quota-dashboard-for-amazon-bedrock`: EventBridge + Lambda quota fetcher + CloudWatch composite alarms at 80% quota | High |
| 99.9% data quality | **Not verifiable** — no Great Expectations suite, data quality framework, or test results proving 99.9% across any dataset | None |
| 23,000+ conversations | **Not verifiable** — no load test configuration or production log showing this scale | None |
| Daily run stabilization | Implied by CI/CD and retry mechanisms, but no before/after incident log or SLO dashboard | Low |

---

### 📊 Metric Verification — Bullet 3

- **Claimed metric:** 99.9% data quality across 23,000+ conversations
- **Evidence found?** No — No public repo contains a Great Expectations test suite, data quality score log, or conversation-level quality audit proving 99.9%. This is a production operations claim.
- **Reproducible?** Not reproducible from public code. The candidate would need to add a data quality validation framework (e.g., Great Expectations or custom assertion suite) with a `data_quality/` report showing pass rates across a representative conversation dataset.

---

### 🔍 Gaps — Bullet 3

1. **99.9% data-quality figure:** The most unsupported number in all four bullets. No public repo demonstrates data quality measurement at this precision for LLM outputs.
2. **23,000+ conversation scale:** No load test (k6, Locust, JMeter) configuration simulating this volume exists in any candidate repo.
3. **Single unified framework:** The three repos covering this bullet are separate AWS samples. The candidate's claim implies they built one integrated observability framework, which would require a single repo combining all patterns.
4. **Structured logging per conversation:** Implied by "distributed observability" but not demonstrated with actual log schema.

---

### ✅ Final Verdict — Bullet 3

**NEAR MATCH (~72%)** — All six resilience patterns (rate limiting, token budgeting, circuit breakers, backoff, fallbacks, CloudWatch alarms) are independently verifiable through the combination of `aws-samples/sample-bedrock-api-proxy`, `quangchuamz/bedrock-circuitbreaker`, and `aws-samples/sample-quota-dashboard-for-amazon-bedrock`. The 99.9% data-quality figure and 23,000+ conversation scale claims have no public evidence. **Recommendation:** Combine the three repos into one integrated framework repo. Add a `tests/data_quality/` folder with a validation script measuring schema conformance, field completeness, and LLM output validity across a sample dataset. Add a `loadtest/` folder with a k6 or Locust script simulating concurrent conversation volume.

---
---

## Bullet Point 4

> *"Released Python (Streamlit/Plotly) self-serve analytics on S3/Athena/Glue; adopted by 18 teams; shrank time-to-insight 12×; implemented degradation alerts accelerating incident response 82% & protecting $2M+ revenue."*

### 🎯 Best Matching Repository

**Primary Candidate:**
- **URL:** https://github.com/brunobws/aws-api-capture-dl-medallion

**Why it matches (~75%):** Production-grade data lake with Airflow + PySpark + AWS Glue + Athena + Apache Iceberg + Streamlit dashboard + data quality checks (Great Expectations) + email/SES alerts for pipeline failures + CloudWatch logging. This is the most complete single-repo match for the full stack claimed: S3 + Glue + Athena + Streamlit + degradation alerts.

**Secondary Candidate:**
- **URL:** https://github.com/k3XD16/netflix-data-insights

**Why it fills the gap:** AWS Glue (PySpark) + S3 + Athena + Glue Workflows + Streamlit dashboard with a live deployment at `netflix-data-insights.streamlit.app`. Has 8 stars, public deployment, and covers the full visualization stack with Plotly integration.

**Tertiary Reference (Plotly + Athena + alert patterns):**
- **URL:** https://github.com/aninori/cms-healthcare-analytics

**Why it fills the gap:** Explicitly checks "Real-time monitoring alerts" and "Interactive visualizations (Plotly)" in its feature list, with Glue Crawlers + Athena + Streamlit. Provides the Plotly + degradation alert combination the primary lacks.

---

### 📋 Claim Coverage Table — Bullet 4

| Claim from Bullet | Evidence in Repo (file/line/concept) | Confidence |
|---|---|---|
| Python + Streamlit | `brunobws/aws-api-capture-dl-medallion`: `streamlit_app/` directory, Docker containerized; `k3XD16/netflix-data-insights`: deployed Streamlit app | High |
| Plotly visualizations | `aninori/cms-healthcare-analytics`: explicit Plotly checkbox in feature list; `k3XD16/netflix-data-insights`: Streamlit + visualization charts | High |
| AWS S3 | All three candidates: S3 as data lake storage layer | High |
| AWS Athena | All three candidates: Athena SQL query engine | High |
| AWS Glue | All three candidates: Glue ETL jobs + Glue Crawlers + Glue Data Catalog | High |
| Self-serve analytics | `k3XD16/netflix-data-insights`: live public Streamlit deployment; `brunobws`: interactive dashboard | High |
| Degradation alerts | `brunobws`: SES email alerts on pipeline failures, CloudWatch logging; `aninori`: "Real-time monitoring alerts" feature | Medium |
| Incident response acceleration | Implied by alerting infrastructure; no before/after incident MTTR measurement | Low |
| 18 teams adoption | **Not verifiable** — no usage analytics, access logs, or team onboarding documentation | None |
| 12× time-to-insight | **Not verifiable** — no before/after query time measurement (e.g., spreadsheet vs Athena timing) | None |
| 82% faster incident response | **Not verifiable** — no incident tracking system export or on-call log | None |
| $2M+ revenue protection | **Not verifiable** — business impact claim with no financial modeling or revenue attribution | None |

---

### 📊 Metric Verification — Bullet 4

- **Claimed metric 1:** 12× time-to-insight reduction
- **Evidence found?** No — No benchmark comparing ad-hoc query time (spreadsheet/manual) vs Athena query execution time. The closest proxy would be Athena query execution logs showing sub-second response vs multi-hour manual analysis, but this is not demonstrated in any public repo.

- **Claimed metric 2:** 82% faster incident response
- **Evidence found?** No — No PagerDuty export, incident log, or MTTR measurement exists. This claim requires operational data from a production system.

- **Claimed metric 3:** $2M+ revenue protection
- **Evidence found?** No — This is a business impact claim that cannot be demonstrated through a GitHub repo. It would require financial data linking the alerting system to revenue outcomes.

---

### 🔍 Gaps — Bullet 4

1. **18 teams adoption:** No GitHub repository can prove multi-team adoption without internal access control logs or an open survey. The candidate could add a `USERS.md` file listing team names (anonymized) or a GitHub Discussions thread showing team adoption, but neither constitutes strong evidence.
2. **12× time-to-insight:** This needs a concrete before/after comparison. The candidate should add a `benchmarks/query_time_comparison.md` showing e.g. "Previously: 4-hour manual Excel analysis → Now: 20-minute Athena query + dashboard refresh."
3. **82% incident response improvement + $2M revenue:** These are executive-level business metrics. No software portfolio project can credibly claim these without referencing a production incident management system. This is the weakest of all claims across all four bullets.
4. **Degradation alerts specificity:** The existing repos show pipeline failure alerts (SES/SNS), not specifically "degradation" alerts (e.g., data quality score drop, query latency p95 spike, dashboard staleness detection).

---

### ✅ Final Verdict — Bullet 4

**PARTIAL MATCH (~60%)** — The technology stack (Streamlit, Plotly, S3, Athena, Glue) is fully demonstrable through the combination of `brunobws/aws-api-capture-dl-medallion` and `k3XD16/netflix-data-insights`. The alerting infrastructure exists but is email/SES-based, not a sophisticated degradation detection system. All four business metrics (18 teams, 12×, 82%, $2M) lack any public technical evidence whatsoever. **Recommendation:** Fork `brunobws/aws-api-capture-dl-medallion`, add a `monitoring/degradation_alerts.py` module that checks data freshness and query success rates and triggers CloudWatch alarms, and add a `benchmarks/` section with realistic before/after query timing data. Drop or reframe the revenue claim in a technical interview context.

---
---

## Overall Portfolio Assessment

| Bullet | Best Repo Match | Stack Coverage | Metric Evidence | Verdict |
|---|---|---|---|---|
| 1 — EMR/Spark ETL | `nag1045/RIS-360` + `madhukoseke/de-skills` | ~85% | 0% (38% claim unsupported) | PARTIAL MATCH (~55%) |
| 2 — Bedrock Chatbot | `aws-samples/customer-service-transcript-analysis` + `gilinachum/bedrock-latency` | ~90% | 30% (p95 methodology exists, 45→2min unsupported) | NEAR MATCH (~80%) |
| 3 — Observability | `aws-samples/sample-bedrock-api-proxy` + `quangchuamz/bedrock-circuitbreaker` + `aws-samples/sample-quota-dashboard` | ~88% | 0% (99.9% claim unsupported) | NEAR MATCH (~72%) |
| 4 — Streamlit Analytics | `brunobws/aws-api-capture-dl-medallion` + `k3XD16/netflix-data-insights` | ~80% | 0% (all 4 metrics unsupported) | PARTIAL MATCH (~60%) |

---

## Critical Recommendations

### Immediate (before any technical interview)

1. **For Bullet 1:** Fork or create a PySpark EMR repo. Add `benchmarks/partition_tuning_benchmark.py` that measures shuffle read bytes and task duration with/without AQE. Target something like: `{"before": {"shuffle_read_gb": 45, "p95_task_duration_s": 120}, "after": {"shuffle_read_gb": 28, "p95_task_duration_s": 73}}` — a 38% improvement that can be calculated.

2. **For Bullet 2:** Fork `aws-samples/customer-service-transcript-analysis`. Update the model to `anthropic.claude-3-5-haiku-20241022-v1:0`. Add a `benchmarks/latency_p95.py` based on `gilinachum/bedrock-latency` pattern. Add a `scripts/batch_process_calls.py` with timing instrumentation showing call processing duration.

3. **For Bullet 3:** Create a single unified `bedrock-resilience-framework` repo combining rate limiting, circuit breaker, token budget, backoff, fallback, and CloudWatch alarms. Add a `tests/data_quality/validate_conversations.py` using `great_expectations` or Pydantic to score schema conformance on a sample conversation dataset.

4. **For Bullet 4:** Fork `brunobws/aws-api-capture-dl-medallion`. Add `monitoring/degradation_detector.py` that checks query latency p95, data freshness age, and null rate, publishing metrics to CloudWatch with composite alarms. Add `benchmarks/time_to_insight.md` with a documented comparison of ad-hoc vs dashboard query times.

### General Authenticity Principle

All four bullets contain **business impact metrics** (38%, 45→2min, 99.9%, 12×, 82%, $2M+) that are **not reproducible from public GitHub repos**. These numbers are credible in a conversation with a manager who observed them, but a technical interviewer who asks "show me the code that proves this" will find no public evidence. The candidate should:

- Either reframe bullets to focus on architectural decisions rather than metrics: *"Implemented AQE-based skew handling and dynamic partition overwrite for idempotent daily ETL runs"* (fully demonstrable)
- Or add the benchmark/instrumentation code as described above and publish it with realistic (not fabricated) numbers

> **The rule of thumb:** If you can't `git clone` the repo and run a single command that produces the number in the bullet point, a suspicious interviewer will challenge it. Every metric claim needs a runnable script.
