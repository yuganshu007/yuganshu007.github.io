"""Compile-time check for the Java backend service.

Locates ``javac`` on ``PATH`` and compiles the Java sources shipped in
``./java`` into a scratch directory.  Returns ``True`` on success.  The
helper is shelled out via ``subprocess`` so it works with any JDK 11+
toolchain (Adoptium, Corretto, Zulu) without depending on a build
system.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
JAVA_DIR = HERE / "java"


def java_sources() -> list[Path]:
    return sorted(JAVA_DIR.rglob("*.java"))


def compile_java(*, jdk: str | None = None) -> bool:
    javac = jdk or shutil.which("javac")
    if not javac:
        return False
    sources = java_sources()
    if not sources:
        return False
    with tempfile.TemporaryDirectory() as out:
        cmd = [javac, "-d", out, *[str(p) for p in sources]]
        try:
            subprocess.check_call(cmd, env={**os.environ, "LC_ALL": "C"})
        except subprocess.CalledProcessError:
            return False
    return True
