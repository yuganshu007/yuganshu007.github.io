"""Lightweight in-process Kafka stand-in.

The real production code in this repository talks to the
``confluent-kafka-python`` client (see the ``metadata-ingestion`` and
``metadata-jobs/mae-consumer`` modules).  For the compliance test
harness we need something that exhibits the same delivery contract —
ordered per partition, offsets monotonic per partition, consumer groups
that own partitions — without spinning up a real broker.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class KafkaMessage:
    topic: str
    partition: int
    offset: int
    key: bytes | None
    value: bytes
    headers: tuple[tuple[str, bytes], ...] = ()
    timestamp_ms: int = 0


@dataclass
class _Partition:
    messages: list[KafkaMessage] = field(default_factory=list)
    next_offset: int = 0


class InMemoryKafka:
    """Thread-safe in-process broker with per-key partitioning."""

    def __init__(self, partitions: int = 4) -> None:
        self.partitions = partitions
        self._topics: dict[str, list[_Partition]] = defaultdict(
            lambda: [_Partition() for _ in range(self.partitions)]
        )
        self._lock = threading.Lock()
        # ``group_id → {(topic, partition) → committed_offset}``
        self._committed: dict[str, dict[tuple[str, int], int]] = defaultdict(dict)

    def partition_for(self, topic: str, key: bytes | None) -> int:
        if key is None:
            return 0
        digest = hashlib.blake2b(key, digest_size=8).digest()
        return int.from_bytes(digest, "big") % self.partitions

    def produce(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: Iterable[tuple[str, bytes]] | None = None,
    ) -> KafkaMessage:
        with self._lock:
            partitions = self._topics[topic]
            partition = self.partition_for(topic, key)
            part = partitions[partition]
            msg = KafkaMessage(
                topic=topic,
                partition=partition,
                offset=part.next_offset,
                key=key,
                value=value,
                headers=tuple(headers or ()),
                timestamp_ms=int(time.time() * 1000),
            )
            part.messages.append(msg)
            part.next_offset += 1
            return msg

    def fetch(
        self,
        topic: str,
        partition: int,
        from_offset: int,
        max_messages: int = 100,
    ) -> list[KafkaMessage]:
        with self._lock:
            messages = list(self._topics[topic][partition].messages)
        return [m for m in messages if m.offset >= from_offset][:max_messages]

    def commit(self, group_id: str, topic: str, partition: int, offset: int) -> None:
        with self._lock:
            self._committed[group_id][(topic, partition)] = offset

    def committed(self, group_id: str, topic: str, partition: int) -> int:
        return self._committed.get(group_id, {}).get((topic, partition), 0)

    def topic_size(self, topic: str) -> int:
        return sum(p.next_offset for p in self._topics[topic])


class KafkaProducer:
    def __init__(self, broker: InMemoryKafka) -> None:
        self._broker = broker
        self._sent = 0

    @property
    def sent(self) -> int:
        return self._sent

    def send(
        self,
        topic: str,
        value: bytes,
        *,
        key: bytes | None = None,
        headers: Iterable[tuple[str, bytes]] | None = None,
    ) -> KafkaMessage:
        msg = self._broker.produce(topic, value, key=key, headers=headers)
        self._sent += 1
        return msg


class KafkaConsumer:
    """A poll-style consumer that respects committed offsets per group."""

    def __init__(
        self,
        broker: InMemoryKafka,
        *,
        group_id: str,
        topics: list[str],
        partitions: list[int] | None = None,
        auto_commit: bool = False,
    ) -> None:
        self._broker = broker
        self.group_id = group_id
        self.topics = topics
        self.partitions = partitions or list(range(broker.partitions))
        self.auto_commit = auto_commit

    def poll(self, max_messages: int = 100) -> list[KafkaMessage]:
        out: list[KafkaMessage] = []
        for topic in self.topics:
            for partition in self.partitions:
                from_offset = self._broker.committed(self.group_id, topic, partition)
                batch = self._broker.fetch(
                    topic, partition, from_offset, max_messages=max_messages
                )
                out.extend(batch)
                if self.auto_commit and batch:
                    self._broker.commit(self.group_id, topic, partition, batch[-1].offset + 1)
        return out

    def commit(self, message: KafkaMessage) -> None:
        self._broker.commit(self.group_id, message.topic, message.partition, message.offset + 1)
