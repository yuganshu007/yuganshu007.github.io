# Logistics Tracking Platform - developer entry points.
#
# Typical flow:
#   make setup      # one-time: venv + pip install + mvn package
#   make demo       # start everything and walk a shipment through the pipeline
#   make bench      # reproduce all resume metrics (1, 2 and 3)

SHELL := /bin/bash
ROOT  := $(shell pwd)
PY    := $(ROOT)/.venv/bin/python
UVICORN := $(ROOT)/.venv/bin/uvicorn
JAR   := $(ROOT)/tracking-worker/target/tracking-worker.jar

export DB_PATH      ?= $(ROOT)/data/logistics.db
export REDIS_URL    ?= redis://localhost:6379/0
export REDIS_HOST   ?= localhost
export REDIS_PORT   ?= 6379
export STREAM_KEY   ?= logistics.events
export DLQ_KEY      ?= logistics.events.dlq
export DOWNSTREAM_MS ?= 20
export TRANSIENT_FAIL_RATE ?= 0.0
export SLA_MS       ?= 750
export INGEST_MODE  ?= optimized
export WORKER_THREADS ?= 12
export MAX_ATTEMPTS ?= 5
export BACKOFF_MS   ?= 40

.PHONY: setup build venv worker ingest demo bench bench-read bench-pipeline bench-routing redis clean

setup: venv build ## one-time setup of python + java artifacts

venv:
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -r ingest-service/requirements.txt

build:
	cd tracking-worker && mvn -q -DskipTests package

redis:
	redis-server --daemonize yes || sudo service redis-server start

worker: ## run the Java background-worker pool (foreground)
	java -jar $(JAR)

ingest: ## run the Python ingest API (foreground); override INGEST_MODE=baseline to compare
	cd ingest-service && $(UVICORN) app.main:app --host 0.0.0.0 --port 8080 \
		--loop $(if $(filter optimized,$(INGEST_MODE)),uvloop,asyncio)

demo: ## end-to-end smoke walk-through
	./scripts/demo.sh

bench: bench-pipeline bench-routing bench-read ## reproduce every resume metric

bench-pipeline: ## Metric 1a & 2 (API response time + SLA breaches)
	$(PY) benchmark/pipeline_bench.py

bench-routing: ## Metric 1b (tuned request routing: urgent end-to-end time)
	$(PY) benchmark/routing_bench.py

bench-read: ## Metric 3 (SQLite read latency)
	$(PY) benchmark/read_latency.py

clean:
	rm -rf .venv tracking-worker/target data/*.db data/*.db-shm data/*.db-wal __pycache__
