"""Java backend compilation test (Bullet 1)."""

from __future__ import annotations

import shutil

import pytest

from rynova_platform.java_bridge import compile_java, java_sources


def test_java_sources_exist() -> None:
    files = java_sources()
    names = {p.name for p in files}
    assert "QueryService.java" in names
    assert "EventBus.java" in names


@pytest.mark.skipif(shutil.which("javac") is None, reason="javac not installed")
def test_java_sources_compile() -> None:
    assert compile_java() is True


def test_java_sources_declare_package() -> None:
    for path in java_sources():
        text = path.read_text()
        assert text.startswith("package com.rynova.platform;"), path
