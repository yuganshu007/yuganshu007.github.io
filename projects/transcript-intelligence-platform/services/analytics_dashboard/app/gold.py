"""Build the pre-aggregated 'gold' table that powers fast self-serve dashboards.

The whole point of the time-to-insight win: analysts stop full-scanning raw transcripts for every
question and instead hit a small, pre-aggregated gold table. This module builds that table from
the landing zone using DuckDB (locally) — the same shape Glue/Athena would materialize in prod.
"""
from __future__ import annotations

import os
from pathlib import Path

from platform_common.logging import get_logger

log = get_logger("gold-builder")

DAILY_TENANT_SQL = """
SELECT
    tenant,
    dt,
    language,
    count(*)                         AS n_calls,
    avg(duration_sec)                AS avg_duration,
    sum(duration_sec)                AS total_duration,
    avg(num_turns)                   AS avg_turns,
    sum(CASE WHEN expected_sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_calls
FROM read_json_auto('{landing}', format='newline_delimited', ignore_errors=true)
WHERE duration_sec >= 0
GROUP BY tenant, dt, language
"""


def build_curated(data_dir: str) -> str:
    """Materialize a curated detail Parquet (all rows, all columns incl. transcript_text).

    This is the 'before' surface for the time-to-insight benchmark: analysts querying the full
    curated detail table. Comparing it (parquet) to the gold table (parquet) isolates the win from
    pre-aggregation + column projection, the same lever as Athena bytes-scanned reduction.
    """
    import duckdb

    data = Path(data_dir)
    landing = str(data / "landing" / "**" / "*.jsonl")
    curated_dir = data / "curated"
    os.makedirs(curated_dir, exist_ok=True)
    out = curated_dir / "conversations.parquet"
    con = duckdb.connect(":memory:")
    con.execute(
        f"COPY (SELECT * FROM read_json_auto('{landing}', format='newline_delimited', "
        f"ignore_errors=true)) TO '{out}' (FORMAT PARQUET)"
    )
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    log.info("curated_built", path=str(out), rows=n)
    return str(out)


def build_gold(data_dir: str) -> str:
    """Materialize gold/daily_tenant_metrics.parquet from the landing JSONL. Returns its path."""
    import duckdb

    data = Path(data_dir)
    landing = str(data / "landing" / "**" / "*.jsonl")
    gold_dir = data / "gold"
    os.makedirs(gold_dir, exist_ok=True)
    out = gold_dir / "daily_tenant_metrics.parquet"

    con = duckdb.connect(":memory:")
    sql = DAILY_TENANT_SQL.format(landing=landing)
    con.execute(f"COPY ({sql}) TO '{out}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT count(*) FROM read_parquet('{out}')").fetchone()[0]
    log.info("gold_built", path=str(out), rows=n)
    return str(out)
