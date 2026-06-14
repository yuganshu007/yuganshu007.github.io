# Pillar 2 — Agentic AI chatbot (Bedrock, Claude 3.5 Haiku)

Produces a structured, schema-validated "call review" for each advertiser transcript using an
agentic, tool-calling orchestration over **Amazon Bedrock Claude 3.5 Haiku**.

## Highlights vs. the resume bullet

| Claim | Implementation |
|-------|----------------|
| Bedrock (Claude 3.5 Haiku) | `bedrock_client.py` — Converse API, model id `anthropic.claude-3-5-haiku-20241022-v1:0`. Mock backend with identical contract for local/CI. |
| LangChain-style orchestration | `agent.py` — system+few-shot prompt → tool routing → tool exec → final structured answer. |
| Prompt engineering | versioned templates in `prompts/`. |
| JSON-schema validation | `schemas/call_review.schema.json` + `validation.py` with a bounded **repair round-trip**. |
| p95 latency under 2s | `loadtest/run_loadtest.py` reports measured p50/p95/p99 to `docs/results/agent_latency.json`. |
| Cut manual review 45m → 2m | the agent returns a full structured review in sub-second time; the 45m human baseline is an assumption (see `docs/METRICS.md`), not measured here. |

Every model call is wrapped by Pillar 3 resilience (rate limit, token budget, circuit breaker,
backoff, fallback), so a Bedrock outage degrades to a schema-valid fallback review rather than an
error.

## Run

```bash
# local API (mock backend, no AWS needed)
make agent-api          # -> http://localhost:8080/docs
curl -s localhost:8080/review -H 'content-type: application/json' \
  -d '{"call_id":"c1","transcript":"advertiser: my invoice is wrong","advertiser_id":"adv_1"}'

# latency benchmark
python -m services.agent_chatbot.loadtest.run_loadtest --requests 1000 --concurrency 16

# real Bedrock: export AWS creds and set LLM_BACKEND=bedrock
```

## Tests

`tests/test_validation.py` (schema + coercion), `tests/test_agent.py` (200 reviews are always
schema-valid incl. the repair loop; budget/circuit-breaker trigger fallback), `tests/test_latency.py`
(percentile math).
