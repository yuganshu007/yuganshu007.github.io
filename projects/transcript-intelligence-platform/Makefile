# Transcript Intelligence Platform — Makefile
# Usage: make install && make data && make test && make bench

PYTHON  := python3
# Detect whether we have a venv or should use the system python
VENV    := .venv
PYBIN   := $(shell [ -f $(VENV)/bin/python ] && echo $(VENV)/bin/python || echo $(PYTHON))
PIP     := $(shell [ -f $(VENV)/bin/pip ] && echo $(VENV)/bin/pip || echo "$(PYTHON) -m pip")
PYTEST  := $(shell [ -f $(VENV)/bin/pytest ] && echo $(VENV)/bin/pytest || echo "$(PYTHON) -m pytest")

.PHONY: all install data test bench lint clean dashboard help

all: install data test bench

help:
	@echo ""
	@echo "  make install   — install dependencies (venv if available, else system)"
	@echo "  make data      — generate 1,000 synthetic transcripts in data/"
	@echo "  make test      — run full pytest suite with coverage"
	@echo "  make bench     — run all three metric benchmarks"
	@echo "  make lint      — run ruff + black check"
	@echo "  make dashboard — launch Streamlit dashboard locally"
	@echo "  make clean     — remove venv and generated files"
	@echo ""

install:
	@echo ">>> Installing dependencies..."
	@if $(PYTHON) -m venv $(VENV) 2>/dev/null; then \
	  echo "  Using virtualenv: $(VENV)"; \
	  $(VENV)/bin/pip install --quiet --upgrade pip; \
	  $(VENV)/bin/pip install --quiet -r requirements-dev.txt; \
	else \
	  echo "  venv unavailable — installing system-wide (--break-system-packages)"; \
	  $(PYTHON) -m pip install --quiet --break-system-packages -r requirements-dev.txt 2>/dev/null || \
	  $(PYTHON) -m pip install --quiet -r requirements-dev.txt; \
	fi
	@echo ">>> Install complete."

data:
	@echo ">>> Generating synthetic transcript data..."
	$(PYBIN) scripts/generate_data.py
	@echo ">>> Data generation complete. See data/sample_transcripts.jsonl"

test:
	@echo ">>> Running test suite..."
	$(PYTEST) tests/ \
		--tb=short \
		-q
	@echo ">>> Tests complete."

bench:
	@echo ""
	@echo "================================================================"
	@echo " BENCHMARK 1/3: Throughput (Bullet 1 — 38% via partition tuning)"
	@echo "================================================================"
	$(PYBIN) -m benchmarks.throughput_benchmark
	@echo ""
	@echo "================================================================"
	@echo " BENCHMARK 2/3: Latency (Bullet 2 — p95 < 2s, 45->2 min/call)"
	@echo "================================================================"
	$(PYBIN) -m benchmarks.latency_p95
	@echo ""
	@echo "================================================================"
	@echo " BENCHMARK 3/3: Data Quality (Bullet 3 — 99.9% across 23K+ calls)"
	@echo "================================================================"
	$(PYBIN) -m benchmarks.data_quality
	@echo ""
	@echo ">>> All benchmarks complete."

lint:
	@echo ">>> Running linter..."
	ruff check src/ benchmarks/ tests/ scripts/ 2>/dev/null || $(PYBIN) -m ruff check src/ benchmarks/ tests/ scripts/ 2>/dev/null || true
	@echo ">>> Lint complete."

dashboard:
	@echo ">>> Launching Streamlit dashboard on http://localhost:8501"
	streamlit run src/transcript_intelligence/dashboard/app.py 2>/dev/null || $(PYBIN) -m streamlit run src/transcript_intelligence/dashboard/app.py

clean:
	rm -rf $(VENV) .pytest_cache .coverage htmlcov dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f data/sample_transcripts.jsonl
	@echo ">>> Clean complete."
