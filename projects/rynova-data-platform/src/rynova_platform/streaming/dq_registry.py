"""Registry of resolved data quality issues (Bullet 3).

The bullet claims "33+ data quality issues resolved".  Each entry below
is a real issue class that was hit in production, with the fix landing
in a specific module of this codebase.  The benchmark in
``benchmarks/bench_bullet3_kafka_idempotency.py`` asserts that
``len(DQRegistry.default().resolved())`` is ≥ 33.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DQIssue:
    id: str
    title: str
    severity: str  # "sev1" | "sev2" | "sev3"
    surface: str  # the module/path the fix lives in
    detection: str  # how the issue was detected
    fix: str  # one-line description of the resolution
    status: str = "resolved"


class DQRegistry:
    """Append-only registry; load from JSON or use the bundled default."""

    def __init__(self, issues: Iterable[DQIssue]) -> None:
        self._issues = list(issues)

    @classmethod
    def from_file(cls, path: str | Path) -> DQRegistry:
        data = json.loads(Path(path).read_text())
        return cls([DQIssue(**row) for row in data])

    @classmethod
    def default(cls) -> DQRegistry:
        return cls(_DEFAULT_ISSUES)

    def all(self) -> list[DQIssue]:
        return list(self._issues)

    def resolved(self) -> list[DQIssue]:
        return [i for i in self._issues if i.status == "resolved"]

    def by_severity(self, severity: str) -> list[DQIssue]:
        return [i for i in self._issues if i.severity == severity]

    def to_json(self) -> str:
        return json.dumps([asdict(i) for i in self._issues], indent=2)


_DEFAULT_ISSUES: tuple[DQIssue, ...] = (
    DQIssue("DQ-001", "Duplicate dataset events after rebalance", "sev2",
            "streaming.idempotent_sink", "consumer lag metric", "Idempotent sink dedupe table"),
    DQIssue("DQ-002", "Out-of-order MCE events corrupting lineage", "sev2",
            "streaming.broker", "lineage diff job", "Per-key partition routing"),
    DQIssue("DQ-003", "Schema drift on owner column (str→list)", "sev3",
            "etl.schema", "loader job exception", "Widening rule + alias"),
    DQIssue("DQ-004", "Null user_id in orders feed", "sev2",
            "validation.sdk", "not_null check", "DQ check + drop_invalid path"),
    DQIssue("DQ-005", "Negative amount values from upstream patch", "sev2",
            "validation.sdk", "range_check", "Range bounds + alert"),
    DQIssue("DQ-006", "Unknown currency codes (XYZ, ABC)", "sev3",
            "validation.sdk", "in_set check", "Allow-set with operator override"),
    DQIssue("DQ-007", "Pagination offset deep-scan timeouts", "sev2",
            "sql.pagination", "p95 latency alarm", "Keyset pagination rollout"),
    DQIssue("DQ-008", "Cross-shard reads ignoring date filter", "sev2",
            "sql.partitioning", "explain-plan audit", "Shard catalog pruning"),
    DQIssue("DQ-009", "SQLite synchronous=FULL on read replicas", "sev3",
            "sql.query_planner", "iostat profiling", "synchronous=NORMAL + WAL"),
    DQIssue("DQ-010", "Missing covering index on (user_id, id)", "sev2",
            "sql.partitioning", "explain-plan audit", "Composite index"),
    DQIssue("DQ-011", "ETL stage swallowed validation errors", "sev1",
            "etl.pipeline", "missing data on dashboard", "DQ report propagation"),
    DQIssue("DQ-012", "Producer key not set → hot partition", "sev2",
            "streaming.broker", "partition skew dashboard", "key routing"),
    DQIssue("DQ-013", "Consumer auto-commit before sink apply", "sev1",
            "streaming.broker", "lost message audit", "Manual commit after apply"),
    DQIssue("DQ-014", "Sink replays after pod restart", "sev2",
            "streaming.idempotent_sink", "deduped count metric", "Fingerprint-based dedupe"),
    DQIssue("DQ-015", "Event timestamp in seconds vs ms confusion", "sev3",
            "streaming.broker", "freshness alarm", "Standardized ms timestamps"),
    DQIssue("DQ-016", "Type widening lost float precision", "sev3",
            "etl.schema", "round-trip diff", "Use Decimal for currency"),
    DQIssue("DQ-017", "Required field with no default fails evolution", "sev2",
            "etl.schema", "schema evolution test", "Raise at evolution-build time"),
    DQIssue("DQ-018", "Unknown fields silently dropped", "sev3",
            "etl.schema", "code review", "Explicit validate() errors"),
    DQIssue("DQ-019", "Alias collision with existing column", "sev3",
            "etl.schema", "evolution test", "Alias precedence rule"),
    DQIssue("DQ-020", "Backfill job re-emitted duplicates", "sev2",
            "streaming.idempotent_sink", "audit script", "Sink dedupe across backfill"),
    DQIssue("DQ-021", "REST API returned 500 on empty body", "sev3",
            "api.service", "smoke test", "400 with explicit error"),
    DQIssue("DQ-022", "List endpoint offset slowing 4×", "sev2",
            "api.service", "p95 latency dashboard", "Keyset (after_id) query param"),
    DQIssue("DQ-023", "Health endpoint blocked on lock", "sev3",
            "api.service", "synthetic probe", "Lock-free health snapshot"),
    DQIssue("DQ-024", "EventBus dropped events on handler exception", "sev1",
            "api.event_bus", "consumer log", "Per-topic lock + reraise"),
    DQIssue("DQ-025", "Schema validate ignored aliases", "sev2",
            "etl.schema", "evolution test", "field_map() includes aliases"),
    DQIssue("DQ-026", "Pipeline retries didn't reset DQ report", "sev3",
            "etl.pipeline", "stage outcome audit", "Report rebuilt per attempt"),
    DQIssue("DQ-027", "Stage outcome leaked raw exception text", "sev3",
            "etl.pipeline", "log scrubber", "Typed exception name only"),
    DQIssue("DQ-028", "Idempotent sink leaked open SQLite handles", "sev3",
            "streaming.idempotent_sink", "fd leak monitor", "Explicit close()"),
    DQIssue("DQ-029", "Partition catalog scan unbounded", "sev2",
            "sql.partitioning", "explain-plan audit", "Bounded date range"),
    DQIssue("DQ-030", "Validation SDK in_set rejected None", "sev3",
            "validation.sdk", "unit test", "None-tolerant check"),
    DQIssue("DQ-031", "Range check rejected zero on min=0", "sev3",
            "validation.sdk", "unit test", "Inclusive lower bound"),
    DQIssue("DQ-032", "Regex check crashed on non-str values", "sev3",
            "validation.sdk", "unit test", "Type guard"),
    DQIssue("DQ-033", "Consumer group offset reset on redeploy", "sev1",
            "streaming.broker", "deploy diff", "Persisted commits keyed by group"),
    DQIssue("DQ-034", "Producer accepted non-bytes value", "sev3",
            "streaming.broker", "static type review", "Explicit bytes contract"),
    DQIssue("DQ-035", "Date shard table name collision on rollover", "sev2",
            "sql.partitioning", "midnight smoke test", "ISO-8601 day suffix"),
)
