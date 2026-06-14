"""Data-quality rule suite for transcript conversations.

Each rule is a pure function returning a violation reason or None. The suite computes a per-record
verdict and an aggregate pass rate. This is what backs the "99.9% data quality" claim: it is a
*measured* pass rate over the corpus, not an asserted constant.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

ALLOWED_LANGUAGES = {"en", "es", "fr", "de"}
MAX_DURATION = 6 * 60 * 60  # 6 hours


def rule_call_id(rec: dict) -> str | None:
    return None if rec.get("call_id") else "missing_call_id"


def rule_transcript_nonempty(rec: dict) -> str | None:
    return None if (rec.get("transcript_text") or "").strip() else "empty_transcript"


def rule_duration_valid(rec: dict) -> str | None:
    d = rec.get("duration_sec")
    if d is None or d < 0:
        return "invalid_duration"
    if d > MAX_DURATION:
        return "duration_out_of_range"
    return None


def rule_language(rec: dict) -> str | None:
    return None if rec.get("language") in ALLOWED_LANGUAGES else "unsupported_language"


def rule_turns(rec: dict) -> str | None:
    return None if (rec.get("num_turns") or 0) > 0 else "no_turns"


RULES: list[Callable[[dict], str | None]] = [
    rule_call_id,
    rule_transcript_nonempty,
    rule_duration_valid,
    rule_language,
    rule_turns,
]


@dataclass
class DQReport:
    total: int
    passed: int
    failed: int
    violations: dict[str, int]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 1.0


def check_record(rec: dict) -> list[str]:
    return [v for r in RULES if (v := r(rec)) is not None]


def evaluate(records) -> DQReport:
    total = passed = failed = 0
    violations: dict[str, int] = {}
    for rec in records:
        total += 1
        vs = check_record(rec)
        if vs:
            failed += 1
            for v in vs:
                violations[v] = violations.get(v, 0) + 1
        else:
            passed += 1
    return DQReport(total=total, passed=passed, failed=failed, violations=violations)
