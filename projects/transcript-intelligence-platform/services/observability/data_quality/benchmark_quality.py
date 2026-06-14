"""Run the data-quality suite over the full generated corpus and record the pass rate.

Writes docs/results/data_quality.json. With the generator's controlled defect rate (~0.05%), the
measured pass rate lands at/above 99.9% over 23,000+ conversations.

Run:  python -m services.observability.data_quality.benchmark_quality --data data
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from platform_common.config import settings
from platform_common.logging import get_logger
from services.observability.cloudwatch.emitter import CloudWatchEmitter
from services.observability.data_quality.quality_checks import evaluate

log = get_logger("dq-benchmark")
RESULTS = Path(__file__).resolve().parents[3] / "docs" / "results" / "data_quality.json"


def iter_records(data_dir: str):
    landing = Path(data_dir) / "landing"
    for part in landing.rglob("*.jsonl"):
        for line in part.read_text().splitlines():
            line = line.strip()
            if line:
                yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=settings.data_dir)
    args = ap.parse_args()

    report = evaluate(iter_records(args.data))
    result = {
        "total_conversations": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "pass_rate": round(report.pass_rate, 6),
        "pass_rate_pct": round(report.pass_rate * 100, 4),
        "meets_999_target": report.pass_rate >= 0.999,
        "violations": report.violations,
        "note": "Measured pass rate of the DQ rule suite over the full corpus.",
    }
    os.makedirs(RESULTS.parent, exist_ok=True)
    RESULTS.write_text(json.dumps(result, indent=2))

    # Emit to CloudWatch (mock locally) — this metric would back an alarm in production.
    CloudWatchEmitter(namespace="TranscriptIntelligence/DataQuality").put_metric(
        "PassRatePercent", result["pass_rate_pct"], unit="Percent"
    )

    print(json.dumps(result, indent=2))
    log.info(
        "dq_done",
        total=report.total,
        pass_rate_pct=result["pass_rate_pct"],
        meets_target=result["meets_999_target"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
