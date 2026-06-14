"""Skew-safe join via key salting.

When one join key dominates (a "hot" advertiser), a plain shuffle join sends all matching rows to
a single reducer task -> one straggler that blows the SLA. Salting splits the hot key into N
virtual sub-keys on the large side and replicates the matching dimension rows N times, spreading
the work across N tasks.
"""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def salted_join(
    fact: DataFrame,
    dim: DataFrame,
    key: str = "advertiser_id",
    salt_buckets: int = 16,
) -> DataFrame:
    """Join `fact` to `dim` on `key` using salting to defuse skew."""
    fact_salted = fact.withColumn(
        "_salt", (F.rand(seed=7) * F.lit(salt_buckets)).cast("int")
    ).withColumn("_skey", F.concat_ws("#", F.col(key), F.col("_salt")))

    salt_range = F.explode(F.sequence(F.lit(0), F.lit(salt_buckets - 1))).alias("_salt")
    dim_replicated = dim.select("*", salt_range).withColumn(
        "_skey", F.concat_ws("#", F.col(key), F.col("_salt"))
    )

    joined = fact_salted.join(
        dim_replicated.drop(key, "_salt"), on="_skey", how="left"
    ).drop("_skey", "_salt")
    return joined
