from __future__ import annotations

from services.agent_chatbot.loadtest.run_loadtest import percentile


def test_percentile_basic():
    data = list(range(1, 101))  # 1..100
    assert percentile(data, 0.50) == 50.5
    assert percentile(data, 0.95) == 95.05
    assert percentile(data, 0.99) == 99.01


def test_percentile_monotonic():
    data = [0.1, 0.2, 0.3, 0.4, 5.0]
    assert percentile(data, 0.5) <= percentile(data, 0.95) <= percentile(data, 0.99)


def test_percentile_empty():
    assert percentile([], 0.95) == 0.0
