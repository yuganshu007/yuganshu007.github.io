"""Central configuration resolved from environment variables with sane local defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    data_dir: str = os.getenv("DATA_DIR", "data")
    aws_region: str = os.getenv("AWS_REGION", "us-east-1")

    # Pillar 2 — agent / Bedrock
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20241022-v1:0"
    )
    # "mock" (default, no creds) or "bedrock" (real AWS)
    llm_backend: str = os.getenv("LLM_BACKEND", "mock")
    agent_p95_budget_seconds: float = float(os.getenv("AGENT_P95_BUDGET_S", "2.0"))

    # Pillar 4 — analytics
    # "duckdb" (default local) or "athena" (real AWS)
    athena_backend: str = os.getenv("ATHENA_BACKEND", "duckdb")
    glue_database: str = os.getenv("GLUE_DATABASE", "transcript_intelligence")
    athena_output: str = os.getenv("ATHENA_OUTPUT_LOCATION", "s3://example-bucket/athena/")

    fast_mode: bool = os.getenv("BENCH_FAST", "0") == "1"


settings = Settings()
