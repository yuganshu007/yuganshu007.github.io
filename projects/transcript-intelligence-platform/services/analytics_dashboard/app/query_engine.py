"""Query engine with two interchangeable backends behind one interface.

  * "athena": real Amazon Athena over Glue-cataloged S3 (boto3) — production.
  * "duckdb": local DuckDB over the same Parquet/JSON — local & CI.

The Streamlit app and the time-to-insight benchmark both go through this interface, so the exact
same analytical SQL runs locally and on Athena.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from platform_common.config import settings
from platform_common.logging import get_logger

log = get_logger("query-engine")


@dataclass
class QueryResult:
    rows: list[dict]
    latency_s: float
    scanned_bytes: int = 0


class QueryEngine:
    def __init__(self, data_dir: str | None = None, backend: str | None = None):
        self.data_dir = Path(data_dir or settings.data_dir)
        self.backend = backend or settings.athena_backend
        self._con = None
        if self.backend == "duckdb":
            import duckdb

            self._con = duckdb.connect(database=":memory:")
        elif self.backend == "athena":
            import boto3

            self._athena = boto3.client("athena", region_name=settings.aws_region)

    # --- paths ----------------------------------------------------------------------
    @property
    def landing_glob(self) -> str:
        return str(self.data_dir / "landing" / "**" / "*.jsonl")

    @property
    def gold_path(self) -> str:
        return str(self.data_dir / "gold" / "daily_tenant_metrics.parquet")

    # --- query ----------------------------------------------------------------------
    def sql(self, query: str) -> QueryResult:
        if self.backend == "duckdb":
            t0 = time.perf_counter()
            cur = self._con.execute(query)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            return QueryResult(rows=rows, latency_s=time.perf_counter() - t0)
        return self._athena_sql(query)

    def _athena_sql(self, query: str) -> QueryResult:  # pragma: no cover - needs AWS
        t0 = time.perf_counter()
        start = self._athena.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": settings.glue_database},
            ResultConfiguration={"OutputLocation": settings.athena_output},
        )
        qid = start["QueryExecutionId"]
        while True:
            ex = self._athena.get_query_execution(QueryExecutionId=qid)
            state = ex["QueryExecution"]["Status"]["State"]
            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(0.2)
        scanned = ex["QueryExecution"]["Statistics"].get("DataScannedInBytes", 0)
        res = self._athena.get_query_results(QueryExecutionId=qid)
        header = [c["VarCharValue"] for c in res["ResultSet"]["Rows"][0]["Data"]]
        rows = [
            {header[i]: c.get("VarCharValue") for i, c in enumerate(r["Data"])}
            for r in res["ResultSet"]["Rows"][1:]
        ]
        return QueryResult(rows=rows, latency_s=time.perf_counter() - t0, scanned_bytes=scanned)
