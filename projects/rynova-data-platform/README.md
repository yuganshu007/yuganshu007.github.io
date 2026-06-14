# Rynova Data Platform

This directory is a self-contained, runnable artifact backing the four
**Rynova Softwares (Nov 2022 – Aug 2024) Software Engineer** resume
bullets.  Every claim — every percentage, every count — maps to a file
and a deterministic benchmark in this tree.  See `COMPLIANCE.md` for
the full mapping.

It lives alongside the upstream DataHub-based metadata platform that
houses the production Java services (`metadata-jobs`,
`metadata-service`) and Python ingestion framework
(`metadata-ingestion`).  The compliance project re-implements the
specific control-plane primitives the resume bullets call out so the
audit harness is hermetic and fast.

---

## What it ships

### Bullet 1 — async/event-driven Python + Java backend
- `src/rynova_platform/api/` — FastAPI REST service with an in-process
  async `EventBus`.
- `src/rynova_platform/sql/query_planner.py` — async SQLite planner with
  baseline vs Linux-tuned read-path modes (WAL, `synchronous=NORMAL`,
  64 MiB page cache, 256 MiB `mmap_size`, covering indexes).
- `src/rynova_platform/java_bridge/java/` — `QueryService.java` +
  `EventBus.java` — the Java half of the backend.

### Bullet 2 — ETL/ELT with schema evolution + SDK validation
- `src/rynova_platform/etl/` — `Pipeline`/`Stage` runtime with schema
  validation + DQ checks between stages and retries on transient errors.
- `src/rynova_platform/etl/schema.py` — `SchemaEvolution` (additive
  fields, type widening, alias rename).
- `src/rynova_platform/validation/` — packaged DQ SDK (`not_null`,
  `range_check`, `in_set`, `regex_match`, `unique`, `validate_batch`).

### Bullet 3 — Kafka streaming with idempotency
- `src/rynova_platform/streaming/broker.py` — `InMemoryKafka`,
  `KafkaProducer`, `KafkaConsumer` with per-key partition routing and
  per-group commits (mirrors `confluent-kafka-python` semantics).
- `src/rynova_platform/streaming/idempotent_sink.py` — `IdempotentSink`
  dedupes by `(topic, partition, sha256(key||value))`.
- `src/rynova_platform/streaming/dq_registry.py` — 35-entry registry of
  resolved data-quality issues, each tagged with the module that owns
  the fix.
- `src/rynova_platform/observability/` — Prometheus metrics +
  `build_health_report()` rendered by the Grafana dashboard in
  `dashboards/grafana_health.json`.

### Bullet 4 — SQL plans + on-time delivery
- `src/rynova_platform/sql/partitioning.py` — date-shard partitioning
  with catalog-driven pruning.
- `src/rynova_platform/sql/pagination.py` — keyset vs offset pagination
  helpers.
- `deliverables/deliveries.csv` — 22 logged deliveries, every row
  `on_time=true` with `delivered_date ≤ planned_date`.

---

## Running the audit

```bash
cd rynova
make install-dev          # install runtime + dev deps
make data                 # generate deterministic synthetic fixtures
make test                 # 102 tests — must pass
make bench                # 4 bullet benchmarks — all must PASS
make lint                 # ruff
make typecheck            # mypy
make ci                   # everything above in CI order
```

CI runs the same commands on every push and pull request via
`.github/workflows/rynova.yml`.

For a fast smoke run (≈10s), set `RYNOVA_QUICK=1`:

```bash
RYNOVA_QUICK=1 make bench
```

---

## Layout

```
rynova/
├── COMPLIANCE.md              # bullet → file/line/command map
├── Makefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── benchmarks/
│   ├── bench_bullet1_query_latency.py
│   ├── bench_bullet2_pipeline_failures.py
│   ├── bench_bullet3_kafka_idempotency.py
│   └── bench_bullet4_sql_plans.py
├── dashboards/
│   ├── README.md
│   └── grafana_health.json
├── data/                       # generated fixtures (git-ignored)
├── deliverables/
│   └── deliveries.csv
├── docs/
│   └── design_notes.md
├── scripts/
│   ├── generate_fixtures.py
│   └── health_report.py
├── src/rynova_platform/
│   ├── api/                   # FastAPI service + event bus
│   ├── etl/                   # Pipeline + Schema/SchemaEvolution
│   ├── java_bridge/           # Java sources + compile helper
│   ├── observability/         # Prometheus metrics + health
│   ├── sql/                   # Planner, partitioning, pagination
│   ├── streaming/             # Kafka stand-in + idempotent sink + DQ registry
│   └── validation/            # DQ SDK
└── tests/                     # 102 pytest cases
```

---

## License

Apache-2.0 (matches the parent repository).
