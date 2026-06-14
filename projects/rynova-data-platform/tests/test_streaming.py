"""Kafka streaming + idempotent sink tests (Bullet 3)."""

from __future__ import annotations

from rynova_platform.streaming import (
    DQRegistry,
    IdempotencyKey,
    IdempotentSink,
    InMemoryKafka,
    KafkaConsumer,
    KafkaMessage,
    KafkaProducer,
)


def test_producer_assigns_monotonic_offsets() -> None:
    broker = InMemoryKafka(partitions=1)
    producer = KafkaProducer(broker)
    a = producer.send("t", b"a", key=b"k")
    b = producer.send("t", b"b", key=b"k")
    assert a.offset == 0
    assert b.offset == 1
    assert producer.sent == 2


def test_consistent_partition_per_key() -> None:
    broker = InMemoryKafka(partitions=4)
    producer = KafkaProducer(broker)
    p1 = producer.send("t", b"x", key=b"alpha").partition
    p2 = producer.send("t", b"y", key=b"alpha").partition
    assert p1 == p2


def test_consumer_resumes_from_committed_offset() -> None:
    broker = InMemoryKafka(partitions=1)
    producer = KafkaProducer(broker)
    for i in range(5):
        producer.send("t", f"{i}".encode(), key=b"k")
    consumer = KafkaConsumer(broker, group_id="g", topics=["t"], auto_commit=False)
    batch = consumer.poll()
    assert len(batch) == 5
    consumer.commit(batch[2])  # commit through offset 2
    second = consumer.poll()
    assert [m.offset for m in second] == [3, 4]


def test_consumer_auto_commit() -> None:
    broker = InMemoryKafka(partitions=1)
    producer = KafkaProducer(broker)
    for i in range(3):
        producer.send("t", f"{i}".encode(), key=b"k")
    consumer = KafkaConsumer(broker, group_id="g", topics=["t"], auto_commit=True)
    assert len(consumer.poll()) == 3
    assert consumer.poll() == []


def test_idempotent_sink_applies_once() -> None:
    sink = IdempotentSink(":memory:")
    msg = KafkaMessage(
        topic="t", partition=0, offset=0, key=b"k", value=b"{\"v\":1}"
    )
    assert sink.apply(msg) is True
    assert sink.apply(msg) is False
    assert sink.applied == 1
    assert sink.duplicates == 1
    sink.close()


def test_idempotent_sink_dedupes_across_drains() -> None:
    broker = InMemoryKafka(partitions=2)
    producer = KafkaProducer(broker)
    for i in range(20):
        producer.send("t", f"value-{i}".encode(), key=f"k{i % 3}".encode())
    sink = IdempotentSink(":memory:")

    consumer = KafkaConsumer(broker, group_id="g", topics=["t"], auto_commit=False)
    for m in consumer.poll(max_messages=1000):
        sink.apply(m)
        consumer.commit(m)
    assert sink.applied == 20

    for partition in range(broker.partitions):
        broker.commit("g", "t", partition, 0)

    consumer = KafkaConsumer(broker, group_id="g", topics=["t"], auto_commit=False)
    replay_applied = 0
    replay_deduped = 0
    for m in consumer.poll(max_messages=1000):
        if sink.apply(m):
            replay_applied += 1
        else:
            replay_deduped += 1
    assert replay_applied == 0
    assert replay_deduped == 20
    sink.close()


def test_idempotency_key_differs_for_different_values() -> None:
    a = IdempotencyKey.for_message(
        KafkaMessage(topic="t", partition=0, offset=0, key=b"k", value=b"a")
    )
    b = IdempotencyKey.for_message(
        KafkaMessage(topic="t", partition=0, offset=0, key=b"k", value=b"b")
    )
    assert a != b


def test_idempotency_key_stable_across_offsets() -> None:
    a = IdempotencyKey.for_message(
        KafkaMessage(topic="t", partition=0, offset=0, key=b"k", value=b"v")
    )
    b = IdempotencyKey.for_message(
        KafkaMessage(topic="t", partition=0, offset=99, key=b"k", value=b"v")
    )
    assert a == b


def test_sink_snapshot_persists_latest_value() -> None:
    sink = IdempotentSink(":memory:")
    sink.apply(KafkaMessage(topic="t", partition=0, offset=0, key=b"k", value=b"v1"))
    sink.apply(KafkaMessage(topic="t", partition=0, offset=1, key=b"k", value=b"v2"))
    snap = sink.snapshot()
    assert snap[("t", 0, "k")] == "v2"
    sink.close()


def test_dq_registry_has_minimum_resolved_issues() -> None:
    issues = DQRegistry.default().resolved()
    assert len(issues) >= 33


def test_dq_registry_by_severity_partition() -> None:
    reg = DQRegistry.default()
    sev1 = reg.by_severity("sev1")
    sev2 = reg.by_severity("sev2")
    sev3 = reg.by_severity("sev3")
    assert len(sev1) + len(sev2) + len(sev3) == len(reg.all())


def test_dq_registry_serialization_roundtrip(tmp_path) -> None:
    reg = DQRegistry.default()
    p = tmp_path / "issues.json"
    p.write_text(reg.to_json())
    loaded = DQRegistry.from_file(p)
    assert len(loaded.all()) == len(reg.all())
