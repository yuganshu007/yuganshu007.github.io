"""Java bridge package.

The Java sources live in ``rynova/src/rynova_platform/java_bridge/java/``.
The Python package exposes a single helper, :func:`compile_java`, used
by the test suite to confirm the Java backend compiles cleanly with the
``javac`` toolchain shipping on Linux build hosts — backing the
"Python/Java backend services" half of resume Bullet 1.
"""

from rynova_platform.java_bridge.compile import compile_java, java_sources

__all__ = ["compile_java", "java_sources"]
