"""Generate deterministic fixture data used by benchmarks and tests.

Run as ``python rynova/scripts/generate_fixtures.py`` — the script is
idempotent: the same seed always produces the same files, so the
benchmarks' pass/fail asserts are deterministic across machines.
"""

from __future__ import annotations

import csv
import json
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

QUICK = bool(os.environ.get("RYNOVA_QUICK"))
N_USERS = 1_000 if QUICK else 5_000
N_ORDERS = 5_000 if QUICK else 25_000
N_DAYS = 14 if QUICK else 30


def main() -> int:
    rng = random.Random(1729)

    users_path = DATA_DIR / "users.csv"
    with users_path.open("w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["user_id", "email", "currency"])
        for i in range(1, N_USERS + 1):
            writer.writerow([
                i,
                f"user{i}@rynova.example",
                rng.choice(["USD", "EUR", "INR", "GBP", "JPY"]),
            ])

    orders_path = DATA_DIR / "orders.jsonl"
    today = date(2024, 6, 1)
    with orders_path.open("w") as fp:
        for i in range(1, N_ORDERS + 1):
            day = today - timedelta(days=rng.randint(0, N_DAYS - 1))
            row = {
                "id": i,
                "user_id": rng.randint(1, N_USERS),
                "amount": round(rng.uniform(1.0, 500.0), 2),
                "currency": rng.choice(["USD", "EUR", "INR", "GBP", "JPY"]),
                "ts": int(day.toordinal()),
                "day": day.isoformat(),
            }
            fp.write(json.dumps(row) + "\n")

    summary = {
        "users": N_USERS,
        "orders": N_ORDERS,
        "days": N_DAYS,
        "quick_mode": QUICK,
    }
    (DATA_DIR / "fixture_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Generated fixtures: {summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
