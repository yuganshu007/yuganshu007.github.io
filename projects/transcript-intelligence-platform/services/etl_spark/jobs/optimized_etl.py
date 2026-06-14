"""Optimized ETL job entrypoint: partition tuning + skew-safe join + idempotent write."""
from __future__ import annotations

import argparse

from platform_common.logging import get_logger
from services.etl_spark.jobs.common import build_spark, make_advertiser_dim, make_skewed_fact
from services.etl_spark.jobs.idempotent import write_idempotent
from services.etl_spark.jobs.pipeline import run_optimized

log = get_logger("etl-optimized")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=2_000_000)
    ap.add_argument("--strategy", choices=["broadcast", "salt"], default="broadcast")
    ap.add_argument("--out", default="data/curated_optimized")
    args = ap.parse_args()

    spark = build_spark("etl-optimized", optimized=True)
    fact = make_skewed_fact(spark, args.rows)
    dim = make_advertiser_dim(spark)
    result = run_optimized(fact, dim, strategy=args.strategy)
    manifest = write_idempotent(
        result.withColumn("dt", result["tenant"]),
        args.out,
        partition_cols=["dt"],
        business_key="tenant",
    )
    log.info("optimized_done", rows=args.rows, out=args.out, manifest_rows=manifest["row_count"])
    spark.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
