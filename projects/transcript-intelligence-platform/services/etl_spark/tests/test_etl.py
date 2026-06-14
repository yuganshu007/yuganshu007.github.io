"""Correctness tests for the ETL pillar.

These prove the optimizations are *behavior-preserving* (baseline and optimized produce the same
result) and that the skew-safe salted join and idempotent writes are correct.
"""
from __future__ import annotations

import shutil
import tempfile

import pytest

from services.etl_spark.jobs.common import build_spark, make_advertiser_dim, make_skewed_fact
from services.etl_spark.jobs.idempotent import write_idempotent
from services.etl_spark.jobs.pipeline import run_baseline, run_optimized


@pytest.fixture(scope="module")
def spark():
    s = build_spark("etl-tests", optimized=True)
    yield s
    s.stop()


def _as_map(rows):
    return {(r["tenant"], r["segment"], r["length_bucket"]): r["n_calls"] for r in rows}


def test_optimized_matches_baseline(spark):
    fact = make_skewed_fact(spark, 50_000).cache()
    dim = make_advertiser_dim(spark)
    base = _as_map(run_baseline(fact, dim).collect())
    opt_b = _as_map(run_optimized(fact, dim, strategy="broadcast").collect())
    opt_s = _as_map(run_optimized(fact, dim, strategy="salt").collect())
    assert base == opt_b, "broadcast optimization changed results"
    assert base == opt_s, "salted skew-safe join changed results"


def test_salted_join_no_row_loss(spark):
    from services.etl_spark.jobs.skew import salted_join

    fact = make_skewed_fact(spark, 20_000)
    dim = make_advertiser_dim(spark)
    naive = fact.join(dim, on="advertiser_id", how="left").count()
    salted = salted_join(fact, dim, key="advertiser_id").count()
    assert naive == salted == 20_000


def test_idempotent_rerun_is_stable(spark):
    fact = make_skewed_fact(spark, 10_000)
    dim = make_advertiser_dim(spark)
    result = run_optimized(fact, dim).withColumnRenamed("tenant", "tenant")
    result = result.withColumn("dt", result["tenant"])
    out = tempfile.mkdtemp(prefix="curated_")
    try:
        m1 = write_idempotent(result, out, partition_cols=["dt"], business_key="tenant")
        m2 = write_idempotent(result, out, partition_cols=["dt"], business_key="tenant")
        assert m1["content_fingerprint"] == m2["content_fingerprint"]
        assert m1["row_count"] == m2["row_count"]
    finally:
        shutil.rmtree(out, ignore_errors=True)
