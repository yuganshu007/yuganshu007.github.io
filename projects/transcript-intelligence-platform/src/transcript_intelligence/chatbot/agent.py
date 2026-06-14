"""
Bullet 2: Agentic AI chatbot using Bedrock (Claude 3.5 Haiku) with
LangChain-style orchestration, prompt engineering, and JSON-schema validation.

Architecture:
  TranscriptAgent
    └─ AgentExecutor (LangChain-style chain loop)
         ├─ PromptBuilder      (prompt engineering)
         ├─ BedrockClient      (Claude 3.5 Haiku invocation)
         ├─ ResponseValidator  (JSON-schema validation via Pydantic)
         └─ RetryOrchestrator  (up to MAX_LLM_RETRY_COUNT attempts)

Business impact:
  - Manual review: ~45 min/call  →  automated: ~2 min/call
  - p95 latency target: < 2 seconds per Bedrock call
"""

from __future__ import annotations

import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional

from .bedrock_client import (
    ADDITIONAL_PROMPT_FOR_RETRY,
    MAX_LLM_RETRY_COUNT,
    NLP_PROMPT_TEMPLATE,
    BedrockClient,
    invoke_bedrock_claude_model,
)
from .schemas import TranscriptInsight, build_retry_prompt, parse_llm_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt engineering
# ---------------------------------------------------------------------------

def build_nlp_prompt(transcript_text: str) -> str:
    """
    Constructs the prompt sent to Claude 3.5 Haiku.
    Mirrors VOCBatchProcessingJob.buildNLPPrompt(JsonNode transcript).
    """
    return NLP_PROMPT_TEMPLATE.format(transcript=transcript_text[:4000])  # token safety cap


# ---------------------------------------------------------------------------
# Agent execution loop — LangChain-style orchestration
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    insight:           Optional[TranscriptInsight]
    attempts:          int
    latency_seconds:   float
    success:           bool
    error_message:     str = ""


class TranscriptAgent:
    """
    Agentic chatbot that processes a single call transcript.

    Implements the retry-with-self-healing pattern from BedRockUtils:
      - First attempt: standard prompt
      - Subsequent attempts: inject ADDITIONAL_PROMPT_FOR_RETRY with
        previous invalid response and the specific validation error

    This loop is the "LangChain-style orchestration" described in Bullet 2.
    """

    def __init__(self, client: Optional[BedrockClient] = None):
        self.client = client or BedrockClient()

    def run(self, transcript: dict) -> AgentResult:
        """
        Process one transcript. Returns AgentResult with structured insight.
        Target: < 2 min/call elapsed, p95 < 2s for Bedrock call alone.
        """
        transcript_text = transcript.get("transcript", "")
        prompt          = build_nlp_prompt(transcript_text)
        prev_response   = ""
        prev_error      = ""

        for attempt in range(1, MAX_LLM_RETRY_COUNT + 1):
            # On retry, inject the self-healing retry prompt
            if attempt > 1 and prev_response:
                active_prompt = build_retry_prompt(prompt, prev_response, prev_error)
            else:
                active_prompt = prompt

            t0 = time.perf_counter()
            try:
                raw = invoke_bedrock_claude_model(self.client, active_prompt)
            except Exception as exc:
                logger.warning("Bedrock invocation failed (attempt %d): %s", attempt, exc)
                prev_error    = str(exc)
                prev_response = ""
                continue
            latency = time.perf_counter() - t0

            insight = parse_llm_response(raw)
            if insight is not None:
                return AgentResult(
                    insight=insight,
                    attempts=attempt,
                    latency_seconds=round(latency, 4),
                    success=True,
                )

            # Schema validation failed — retry with self-healing prompt
            prev_response = raw
            prev_error    = "response did not conform to required JSON schema"
            logger.debug("Attempt %d: schema validation failed, retrying", attempt)

        return AgentResult(
            insight=None,
            attempts=MAX_LLM_RETRY_COUNT,
            latency_seconds=0.0,
            success=False,
            error_message="Exhausted retries without valid schema response",
        )


# ---------------------------------------------------------------------------
# Batch processor — replaces 45 min/call manual review
# ---------------------------------------------------------------------------

@dataclass
class BatchProcessingResult:
    total:               int
    processed:           int
    failed:              int
    latencies:           List[float] = field(default_factory=list)
    data_quality_rate:   float = 0.0
    p95_latency_seconds: float = 0.0
    mean_latency_seconds: float = 0.0
    total_elapsed_seconds: float = 0.0


def process_batch(
    transcripts: List[dict],
    agent: Optional[TranscriptAgent] = None,
) -> BatchProcessingResult:
    """
    Process a batch of transcripts through the agent.
    Measures per-call latency to verify p95 < 2s claim.
    """
    agent   = agent or TranscriptAgent()
    results = BatchProcessingResult(total=len(transcripts), processed=0, failed=0)
    t_start = time.perf_counter()

    for transcript in transcripts:
        res = agent.run(transcript)
        if res.success:
            results.processed  += 1
            results.latencies.append(res.latency_seconds)
        else:
            results.failed += 1

    results.total_elapsed_seconds = round(time.perf_counter() - t_start, 3)

    if results.latencies:
        sorted_lat             = sorted(results.latencies)
        p95_idx                = int(len(sorted_lat) * 0.95)
        results.p95_latency_seconds  = sorted_lat[p95_idx]
        results.mean_latency_seconds = statistics.mean(results.latencies)

    total = results.processed + results.failed
    results.data_quality_rate = results.processed / total if total else 0.0

    return results
