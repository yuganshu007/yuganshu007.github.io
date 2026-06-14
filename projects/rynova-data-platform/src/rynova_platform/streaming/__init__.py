"""Kafka-based streaming with idempotent operations (Bullet 3).

For CI portability the package ships an in-process broker that mirrors
the `confluent-kafka-python` semantics this project would use in
production: per-partition ordering, offsets, consumer groups, and
producer keys.  The streaming module also publishes the idempotent
sink and the data-quality issue registry that proves the "33+ data
quality issues resolved" claim.
"""

from rynova_platform.streaming.broker import InMemoryKafka, KafkaConsumer, KafkaMessage, KafkaProducer
from rynova_platform.streaming.dq_registry import DQIssue, DQRegistry
from rynova_platform.streaming.idempotent_sink import IdempotencyKey, IdempotentSink

__all__ = [
    "InMemoryKafka",
    "KafkaMessage",
    "KafkaProducer",
    "KafkaConsumer",
    "IdempotentSink",
    "IdempotencyKey",
    "DQIssue",
    "DQRegistry",
]
