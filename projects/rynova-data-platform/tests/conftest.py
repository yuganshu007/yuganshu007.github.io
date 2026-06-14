"""Shared pytest fixtures and path bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def in_memory_planner():
    from rynova_platform.sql import QueryPlanner

    planner = QueryPlanner.in_memory(mode="optimized")
    yield planner
    planner.close()


@pytest.fixture
def baseline_planner():
    from rynova_platform.sql import QueryPlanner

    planner = QueryPlanner.in_memory(mode="baseline")
    yield planner
    planner.close()
