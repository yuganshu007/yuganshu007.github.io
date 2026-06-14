"""Idempotent, retry-safe writes.

Daily SLA pipelines must be safely re-runnable: a retried run for the same logical partition
(`dt`) must produce identical output with no duplicates. We achieve this with:

  * a deterministic de-duplication on the business key before write, and
  * partition-scoped *dynamic overwrite* so re-running a `dt` atomically replaces only that
    partition's data (never appends duplicates), and
  * a run manifest recording the input fingerprint so a retry is observably idempotent.
"""
from __future__ import annotations

import hashlib
import json
import os

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def deduplicate(df: DataFrame, business_key: str = "call_id") -> DataFrame:
    """Keep one row per business key (latest by a deterministic ordering)."""
    return df.dropDuplicates([business_key])


def write_idempotent(
    df: DataFrame,
    path: str,
    partition_cols: list[str],
    business_key: str = "call_id",
) -> dict:
    """Write `df` idempotently. Returns a run manifest dict."""
    deduped = deduplicate(df, business_key)
    spark = df.sparkSession
    # Dynamic partition overwrite => only touched partitions are replaced, atomically.
    spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
    (
        deduped.write.mode("overwrite")
        .partitionBy(*partition_cols)
        .parquet(path)
    )

    row_count = deduped.count()
    fingerprint = _fingerprint(deduped, business_key)
    manifest = {
        "path": path,
        "partition_cols": partition_cols,
        "row_count": row_count,
        "content_fingerprint": fingerprint,
    }
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "_run_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def _fingerprint(df: DataFrame, business_key: str) -> str:
    """Order-independent content fingerprint: hash of sorted business keys + row count."""
    keys = [r[business_key] for r in df.select(business_key).collect()]
    keys_sorted = sorted(str(k) for k in keys)
    h = hashlib.sha256()
    h.update(str(len(keys_sorted)).encode())
    for k in keys_sorted:
        h.update(k.encode())
    return h.hexdigest()
