PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: help install install-dev test lint typecheck bench bench-quick data ci all clean

help:
	@echo "Rynova Data Platform — compliance Makefile"
	@echo
	@echo "Targets:"
	@echo "  make install      Install runtime dependencies"
	@echo "  make install-dev  Install dev + test dependencies"
	@echo "  make test         Run full pytest suite"
	@echo "  make lint         Run ruff + mypy"
	@echo "  make bench        Run all 4 resume-bullet benchmarks"
	@echo "  make bench-quick  Run benchmarks with smaller sample sizes"
	@echo "  make data         Generate synthetic fixtures"
	@echo "  make ci           install-dev + lint + test + bench (CI entrypoint)"

install:
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

install-dev:
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e ".[dev]"

data:
	$(PYTHON) scripts/generate_fixtures.py

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check src tests benchmarks scripts
	$(PYTHON) -m ruff format --check src tests benchmarks scripts || true

typecheck:
	$(PYTHON) -m mypy src

bench: data
	@echo "=========================================="
	@echo "Bullet 1 — async REST + 40% query latency"
	@echo "=========================================="
	$(PYTHON) benchmarks/bench_bullet1_query_latency.py
	@echo
	@echo "=========================================="
	@echo "Bullet 2 — ETL: 30% pipeline failure cut"
	@echo "=========================================="
	$(PYTHON) benchmarks/bench_bullet2_pipeline_failures.py
	@echo
	@echo "=========================================="
	@echo "Bullet 3 — Kafka idempotency + 33+ DQ"
	@echo "=========================================="
	$(PYTHON) benchmarks/bench_bullet3_kafka_idempotency.py
	@echo
	@echo "=========================================="
	@echo "Bullet 4 — SQL plans: 25% latency cut"
	@echo "=========================================="
	$(PYTHON) benchmarks/bench_bullet4_sql_plans.py

bench-quick:
	RYNOVA_QUICK=1 $(MAKE) bench

ci: install-dev lint test bench

all: install-dev data lint test bench

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
	find . -name __pycache__ -type d -exec rm -rf {} +
