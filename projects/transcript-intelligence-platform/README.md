# Transcript Intelligence Platform

A cloud‑native, end‑to‑end platform for processing advertiser call transcripts, summarizing
them with an agentic LLM, guarding the pipeline with production‑grade resilience, and serving
self‑serve analytics. It is a **single project that implements every technology and pattern**
referenced across four resume bullet points, with **reproducible benchmarks** for the
headline engineering metrics.

> **Read [`docs/METRICS.md`](docs/METRICS.md) first.** It explains, claim‑by‑claim, which numbers
> are produced by a runnable benchmark in this repo (real, reproducible) and which are
> *synthetic / illustrative scale scenarios* (demonstration data volumes, **not** a claim of
> real‑world production adoption or revenue). The project is designed to be honest under
> technical scrutiny.

---

## The four pillars

| # | Pillar | Tech | Lives in |
|---|--------|------|----------|
| 1 | **EMR/Spark ETL** for advertiser transcripts — partition tuning, skew‑safe joins, idempotent retries, daily SLA for 100+ tenant teams | PySpark, EMR (Terraform) | [`services/etl_spark`](services/etl_spark) |
| 2 | **Agentic AI chatbot** — Amazon Bedrock (Claude 3.5 Haiku), LangChain‑style orchestration, prompt engineering, JSON‑schema validation, p95 < 2s | Python, Bedrock, FastAPI | [`services/agent_chatbot`](services/agent_chatbot) |
| 3 | **Distributed observability** — rate limiting, token budgeting, circuit breakers, backoff, fallbacks, CloudWatch alarms, 99.9% data quality | Python, CloudWatch (Terraform) | [`services/observability`](services/observability) |
| 4 | **Self‑serve analytics** — Streamlit/Plotly on S3/Athena/Glue, degradation alerts, 12× time‑to‑insight | Streamlit, Plotly, Athena/Glue | [`services/analytics_dashboard`](services/analytics_dashboard) |

Together they form one logical system:

```
                        ┌──────────────────────────────────────────────────────────┐
   raw transcripts ───► │ (1) EMR/Spark ETL  ──►  curated Parquet on S3 (Glue table) │
   (S3 landing)         └───────────────┬──────────────────────────┬────────────────┘
                                        │                           │
                          per‑call text │                           │ curated facts
                                        ▼                           ▼
                        ┌───────────────────────────┐   ┌──────────────────────────┐
                        │ (2) Bedrock agent chatbot  │   │ (4) Streamlit/Plotly      │
                        │     summarize + extract    │   │     analytics on Athena   │
                        └─────────────┬──────────────┘   └──────────────────────────┘
                                      │ every external call wrapped by
                                      ▼
                        ┌───────────────────────────────────────────┐
                        │ (3) Observability: rate limit / token       │
                        │     budget / circuit breaker / backoff /    │
                        │     fallback / CloudWatch alarms / DQ checks│
                        └─────────────────────────────────────────────┘
```

---

## Quick start

```bash
cd projects/transcript-intelligence-platform
make install          # create venv + install all service deps
make data             # generate synthetic transcripts (default 23,000+ conversations, 100+ tenants)
make test             # run the full unit-test suite across all services
make bench            # run every benchmark and regenerate docs/results/*.json
make dashboard        # launch the Streamlit analytics app on http://localhost:8501
```

Everything runs **locally** with no AWS account required (LLM and Athena/Glue calls fall back to
faithful local mocks). The same code paths target real AWS via the Terraform in each service's
`infra/` folder.

## Repository layout

```
transcript-intelligence-platform/
├── platform_common/        # shared structured logging, config, synthetic data model
├── services/
│   ├── etl_spark/          # Pillar 1
│   ├── agent_chatbot/      # Pillar 2
│   ├── observability/      # Pillar 3
│   └── analytics_dashboard/# Pillar 4
├── scripts/                # data generation + end-to-end runners
├── docs/                   # METRICS.md, ARCHITECTURE.md, results/
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

## License

MIT — see [`LICENSE`](LICENSE).
