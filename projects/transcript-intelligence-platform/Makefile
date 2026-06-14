VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DATA_DIR ?= data
N_CONVERSATIONS ?= 23000
N_TENANTS ?= 100

.PHONY: help install data test lint bench bench-etl bench-agent bench-dq bench-analytics \
        dashboard agent-api clean

help:
	@echo "Targets:"
	@echo "  install         create venv and install dependencies"
	@echo "  data            generate synthetic transcripts (N_CONVERSATIONS, N_TENANTS)"
	@echo "  test            run all unit tests"
	@echo "  lint            run ruff"
	@echo "  bench           run every benchmark and refresh docs/results/*.json"
	@echo "  bench-etl       Spark baseline-vs-optimized throughput benchmark"
	@echo "  bench-agent     agent p50/p95/p99 latency load test"
	@echo "  bench-dq        data-quality pass-rate over the full corpus"
	@echo "  bench-analytics time-to-insight + degradation-detect benchmark"
	@echo "  dashboard       launch the Streamlit analytics app"
	@echo "  agent-api       launch the FastAPI agent service"

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

data:
	$(PY) scripts/generate_data.py --out $(DATA_DIR) --conversations $(N_CONVERSATIONS) --tenants $(N_TENANTS)

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

bench: bench-etl bench-agent bench-dq bench-analytics
	@echo "All benchmarks complete. See docs/results/"

bench-etl:
	$(PY) -m services.etl_spark.benchmarks.run_benchmark --data $(DATA_DIR)

bench-agent:
	$(PY) -m services.agent_chatbot.loadtest.run_loadtest

bench-dq:
	$(PY) -m services.observability.data_quality.benchmark_quality --data $(DATA_DIR)

bench-analytics:
	$(PY) -m services.analytics_dashboard.benchmarks.run_benchmark --data $(DATA_DIR)

dashboard:
	$(VENV)/bin/streamlit run services/analytics_dashboard/app/Home.py

agent-api:
	$(VENV)/bin/uvicorn services.agent_chatbot.app.api:app --reload --port 8080

clean:
	rm -rf $(VENV) $(DATA_DIR) docs/results/*.json
