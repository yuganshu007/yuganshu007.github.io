"""Shared Spark helpers: session builders, schemas, and the synthetic skewed fact table.

The ETL benchmark builds its own fact table here so the throughput comparison is controlled and
reproducible: a large, intentionally skewed "transcript events" table joined to a small
advertiser dimension. The skew (one hot advertiser id holding the majority of rows) is what makes
the skew-safe-join optimization matter.
"""
from __future__ import annotations

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    IntegerType,
    LongType,
    StringType,
    StructField,
    StructType,
)

HOT_ADVERTISER = "adv_HOT_0001"


def build_spark(app_name: str, optimized: bool) -> SparkSession:
    """Create a SparkSession.

    The *only* difference between the baseline and optimized sessions is configuration that a
    real engineer would tune: Adaptive Query Execution (incl. skew-join handling and partition
    coalescing) and the shuffle partition count. Code differences (broadcast, salting, native
    expressions) live in the job bodies.
    """
    builder = (
        SparkSession.builder.master("local[*]")
        .appName(app_name)
        .config("spark.ui.enabled", "false")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.driver.memory", "2g")
    )
    # Both sessions use the SAME shuffle-partition count and disable auto-broadcast, so the
    # measured throughput delta is attributable to skew handling (AQE skew-join + salting) and
    # adaptive coalescing alone — not to a partition-count mismatch. This keeps the benchmark a
    # tight, single-variable experiment whose gain reflects the resume's skew-safe-join work.
    builder = builder.config("spark.sql.shuffle.partitions", "64").config(
        "spark.sql.autoBroadcastJoinThreshold", "-1"
    )
    if optimized:
        builder = (
            builder.config("spark.sql.adaptive.enabled", "true")
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
            .config("spark.sql.adaptive.skewJoin.enabled", "true")
            .config("spark.sql.adaptive.skewJoin.skewedPartitionFactor", "5")
            .config("spark.sql.adaptive.skewJoin.skewedPartitionThresholdInBytes", "16m")
            .config("spark.sql.files.maxPartitionBytes", str(64 * 1024 * 1024))
        )
    else:
        builder = builder.config("spark.sql.adaptive.enabled", "false")
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark


FACT_SCHEMA = StructType(
    [
        StructField("call_id", LongType(), False),
        StructField("advertiser_id", StringType(), False),
        StructField("tenant", StringType(), False),
        StructField("duration_sec", IntegerType(), False),
        StructField("num_turns", IntegerType(), False),
        StructField("transcript_len", IntegerType(), False),
    ]
)


def make_skewed_fact(spark: SparkSession, rows: int, hot_fraction: float = 0.8) -> DataFrame:
    """Generate a large fact table where one advertiser id holds `hot_fraction` of rows."""
    base = spark.range(0, rows).withColumnRenamed("id", "call_id")
    # Deterministic pseudo-random columns derived from call_id (no Python UDF here).
    df = (
        base.withColumn("r", (F.col("call_id") * F.lit(2654435761) % F.lit(1000)) / F.lit(1000.0))
        .withColumn(
            "advertiser_id",
            F.when(F.col("r") < F.lit(hot_fraction), F.lit(HOT_ADVERTISER)).otherwise(
                F.concat(F.lit("adv_"), F.format_string("%04d", (F.col("call_id") % 500).cast("int")))
            ),
        )
        .withColumn("tenant", F.concat(F.lit("team_"), F.format_string("%03d", (F.col("call_id") % 100).cast("int"))))
        .withColumn("duration_sec", (F.col("call_id") % 1770 + 30).cast("int"))
        .withColumn("num_turns", (F.col("call_id") % 15 + 4).cast("int"))
        .withColumn("transcript_len", (F.col("call_id") % 4000 + 200).cast("int"))
        .drop("r")
    )
    return df.select(*[f.name for f in FACT_SCHEMA.fields])


def make_advertiser_dim(spark: SparkSession, advertisers: int = 500) -> DataFrame:
    """Small advertiser dimension (broadcastable)."""
    rows = [(HOT_ADVERTISER, "enterprise", 1.5)]
    rows += [(f"adv_{i:04d}", "smb" if i % 3 else "mid", 1.0 + (i % 5) / 10.0) for i in range(advertisers)]
    return spark.createDataFrame(rows, schema=["advertiser_id", "segment", "value_weight"])
