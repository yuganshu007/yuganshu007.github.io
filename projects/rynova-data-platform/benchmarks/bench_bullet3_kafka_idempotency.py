"""Bullet 3 benchmark — Kafka streaming with idempotent operations.

Produces 5,000 messages into the in-process broker, then replays the
same partitions twice through the idempotent sink to simulate a
consumer rebalance.  Asserts:

* the sink applies every unique message exactly once;
* the replay is observed as 100% dedupe;
* the resolved data-quality issue registry contains ≥ 33 entries.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from benchmarks._common import assert_pass, banner, quick_mode  # noqa: E402
from rynova_platform.streaming import (  # noqa: E402
    DQRegistry,
    IdempotentSink,
    InMemoryKafka,
    KafkaConsumer,
    KafkaProducer,
)

N_MESSAGES = 1_000 if quick_mode() else 5_000
REQUIRED_DQ_ISSUES = 33


def main() -> int:
    banner("Bullet 3 — Kafka idempotency + DQ registry")

    broker = InMemoryKafka(partitions=4)
    producer = KafkaProducer(broker)

    for i in range(N_MESSAGES):
        key = f"user-{i % 250}".encode()
        value = f'{{"id":{i},"value":{i * 2}}}'.encode()
        producer.send("orders", value, key=key)

    sink = IdempotentSink(":memory:")

    def drain() -> tuple[int, int]:
        consumer = KafkaConsumer(
            broker, group_id="rynova-cdc", topics=["orders"], auto_commit=False
        )
        applied = 0
        deduped = 0
        for message in consumer.poll(max_messages=N_MESSAGES):
            ok = sink.apply(message)
            if ok:
                applied += 1
            else:
                deduped += 1
            consumer.commit(message)
        return applied, deduped

    first_applied, first_deduped = drain()
    print(f"First pass : applied={first_applied} deduped={first_deduped}")

    # Force a rebalance: the consumer group's committed offsets are
    # reset to 0 (the bullet's "deployed via CI/CD" scenario where pods
    # restart mid-flight).  The idempotent sink must catch every replay.
    for partition in range(broker.partitions):
        broker.commit("rynova-cdc", "orders", partition, 0)
    second_applied, second_deduped = drain()
    print(f"Replay     : applied={second_applied} deduped={second_deduped}")

    issues = DQRegistry.default().resolved()
    print(f"Resolved DQ issues registered: {len(issues)}")

    failures = 0
    failures += assert_pass(
        first_applied == broker.topic_size("orders"),
        f"Exactly-once apply on first pass: {first_applied}/{broker.topic_size('orders')}",
    )
    failures += assert_pass(
        second_applied == 0 and second_deduped == broker.topic_size("orders"),
        f"100% dedupe on replay (applied={second_applied}, deduped={second_deduped})",
    )
    failures += assert_pass(
        len(issues) >= REQUIRED_DQ_ISSUES,
        f"{len(issues)}+ resolved data quality issues (target ≥ {REQUIRED_DQ_ISSUES})",
    )
    sink.close()
    return failures


if __name__ == "__main__":
    sys.exit(main())
