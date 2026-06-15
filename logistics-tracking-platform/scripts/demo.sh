#!/usr/bin/env bash
# End-to-end demonstration of the logistics tracking pipeline.
#
# Starts Redis (if needed), the Java background-worker pool and the Python ingest
# API, then walks a shipment through several tracking events and reads the
# assembled status back out of the SQLite store. Intended for a live interview
# walk-through.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export DB_PATH="$ROOT/data/logistics.db"
export REDIS_URL="redis://localhost:6379/0"
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export STREAM_KEY="logistics.events"
export DLQ_KEY="logistics.events.dlq"
export DOWNSTREAM_MS="${DOWNSTREAM_MS:-20}"
export TRANSIENT_FAIL_RATE="${TRANSIENT_FAIL_RATE:-0.25}"   # show retries kicking in
export SLA_MS="${SLA_MS:-750}"
export WORKER_THREADS="${WORKER_THREADS:-6}"
export MAX_ATTEMPTS="${MAX_ATTEMPTS:-5}"
export BACKOFF_MS="${BACKOFF_MS:-40}"
export INGEST_MODE="optimized"

PY="$ROOT/.venv/bin/python"
UVICORN="$ROOT/.venv/bin/uvicorn"
JAR="$ROOT/tracking-worker/target/tracking-worker.jar"
BASE="http://127.0.0.1:8080"

mkdir -p "$ROOT/data"
redis-cli del "$STREAM_KEY" "$DLQ_KEY" >/dev/null 2>&1 || true

cleanup() {
  [[ -n "${WORKER_PID:-}" ]] && kill "$WORKER_PID" 2>/dev/null || true
  [[ -n "${INGEST_PID:-}" ]] && kill "$INGEST_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> ensuring redis is up"
redis-cli ping >/dev/null 2>&1 || { redis-server --daemonize yes || sudo service redis-server start; }

echo "==> starting ingest API (optimized)"
( cd ingest-service && "$UVICORN" app.main:app --host 127.0.0.1 --port 8080 --loop uvloop --log-level warning ) &
INGEST_PID=$!

echo "==> waiting for health"
for _ in $(seq 1 40); do
  if curl -fsS "$BASE/healthz" >/dev/null 2>&1; then break; fi
  sleep 0.3
done

echo "==> resetting state (db + queue) on a clean slate"
curl -fsS "$BASE/admin/reset" -X POST >/dev/null

echo "==> starting Java background-worker pool"
java -jar "$JAR" &
WORKER_PID=$!
sleep 2  # let the worker create its consumer group on the fresh stream

echo "==> creating shipment"
SID=$(curl -fsS -X POST "$BASE/shipments" -H 'content-type: application/json' \
  -d '{"origin":"New York, NY","destination":"Boston, MA","carrier":"ACME Freight"}' \
  | "$PY" -c "import sys,json;print(json.load(sys.stdin)['shipment_id'])")
echo "    shipment_id=$SID"

echo "==> posting tracking events (async-accepted, processed by workers)"
for T in PICKUP IN_TRANSIT IN_TRANSIT OUT_FOR_DELIVERY DELIVERED; do
  curl -fsS -X POST "$BASE/shipments/$SID/events" -H 'content-type: application/json' \
    -d "{\"event_type\":\"$T\",\"location\":\"Hub-$RANDOM\"}" >/dev/null
  echo "    queued $T"
done

echo "==> posting an INVALID event (rejected by validation -> HTTP 422)"
curl -s -o /dev/null -w "    validation status: %{http_code}\n" \
  -X POST "$BASE/shipments/$SID/events" -H 'content-type: application/json' \
  -d '{"event_type":"TELEPORT","location":""}'

echo "==> waiting for the worker pool to drain the queue backlog"
for _ in $(seq 1 50); do
  BACKLOG=$(curl -fsS "$BASE/metrics" | "$PY" -c "import sys,json;print(json.load(sys.stdin)['queue_backlog'])")
  [[ "$BACKLOG" == "0" ]] && break
  sleep 0.2
done
sleep 1

echo "==> final shipment status (read via SQLite + cache):"
curl -fsS "$BASE/shipments/$SID" | "$PY" -m json.tool

echo "==> service metrics:"
curl -fsS "$BASE/metrics" | "$PY" -m json.tool

echo "==> done."
