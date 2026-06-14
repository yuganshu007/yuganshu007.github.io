#!/usr/bin/env python3
"""Generate the synthetic transcript corpus.

Usage:
    python scripts/generate_data.py --out data --conversations 23000 --tenants 100
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the project root importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from platform_common.data import GenConfig, write_corpus  # noqa: E402
from platform_common.logging import get_logger  # noqa: E402

log = get_logger("data-generator")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate synthetic advertiser transcripts.")
    ap.add_argument("--out", default="data")
    ap.add_argument("--conversations", type=int, default=23000)
    ap.add_argument("--tenants", type=int, default=100)
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    cfg = GenConfig(
        conversations=args.conversations,
        tenants=args.tenants,
        days=args.days,
        seed=args.seed,
    )
    meta = write_corpus(cfg, args.out)
    log.info(
        "corpus_generated",
        out=args.out,
        conversations=meta["counts"]["total"],
        defective=meta["counts"]["defective"],
        n_tenants=meta["n_tenants"],
        clean_rate=round(meta["clean_rate"], 6),
    )
    print(
        f"Generated {meta['counts']['total']} conversations across {meta['n_tenants']} tenants "
        f"({meta['counts']['defective']} defective, clean_rate={meta['clean_rate']:.5f})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
