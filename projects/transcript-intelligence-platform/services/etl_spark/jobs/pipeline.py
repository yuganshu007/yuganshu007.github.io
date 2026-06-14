"""Shared transent logic so the baseline and optimized jobs do the *same* work.

The only differences between baseline and optimized are the join strategy and the Spark
configuration (partition tuning + skew handling) — i.e. exactly the optimizations named in the
resume bullet. This keeps the throughput comparison a fair, controlled experiment.
"""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from services.etl_spark.jobs.skew import salted_join


def enrich(joined: DataFrame) -> DataFrame:
    """Native-expression feature engineering shared by both code paths."""
    return (
        joined.withColumn(
            "weighted_score",
            F.col("duration_sec") * F.coalesce(F.col("value_weight"), F.lit(1.0))
            / F.greatest(F.col("num_turns"), F.lit(1)),
        )
        .withColumn(
            "length_bucket",
            F.when(F.col("transcript_len") < 1000, "short")
            .when(F.col("transcript_len") < 3000, "medium")
            .otherwise("long"),
        )
        .withColumn("segment", F.coalesce(F.col("segment"), F.lit("unknown")))
    )


def aggregate(enriched: DataFrame) -> DataFrame:
    """Daily per-tenant/segment rollup — forces the shuffle where skew bites."""
    return (
        enriched.groupBy("tenant", "segment", "length_bucket")
        .agg(
            F.count("*").alias("n_calls"),
            F.avg("weighted_score").alias("avg_weighted_score"),
            F.sum("duration_sec").alias("total_duration"),
        )
        .orderBy("tenant", "segment", "length_bucket")
    )


def run_baseline(fact: DataFrame, dim: DataFrame) -> DataFrame:
    """Naive path: shuffle sort-merge join on the skewed key (broadcast disabled in session)."""
    joined = fact.join(dim, on="advertiser_id", how="left")
    return aggregate(enrich(joined))


def run_optimized(fact: DataFrame, dim: DataFrame, strategy: str = "broadcast") -> DataFrame:
    """Optimized path.

    strategy="broadcast": broadcast the small dimension (best choice for a tiny dim).
    strategy="salt":      salted skew-safe shuffle join (for when the dim is too big to broadcast).
    AQE + skew-join + coalesce + tuned shuffle partitions come from the optimized session config.
    """
    if strategy == "salt":
        joined = salted_join(fact, dim, key="advertiser_id")
    else:
        joined = fact.join(F.broadcast(dim), on="advertiser_id", how="left")
    return aggregate(enrich(joined))
